from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from time import perf_counter

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .db import SessionLocal
from .models import Device, Farm, RackCurrent, TelemetrySample, InventorySyncReceipt
from .schemas import EdgeSnapshotIn, FarmLiveOut, RackLiveOut
from .security import authenticate_device, get_session
from .marketplace_service import process_waitlist, sync_edge_inventory


router = APIRouter(prefix="/api/v1")
_pending_inventory: dict[str, tuple[EdgeSnapshotIn, datetime]] = {}
_inventory_locks: dict[str, asyncio.Lock] = {}


def _as_aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def _sync_queued_inventory(
    device_id: str,
    payload: EdgeSnapshotIn,
    received_at: datetime,
) -> None:
    """Process only the latest queued growing snapshot for a device.

    This runs after the telemetry response has been sent. Slow inventory or
    waitlist queries therefore cannot block the Pi's regular sensor exchange.
    """
    if payload.inventory_sync_id:
        # Deltas must never be coalesced like legacy full snapshots.
        lock = _inventory_locks.setdefault(device_id, asyncio.Lock())
        async with lock:
            async with SessionLocal() as session:
                await session.execute(select(Device).where(Device.id == device_id).with_for_update())
                receipt = await session.get(InventorySyncReceipt, device_id)
                if receipt and (
                    receipt.sync_id == payload.inventory_sync_id or
                    _as_aware_utc(receipt.observed_at) > payload.inventory_observed_at
                ):
                    return
                if payload.inventory_base_id is not None and (
                    receipt is None or receipt.sync_id != payload.inventory_base_id
                ):
                    raise RuntimeError("inventory baseline mismatch; full sync required")
                await sync_edge_inventory(session, device_id, payload, received_at)
                await process_waitlist(session, device_id)
                if receipt is None:
                    receipt = InventorySyncReceipt(device_id=device_id)
                    session.add(receipt)
                receipt.sync_id = payload.inventory_sync_id
                receipt.observed_at = payload.inventory_observed_at
                await session.commit()
            print(
                f"[cloud-api] inventory delta committed: device={device_id}, "
                f"plants={len(payload.plants)}, "
                f"slots={sum(len(r.slots) for r in payload.racks)}"
            )
        return
    _pending_inventory[device_id] = (payload, received_at)
    lock = _inventory_locks.setdefault(device_id, asyncio.Lock())
    if lock.locked():
        return

    async with lock:
        while True:
            queued = _pending_inventory.pop(device_id, None)
            if queued is None:
                return
            queued_payload, queued_at = queued
            started_at = perf_counter()
            try:
                async with SessionLocal() as session:
                    await sync_edge_inventory(
                        session,
                        device_id,
                        queued_payload,
                        queued_at,
                    )
                    await process_waitlist(session, device_id)
                    await session.commit()
                print(
                    f"[cloud-api] growing inventory synchronized: device={device_id}, "
                    f"plants={len(queued_payload.plants)}, "
                    f"slots={sum(len(rack.slots) for rack in queued_payload.racks)}, "
                    f"elapsed={perf_counter() - started_at:.3f}s"
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(
                    f"[cloud-api] growing inventory failed: device={device_id}, "
                    f"elapsed={perf_counter() - started_at:.3f}s, "
                    f"error={type(exc).__name__}: {exc!r}"
                )


async def process_edge_snapshot(
    device_id: str,
    payload: EdgeSnapshotIn,
    received_at: datetime,
    *,
    sync_inventory_now: bool = True,
) -> bool:
    """Persist telemetry immediately and queue inventory work when present."""
    async with SessionLocal() as session:
        device = await session.get(Device, device_id)
        if device is None or not device.is_active:
            raise RuntimeError(f"active device {device_id!r} was not found")

        device.last_seen_at = received_at
        device.software_version = payload.software_version
        device.racks_count = payload.racks_count
        device.levels = payload.levels

        rack_ids = [incoming.rack_id for incoming in payload.racks]
        current_by_rack_id: dict[int, RackCurrent] = {}
        if rack_ids:
            current_racks = (
                await session.execute(
                    select(RackCurrent).where(
                        RackCurrent.device_id == device.id,
                        RackCurrent.rack_id.in_(rack_ids),
                    )
                )
            ).scalars().all()
            current_by_rack_id = {rack.rack_id: rack for rack in current_racks}

        for incoming in payload.racks:
            current = current_by_rack_id.get(incoming.rack_id)

            values = {
                "light_on": incoming.light_on,
                "water_on": incoming.water_on,
                "light_mode": incoming.light_mode,
                "water_mode": incoming.water_mode,
                "soil_moisture": incoming.soil_moisture,
                "soil_temperature": incoming.soil_temperature,
                "sensor_observed_at": incoming.sensor_observed_at,
                "camera_id": incoming.camera_id,
                "observed_at": payload.observed_at,
            }

            if current is None:
                current = RackCurrent(device_id=device.id, rack_id=incoming.rack_id, **values)
                session.add(current)
                current_by_rack_id[incoming.rack_id] = current
            else:
                for key, value in values.items():
                    setattr(current, key, value)

            session.add(
                TelemetrySample(
                    device_id=device.id,
                    rack_id=incoming.rack_id,
                    light_on=incoming.light_on,
                    water_on=incoming.water_on,
                    soil_moisture=incoming.soil_moisture,
                    soil_temperature=incoming.soil_temperature,
                    observed_at=payload.observed_at,
                    received_at=received_at,
                )
            )

        has_growing_data = bool(payload.inventory_sync_id or payload.plants) or any(rack.slots for rack in payload.racks)
        await session.commit()

    if has_growing_data and sync_inventory_now:
        await _sync_queued_inventory(device_id, payload, received_at)
    return has_growing_data


@router.get("/health")
async def health(session: AsyncSession = Depends(get_session)):
    await session.execute(text("SELECT 1"))
    return {"status": "ok"}


@router.post("/edge/snapshot", status_code=202)
async def ingest_snapshot(
    payload: EdgeSnapshotIn,
    background_tasks: BackgroundTasks,
    device: Device = Depends(authenticate_device),
):
    started_at = perf_counter()
    now = datetime.now(timezone.utc)
    if payload.observed_at > now + timedelta(minutes=5):
        raise HTTPException(status_code=422, detail="observed_at is too far in the future")

    has_growing_data = bool(payload.inventory_sync_id or payload.plants) or any(rack.slots for rack in payload.racks)
    await process_edge_snapshot(device.id, payload, now, sync_inventory_now=False)
    if has_growing_data:
        background_tasks.add_task(
            _sync_queued_inventory,
            device.id,
            payload,
            now,
        )
    print(
        f"[cloud-api] snapshot accepted: device={device.id}, "
        f"racks={len(payload.racks)}, growing_queued={has_growing_data}, "
        f"elapsed={perf_counter() - started_at:.3f}s"
    )
    return {"accepted": True, "received_at": now}


@router.get("/public/farms/{farm_slug}/live", response_model=FarmLiveOut)
async def public_farm_live(
    farm_slug: str,
    session: AsyncSession = Depends(get_session),
):
    farm = (
        await session.execute(
            select(Farm).where(Farm.slug == farm_slug, Farm.is_public.is_(True))
        )
    ).scalar_one_or_none()
    if farm is None:
        raise HTTPException(status_code=404, detail="Public farm not found")

    device = (
        await session.execute(
            select(Device)
            .where(Device.farm_id == farm.id, Device.is_active.is_(True))
            .order_by(Device.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=404, detail="Farm device not found")

    racks = (
        await session.execute(
            select(RackCurrent)
            .where(
                RackCurrent.device_id == device.id,
                RackCurrent.rack_id <= device.racks_count,
            )
            .order_by(RackCurrent.rack_id)
        )
    ).scalars().all()

    last_seen = _as_aware_utc(device.last_seen_at)
    if last_seen is None:
        connection_status = "waiting"
    elif datetime.now(timezone.utc) - last_seen > timedelta(
        seconds=get_settings().offline_after_seconds
    ):
        connection_status = "offline"
    else:
        connection_status = "online"

    return FarmLiveOut(
        farm_slug=farm.slug,
        farm_name=farm.name,
        device_id=device.id,
        device_name=device.name,
        status=connection_status,
        last_seen_at=last_seen,
        software_version=device.software_version,
        racks_count=device.racks_count,
        racks=[
            RackLiveOut(
                rack_id=rack.rack_id,
                light_on=rack.light_on,
                water_on=rack.water_on,
                light_mode=rack.light_mode,
                water_mode=rack.water_mode,
                soil_moisture=rack.soil_moisture,
                soil_temperature=rack.soil_temperature,
                sensor_observed_at=_as_aware_utc(rack.sensor_observed_at),
                camera_id=rack.camera_id,
                observed_at=_as_aware_utc(rack.observed_at),
            )
            for rack in racks
        ],
    )
