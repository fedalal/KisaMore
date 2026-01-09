import asyncio
from datetime import datetime
from sqlalchemy import select
from .config import settings
from .db import SessionLocal
from .models import RackState, RackSchedule

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

def _in_any_range(now_hm: str, ranges: list[dict]) -> bool:
    for r in ranges:
        if r["start"] <= now_hm < r["end"]:
            return True
    return False

class Scheduler:
    def __init__(self, runtime):
        self.runtime = runtime
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def start(self):
        self._stop.clear()
        self._task = asyncio.create_task(self._run())

    async def stop(self):
        self._stop.set()
        if self._task:
            await self._task

    async def _run(self):
        while not self._stop.is_set():
            try:
                await self.tick()
            except Exception as e:
                print("[SCHED] error:", e)
            await asyncio.sleep(settings.scheduler_tick_seconds)

    async def tick(self):
        if not self.runtime.cfg or not self.runtime.driver:
            return

        now = datetime.now()
        day_key = DAYS[now.weekday()]
        now_hm = now.strftime("%H:%M")

        async with SessionLocal() as s:
            states = (await s.execute(select(RackState))).scalars().all()
            schedules = {x.rack_id: x for x in (await s.execute(select(RackSchedule))).scalars().all()}

            for st in states:
                if st.rack_id > self.runtime.cfg.racks_count:
                    continue

                sch = schedules.get(st.rack_id)
                sch_json = sch.schedule_json if sch else {}

                if st.light_mode == "schedule":
                    light_ranges = (((sch_json.get("light") or {}).get(day_key)) or [])
                    want = _in_any_range(now_hm, light_ranges)
                    if want != st.light_on:
                        st.light_on = want
                        relay_id = self.runtime.cfg.racks[str(st.rack_id)].light_relay
                        await self.runtime.driver.set_relay(relay_id, want)

                if st.water_mode == "schedule":
                    water_ranges = (((sch_json.get("water") or {}).get(day_key)) or [])
                    want = _in_any_range(now_hm, water_ranges)
                    if want != st.water_on:
                        st.water_on = want
                        relay_id = self.runtime.cfg.racks[str(st.rack_id)].water_relay
                        await self.runtime.driver.set_relay(relay_id, want)

            await s.commit()
