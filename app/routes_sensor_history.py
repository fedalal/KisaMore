from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Query
from sqlalchemy import select

from .db import SessionLocal
from .models import RackSensorHistory


def get_moscow_tz():
    try:
        return ZoneInfo("Europe/Moscow")
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=3))


MOSCOW_TZ = get_moscow_tz()
UTC_TZ = timezone.utc

router = APIRouter(prefix="/api", tags=["sensor-history"])


@router.get("/sensor-history")
async def get_sensor_history(
    rack_id: int | None = None,
    hours: int = Query(default=24, ge=1, le=24 * 30),
):
    dt_from = datetime.now(UTC_TZ) - timedelta(hours=hours)

    async with SessionLocal() as s:
        query = (
            select(RackSensorHistory)
            .where(RackSensorHistory.created_at >= dt_from)
            .order_by(RackSensorHistory.created_at.asc())
        )

        if rack_id is not None:
            query = query.where(RackSensorHistory.rack_id == rack_id)

        rows = (await s.execute(query)).scalars().all()

    grouped: dict[str, list[dict]] = {}

    for r in rows:
        dt = r.created_at

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC_TZ)

        dt_local = dt.astimezone(MOSCOW_TZ)

        key = str(r.rack_id)
        grouped.setdefault(key, []).append({
            "created_at": dt_local.isoformat(),
            "soil_moisture": r.soil_moisture,
            "soil_temperature": r.soil_temperature,
        })

    return {
        "items": grouped
    }