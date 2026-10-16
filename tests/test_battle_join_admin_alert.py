"""Regression: every paid Plant Battle join queues one durable Telegram admin alert.

Run in an isolated in-memory SQLite DB: python tests/test_battle_join_admin_alert.py
"""
import asyncio
from datetime import datetime, timezone
from html import escape
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from cloud.app import db  # Register all mapped tables, including outbox.
from cloud.app.battle_api import JoinBattleIn, join_battle
from cloud.app.battle_models import PlantBattle
from cloud.app.models import Base, Device, Farm, Plant, User
from cloud.app.site_wallet import SiteWallet
from cloud.app.telegram.activity_notifier import TelegramActivityDelivery
from cloud.app.telegram.admin_models import TelegramAdmin
from cloud.app.telegram.models import TelegramUser


def uid():
    return str(uuid4())


async def main():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    battle_id, admin_id, buyer1_id, buyer2_id, poor_id = (uid() for _ in range(5))
    buyer1_name = "<Tester & Co>"
    buyer1_email = "first+test@example.invalid"
    async with factory() as s:
        farm = Farm(slug="battle-join-admin-test", name="Battle alert test")
        s.add(farm)
        await s.flush()
        s.add(Device(id="join-alert-device", farm_id=farm.id,
                     name="test", token_hash="test"))
        plant = Plant(id=uid(), code="radish-alert", names={"ru": "Редис"})
        s.add(plant)
        admin = User(id=admin_id, email="site-admin@example.invalid",
                     display_name="Site admin", password_hash="x", role="admin",
                     created_at=now)
        buyer1 = User(id=buyer1_id, email=buyer1_email,
                      display_name=buyer1_name, password_hash="x", created_at=now)
        buyer2 = User(id=buyer2_id, email="second@example.invalid",
                      display_name="Second tester", password_hash="x", created_at=now)
        poor = User(id=poor_id, email="poor@example.invalid",
                    display_name="Cannot afford", password_hash="x", created_at=now)
        s.add_all([admin, buyer1, buyer2, poor])
        tg_admin = TelegramUser(telegram_user_id=9876543210, username="admin_test", is_active=True)
        s.add(tg_admin)
        await s.flush()
        s.add(TelegramAdmin(user_id=tg_admin.id, enabled=True))
        s.add_all([SiteWallet(user_id=buyer1_id,balance=50),
                   SiteWallet(user_id=buyer2_id,balance=50),
                   SiteWallet(user_id=poor_id,balance=0)])
        s.add(PlantBattle(id=battle_id, device_id="join-alert-device",
                          rack_id=1, plant_id=plant.id, title="<Battle & Test>",
                          status="open", max_entries=2, entry_price_kisa=10,
                          created_by_user_id=admin_id, created_at=now, updated_at=now))
        await s.commit()

        async def outbox():
            return (await s.execute(
                select(TelegramActivityDelivery).order_by(TelegramActivityDelivery.event_key)
            )).scalars().all()

        try:
            await join_battle(battle_id, JoinBattleIn(quantity=1), user=poor, session=s)
        except HTTPException as exc:
            assert exc.status_code == 409
            await s.commit()
        else:
            raise AssertionError("Unfunded entry accepted")
        assert await outbox() == [], "Failed joins must not notify administrators"

        receipt1 = await join_battle(battle_id, JoinBattleIn(quantity=1), user=buyer1, session=s)
        assert receipt1["slots"] == [1] and receipt1["status"] == "open", receipt1
        rows = await outbox()
        assert len(rows) == 1, rows
        assert rows[0].event_key == f"battle_join:{receipt1['entry_ids'][0]}:{tg_admin.id}"
        assert rows[0].telegram_user_id == tg_admin.telegram_user_id
        assert rows[0].status == "pending"
        text = rows[0].payload["text"]
        assert escape(buyer1_name) in text and escape(buyer1_email) in text
        assert "&lt;Battle &amp; Test&gt;" in text
        assert "1/2" in text and "Свободных мест: 1" in text
        assert "контейнер №1" in text

        try:
            await join_battle(battle_id, JoinBattleIn(quantity=1), user=buyer1, session=s)
        except HTTPException as exc:
            assert exc.status_code == 409
            await s.commit()
        else:
            raise AssertionError("Duplicate entry accepted")
        assert len(await outbox()) == 1, "Failed duplicate must not create alert"

        receipt2 = await join_battle(battle_id, JoinBattleIn(quantity=1), user=buyer2, session=s)
        assert receipt2["slots"] == [2] and receipt2["status"] == "ready_to_plant"
        rows = await outbox()
        per_join = [r for r in rows if r.event_key.startswith("battle_join:")]
        ready = [r for r in rows if r.event_key.startswith("battle_ready:")]
        assert len(per_join) == 2 and len(ready) == 1, [(r.event_key,r.status) for r in rows]
        second = next(r for r in per_join if receipt2["entry_ids"][0] in r.event_key)
        assert "2/2" in second.payload["text"] and "Свободных мест: 0" in second.payload["text"]
        assert (await s.get(SiteWallet, buyer1_id)).balance == 40
        assert (await s.get(SiteWallet, buyer2_id)).balance == 40

    await engine.dispose()
    print("PASS: each join queues exactly one admin alert; failed join none; filled battle retains ready alert")


if __name__ == "__main__":
    asyncio.run(main())
