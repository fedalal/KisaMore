from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Device, RackPhoto, User
from .security import get_admin_user, get_session


router = APIRouter(prefix="/api/v1/admin", tags=["admin-cameras"])


@router.get("/rack-photos")
async def rack_photos(
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    devices = (
        await session.execute(
            select(Device)
            .where(Device.is_active.is_(True))
            .order_by(Device.id)
        )
    ).scalars().all()

    if not devices:
        return []

    device_ids = [device.id for device in devices]
    photos = (
        await session.execute(
            select(RackPhoto).where(RackPhoto.device_id.in_(device_ids))
        )
    ).scalars().all()
    photo_by_key = {(photo.device_id, photo.rack_id): photo for photo in photos}

    result = []
    for device in devices:
        for rack_id in range(1, max(int(device.racks_count or 0), 0) + 1):
            photo = photo_by_key.get((device.id, rack_id))
            result.append(
                {
                    "device_id": device.id,
                    "device_name": device.name,
                    "rack_id": rack_id,
                    "has_photo": photo is not None,
                    "photo_id": photo.id if photo else None,
                    "photo_url": (
                        f"/api/v1/admin/rack-photos/{photo.id}/image"
                        if photo
                        else None
                    ),
                    "captured_at": photo.captured_at if photo else None,
                    "updated_at": photo.updated_at if photo else None,
                    "size_bytes": int(photo.size_bytes) if photo else None,
                }
            )
    return result


@router.get("/rack-photos/{photo_id}/image")
async def rack_photo_image(
    photo_id: int,
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    photo = await session.get(RackPhoto, photo_id)
    if photo is None:
        raise HTTPException(status_code=404, detail="Rack photo not found")

    path = Path(photo.file_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Rack photo file not found")

    return FileResponse(
        path,
        media_type=photo.content_type or "image/jpeg",
        headers={"Cache-Control": "no-store"},
    )
