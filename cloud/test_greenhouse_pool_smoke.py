"""Integration smoke test for the pooled marketplace on disposable SQLite."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select

from cloud.app.db import SessionLocal, create_tables
from cloud.app.models import Farm, Device, RackSlot
from cloud.app.greenhouse_pool_api import public_pool, set_greenhouse_status, GreenhouseStatusUpdate
from cloud.app.marketplace_api import purchase, create_reservation
from cloud.app.schemas import PurchaseIn, ReservationIn


async def main():
    await create_tables()
    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        for number in (1, 2):
            farm = Farm(slug=f"pool-test-{number}", name=f"Test Farm {number}", is_public=True)
            session.add(farm)
            await session.flush()
            device = Device(
                id=f"pool-device-{number}", farm_id=farm.id, name=f"Pi {number}",
                token_hash="0" * 64, is_active=True,
                marketplace_status="active", racks_count=2, last_seen_at=now,
            )
            session.add(device)
            for rack_id in (1, 2):
                for slot_no in range(1, 7):
                    session.add(RackSlot(
                        device_id=device.id, rack_id=rack_id, slot_number=slot_no,
                        physical_status="available", enabled=True, observed_at=now,
                    ))
        await session.commit()

        market = await public_pool(session=session)
        assert market["greenhouses_count"] == 2, market
        assert len(market["racks"]) == 4
        assert len([s for r in market["racks"] for s in r["slots"]]) == 24
        assert [r["display_number"] for r in market["racks"]] == [1,2,3,4]
        assert len({(r["device_id"],r["rack_id"]) for r in market["racks"]}) == 4
        print("POOL_2_GREENHOUSES_OK",len(market["racks"]),"racks")

        _ = await set_greenhouse_status(
            "pool-device-1",
            GreenhouseStatusUpdate(status="transport",note="Moving greenhouse"),
            None,session
        )
        item = await session.get(Device, "pool-device-1")
        assert item.is_active is True
        assert item.marketplace_status == "transport"
        market = await public_pool(session=session)
        assert len(market["racks"]) == 2
        assert [r["display_number"] for r in market["racks"]] == [3,4]
        assert all(r["device_id"] == "pool-device-2" for r in market["racks"])
        print("PAUSED_POOL_EXCLUDES_SHELVES_BUT_TELEMETRY_ACTIVE")

        for operation, payload in [
            (purchase, PurchaseIn(device_id="pool-device-1", resource_type="slot", rack_id=1, slot_number=1)),
            (create_reservation, ReservationIn(device_id="pool-device-1", resource_type="slot", rack_id=1, slot_number=1)),
        ]:
            try:
                await operation(payload=payload, user=None, session=session)
            except HTTPException as error:
                assert error.status_code == 409, error
            else:
                raise AssertionError("Maintenance greenhouse accepted an order")
        print("PURCHASE_AND_RESERVATION_BLOCKED_OK")

        await set_greenhouse_status(
            "pool-device-1",
            GreenhouseStatusUpdate(status="active", note=""),
            None,session
        )
        market = await public_pool(session=session)
        assert len(market["racks"]) == 4
        assert [r["display_number"] for r in market["racks"]] == [1,2,3,4]
        print("REACTIVATION_OK")

asyncio.run(main())
