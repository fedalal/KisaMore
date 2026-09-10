from __future__ import annotations

from datetime import timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .admin_models import AdminAuditLog
from .models import Plant, User
from .security import get_admin_user, get_session
from .seed_inventory import (
    SeedInventoryTransaction,
    SeedUnavailable,
    add_seed_movement,
    seed_availability,
    set_seed_rate,
)


router = APIRouter(prefix="/api/v1/admin/seeds", tags=["admin-seeds"])


class SeedMovementIn(BaseModel):
    movement_type: Literal["receipt", "writeoff"]
    amount_g: float = Field(gt=0, le=1_000_000)
    note: str = Field(default="", max_length=300)


class SeedRateIn(BaseModel):
    seed_rate_g: float = Field(gt=0, le=5000)


def _plant_name(plant: Plant) -> str:
    names = plant.names or {}
    for key in ("ru", "en"):
        if names.get(key):
            return str(names[key])
    return next((str(value) for value in names.values() if value), plant.code)


def _movement_out(item: SeedInventoryTransaction) -> dict:
    created = item.created_at
    if created is not None and created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return {
        "id": item.id,
        "plant_id": item.plant_id,
        "amount_g": round(float(item.amount_g or 0), 3),
        "movement_type": item.movement_type,
        "note": item.note,
        "reference_type": item.reference_type,
        "reference_id": item.reference_id,
        "admin_user_id": item.admin_user_id,
        "created_at": created,
    }


async def _summary(session: AsyncSession, plant: Plant) -> dict:
    availability = await seed_availability(session, plant.id)
    if availability.seed_rate_g <= 0:
        status = "unconfigured"
    elif availability.available_plantings <= 0:
        status = "out"
    elif availability.available_plantings <= 2:
        status = "low"
    else:
        status = "ok"
    return {
        "plant_id": plant.id,
        "plant_code": plant.code,
        "plant_name": _plant_name(plant),
        "plant_active": bool(plant.active),
        "seed_rate_g": availability.seed_rate_g,
        "balance_g": availability.balance_g,
        "reserved_plantings": availability.reserved_plantings,
        "reserved_g": availability.reserved_g,
        "available_g": availability.available_g,
        "available_plantings": availability.available_plantings,
        "in_stock": availability.in_stock,
        "status": status,
    }


@router.get("")
async def list_seed_inventory(
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    plants = list((await session.execute(select(Plant))).scalars().all())
    plants.sort(
        key=lambda plant: (
            _plant_name(plant).casefold(),
            (plant.code or "").casefold(),
        )
    )
    return [await _summary(session, plant) for plant in plants]


@router.get("/{plant_id}/history")
async def seed_history(
    plant_id: str,
    limit: int = 50,
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    plant = await session.get(Plant, plant_id)
    if plant is None:
        raise HTTPException(status_code=404, detail="Plant not found")
    rows = list(
        (
            await session.execute(
                select(SeedInventoryTransaction)
                .where(SeedInventoryTransaction.plant_id == plant_id)
                .order_by(SeedInventoryTransaction.created_at.desc())
                .limit(max(1, min(limit, 200)))
            )
        ).scalars().all()
    )
    return {
        "plant_id": plant.id,
        "plant_name": _plant_name(plant),
        "items": [_movement_out(item) for item in rows],
    }


@router.patch("/{plant_id}/rate")
async def update_seed_rate(
    plant_id: str,
    payload: SeedRateIn,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    plant = (
        await session.execute(
            select(Plant).where(Plant.id == plant_id).with_for_update()
        )
    ).scalar_one_or_none()
    if plant is None:
        raise HTTPException(status_code=404, detail="Plant not found")
    await set_seed_rate(session, plant_id, payload.seed_rate_g)
    session.add(
        AdminAuditLog(
            admin_user_id=admin.id,
            action="set_seed_rate",
            target_type="plant",
            target_id=plant_id,
            details={"seed_rate_g": round(float(payload.seed_rate_g), 3)},
        )
    )
    await session.commit()
    return await _summary(session, plant)


@router.post("/{plant_id}/movements", status_code=201)
async def create_seed_movement(
    plant_id: str,
    payload: SeedMovementIn,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    plant = await session.get(Plant, plant_id)
    if plant is None:
        raise HTTPException(status_code=404, detail="Plant not found")
    try:
        movement = await add_seed_movement(
            session,
            plant_id=plant_id,
            movement_type=payload.movement_type,
            amount_g=payload.amount_g,
            note=payload.note,
            admin_user_id=admin.id,
        )
    except SeedUnavailable as exc:
        available = exc.availability.available_g
        reserved = exc.availability.reserved_g
        raise HTTPException(
            status_code=409,
            detail=(
                f"Нельзя списать столько семян. Свободно {available:g} г; "
                f"зарезервировано под аренды {reserved:g} г."
            ),
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    session.add(
        AdminAuditLog(
            admin_user_id=admin.id,
            action=f"seed_{payload.movement_type}",
            target_type="plant",
            target_id=plant_id,
            details={
                "movement_id": movement.id,
                "amount_g": round(float(payload.amount_g), 3),
                "note": payload.note.strip(),
            },
        )
    )
    await session.commit()
    await session.refresh(movement)
    return {
        "movement": _movement_out(movement),
        "inventory": await _summary(session, plant),
    }
