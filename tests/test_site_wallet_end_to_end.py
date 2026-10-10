"""Standalone integration test for website Kisa wallet (isolated SQLite).
Run with: python tests/test_site_wallet_end_to_end.py
"""
import asyncio
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

tmp = Path(tempfile.mkdtemp(prefix="kisamore-website-wallet-test-"))
os.environ["KISAMORE_DATABASE_URL"] = f"sqlite+aiosqlite:///wallet-test-{uuid4().hex}.db"
os.environ["KISAMORE_BOOTSTRAP_FARM_SLUG"] = "wallet-test"
os.environ["KISAMORE_BOOTSTRAP_DEVICE_ID"] = "wallet-device-01"
os.environ["KISAMORE_BOOTSTRAP_DEVICE_TOKEN"] = "wallet-test-token-with-more-than-32-bytes"
os.environ["KISAMORE_COOKIE_SECURE"] = "false"
os.environ["KISAMORE_PHOTO_DIR"] = str(tmp / "photos")
os.environ["KISAMORE_MQTT_ENABLED"] = "false"

from fastapi.testclient import TestClient
from sqlalchemy import select

from cloud.app.main import app
from cloud.app.db import SessionLocal
from cloud.app.battle_models import PlantBattle, PlantBattleEntry
from cloud.app.models import Device, Plant, User
from cloud.app.security import hash_password
from cloud.app.site_wallet import SiteWallet, SiteWalletTransaction
from cloud.app.telegram.models import TelegramUser, WalletAccount, WalletTransaction
from cloud.app.telegram_link import create_telegram_link_token, consume_telegram_link_token


async def seed():
    async with SessionLocal() as db:
        device = (await db.execute(select(Device))).scalars().first()
        assert device is not None
        now = datetime.now(timezone.utc)
        admin_id = str(uuid4())
        db.add(User(
            id=admin_id, email="kisa-admin@example.org", display_name="Wallet Admin",
            role="admin", password_hash=hash_password("strong-test-pass"),
            is_active=True, created_at=now,
        ))
        plant_id = str(uuid4())
        db.add(Plant(id=plant_id, code="kisa-wallet-test", names={"en": "Radish"}))
        battle_id = str(uuid4())
        db.add(PlantBattle(
            id=battle_id, device_id=device.id, rack_id=1, plant_id=plant_id,
            title="Wallet test battle", status="open", entry_price_kisa=10,
            max_entries=6, water_budget_ml=500, nutrient_budget_ml=20,
            shade_budget_minutes=200, winner_reward_kisa=20,
            created_by_user_id=admin_id, created_at=now, updated_at=now,
        ))
        await db.commit()
        return battle_id


async def check_after_join(battle_id, website_id):
    async with SessionLocal() as db:
        entry = (await db.execute(select(PlantBattleEntry).where(
            PlantBattleEntry.battle_id == battle_id
        ))).scalar_one()
        assert entry.user_id == website_id and entry.telegram_user_id is None
        assert entry.price_kisa == 10 and entry.slot_number == 1
        wallet = await db.get(SiteWallet, website_id)
        assert wallet is not None and wallet.balance == 40
        transactions = (await db.execute(select(SiteWalletTransaction).where(
            SiteWalletTransaction.user_id == website_id
        ))).scalars().all()
        assert sorted(tx.amount for tx in transactions) == [-10, 50]
        return entry.id


async def prepare_telegram(website_id):
    async with SessionLocal() as db:
        tg = TelegramUser(telegram_user_id=9998776655, first_name="Web Customer",
                          username="webcustomer_2026", is_active=True, language_code="en")
        db.add(tg)
        await db.flush()
        db.add(WalletAccount(user_id=tg.id, balance=13))
        token, _ = await create_telegram_link_token(db, user_id=website_id)
        await db.commit()
        return tg.id, token


async def prepare_orphan_telegram():
    async with SessionLocal() as db:
        tg = TelegramUser(
            telegram_user_id=9998776644, first_name="Telegram only",
            username="telegramonly_2026", is_active=True, language_code="ru"
        )
        db.add(tg)
        await db.flush()
        db.add(WalletAccount(user_id=tg.id, balance=7))
        await db.commit()
        return tg.id


async def verify_orphan_telegram_wallet(tg_id):
    async with SessionLocal() as db:
        tg = await db.get(TelegramUser, tg_id)
        assert tg.marketplace_user_id is None
        wallet = (await db.execute(select(WalletAccount).where(
            WalletAccount.user_id == tg_id
        ))).scalar_one()
        assert wallet.balance == 20
        transaction = (await db.execute(select(WalletTransaction).where(
            WalletTransaction.user_id == tg_id,
            WalletTransaction.kind == "admin_gift",
        ))).scalar_one()
        assert transaction.amount == 13 and transaction.balance_after == 20


async def check_telegram_transfer(tg_id, website_id, entry_id):
    async with SessionLocal() as db:
        tgwallet = (await db.execute(select(WalletAccount).where(
            WalletAccount.user_id == tg_id
        ))).scalar_one()
        assert tgwallet.balance == 63
        website_wallet = await db.get(SiteWallet, website_id)
        assert website_wallet.balance == 0
        entry = await db.get(PlantBattleEntry, entry_id)
        assert entry.telegram_user_id == tg_id
        transfer = (await db.execute(select(WalletTransaction).where(
            WalletTransaction.user_id == tg_id,
            WalletTransaction.kind == "site_wallet_transfer",
        ))).scalar_one()
        assert transfer.amount == 50 and transfer.balance_after == 63


async def seed_second_battle():
    async with SessionLocal() as db:
        device = (await db.execute(select(Device))).scalars().first()
        plant = (await db.execute(select(Plant))).scalars().first()
        admin = (await db.execute(select(User).where(User.role == "admin"))).scalars().first()
        now = datetime.now(timezone.utc)
        battle_id = str(uuid4())
        db.add(PlantBattle(
            id=battle_id, device_id=device.id, rack_id=2, plant_id=plant.id,
            title="Linked-wallet battle", status="open", entry_price_kisa=10,
            max_entries=6, water_budget_ml=500, nutrient_budget_ml=20,
            shade_budget_minutes=200, winner_reward_kisa=20,
            created_by_user_id=admin.id, created_at=now, updated_at=now,
        ))
        await db.commit()
        return battle_id


async def check_linked_join(battle_id, telegram_id, user_id):
    async with SessionLocal() as db:
        entry = (await db.execute(select(PlantBattleEntry).where(
            PlantBattleEntry.battle_id == battle_id,
        ))).scalar_one()
        assert entry.user_id == user_id and entry.telegram_user_id == telegram_id
        wallet = (await db.execute(select(WalletAccount).where(
            WalletAccount.user_id == telegram_id,
        ))).scalar_one()
        assert wallet.balance == 53
        debit = (await db.execute(select(WalletTransaction).where(
            WalletTransaction.user_id == telegram_id,
            WalletTransaction.kind == "battle_entry",
            WalletTransaction.reference_id == battle_id,
        ))).scalar_one()
        assert debit.amount == -10 and debit.balance_after == 53


def main():
    with TestClient(app) as client:
        battle_id = asyncio.run(seed())
        public = client.post("/api/v1/auth/register", json={
            "email": "new-buyer@example.org", "display_name": "New buyer",
            "password": "buyer-strong-pass", "language": "ru",
        })
        assert public.status_code == 201, public.text
        website_id = public.json()["id"]
        balance = client.get("/api/v1/account/kisa-wallet")
        assert balance.status_code == 200 and balance.json()["balance"] == 0
        assert balance.json()["telegram_linked"] is False

        assert client.get("/api/v1/admin/users").status_code == 403
        forbidden = client.post(f"/api/v1/admin/users/site/{website_id}/gift-kisa", json={
            "amount": 500, "reason": "Unauthorized attempt"
        })
        assert forbidden.status_code == 403
        first = client.post(f"/api/v1/battles/{battle_id}/join", json={"quantity": 1})
        assert first.status_code == 409 and "Not enough Kisa" in first.text, first.text

        client.post("/api/v1/auth/login", json={
            "email": "kisa-admin@example.org", "password": "strong-test-pass",
        }).raise_for_status()
        website_rows = client.get("/api/v1/admin/users")
        assert website_rows.status_code == 200
        assert len(website_rows.json()) == 2
        assert {row["kind"] for row in website_rows.json()} == {"site"}
        assert any(row["email"] == "new-buyer@example.org" for row in website_rows.json())
        assert len(client.get("/api/v1/admin/users?q=new-buyer%40example.org").json()) == 1

        orphan_tg = asyncio.run(prepare_orphan_telegram())
        all_rows = client.get("/api/v1/admin/users")
        assert all_rows.status_code == 200
        assert len(all_rows.json()) == 3
        telegram_only = next(row for row in all_rows.json() if row["kind"] == "telegram")
        assert telegram_only["id"] == str(orphan_tg)
        assert telegram_only["email"] is None and telegram_only["balance"] == 7
        assert len(client.get("/api/v1/admin/users?q=%40telegramonly_2026").json()) == 1
        assert len(client.get("/api/v1/admin/users?q=9998776644").json()) == 1
        telegram_gift = client.post(f"/api/v1/admin/users/telegram/{orphan_tg}/gift-kisa", json={
            "amount": 13, "reason": "Test Telegram admin credit",
        })
        assert telegram_gift.status_code == 200 and telegram_gift.json()["balance"] == 20
        asyncio.run(verify_orphan_telegram_wallet(orphan_tg))
        assert client.post(f"/api/v1/admin/users/invalid/{orphan_tg}/gift-kisa",
                           json={"amount": 1, "reason": "No"}).status_code == 404

        gift = client.post(f"/api/v1/admin/users/site/{website_id}/gift-kisa", json={
            "amount": 50, "reason": "Test manual settled invoice",
        })
        assert gift.status_code == 200 and gift.json()["balance"] == 50, gift.text

        client.post("/api/v1/auth/login", json={
            "email": "new-buyer@example.org", "password": "buyer-strong-pass",
        }).raise_for_status()
        assert client.get("/api/v1/account/kisa-wallet").json()["balance"] == 50
        buy = client.post(f"/api/v1/battles/{battle_id}/join", json={"quantity": 1})
        assert buy.status_code == 201 and buy.json()["balance"] == 40, buy.text
        again = client.post(f"/api/v1/battles/{battle_id}/join", json={"quantity": 1})
        assert again.status_code == 409 and "already own" in again.text
        entry_id = asyncio.run(check_after_join(battle_id, website_id))

        client.post("/api/v1/auth/login", json={
            "email": "kisa-admin@example.org", "password": "strong-test-pass",
        }).raise_for_status()
        cancelled = client.post(f"/api/v1/admin/battles/{battle_id}/cancel")
        assert cancelled.status_code == 200, cancelled.text
        client.post("/api/v1/auth/login", json={
            "email": "new-buyer@example.org", "password": "buyer-strong-pass",
        }).raise_for_status()
        assert client.get("/api/v1/account/kisa-wallet").json()["balance"] == 50
        tg_id, token = asyncio.run(prepare_telegram(website_id))

        async def link():
            async with SessionLocal() as db:
                result = await consume_telegram_link_token(
                    db, raw_token=token, telegram_user_id=9998776655
                )
                assert result.id == website_id
                await db.commit()

        asyncio.run(link())
        # A formerly Telegram-only profile is not duplicated after linking.
        client.post("/api/v1/auth/login", json={
            "email": "kisa-admin@example.org", "password": "strong-test-pass",
        }).raise_for_status()
        linked_rows = client.get("/api/v1/admin/users").json()
        assert len(linked_rows) == 3
        linked = next(row for row in linked_rows if row["id"] == website_id)
        assert linked["kind"] == "site" and linked["telegram_linked"] is True
        assert linked["telegram_id"] == 9998776655 and linked["balance"] == 63
        assert len(client.get("/api/v1/admin/users?q=%40webcustomer_2026").json()) == 1
        assert client.post(f"/api/v1/admin/users/telegram/{tg_id}/gift-kisa", json={
            "amount": 5, "reason": "Must use linked website account"
        }).status_code == 409
        client.post("/api/v1/auth/login", json={
            "email": "new-buyer@example.org", "password": "buyer-strong-pass",
        }).raise_for_status()
        balance = client.get("/api/v1/account/kisa-wallet")
        assert balance.status_code == 200
        assert balance.json()["balance"] == 63 and balance.json()["telegram_linked"] is True
        asyncio.run(check_telegram_transfer(tg_id, website_id, entry_id))

        # Once linked, the same website user can spend from the legacy Telegram
        # balance without losing either wallet's transaction history.
        second_battle = asyncio.run(seed_second_battle())
        paid = client.post(f"/api/v1/battles/{second_battle}/join", json={"quantity": 1})
        assert paid.status_code == 201 and paid.json()["balance"] == 53, paid.text
        assert client.get("/api/v1/account/kisa-wallet").json()["balance"] == 53
        asyncio.run(check_linked_join(second_battle, tg_id, website_id))
        print("PASS: unified site+Telegram listing, search, credit by type, access permissions, paid join, refund, deduplication and linking")


if __name__ == "__main__":
    main()
