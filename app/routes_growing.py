from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from . import runtime
from .db import SessionLocal
from .models import Plant, Planting, RackSlot
from .schemas import (
    PlantIn,
    PlantOut,
    PlantingCreateIn,
    PlantingOut,
    PlantingUpdateIn,
    RackSlotOut,
    SlotUpdateIn,
)


router = APIRouter(prefix="/api/growing", tags=["growing"])
ACTIVE_PLANTING_STATUSES = ("planned", "growing", "ready")


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _plant_out(plant: Plant) -> PlantOut:
    return PlantOut(
        id=plant.id,
        code=plant.code,
        names=plant.names,
        descriptions=plant.descriptions,
        seed_image_name=plant.seed_image_name,
        microgreen_image_name=plant.microgreen_image_name,
        grow_days=plant.grow_days,
        active=plant.active,
        created_at=plant.created_at,
        updated_at=plant.updated_at,
    )


def _planting_out(planting: Planting, plant: Plant) -> PlantingOut:
    return PlantingOut(
        id=planting.id,
        plant_id=plant.id,
        plant_code=plant.code,
        plant_names=plant.names,
        planted_at=planting.planted_at,
        expected_harvest_at=planting.expected_harvest_at,
        actual_harvest_at=planting.actual_harvest_at,
        status=planting.status,
        cloud_allocation_id=planting.cloud_allocation_id,
        notes=planting.notes,
    )


async def _slot_out(session, slot: RackSlot) -> RackSlotOut:
    row = (
        await session.execute(
            select(Planting, Plant)
            .join(Plant, Plant.id == Planting.plant_id)
            .where(
                Planting.slot_id == slot.id,
                Planting.status.in_(ACTIVE_PLANTING_STATUSES),
            )
            .order_by(Planting.planted_at.desc())
            .limit(1)
        )
    ).first()
    current = _planting_out(*row) if row else None
    return RackSlotOut(
        id=slot.id,
        rack_id=slot.rack_id,
        slot_number=slot.slot_number,
        status=slot.status,
        enabled=slot.enabled,
        cloud_allocation_id=slot.cloud_allocation_id,
        requested_plant_id=slot.requested_plant_id,
        current_planting=current,
    )


@router.get("/plants", response_model=list[PlantOut])
async def list_plants(include_inactive: bool = False):
    async with SessionLocal() as session:
        query = select(Plant).order_by(Plant.code)
        if not include_inactive:
            query = query.where(Plant.active.is_(True))
        plants = (await session.execute(query)).scalars().all()
        return [_plant_out(plant) for plant in plants]


