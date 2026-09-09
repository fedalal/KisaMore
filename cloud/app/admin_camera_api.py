from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .models import Device, RackPhoto, User
from .rack_photo_storage import SLOT_COUNT, slot_latest_path
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
    settings = get_settings()

    result = []
    for device in devices:
        for rack_id in range(1, max(int(device.racks_count or 0), 0) + 1):
            photo = photo_by_key.get((device.id, rack_id))
            slot_photo_urls: dict[str, str] = {}
            if photo is not None:
                for slot_number in range(1, SLOT_COUNT + 1):
                    path = slot_latest_path(
                        settings.photo_dir,
                        device.id,
                        rack_id,
                        slot_number,
                    )
                    if path.is_file():
                        slot_photo_urls[str(slot_number)] = (
                            f"/api/v1/admin/rack-photos/{photo.id}/slots/{slot_number}/image"
                        )

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
                    "slot_photo_urls": slot_photo_urls,
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


@router.get("/rack-photos/{photo_id}/slots/{slot_number}/image")
async def rack_slot_photo_image(
    photo_id: int,
    slot_number: int,
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    if slot_number < 1 or slot_number > SLOT_COUNT:
        raise HTTPException(status_code=404, detail="Container not found")

    photo = await session.get(RackPhoto, photo_id)
    if photo is None:
        raise HTTPException(status_code=404, detail="Rack photo not found")

    path = slot_latest_path(
        get_settings().photo_dir,
        photo.device_id,
        photo.rack_id,
        slot_number,
    )
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Container photo not found")

    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )
