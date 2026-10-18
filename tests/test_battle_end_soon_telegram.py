"""Regression: existing final-day inbox events reach linked Telegram users once."""
import asyncio
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from cloud.app import db  # noqa: F401 -- register all models
from cloud.app.battle_models import PlantBattle, PlantBattleEntry
from cloud.app.battle_event_models import BattleEventNotification
from cloud.app.models import Base, Device, Farm, Plant, User
from cloud.app.telegram.models import TelegramUser
from cloud.app.telegram.activity_notifier import TelegramActivityDelivery
from cloud.app.telegram.battle_notifications import discover_end_soon_telegram


def uid():
    return str(uuid4())


async def main():
    now = datetime(2026, 10, 18, 9, 30, tzinfo=timezone.utc)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        farm = Farm(slug="battle-tg-final-day", name="Battle final day test")
        session.add(farm)
        await session.flush()
        session.add(Device(id="tg-final-day-device", farm_id=farm.id, name="test", token_hash="test"))
        plant = Plant(id=uid(), code="test-plant", names={"ru": "Растение"})
        session.add(plant)
        users = [
            User(id=uid(), email=f"final-day-{i}@example.invalid",
                 display_name=f"Tester {i}", password_hash="test", created_at=now)
            for i in range(4)
        ]
        admin = User(id=uid(), email="final-day-admin@example.invalid",
                     display_name="Admin", password_hash="test", role="admin", created_at=now)
        session.add_all([admin, *users])
        await session.flush()
        battle = PlantBattle(
            id=uid(), device_id="tg-final-day-device", rack_id=1, plant_id=plant.id,
            title="Battle <Radish & Friends>", status="growing", created_by_user_id=admin.id,
            created_at=now, updated_at=now,
            start_date=date(2026, 10, 12), end_date=date(2026, 10, 18),
        )
        session.add(battle)
        tg_account = TelegramUser(telegram_user_id=10001001, is_active=True,
                                  marketplace_user_id=users[0].id, language_code="ru")
        tg_direct = TelegramUser(telegram_user_id=10001002, is_active=True, language_code="en")
        tg_inactive = TelegramUser(telegram_user_id=10001003, is_active=False,
                                   marketplace_user_id=users[2].id, language_code="ru")
        session.add_all([tg_account, tg_direct, tg_inactive])
        await session.flush()
        for i, user in enumerate(users):
            entry = PlantBattleEntry(
                id=uid(), battle_id=battle.id, slot_number=i + 1,
                user_id=user.id, price_kisa=20, status="active", created_at=now,
                telegram_user_id=tg_direct.id if i == 1 else None,
            )
            session.add(entry)
            session.add(BattleEventNotification(
                id=uid(), event_key=f"battle:{battle.id}:end_soon::{user.id}",
                user_id=user.id, battle_id=battle.id, entry_id=entry.id,
                body="Last day!", created_at=now - timedelta(minutes=15),
            ))
        await session.commit()
        assert await discover_end_soon_telegram(session, now) == 2
        delivered = list((await session.execute(
            select(TelegramActivityDelivery).where(TelegramActivityDelivery.kind == "battle_end_soon")
        )).scalars().all())
        assert len(delivered) == 2
        assert {d.telegram_user_id for d in delivered} == {10001001, 10001002}
        assert all(d.status == "pending" and d.payload["url"].endswith("/battle") for d in delivered)
        ru = next(d for d in delivered if d.telegram_user_id == 10001001)
        assert "Сегодня последний день" in ru.payload["text"]
        assert "&lt;Radish &amp; Friends&gt;" in ru.payload["text"], ru.payload
        assert ru.payload["url"] == "https://ru.kisamore.farm/battle"
        assert await discover_end_soon_telegram(session, now) == 0, "Duplicate Telegram notices"
        assert await discover_end_soon_telegram(session, now + timedelta(days=1)) == 0
        assert len((await session.execute(select(TelegramActivityDelivery))).scalars().all()) == 2
        assert len((await session.execute(select(BattleEventNotification))).scalars().all()) == 4, "Web inbox duplicated"
    await engine.dispose()
    print("PASS: end-soon reaches linked Telegram once; inactive/unlinked skipped; website inbox unchanged")


if __name__ == "__main__":
    asyncio.run(main())
