from fastapi import APIRouter
from sqlalchemy import select
from datetime import datetime

from .db import SessionLocal
from .models import RackState
from .schemas import RackStateOut
from . import runtime
from .routes_schedule import load_schedule_for_rack
from .schedule_info import compute_now_next

router = APIRouter(prefix="/api", tags=["state"])

@router.get("/state", response_model=list[RackStateOut])
async def get_state():
    max_racks = runtime.cfg.racks_count if runtime.cfg else 4
    now = datetime.now()

    async with SessionLocal() as s:
        rows = (await s.execute(select(RackState).order_by(RackState.rack_id))).scalars().all()
        rows = [r for r in rows if r.rack_id <= max_racks]

        result = []
        for r in rows:
            # Всегда инициализируем ВСЕ поля, которые возвращаем
            light_until = None
            water_until = None

            light_interval = None
            water_interval = None

            light_next_on = None
            water_next_on = None

            # Расписание нужно только если хотя бы один канал работает по расписанию
            sch = None
            if r.light_mode == "schedule" or r.water_mode == "schedule":
                sch = await load_schedule_for_rack(r.rack_id)

            # LIGHT
            if r.light_mode == "schedule" and sch is not None:
                info = compute_now_next(sch.get("light", {}), now)
                if r.light_on:
                    light_interval = info.interval_text()  # "08:00–21:30"
                    light_until = info.active_end          # "21:30"
                else:
                    light_next_on = info.next_text()       # "Пн 08:00"

            # WATER
            if r.water_mode == "schedule" and sch is not None:
                info = compute_now_next(sch.get("water", {}), now)
                if r.water_on:
                    water_interval = info.interval_text()
                    water_until = info.active_end
                else:
                    water_next_on = info.next_text()

            result.append(
                RackStateOut(
                    rack_id=r.rack_id,
                    light_on=r.light_on,
                    water_on=r.water_on,
                    light_mode=r.light_mode,
                    water_mode=r.water_mode,

                    light_until=light_until,
                    water_until=water_until,
                    light_interval=light_interval,
                    water_interval=water_interval,
                    light_next_on=light_next_on,
                    water_next_on=water_next_on,
                )
            )

        return result
