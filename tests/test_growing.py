from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import bootstrap, cloud_sync_service, routes_growing
from app.cloud_sync_service import CloudSyncService
from app.models import Base, Plant, Planting, RackSlot
from app.schemas import PlantIn, PlantingCreateIn, PlantingUpdateIn, SlotUpdateIn


def test_six_slots_and_planting_lifecycle(monkeypatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'growing.db'}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(bootstrap, "engine", engine)
    monkeypatch.setattr(bootstrap, "SessionLocal", session_factory)
    monkeypatch.setattr(routes_growing, "SessionLocal", session_factory)
    monkeypatch.setattr(routes_growing.runtime, "cfg", SimpleNamespace(racks_count=2))

    async def scenario():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await bootstrap.ensure_db_racks(2)

        async with session_factory() as session:
            slots = (
                await session.execute(
                    select(RackSlot).order_by(RackSlot.rack_id, RackSlot.slot_number)
                )
            ).scalars().all()
            assert len(slots) == 12
            assert [slot.slot_number for slot in slots[:6]] == [1, 2, 3, 4, 5, 6]

        plant = await routes_growing.create_plant(
            PlantIn(
                code="radish",
                names={"en": "Radish", "ru": "Редис"},
                seed_image_name="radish_seeds.jpg",
                microgreen_image_name="radish_microgreens.jpg",
                grow_days=12,
            )
        )
        assert plant.seed_image_name == "radish_seeds.jpg"
        assert plant.microgreen_image_name == "radish_microgreens.jpg"
        planting = await routes_growing.create_planting(
            PlantingCreateIn(
                rack_id=1,
                slot_number=1,
                plant_id=plant.id,
                planted_at=datetime(2026, 8, 30, tzinfo=timezone.utc),
            )
        )
        assert planting.status == "growing"
        assert (planting.expected_harvest_at - planting.planted_at).days == 12

        ready = await routes_growing.update_planting(
            planting.id, PlantingUpdateIn(status="ready")
        )
        assert ready.status == "ready"
        harvested = await routes_growing.update_planting(
            planting.id, PlantingUpdateIn(status="harvested")
        )
        assert harvested.actual_harvest_at is not None
        slot = await routes_growing.update_slot(
            1, 1, SlotUpdateIn(status="available")
        )
        assert slot.status == "available"

        archived = await routes_growing.update_plant(
            plant.id,
            PlantIn(
                code=plant.code,
                names=plant.names,
                seed_image_name=plant.seed_image_name,
                microgreen_image_name=plant.microgreen_image_name,
                grow_days=plant.grow_days,
                active=False,
            ),
        )
        assert archived.active is False
        assert await routes_growing.list_plants() == []
        all_plants = await routes_growing.list_plants(include_inactive=True)
        assert len(all_plants) == 1
        assert all_plants[0].id == plant.id
        await engine.dispose()

    asyncio.run(scenario())


def test_existing_plant_table_gets_image_columns(monkeypatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'old.db'}")
    monkeypatch.setattr(bootstrap, "engine", engine)

    async def scenario():
        async with engine.begin() as connection:
            await connection.exec_driver_sql(
                """
                CREATE TABLE plants (
                    id VARCHAR(36) PRIMARY KEY,
                    code VARCHAR(80) NOT NULL UNIQUE,
                    names JSON NOT NULL,
                    descriptions JSON NOT NULL,
                    grow_days INTEGER NOT NULL,
                    active BOOLEAN NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
                """
            )

        await bootstrap.ensure_db_tables()

        async with engine.connect() as connection:
            columns = await connection.run_sync(
                lambda sync_connection: {
                    item["name"]
                    for item in inspect(sync_connection).get_columns("plants")
                }
            )
        assert {"seed_image_name", "microgreen_image_name"} <= columns
        await engine.dispose()

    asyncio.run(scenario())


def test_cloud_assignments_are_applied_without_personal_data(monkeypatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'assignments.db'}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(cloud_sync_service, "SessionLocal", session_factory)

    async def scenario():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with session_factory() as session:
            plant = Plant(
                id="plant-radish",
                code="radish",
                names={"en": "Radish"},
                descriptions={},
                grow_days=12,
            )
            session.add(plant)
            session.add_all(
                [RackSlot(rack_id=1, slot_number=number) for number in range(1, 7)]
            )
            await session.commit()

        service = CloudSyncService()
        await service._apply_assignments(
            {
                "assignments": [
                    {
                        "allocation_id": "allocation-1",
                        "resource_type": "slot",
                        "rack_id": 1,
                        "slot_number": 2,
                        "plant_id": "plant-radish",
                    }
                ]
            }
        )
        async with session_factory() as session:
            slots = (
                await session.execute(select(RackSlot).order_by(RackSlot.slot_number))
            ).scalars().all()
            assert slots[1].status == "reserved"
            assert slots[1].cloud_allocation_id == "allocation-1"
            assert slots[1].requested_plant_id == "plant-radish"
            assert not hasattr(slots[1], "user_email")
        await engine.dispose()

    asyncio.run(scenario())
