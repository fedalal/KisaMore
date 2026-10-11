"""Administrator-only editor for per-camera slot outlines.

Points are fractions of the *original* camera photo, not the browser viewport.
Mobile readers receive the same coordinates through the public battle payload.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    Device, Farm, RackCameraPhoto, RackCameraCalibration, User
)
from .security import get_admin_user, get_session

router = APIRouter(prefix="/api/v1/admin/rack-calibrations", tags=["admin-rack-calibrations"])


def _signed_area(points: list[list[float]]) -> float:
    return sum(
        points[i][0] * points[(i + 1) % 4][1] -
        points[(i + 1) % 4][0] * points[i][1]
        for i in range(4)
    ) / 2.0


def _valid_quad(points: list[list[float]]) -> bool:
    if len(points) != 4 or not all(
        isinstance(p, list) and len(p) == 2 and all(
            isinstance(v, (int, float)) and not isinstance(v, bool) and
            0 <= v <= 1 for v in p
        ) for p in points
    ):
        return False
    if abs(_signed_area(points)) < .0001:
        return False
    turns = []
    for i in range(4):
        a, b, c = (points[(i + k) % 4] for k in range(3))
        cross = (b[0]-a[0]) * (c[1]-b[1]) - (b[1]-a[1]) * (c[0]-b[0])
        turns.append(cross)
    return all(v > 0.000001 for v in turns) or all(v < -0.000001 for v in turns)


class CalibrationIn(BaseModel):
    slot_outlines: dict[str, list[list[float]]] = Field(description="Six polygons, four XY pairs each")

    @model_validator(mode="after")
    def check_shapes(self):
        if set(self.slot_outlines) != {str(i) for i in range(1, 7)}:
            raise ValueError("Exactly six outlines, for slots 1 through 6, are required")
        for number, points in self.slot_outlines.items():
            if not _valid_quad(points):
                raise ValueError(f"Invalid four-corner outline for container {number}")
        return self


@router.get("")
async def list_rack_calibrations(
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    cameras = (await session.execute(
        select(RackCameraPhoto, Device.name, Farm.slug)
        .join(Device, Device.id == RackCameraPhoto.device_id)
        .join(Farm, Farm.id == Device.farm_id)
        .order_by(Device.name, RackCameraPhoto.rack_id,
                  RackCameraPhoto.is_primary.desc(), RackCameraPhoto.camera_id)
    )).all()
    saved = (await session.execute(select(RackCameraCalibration))).scalars().all()
    index = {(row.device_id, row.rack_id, row.camera_id): row for row in saved}
    return [{
        "device_id": camera.device_id,
        "device_name": name,
        "rack_id": camera.rack_id,
        "camera_id": camera.camera_id,
        "primary": camera.is_primary,
        "captured_at": camera.captured_at,
        "photo_url": (
            f"/api/v1/public/farms/{slug}/racks/{camera.rack_id}/"
            f"cameras/{camera.camera_id}/photo"
        ),
        "slot_outlines": (
            index[(camera.device_id, camera.rack_id, camera.camera_id)].slot_outlines
            if (camera.device_id, camera.rack_id, camera.camera_id) in index
            else None
        ),
    } for camera, name, slug in cameras]


@router.put("/{device_id}/{rack_id}/{camera_id}")
async def save_rack_calibration(
    device_id: str,
    rack_id: int,
    camera_id: str,
    payload: CalibrationIn,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    camera = (await session.execute(select(RackCameraPhoto).where(
        RackCameraPhoto.device_id == device_id,
        RackCameraPhoto.rack_id == rack_id,
        RackCameraPhoto.camera_id == camera_id,
    ))).scalar_one_or_none()
    if camera is None:
        raise HTTPException(404, "Camera for this rack was not found")
    saved = (await session.execute(
        select(RackCameraCalibration)
        .where(
            RackCameraCalibration.device_id == device_id,
            RackCameraCalibration.rack_id == rack_id,
            RackCameraCalibration.camera_id == camera_id,
        )
        .with_for_update()
    )).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if saved is None:
        saved = RackCameraCalibration(
            device_id=device_id, rack_id=rack_id, camera_id=camera_id,
            slot_outlines=payload.slot_outlines,
            updated_at=now, updated_by_user_id=admin.id,
        )
        session.add(saved)
    else:
        saved.slot_outlines = payload.slot_outlines
        saved.updated_at = now
        saved.updated_by_user_id = admin.id
    await session.commit()
    return {"saved": True, "device_id": device_id, "rack_id": rack_id,
            "camera_id": camera_id, "slot_outlines": saved.slot_outlines}
