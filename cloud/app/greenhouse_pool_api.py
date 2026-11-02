"""Unified public shelf catalogue and administrator greenhouse operations.

Physical Raspberry Pis stay independently authenticated and continue telemetry
while an administrator removes a greenhouse from the order catalogue.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .models import Allocation, Device, Farm, RackSlot, User
from .marketplace_api import public_market
from .marketplace_service import process_waitlist
from .security import get_admin_user, get_session

router = APIRouter(prefix="/api/v1", tags=["greenhouse-pool"])

STATUSES = ("active", "maintenance", "transport", "paused")


def accepting_orders(device: Device) -> bool:
    return bool(device.is_active and device.marketplace_status == "active")


class GreenhouseStatusUpdate(BaseModel):
    status: Literal["active", "maintenance", "transport", "paused"]
    note: str = Field(default="", max_length=250)


@router.get("/public/market")
async def public_pool(session: AsyncSession = Depends(get_session)):
    """One catalogue, consecutive public shelf numbers, private device routing."""
    rows = (await session.execute(
        select(Farm, Device)
        .join(Device, Device.farm_id == Farm.id)
        .where(
            Farm.is_public.is_(True),
            Device.is_active.is_(True),
        )
        .order_by(Farm.id, Device.id)
    )).all()
    racks = []
    plant_map = {}
    latest = None
    online = False
    total = 0
    seen_farms = set()
    threshold = timedelta(seconds=get_settings().offline_after_seconds)
    now = datetime.now(timezone.utc)
    display_offset = 0
    for farm, device in rows:
        # Existing farm-specific API uses the first device of each farm.
        # Do not duplicate a physical shelf when a farm has many devices.
        if farm.slug in seen_farms:
            continue
        seen_farms.add(farm.slug)
        if device.marketplace_status != "active":
            display_offset += device.racks_count
            continue
        market = await public_market(farm_slug=farm.slug, session=session)
        for plant in market.plants:
            plant_map[plant.id] = plant.model_dump(mode="json")
        for rack in market.racks:
            item = rack.model_dump(mode="json")
            item["device_id"] = device.id
            item["farm_slug"] = farm.slug
            item["display_number"] = display_offset + rack.rack_id
            # Real local rack IDs remain unchanged for purchases and photos.
            for slot in item["slots"]:
                slot["device_id"] = device.id
            racks.append(item)
        total += 1
        display_offset += device.racks_count
        if device.last_seen_at is not None:
            value = device.last_seen_at
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            value = value.astimezone(timezone.utc)
            latest = max(latest, value) if latest else value
            if now - value <= threshold:
                online = True

    return {
        "farm_name": "KisaMore",
        "plants": list(plant_map.values()),
        "racks": racks,
        "greenhouses_count": total,
        "status": "online" if online else ("offline" if latest else "waiting"),
        "last_seen_at": latest.isoformat() if latest else None,
    }


@router.get("/admin/greenhouses")
async def admin_greenhouses(
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    rows = (await session.execute(
        select(Device, Farm).join(Farm, Device.farm_id == Farm.id).order_by(Farm.id, Device.id)
    )).all()
    counts = dict((await session.execute(
        select(Allocation.device_id, func.count(Allocation.id))
        .where(Allocation.status == "active")
        .group_by(Allocation.device_id)
    )).all())
    return [
        {
            "device_id": device.id,
            "device_name": device.name,
            "farm_name": farm.name,
            "status": device.marketplace_status,
            "note": device.marketplace_note,
            "telemetry_enabled": device.is_active,
            "public": farm.is_public,
            "last_seen_at": device.last_seen_at,
            "racks_count": device.racks_count,
            "active_allocations": counts.get(device.id, 0),
        }
        for device, farm in rows
    ]


@router.patch("/admin/greenhouses/{device_id}")
async def set_greenhouse_status(
    device_id: str,
    payload: GreenhouseStatusUpdate,
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    device = (await session.execute(
        select(Device).where(Device.id == device_id).with_for_update()
    )).scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=404, detail="Greenhouse not found")
    device.marketplace_status = payload.status
    device.marketplace_note = payload.note.strip()
    # Releasing a greenhouse for sale rechecks old waiting requests.
    if payload.status == "active":
        await process_waitlist(session, device_id)
    await session.commit()
    return {
        "device_id": device.id,
        "status": device.marketplace_status,
        "note": device.marketplace_note,
    }
