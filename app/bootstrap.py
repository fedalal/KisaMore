from sqlalchemy import select
from .db import engine, SessionLocal
from .models import Base, RackState, RackSchedule

_EMPTY = {"mon": [], "tue": [], "wed": [], "thu": [], "fri": [], "sat": [], "sun": []}

async def ensure_db_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def ensure_db_racks(racks_count: int):
    async with SessionLocal() as s:
        for rack_id in range(1, racks_count + 1):
            st = (await s.execute(select(RackState).where(RackState.rack_id == rack_id))).scalar_one_or_none()
            if not st:
                s.add(RackState(rack_id=rack_id))

            sch = (await s.execute(select(RackSchedule).where(RackSchedule.rack_id == rack_id))).scalar_one_or_none()
            if not sch:
                s.add(RackSchedule(
                    rack_id=rack_id,
                    schedule_json={"light": dict(_EMPTY), "water": dict(_EMPTY)},
                ))
        await s.commit()
