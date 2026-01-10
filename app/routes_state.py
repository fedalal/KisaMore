from fastapi import APIRouter
from sqlalchemy import select
from datetime import datetime

from .db import SessionLocal
from .models import RackState
from .schemas import RackStateOut
from . import runtime
from .schedule_until import active_until
from .routes_schedule import load_schedule_for_rack  # функция уже есть у тебя

router = APIRouter(prefix="/api", tags=["state"])

@router.get("/state", response_model=list[RackStateOut])
async def get_state():
    max_racks = runtime.cfg.racks_count if runtime.cfg else 4
    now = datetime.now()

    async with SessionLocal() as s:
        rows = (await s.execute(
            select(RackState).order_by(RackState.rack_id)
        )).scalars().all()

        rows = [r for r in rows if r.rack_id <= max_racks]

        result = []
        for r in rows:
            light_until = None
            water_until = None

            if r.light_mode == "schedule" and r.light_on:
                sch = await load_schedule_for_rack(r.rack_id)
                light_until = active_until(sch.get("light", {}), now)

            if r.water_mode == "schedule" and r.water_on:
                sch = await load_schedule_for_rack(r.rack_id)
                water_until = active_until(sch.get("water", {}), now)

            result.append(
                RackStateOut(
                    rack_id=r.rack_id,
                    light_on=r.light_on,
                    water_on=r.water_on,
                    light_mode=r.light_mode,
                    water_mode=r.water_mode,
                    light_until=light_until,
                    water_until=water_until,
                )
            )

        return result
