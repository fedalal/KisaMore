from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .models import Device, Farm, RackPhoto, RackCameraPhoto
from .rack_photo_storage import (
    SLOT_COUNT,
    rack_latest_path,
    slot_latest_path,
    slot_camera_latest_path,
)
from .security import get_session


router = APIRouter(prefix="/api/v1", tags=["rack-photos"])


@router.get(
    "/public/farms/{farm_slug}/racks/{rack_id}/photo",
    response_class=FileResponse,
)
async def public_rack_photo(
    farm_slug: str,
    rack_id: int,
    session: AsyncSession = Depends(get_session),
):
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

    path = rack_latest_path(get_settings().photo_dir, row.device_id, rack_id)
    if not Path(path).is_file():
        raise HTTPException(status_code=404, detail="Rack photo not found")

    captured = row.captured_at.isoformat() if row.captured_at else ""
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-store",
            "X-Captured-At": captured,
        },
    )


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

@router.get("/public/farms/{farm_slug}/racks/{rack_id}/cameras")
async def public_rack_cameras(
    farm_slug: str,
    rack_id: int,
    session: AsyncSession = Depends(get_session),
):
    rows = list(
        (
            await session.execute(
                select(RackCameraPhoto)
                .join(Device, Device.id == RackCameraPhoto.device_id)
                .join(Farm, Farm.id == Device.farm_id)
                .where(
                    Farm.slug == farm_slug,
                    Farm.is_public.is_(True),
                    Device.is_active.is_(True),
                    RackCameraPhoto.rack_id == rack_id,
                )
                .order_by(RackCameraPhoto.is_primary.desc(), RackCameraPhoto.camera_id)
            )
        ).scalars().all()
    )
    return [
        {
            "camera_id": row.camera_id,
            "primary": bool(row.is_primary),
            "captured_at": row.captured_at,
            "photo_url": (
                f"/api/v1/public/farms/{farm_slug}/racks/{rack_id}/"
                f"cameras/{row.camera_id}/photo"
            ),
        }
        for row in rows
    ]


async def _public_camera_photo_row(
    session: AsyncSession,
    farm_slug: str,
    rack_id: int,
    camera_id: str,
) -> RackCameraPhoto:
    row = (
        await session.execute(
            select(RackCameraPhoto)
            .join(Device, Device.id == RackCameraPhoto.device_id)
            .join(Farm, Farm.id == Device.farm_id)
            .where(
                Farm.slug == farm_slug,
                Farm.is_public.is_(True),
                Device.is_active.is_(True),
                RackCameraPhoto.rack_id == rack_id,
                RackCameraPhoto.camera_id == camera_id,
            )
            .order_by(Device.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Rack camera photo not found")
    return row


@router.get(
    "/public/farms/{farm_slug}/racks/{rack_id}/cameras/{camera_id}/photo",
    response_class=FileResponse,
)
async def public_rack_camera_photo(
    farm_slug: str,
    rack_id: int,
    camera_id: str,
    session: AsyncSession = Depends(get_session),
):
    row = await _public_camera_photo_row(session, farm_slug, rack_id, camera_id)
    path = Path(row.file_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Rack camera photo file not found")
    return FileResponse(
        path,
        media_type=row.content_type or "image/jpeg",
        headers={
            "Cache-Control": "no-store",
            "X-Captured-At": row.captured_at.isoformat() if row.captured_at else "",
            "X-Camera-ID": row.camera_id,
            "X-Camera-Primary": "true" if row.is_primary else "false",
        },
    )


@router.get(
    "/public/farms/{farm_slug}/racks/{rack_id}/cameras/{camera_id}/"
    "slots/{slot_number}/photo",
    response_class=FileResponse,
)
async def public_rack_camera_slot_photo(
    farm_slug: str,
    rack_id: int,
    camera_id: str,
    slot_number: int,
    session: AsyncSession = Depends(get_session),
):
    if slot_number < 1 or slot_number > SLOT_COUNT:
        raise HTTPException(status_code=404, detail="Container not found")
    row = await _public_camera_photo_row(session, farm_slug, rack_id, camera_id)
    path = slot_camera_latest_path(
        get_settings().photo_dir,
        row.device_id,
        rack_id,
        row.camera_id,
        slot_number,
        primary=bool(row.is_primary),
    )
    if not Path(path).is_file():
        raise HTTPException(status_code=404, detail="Container camera photo not found")
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-store",
            "X-Captured-At": row.captured_at.isoformat() if row.captured_at else "",
            "X-Camera-ID": row.camera_id,
            "X-Camera-Primary": "true" if row.is_primary else "false",
        },
    )

