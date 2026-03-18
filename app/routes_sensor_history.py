from datetime import datetime, timedelta

from fastapi import APIRouter, Query
from sqlalchemy import select

from .db import SessionLocal
from .models import RackSensorHistory

router = APIRouter(prefix="/api", tags=["sensor-history"])


@router.get("/sensor-history/{rack_id}")
async def get_sensor_history(
    rack_id: int,
    hours: int = Query(default=24, ge=1, le=24 * 30),
):
    dt_from = datetime.utcnow() - timedelta(hours=hours)

    async with SessionLocal() as s:
        rows = (await s.execute(
            select(RackSensorHistory)
            .where(RackSensorHistory.rack_id == rack_id)
            .where(RackSensorHistory.created_at >= dt_from)
            .order_by(RackSensorHistory.created_at.asc())
        )).scalars().all()

    return {
        "rack_id": rack_id,
        "items": [
            {
                "created_at": r.created_at.isoformat(),
                "soil_moisture": r.soil_moisture,
                "soil_temperature": r.soil_temperature,
            }
            for r in rows
        ]
    }