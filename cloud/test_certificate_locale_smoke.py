"""Regression tests for region-aware QR/Telegram certificate links.

Run: python -m cloud.test_certificate_locale_smoke
Uses a temporary in-memory database, never production rows or Telegram.
"""
import asyncio
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from cloud.app.models import Base, Farm, Device, Plant, User
from cloud.app.battle_models import PlantBattle, PlantBattleEntry
from cloud.app.battle_api import battle_entry_qr, _certificate_context
from cloud.app.battle_certificate_urls import certificate_url, certificate_base_url


def uid(): return str(uuid4())


async def run():
    eid=uid()
    assert certificate_url(eid,"ru")==f"https://ru.kisamore.farm/api/v1/battle-certificate/{eid}"
    assert certificate_url(eid,"ru-RU").startswith("https://ru.")
    assert certificate_url(eid,"EN","ru").startswith("https://ru.")
    assert certificate_url(eid,"en","en").startswith("https://kisamore.farm/")
    assert certificate_url(eid,"zh").startswith("https://kisamore.farm/")
    assert certificate_base_url("RU_ru")=="https://ru.kisamore.farm"
    engine=create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory=async_sessionmaker(engine,expire_on_commit=False)
    now=datetime.now(timezone.utc)
    async with factory() as session:
        farm=Farm(slug="langtest",name="Language test")
        session.add(farm); await session.flush()
        device=Device(id="locale-test-device",farm_id=farm.id,name="Test",token_hash="fake")
        plant=Plant(id=uid(),code="test-plant",names={"ru":"Растение","en":"Plant"})
        user=User(id=uid(),email="locale@test.invalid",display_name="Тест",
                  password_hash="fake",preferred_language="ru",created_at=now)
        session.add_all([device,plant,user]);await session.flush()
        battle=PlantBattle(id=uid(),device_id=device.id,rack_id=1,plant_id=plant.id,
                           title="Test",status="finished",created_by_user_id=user.id,
                           created_at=now,updated_at=now,finished_at=now)
        entry=PlantBattleEntry(id=eid,battle_id=battle.id,user_id=user.id,
                               slot_number=1,status="finished",price_kisa=1,
                               created_at=now)
        session.add_all([battle,entry]);await session.commit()
        from cloud.app import battle_api
        original_make=battle_api.qrcode.make
        encoded=[]
        def make(data):
            encoded.append(data)
            return original_make(data)
        with patch.object(battle_api.qrcode,"make",make):
            qr=await battle_entry_qr(eid, session)
        assert qr.media_type=="image/png"
        assert encoded==[f"https://ru.kisamore.farm/api/v1/battle-certificate/{eid}"]
        user.preferred_language="en";await session.commit()
        encoded.clear()
        with patch.object(battle_api.qrcode,"make",make):
            await battle_entry_qr(eid,session)
        assert encoded==[f"https://kisamore.farm/api/v1/battle-certificate/{eid}"]
        entry.status="refunded";await session.commit()
        for endpoint in (_certificate_context,battle_entry_qr):
            try:
                await endpoint(session,eid) if endpoint==_certificate_context else await endpoint(eid,session)
                raise AssertionError("Refunded entry unexpectedly has a public diploma")
            except HTTPException as err:
                assert err.status_code==404,err.status_code
    await engine.dispose()
    print("PASS: Russian mirror for RU account/Telegram, main host for others, valid QR PNG, refunded entries blocked")


if __name__=="__main__":
    asyncio.run(run())
