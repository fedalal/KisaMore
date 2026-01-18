from fastapi import APIRouter
from sqlalchemy import select
from .db import SessionLocal
from .models import RackState, RackSchedule
from .schemas import RackStateOut
from . import runtime
from datetime import datetime
from .schedule_info import compute_now_next

router = APIRouter(prefix="/api", tags=["state"])

@router.get("/state", response_model=list[RackStateOut])
async def get_state():
    max_racks = runtime.cfg.racks_count if runtime.cfg else 4
    async with SessionLocal() as s:
        states = (await s.execute(select(RackState).order_by(RackState.rack_id))).scalars().all()
        states = [r for r in states if r.rack_id <= max_racks]

        schedules = {x.rack_id: x for x in (await s.execute(select(RackSchedule))).scalars().all()}
        now = datetime.now()

        out: list[RackStateOut] = []
        for r in states:
            sch = schedules.get(r.rack_id)
            sch_json = (sch.schedule_json or {}) if sch else {}

            light_ch = (sch_json.get("light") or {})
            water_ch = (sch_json.get("water") or {})

            light_info = compute_now_next(light_ch, now)
            water_info = compute_now_next(water_ch, now)

            # Логика подсказок для UI:
            # - если сейчас включено — показываем "до HH:MM" только если мы реально внутри интервала расписания
            # - если сейчас выключено — показываем ближайший следующий старт
            light_until = light_info.active_end if (r.light_on and light_info.active_end) else None
            light_next = (None if r.light_on else light_info.next_text())
            water_until = water_info.active_end if (r.water_on and water_info.active_end) else None
            water_next = (None if r.water_on else water_info.next_text())

            out.append(RackStateOut(
                rack_id=r.rack_id,
                light_on=r.light_on,
                water_on=r.water_on,
                light_mode=r.light_mode,
                water_mode=r.water_mode,
                light_until=light_until,
                light_next=light_next,
                water_until=water_until,
                water_next=water_next,
            ))

        return out
