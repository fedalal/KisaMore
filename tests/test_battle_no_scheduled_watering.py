"""Integration test against isolated SQLite; never touches production data."""
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from cloud.app import db  # Registers every FK referenced by the model metadata.
from cloud.app.models import Base, Plant, RackSlot, Planting, WateringTask
from cloud.app.battle_models import PlantBattleEntry
from cloud.app.watering_service import refresh_watering_tasks
from cloud.app.watering_admin_api import (
    CompleteWateringIn, complete_watering_task, list_watering_tasks
)

NOW = datetime(2026, 10, 13, 7, 0, tzinfo=timezone.utc)


def task(planting_id, when, status="pending"):
    return WateringTask(
        id=str(uuid4()), planting_id=planting_id, device_id="test-device",
        rack_id=1, slot_number=1 if planting_id=="battle-planting" else 2,
        scheduled_at=when, planned_ml=150, task_type="scheduled",
        status=status, created_at=NOW-timedelta(days=2),
        completed_at=when if status=="done" else None,
    )


async def main():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as con:
        await con.run_sync(Base.metadata.create_all)
    Session=async_sessionmaker(engine, expire_on_commit=False)
    start=NOW-timedelta(days=1)
    async with Session() as session:
        plant=Plant(id=str(uuid4()),code="test-water-plant",
            names={"en":"Test"},watering_schedule=[{"time":"12:00","ml":150}])
        rack1=RackSlot(device_id="test-device",rack_id=1,slot_number=1,
            physical_status="growing",enabled=True,observed_at=NOW)
        rack2=RackSlot(device_id="test-device",rack_id=1,slot_number=2,
            physical_status="growing",enabled=True,observed_at=NOW)
        session.add_all([plant,rack1,rack2])
        await session.flush()
        battle=Planting(id="battle-planting",slot_id=rack1.id,plant_id=plant.id,
            status="growing",planted_at=start,
            expected_harvest_at=NOW+timedelta(days=5),observed_at=NOW)
        regular=Planting(id="regular-planting",slot_id=rack2.id,plant_id=plant.id,
            status="growing",planted_at=start,
            expected_harvest_at=NOW+timedelta(days=5),observed_at=NOW)
        battle_entry=PlantBattleEntry(id=str(uuid4()),battle_id=str(uuid4()),
            user_id=str(uuid4()),planting_id=battle.id,slot_number=1,price_kisa=10,
            status="active",created_at=NOW)
        old_battle=[
            task(battle.id, NOW-timedelta(days=5)),
            task(battle.id, NOW+timedelta(hours=3)),
            task(battle.id, NOW-timedelta(days=3),status="done"),
        ]
        session.add_all([battle,regular,battle_entry,*old_battle])
        await session.commit()
        result=await refresh_watering_tasks(session,now=NOW,horizon_hours=24,lookback_hours=24)
        await session.commit()
        battle_tasks=(await session.execute(select(WateringTask).where(
            WateringTask.planting_id == battle.id))).scalars().all()
        assert len(battle_tasks)==3, "No NEW Battle scheduled tasks"
        assert sum(t.status=="skipped" for t in battle_tasks)==2
        assert sum(t.status=="done" for t in battle_tasks)==1, "History preserved"
        assert all("Battle" in (t.note or "") for t in battle_tasks if t.status=="skipped")
        normal_tasks=(await session.execute(select(WateringTask).where(
            WateringTask.planting_id == regular.id))).scalars().all()
        assert normal_tasks and all(t.status=="pending" for t in normal_tasks), "Normal plant schedule is intact"
        assert result["skipped"]==2, result
        again=await refresh_watering_tasks(session,now=NOW,horizon_hours=24,lookback_hours=24)
        await session.commit()
        assert again["skipped"]==0 and again["created"]==0, again

        # Even a cancelled/finished Battle entry still prevents its
        # planting from being treated as a regular scheduled rental.
        battle_entry.status="finished"
        await session.commit()
        third=await refresh_watering_tasks(session,now=NOW,horizon_hours=24,lookback_hours=24)
        assert third["created"]==0 and third["skipped"]==0, third

        # Simulate a stale task ID from an old admin message: API may not
        # allow an admin to accidentally mark it complete as a generic rental.
        forbidden = task(battle.id, NOW+timedelta(days=4))
        session.add(forbidden)
        await session.commit()
        try:
            await complete_watering_task(
                forbidden.id, CompleteWateringIn(actual_ml=150),
                admin=type("Admin", (), {"id":str(uuid4())})(),
                session=session,
            )
        except HTTPException as exc:
            assert exc.status_code == 409 and "Battle" in exc.detail
        else:
            raise AssertionError("Generic admin endpoint fulfilled Battle watering")
        assert (await session.get(WateringTask, forbidden.id)).status == "pending"

        # The admin watering queue lists ordinary plant tasks only (even
        # for previously skipped Battle entries).
        listed = await list_watering_tasks(day="2026-10-13",session=session)
        assert listed["tasks"]
        assert all(t["planting_id"] == regular.id for t in listed["tasks"]), listed["tasks"]

        sql=str(select(WateringTask).where(
            ~WateringTask.planting_id.in_(select(PlantBattleEntry.planting_id).where(
                PlantBattleEntry.planting_id.is_not(None)
            ))
        ))
        assert "plant_battle_entries" in sql
        print("PASS: no Battle schedule; stale tasks skipped; completed history preserved; normal rentals intact; admin API protected")
    await engine.dispose()


if __name__=="__main__":
    asyncio.run(main())
