from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .models import Device, RackPhoto, RackCameraPhoto, User
from .rack_photo_storage import SLOT_COUNT, slot_latest_path, slot_camera_latest_path
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
    legacy_photos = (
        await session.execute(
            select(RackPhoto).where(RackPhoto.device_id.in_(device_ids))
        )
    ).scalars().all()
    camera_photos = (
        await session.execute(
            select(RackCameraPhoto).where(RackCameraPhoto.device_id.in_(device_ids))
        )
    ).scalars().all()

    legacy_by_key = {
        (photo.device_id, photo.rack_id): photo for photo in legacy_photos
    }
    camera_by_key: dict[tuple[str, int], list[RackCameraPhoto]] = {}
    for photo in camera_photos:
        camera_by_key.setdefault((photo.device_id, photo.rack_id), []).append(photo)
    for rows in camera_by_key.values():
        rows.sort(key=lambda item: (not item.is_primary, item.camera_id))

    settings = get_settings()
    result = []
    for device in devices:
        for rack_id in range(1, max(int(device.racks_count or 0), 0) + 1):
            key = (device.id, rack_id)
            rows = camera_by_key.get(key, [])
            if rows:
                for photo in rows:
                    slot_photo_urls: dict[str, str] = {}
                    for slot_number in range(1, SLOT_COUNT + 1):
                        path = slot_camera_latest_path(
                            settings.photo_dir,
                            device.id,
                            rack_id,
                            photo.camera_id,
                            slot_number,
                            primary=bool(photo.is_primary),
                        )
                        if path.is_file():
                            slot_photo_urls[str(slot_number)] = (
                                f"/api/v1/admin/rack-camera-photos/{photo.id}/"
                                f"slots/{slot_number}/image"
                            )

                    result.append(
                        {
                            "device_id": device.id,
                            "device_name": device.name,
                            "rack_id": rack_id,
                            "camera_id": photo.camera_id,
                            "camera_name": photo.camera_id,
                            "is_primary": bool(photo.is_primary),
                            "has_photo": True,
                            "photo_id": photo.id,
                            "photo_url": (
                                f"/api/v1/admin/rack-camera-photos/{photo.id}/image"
                            ),
                            "captured_at": photo.captured_at,
                            "updated_at": photo.updated_at,
                            "size_bytes": int(photo.size_bytes),
                            "slot_photo_urls": slot_photo_urls,
                        }
                    )
                continue

            # A server upgraded before the Pi may still only have the original
            # one-photo-per-rack record. Keep showing it until a camera-aware
            # upload arrives.
            legacy = legacy_by_key.get(key)
            slot_photo_urls: dict[str, str] = {}
            if legacy is not None:
                for slot_number in range(1, SLOT_COUNT + 1):
                    path = slot_latest_path(
                        settings.photo_dir,
                        device.id,
                        rack_id,
                        slot_number,
                    )
                    if path.is_file():
                        slot_photo_urls[str(slot_number)] = (
                            f"/api/v1/admin/rack-photos/{legacy.id}/"
                            f"slots/{slot_number}/image"
                        )

            result.append(
                {
                    "device_id": device.id,
                    "device_name": device.name,
                    "rack_id": rack_id,
                    "camera_id": None,
                    "camera_name": "Основная камера",
                    "is_primary": True,
                    "has_photo": legacy is not None,
                    "photo_id": legacy.id if legacy else None,
                    "photo_url": (
                        f"/api/v1/admin/rack-photos/{legacy.id}/image"
                        if legacy
                        else None
                    ),
                    "captured_at": legacy.captured_at if legacy else None,
                    "updated_at": legacy.updated_at if legacy else None,
                    "size_bytes": int(legacy.size_bytes) if legacy else None,
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

@router.get("/rack-camera-photos/{photo_id}/image")
async def rack_camera_photo_image(
    photo_id: int,
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    photo = await session.get(RackCameraPhoto, photo_id)
    if photo is None:
        raise HTTPException(status_code=404, detail="Rack camera photo not found")
    path = Path(photo.file_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Rack camera photo file not found")
    return FileResponse(
        path,
        media_type=photo.content_type or "image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/rack-camera-photos/{photo_id}/slots/{slot_number}/image")
async def rack_camera_slot_photo_image(
    photo_id: int,
    slot_number: int,
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    if slot_number < 1 or slot_number > SLOT_COUNT:
        raise HTTPException(status_code=404, detail="Container not found")
    photo = await session.get(RackCameraPhoto, photo_id)
    if photo is None:
        raise HTTPException(status_code=404, detail="Rack camera photo not found")
    path = slot_camera_latest_path(
        get_settings().photo_dir,
        photo.device_id,
        photo.rack_id,
        photo.camera_id,
        slot_number,
        primary=bool(photo.is_primary),
    )
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Container photo not found")
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )

