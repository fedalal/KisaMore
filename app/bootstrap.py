from sqlalchemy import inspect, select
from .db import engine, SessionLocal
from .models import Base, RackSlot, RackState, RackSchedule

_EMPTY = {"mon": [], "tue": [], "wed": [], "thu": [], "fri": [], "sat": [], "sun": []}

_PLANT_IMAGE_COLUMNS = {
    "seed_image_name": "VARCHAR(255) NOT NULL DEFAULT ''",
    "microgreen_image_name": "VARCHAR(255) NOT NULL DEFAULT ''",
}


def _ensure_plant_image_columns(connection) -> None:
    inspector = inspect(connection)
    if "plants" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("plants")}
    for name, definition in _PLANT_IMAGE_COLUMNS.items():
        if name not in existing:
            connection.exec_driver_sql(f"ALTER TABLE plants ADD COLUMN {name} {definition}")

async def ensure_db_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_plant_image_columns)

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

            existing_slots = set(
                (
                    await s.execute(
                        select(RackSlot.slot_number).where(RackSlot.rack_id == rack_id)
                    )
                ).scalars().all()
            )
            for slot_number in range(1, 7):
                if slot_number not in existing_slots:
                    s.add(RackSlot(rack_id=rack_id, slot_number=slot_number))
        await s.commit()
