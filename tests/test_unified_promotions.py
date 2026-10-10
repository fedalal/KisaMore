"""Integration tests of unified Kisa promotions, isolated SQLite only."""
import asyncio
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

os.environ["KISAMORE_DATABASE_URL"] = f"sqlite+aiosqlite:///promo-integrated-{uuid4().hex}.db"
os.environ["KISAMORE_BOOTSTRAP_FARM_SLUG"] = "promo-test"
os.environ["KISAMORE_BOOTSTRAP_DEVICE_ID"] = "promotion-test-device"
os.environ["KISAMORE_BOOTSTRAP_DEVICE_TOKEN"] = "promotion-test-device-token-longer-than-32"
os.environ["KISAMORE_COOKIE_SECURE"] = "false"
os.environ["KISAMORE_MQTT_ENABLED"] = "false"

from fastapi.testclient import TestClient
from sqlalchemy import select

from cloud.app.main import app
from cloud.app.db import SessionLocal
from cloud.app.models import User
from cloud.app.security import hash_password
from cloud.app.site_wallet import SiteWallet, SiteWalletTransaction
from cloud.app.telegram.models import TelegramUser, WalletAccount, WalletTransaction
from cloud.app.telegram.promotion_models import (
    TelegramPromotion, TelegramPromotionGrant, SitePromotionGrant
)
from cloud.app.site_promotion_service import (
    discover_and_grant_website, grant_for_website_user
)
from cloud.app.telegram.promotion_service import _grant_one
from cloud.app.telegram_link import create_telegram_link_token, consume_telegram_link_token
from cloud.app.promotion_admin_api import _payload


def run(coro):
    return asyncio.run(coro)


async def seed():
    async with SessionLocal() as session:
        now = datetime.now(timezone.utc)
        campaign = TelegramPromotion(
            name="Welcome new users", audience="new",
            start_at=now - timedelta(days=1), end_at=now + timedelta(days=1),
            created_at=now - timedelta(days=2),
            updated_at=now, amount_kisa=20, message="Enjoy 20 Kisa",
            enabled=True
        )
        session.add(campaign)
        await session.commit()
        return campaign.id


async def site_state(uid):
    async with SessionLocal() as session:
        wallet = await session.get(SiteWallet, uid)
        rows=(await session.execute(select(SiteWalletTransaction).where(
            SiteWalletTransaction.user_id == uid
        ))).scalars().all()
        grants=(await session.execute(select(SitePromotionGrant).where(
            SitePromotionGrant.user_id == uid
        ))).scalars().all()
        return wallet.balance if wallet else 0, rows, grants


async def site_award_retry(uid):
    async with SessionLocal() as session:
        user=(await session.execute(select(User).where(User.id==uid).with_for_update())).scalar_one()
        amount=await grant_for_website_user(session,user)
        await session.commit()
        return amount


async def telegram_create(code, created_delta=0):
    async with SessionLocal() as session:
        tg=TelegramUser(
            telegram_user_id=code, first_name="Promo", username=f"promo_{code}",
            is_active=True, language_code="ru",
            created_at=datetime.now(timezone.utc)+timedelta(minutes=created_delta)
        )
        session.add(tg)
        await session.flush()
        await session.commit()
        return tg.id