@router.post("/plants", response_model=PlantOut, status_code=201)
async def create_plant(payload: PlantIn):
    async with SessionLocal() as session:
        existing = (
            await session.execute(select(Plant).where(Plant.code == payload.code))
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Plant code already exists")
        plant = Plant(id=str(uuid4()), **payload.model_dump())
        session.add(plant)
        await session.commit()
        await session.refresh(plant)
        return _plant_out(plant)


@router.put("/plants/{plant_id}", response_model=PlantOut)
async def update_plant(plant_id: str, payload: PlantIn):
    async with SessionLocal() as session:
        plant = await session.get(Plant, plant_id)
        if plant is None:
            raise HTTPException(status_code=404, detail="Plant not found")
        duplicate = (
            await session.execute(
                select(Plant).where(Plant.code == payload.code, Plant.id != plant_id)
            )
        ).scalar_one_or_none()
        if duplicate:
            raise HTTPException(status_code=409, detail="Plant code already exists")
        for key, value in payload.model_dump().items():
            setattr(plant, key, value)
        plant.updated_at = _now_naive()
        await session.commit()
        await session.refresh(plant)
        return _plant_out(plant)


@router.get("/slots", response_model=list[RackSlotOut])
async def list_slots():
    async with SessionLocal() as session:
        max_racks = runtime.cfg.racks_count if runtime.cfg else 4
        slots = (
            await session.execute(
                select(RackSlot)
                .where(RackSlot.rack_id <= max_racks)
                .order_by(RackSlot.rack_id, RackSlot.slot_number)
            )
        ).scalars().all()
        return [await _slot_out(session, slot) for slot in slots]


@router.patch("/slots/{rack_id}/{slot_number}", response_model=RackSlotOut)
async def update_slot(rack_id: int, slot_number: int, payload: SlotUpdateIn):
    async with SessionLocal() as session:
        slot = (
            await session.execute(
                select(RackSlot).where(
                    RackSlot.rack_id == rack_id,
                    RackSlot.slot_number == slot_number,
                )
            )
        ).scalar_one_or_none()
        if slot is None:
            raise HTTPException(status_code=404, detail="Rack slot not found")
        if payload.status == "available":
            active = (
                await session.execute(
                    select(Planting).where(
                        Planting.slot_id == slot.id,
                        Planting.status.in_(ACTIVE_PLANTING_STATUSES),
                    )
                )
            ).scalar_one_or_none()
            if active:
                raise HTTPException(status_code=409, detail="Slot has an active planting")
        slot.status = payload.status
        if payload.enabled is not None:
            slot.enabled = payload.enabled
        slot.updated_at = _now_naive()
        await session.commit()
        await session.refresh(slot)
        return await _slot_out(session, slot)


@router.post("/plantings", response_model=PlantingOut, status_code=201)
async def create_planting(payload: PlantingCreateIn):
    async with SessionLocal() as session:
        plant = await session.get(Plant, payload.plant_id)
        if plant is None or not plant.active:
            raise HTTPException(status_code=404, detail="Active plant not found")
        slot = (
            await session.execute(
                select(RackSlot).where(
                    RackSlot.rack_id == payload.rack_id,
                    RackSlot.slot_number == payload.slot_number,
                )
            )
        ).scalar_one_or_none()
        if slot is None:
            raise HTTPException(status_code=404, detail="Rack slot not found")
        if not slot.enabled or slot.status not in ("available", "reserved"):
            raise HTTPException(status_code=409, detail="Rack slot is not ready for planting")
        active = (
            await session.execute(
                select(Planting).where(
                    Planting.slot_id == slot.id,
                    Planting.status.in_(ACTIVE_PLANTING_STATUSES),
                )
            )
        ).scalar_one_or_none()
        if active:
            raise HTTPException(status_code=409, detail="Rack slot already has an active planting")

        planted_at = _utc_naive(payload.planted_at)
        expected = (
            _utc_naive(payload.expected_harvest_at)
            if payload.expected_harvest_at
            else planted_at + timedelta(days=plant.grow_days)
        )
        planting = Planting(
            id=str(uuid4()),
            slot_id=slot.id,
            plant_id=plant.id,
            planted_at=planted_at,
            expected_harvest_at=expected,
            status="growing",
            cloud_allocation_id=slot.cloud_allocation_id,
            notes=payload.notes,
        )
        slot.status = "growing"
        slot.requested_plant_id = plant.id
        session.add(planting)
        await session.commit()
        await session.refresh(planting)
        return _planting_out(planting, plant)


@router.patch("/plantings/{planting_id}", response_model=PlantingOut)
async def update_planting(planting_id: str, payload: PlantingUpdateIn):
    async with SessionLocal() as session:
        planting = await session.get(Planting, planting_id)
        if planting is None:
            raise HTTPException(status_code=404, detail="Planting not found")
        plant = await session.get(Plant, planting.plant_id)
        slot = await session.get(RackSlot, planting.slot_id)
        changes = payload.model_dump(exclude_unset=True)
        for key in ("expected_harvest_at", "actual_harvest_at"):
            if changes.get(key) is not None:
                changes[key] = _utc_naive(changes[key])
        for key, value in changes.items():
            setattr(planting, key, value)

        if planting.status == "ready":
            slot.status = "ready"
        elif planting.status in ("harvested", "cancelled"):
            if planting.actual_harvest_at is None:
                planting.actual_harvest_at = _now_naive()
            slot.status = "maintenance"
        elif planting.status in ("planned", "growing"):
            slot.status = "growing"
        planting.updated_at = _now_naive()
        await session.commit()
        await session.refresh(planting)
        return _planting_out(planting, plant)
