"""Isolated battle inbox, recipient access and Telegram outbox integration."""
import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from cloud.app.models import Base, Farm, Device, Plant, User
from cloud.app.battle_models import PlantBattle, PlantBattleEntry
from cloud.app.battle_message_models import BattleAdminMessage, BattleMessageReceipt
from cloud.app.battle_messages_api import (
    ComposeBattleMessage, compose_battle_message, battle_inbox,
    read_battle_message, admin_battle_message_history
)
from cloud.app.telegram.models import TelegramUser
from cloud.app.telegram.activity_notifier import TelegramActivityDelivery
from cloud.app import db  # registers legacy FK tables

now=datetime.now(timezone.utc)
def uid():return str(uuid4())

async def main():
    engine=create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:await conn.run_sync(Base.metadata.create_all)
    factory=async_sessionmaker(engine,expire_on_commit=False)
    battle_id=uid()
    ids=[uid() for _ in range(3)]
    entry_ids=[uid() for _ in range(3)]
    admin_id=uid()
    async with factory() as s:
        farm=Farm(slug="messages-test",name="Tests");s.add(farm);await s.flush()
        admin=User(id=admin_id,email="test-admin@example.invalid",
            display_name="Admin",password_hash="hash",created_at=now)
        participants=[
           User(id=id,email=f"test-{i}@example.invalid",display_name=f"Player {i}",
                password_hash="hash",created_at=now)
           for i,id in enumerate(ids)
        ]
        plant=Plant(id=uid(),code="test-plant",names={"ru":"Редис"})
        device=Device(id="test-device",farm_id=farm.id,name="test",token_hash="hash")
        s.add_all([admin,*participants,plant,device])
        await s.flush()
        battle=PlantBattle(id=battle_id,device_id="test-device",rack_id=1,
            plant_id=plant.id,title="Battle <img>",status="growing",
            created_by_user_id=admin_id,created_at=now,updated_at=now)
        tg=TelegramUser(telegram_user_id=138547,first_name="Telegram",
                        marketplace_user_id=ids[0],is_active=True,created_at=now,updated_at=now,
                        language_code="ru")
        s.add_all([battle,tg]);await s.flush()
        for i in range(3):
            s.add(PlantBattleEntry(id=entry_ids[i],battle_id=battle_id,
                slot_number=i+1,user_id=ids[i],telegram_user_id=tg.id if i==0 else None,
                price_kisa=10,status="active",created_at=now))
        await s.commit()
        result=await compose_battle_message(battle_id,ComposeBattleMessage(
            body='Уход! <script>alert("x")</script>'),admin=admin,session=s)
        assert result["recipients"]==3
        assert result["telegram_queued"]==1
        msgs=(await s.execute(select(BattleAdminMessage))).scalars().all()
        receipts=(await s.execute(select(BattleMessageReceipt))).scalars().all()
        outbox=(await s.execute(select(TelegramActivityDelivery))).scalars().all()
        assert len(msgs)==1 and len(receipts)==3 and len(outbox)==1
        assert "<script>" not in outbox[0].payload["text"]
        assert "&lt;script&gt;" in outbox[0].payload["text"]
        assert outbox[0].payload["callback_data"]=="battle:open:"+entry_ids[0]
        assert outbox[0].telegram_user_id==138547
        for i in range(3):
            mine=await battle_inbox(user=participants[i],session=s)
            assert mine["unread_count"]==1
            assert len(mine["messages"])==1
            assert mine["messages"][0]["body"]=='Уход! <script>alert("x")</script>'
            assert mine["messages"][0]["entry_id"]==entry_ids[i]
        await read_battle_message(receipts[0].id,user=participants[0],session=s)
        assert (await battle_inbox(user=participants[0],session=s))["unread_count"]==0
        try: await read_battle_message(receipts[0].id,user=participants[1],session=s)
        except HTTPException as e:assert e.status_code==404
        else:raise AssertionError("Cross-account read allowed")
        hist=await admin_battle_message_history(battle_id,_=admin,session=s)
        assert len(hist)==1 and len(hist[0]["recipients"])==3
        assert sum(bool(x["read_at"]) for x in hist[0]["recipients"])==1

        subset=await compose_battle_message(battle_id,ComposeBattleMessage(
            body="Only #2",recipient_entry_ids=[entry_ids[1]]),admin=admin,session=s)
        assert subset["recipients"]==1 and subset["telegram_queued"]==0
        assert (await battle_inbox(user=participants[0],session=s))["unread_count"]==0
        assert (await battle_inbox(user=participants[1],session=s))["unread_count"]==2
        try:
            await compose_battle_message(battle_id,ComposeBattleMessage(
                body="Wrong",recipient_entry_ids=[uid()]),admin=admin,session=s)
        except HTTPException as e:assert e.status_code==422
        else:raise AssertionError("Foreign entry accepted")
    await engine.dispose()
    print("PASS: multi-channel persistent inbox, Telegram queue, safe HTML, selected audience, unread receipts and access control.")

if __name__=="__main__":asyncio.run(main())
