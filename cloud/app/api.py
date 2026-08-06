from __future__ import annotations

from datetime import datetime, timedelta, timezone
from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .models import Device, Farm, RackCurrent, TelemetrySample
from .schemas import EdgeSnapshotIn, FarmLiveOut, RackLiveOut
from .security import authenticate_device, get_session


router = APIRouter(prefix="/api/v1")


def _as_aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@router.get("/health")
async def health(session: AsyncSession = Depends(get_session)):
    await session.execute(text("SELECT 1"))
    return {"status": "ok"}


@router.post("/edge/snapshot", status_code=202)
async def ingest_snapshot(
    payload: EdgeSnapshotIn,
    device: Device = Depends(authenticate_device),
    session: AsyncSession = Depends(get_session),
):
    started_at = perf_counter()
    now = datetime.now(timezone.utc)
    if payload.observed_at > now + timedelta(minutes=5):
        raise HTTPException(status_code=422, detail="observed_at is too far in the future")

    device.last_seen_at = now
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
                received_at=now,
            )
        )

    await session.commit()
    print(
        f"[cloud-api] snapshot accepted: device={device.id}, "
        f"racks={len(payload.racks)}, elapsed={perf_counter() - started_at:.3f}s"
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