async def technical_telegram_create():
    # The older bot created an inactive placeholder website identity for some
    # users. They must still be eligible for Telegram-only promotions.
    async with SessionLocal() as session:
        internal=User(
            id=str(uuid4()), email=f"promo-{uuid4().hex}@internal.kisamore.local",
            display_name="Legacy placeholder", role="customer",
            password_hash="unusable", preferred_language="en",
            is_active=False, created_at=datetime.now(timezone.utc),
        )
        session.add(internal)
        await session.flush()
        tg=TelegramUser(
            telegram_user_id=98877003, marketplace_user_id=internal.id,
            first_name="Legacy Telegram", is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        session.add(tg)
        await session.flush()
        await session.commit()
        return tg.id


async def telegram_state(tg_id):
    async with SessionLocal() as session:
        w=(await session.execute(select(WalletAccount).where(
            WalletAccount.user_id==tg_id
        ))).scalar_one_or_none()
        grants=(await session.execute(select(TelegramPromotionGrant).where(
            TelegramPromotionGrant.user_id==tg_id
        ))).scalars().all()
        tx=(await session.execute(select(WalletTransaction).where(
            WalletTransaction.user_id==tg_id
        ))).scalars().all()
        return w.balance if w else 0,grants,tx


async def link(user_id,code):
    async with SessionLocal() as session:
        token,_=await create_telegram_link_token(session,user_id=user_id)
        await session.commit()
    async with SessionLocal() as session:
        result=await consume_telegram_link_token(
            session,raw_token=token,telegram_user_id=code
        )
        assert result.id==user_id
        await session.commit()


async def admin_payload(promo_id):
    async with SessionLocal() as session:
        promo=await session.get(TelegramPromotion,promo_id)
        return await _payload(session,promo)


async def late_user():
    """Simulates pre-upgrade web registration missed by the old worker."""
    async with SessionLocal() as session:
        user=User(
            id=str(uuid4()), email="preupgrade@example.test",
            display_name="Existing Web User", role="customer",
            password_hash=hash_password("pass-123456"),
            preferred_language="en", is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        session.add(user)
        await session.commit()
        return user.id


def main():
    with TestClient(app) as client:
        promo_id=run(seed())

        # Website registration credits at once; Android uses the same endpoint.
        for i in range(2):
            r=client.post("/api/v1/auth/register",json={
                "email":f"account{i}@example.test",
                "display_name":f"User {i}",
                "password":"strong-password-123",
                "language":"en" if i else "ru",
            })
            assert r.status_code==201,r.text
            uid=r.json()["id"]
            balance=client.get("/api/v1/account/kisa-wallet")
            assert balance.status_code==200 and balance.json()["balance"]==20
            amount,tx,grants=run(site_state(uid))
            assert amount==20
            assert len(tx)==1 and tx[0].amount==20 and tx[0].kind=="promotion_bonus"
            assert len(grants)==1 and grants[0].promotion_id==promo_id
            assert run(site_award_retry(uid))==0
            assert run(discover_and_grant_website())==0
            if i==0: site_user=uid
            else: android_user=uid

        # Telegram-only promotional credits still work unchanged.
        tg_id=run(telegram_create(98877001))
        assert run(_grant_one(promo_id,tg_id)) is True
        assert run(_grant_one(promo_id,tg_id)) is False
        amount,grants,tx=run(telegram_state(tg_id))
        assert amount==20 and len(grants)==1

        # Account linking reconciles a previously independently claimed bonus.
        run(link(site_user,98877001))
        amount,grants,tx=run(telegram_state(tg_id))
        assert amount==20, f"Should preserve only one welcome 20 Kisa: {amount}"
        assert any(r.kind=="promotion_link_dedup" and r.amount==-20 for r in tx)
        assert run(_grant_one(promo_id,tg_id)) is False
        assert run(site_award_retry(site_user))==0
        assert run(discover_and_grant_website())==0
        assert run(site_state(site_user))[0]==0

        # Periodic recovery handles site users who signed up before this fix.
        older=run(late_user())
        assert run(site_state(older))[0]==0
        assert run(discover_and_grant_website())==1
        assert run(site_state(older))[0]==20
        assert run(discover_and_grant_website())==0

        # Telegram first, then website linking without duplicate award:
        # simulate a delayed website grant, while linked Telegram already earned.
        tg2=run(telegram_create(98877002))
        assert run(_grant_one(promo_id,tg2)) is True
        run(link(older,98877002))
        assert run(discover_and_grant_website())==0

        legacy_tg=run(technical_telegram_create())
        assert run(_grant_one(promo_id,legacy_tg)) is True
        assert run(_grant_one(promo_id,legacy_tg)) is False
        assert run(telegram_state(legacy_tg))[0] == 20

        summary=run(admin_payload(promo_id))
        # three site accounts + three Telegram accounts; 2 linked to real
        # users and one linked only to an inactive technical placeholder.
        assert summary["grant_count"]==4,summary
        assert summary["site_grant_count"]==3
        assert summary["telegram_grant_count"]==3
        assert summary["eligible_count"]==4
        assert summary["notified_count"]==0

        # Test two different original registrations are still credited once.
        assert run(site_state(android_user))[0]==20
        print("PASS: website+Android immediate bonus, Telegram-only grants,")
        print("      idempotency, post-link reconciliation, missed registration")
        print("      recovery, shared admin promotion totals and original history.")


if __name__=="__main__":
    main()
