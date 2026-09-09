from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .models import Device, Farm, Planting, RackSlot
from .security import get_session
from .timelapse_service import planting_timelapse_path, slot_timelapse_path


router = APIRouter(prefix="/api/v1", tags=["timelapse"])


def _video_response(path: Path) -> FileResponse:
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Timelapse is not ready yet")
    return FileResponse(
        path,
        media_type="video/mp4",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/public/farms/{farm_slug}/racks/{rack_id}/slots/{slot_number}/timelapse/{period}")
async def public_slot_timelapse(
    farm_slug: str,
    rack_id: int,
    slot_number: int,
    period: str,
    session: AsyncSession = Depends(get_session),
):
    if period not in ("24h", "3d"):
        raise HTTPException(status_code=404, detail="Timelapse period not found")
    if slot_number < 1 or slot_number > 6:
        raise HTTPException(status_code=404, detail="Container not found")

    device = (
        await session.execute(
            select(Device)
            .join(Farm, Farm.id == Device.farm_id)
            .where(
                Farm.slug == farm_slug,
                Farm.is_public.is_(True),
                Device.is_active.is_(True),
                Device.racks_count >= rack_id,
            )
            .order_by(Device.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=404, detail="Rack not found")

    return _video_response(
        slot_timelapse_path(
            get_settings().photo_dir,
            device.id,
            rack_id,
            slot_number,
            period,
        )
    )


@router.get("/public/plantings/{planting_id}/timelapse/full")
async def public_planting_timelapse(
    planting_id: str,
    session: AsyncSession = Depends(get_session),
):
    row = (
        await session.execute(
            select(Planting)
            .join(RackSlot, RackSlot.id == Planting.slot_id)
            .join(Device, Device.id == RackSlot.device_id)
            .join(Farm, Farm.id == Device.farm_id)
            .where(
                Planting.id == planting_id,
                Farm.is_public.is_(True),
                Device.is_active.is_(True),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Planting not found")

    return _video_response(planting_timelapse_path(get_settings().photo_dir, planting_id))
