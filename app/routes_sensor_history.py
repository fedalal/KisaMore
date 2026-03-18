from datetime import datetime, timedelta

from fastapi import APIRouter, Query
from sqlalchemy import select

from .db import SessionLocal
from .models import RackSensorHistory
from zoneinfo import ZoneInfo

MOSCOW_TZ = ZoneInfo("Europe/Moscow")

router = APIRouter(prefix="/api", tags=["sensor-history"])


@router.get("/sensor-history/{rack_id}")
async def get_sensor_history(
    rack_id: int,
    hours: int = Query(default=24, ge=1, le=24 * 30),
):
    dt_from = datetime.now(ZoneInfo("UTC")) - timedelta(hours=hours)

    async with SessionLocal() as s:
        rows = (await s.execute(
            select(RackSensorHistory)
            .where(RackSensorHistory.rack_id == rack_id)
            .where(RackSensorHistory.created_at >= dt_from)
            .order_by(RackSensorHistory.created_at.asc())
        )).scalars().all()

    items = []
    for r in rows:
        dt = r.created_at

        # если дата без timezone → считаем, что это UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))

        dt_local = dt.astimezone(MOSCOW_TZ)

        items.append({
            "created_at": dt_local.isoformat(),
            "soil_moisture": r.soil_moisture,
            "soil_temperature": r.soil_temperature,
        })

    return {
        "rack_id": rack_id,
        "items": items
    }