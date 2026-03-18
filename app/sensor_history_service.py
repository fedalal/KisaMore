from __future__ import annotations

import asyncio
from datetime import datetime

from sqlalchemy import select

from .db import SessionLocal
from .models import RackSensorHistory, RackState
from . import runtime


class SensorHistoryService:
    def __init__(self, interval_sec: int = 300):
        self.interval_sec = interval_sec
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self):
        if self._task and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self):
        while self._running:
            try:
                await self.collect_once()
            except Exception as e:
                print(f"[sensor_history] collect error: {e}")
            await asyncio.sleep(self.interval_sec)

    async def collect_once(self):
        if not runtime.cfg or not runtime.driver:
            return

        max_racks = runtime.cfg.racks_count

        async with SessionLocal() as s:
            states = (await s.execute(
                select(RackState).order_by(RackState.rack_id)
            )).scalars().all()

            for st in states:
                if st.rack_id > max_racks:
                    continue

                rack_cfg = runtime.cfg.racks.get(str(st.rack_id))
                if not rack_cfg:
                    continue

                sensor_slave_id = rack_cfg.sensor_slave_id
                if sensor_slave_id is None:
                    continue

                soil_moisture = None
                soil_temperature = None

                try:
                    soil_moisture, soil_temperature = await runtime.driver.read_soil_sensor(sensor_slave_id)
                except Exception as e:
                    print(f"[sensor_history] rack {st.rack_id} sensor read failed: {e}")

                row = RackSensorHistory(
                    rack_id=st.rack_id,
                    sensor_slave_id=sensor_slave_id,
                    soil_moisture=soil_moisture,
                    soil_temperature=soil_temperature,
                    created_at=datetime.utcnow(),
                )
                s.add(row)

            await s.commit()