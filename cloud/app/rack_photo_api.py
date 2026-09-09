from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .models import Device, Farm, RackPhoto
from .rack_photo_storage import SLOT_COUNT, slot_latest_path
from .security import get_session


router = APIRouter(prefix="/api/v1", tags=["rack-photos"])


@router.get(
    "/public/farms/{farm_slug}/racks/{rack_id}/slots/{slot_number}/photo",
    response_class=FileResponse,
)
async def public_slot_photo(
    farm_slug: str,
    rack_id: int,
    slot_number: int,
    session: AsyncSession = Depends(get_session),
):
    if slot_number < 1 or slot_number > SLOT_COUNT:
        raise HTTPException(status_code=404, detail="Container not found")

    row = (
        await session.execute(
            select(RackPhoto)
            .join(Device, Device.id == RackPhoto.device_id)
            .join(Farm, Farm.id == Device.farm_id)
            .where(
                Farm.slug == farm_slug,
                Farm.is_public.is_(True),
                Device.is_active.is_(True),
                RackPhoto.rack_id == rack_id,
            )
            .order_by(Device.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Rack photo not found")

    path = slot_latest_path(
        get_settings().photo_dir,
        row.device_id,
        rack_id,
        slot_number,
    )
    if not Path(path).is_file():
        raise HTTPException(status_code=404, detail="Container photo not found")

    captured = row.captured_at.isoformat() if row.captured_at else ""
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-store",
            "X-Captured-At": captured,
        },
    )
