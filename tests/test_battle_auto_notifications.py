"""Isolated, production-free tests for Battle event audiences, deduplication and FCM."""
import asyncio
from datetime import date,datetime,timedelta,timezone
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker

from cloud.app import db,battle_push_worker
from cloud.app.models import Base,Farm,Device,Plant,User
from cloud.app.battle_models import PlantBattle,PlantBattleEntry,PlantBattleAction
from cloud.app.battle_push_models import BattlePushDevice
from cloud.app.battle_event_models import (
    BattleEventNotification,BattleEventPushDelivery,BattleNotificationPreferences
)
from cloud.app.battle_events import (
    enqueue_battle_event,notify_battle_members,notify_new_battle,
    notify_resource_low,notify_action_done,notify_end_soon,
)
from cloud.app.battle_messages_api import (
    NotificationSettingsPatch,get_battle_notification_preferences,
    update_battle_notification_preferences,battle_inbox,read_battle_message
)

def uid():
    return str(uuid4())

async def main():
    now=datetime.now(timezone.utc)
    engine=create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions=async_sessionmaker(engine,expire_on_commit=False)
    async with sessions() as s:
        farm=Farm(slug="battle-events-unit",name="Unit");s.add(farm);await s.flush()
        s.add(Device(id="device-events",farm_id=farm.id,name="unit",token_hash="hash"))
        plant=Plant(id=uid(),code="radish-events",names={"ru":"Редис"})
        admin=User(id=uid(),email="admin-events@example.invalid",display_name="Admin",
            role="admin",password_hash="hash",created_at=now)
        users=[User(id=uid(),email=f"events-{i}@example.invalid",display_name=f"Player {i}",
            password_hash="hash",created_at=now) for i in range(3)]
        s.add_all([plant,admin,*users]);await s.flush()
        battle=PlantBattle(id=uid(),device_id="device-events",rack_id=1,plant_id=plant.id,
            title="Редис",status="growing",created_by_user_id=admin.id,
            created_at=now,updated_at=now,end_date=(now+timedelta(hours=12)).date(),
            water_budget_ml=1000,nutrient_budget_ml=100,shade_budget_minutes=100)
        new_battle=PlantBattle(id=uid(),device_id="device-events",rack_id=2,plant_id=plant.id,
            title="Новая битва",status="open",created_by_user_id=admin.id,
            created_at=now,updated_at=now)
        s.add_all([battle,new_battle]);await s.flush()
        entries=[PlantBattleEntry(id=uid(),battle_id=battle.id,slot_number=i+1,
                 user_id=users[i].id,price_kisa=20,status="active",created_at=now)
                 for i in range(2)]
        s.add_all(entries)
        token="test-FCM-token-"+"x"*150
        s.add(BattlePushDevice(token_hash="t"*64,user_id=users[0].id,
                    token=token,active=True,created_at=now,updated_at=now))
        await s.commit()
        assert (await get_battle_notification_preferences(user=users[0],session=s))["new_battles"] is False
        assert await notify_new_battle(s,new_battle)==0,"No unsolicited marketing"
        await update_battle_notification_preferences(
            NotificationSettingsPatch(new_battles=True),user=users[0],session=s)
        assert await notify_new_battle(s,new_battle)==1
        assert await notify_new_battle(s,new_battle)==0,"New Battle notice duplicated"
        assert await notify_battle_members(s,battle=battle,kind="start",
                   ru="Началась",en="Started")==2
        assert await notify_battle_members(s,battle=battle,kind="start",
                   ru="Началась",en="Started")==0
        await update_battle_notification_preferences(
            NotificationSettingsPatch(resource_low=False),user=users[1],session=s)
        # Only the owning user gets their scarce resource warning.
        entries[0].water_used_ml=810
        assert await notify_resource_low(s,battle=battle,entry=entries[0],
            kind="water",remaining=190,budget=1000)
        assert not await notify_resource_low(s,battle=battle,entry=entries[0],
            kind="water",remaining=100,budget=1000),"Repeated low water"
        entries[1].water_used_ml=900
        assert not await notify_resource_low(s,battle=battle,entry=entries[1],
            kind="water",remaining=100,budget=1000),"Opt out ignored"
        assert not await notify_resource_low(s,battle=battle,entry=entries[0],
            kind="nutrient",remaining=80,budget=100),"Warning before threshold"
        action=PlantBattleAction(id=uid(),entry_id=entries[0].id,
            kind="water",amount=100,status="completed",requested_at=now,completed_at=now)
        s.add(action)
        assert await notify_action_done(s,battle=battle,entry=entries[0],action=action)
        assert not await notify_action_done(s,battle=battle,entry=entries[0],action=action)
        # End-date is a date with end-of-day farm timezone; this test sets the
        # poll instant to 30 minutes before the end.
        from cloud.app.battle_events import planned_end_utc
        end=planned_end_utc(battle)
        assert end is not None
        assert await notify_end_soon(s,now=end-timedelta(minutes=30))==2
        assert await notify_end_soon(s,now=end-timedelta(minutes=25))==0
        assert await notify_end_soon(s,now=end+timedelta(minutes=1))==0
        assert await notify_battle_members(s,battle=battle,kind="finished",
                   ru="Завершена",en="Finished")==2
        assert await notify_battle_members(s,battle=battle,kind="winner",
                   ru="Победитель",en="Winner")==2
        await s.commit()
        notices=list((await s.execute(select(BattleEventNotification))).scalars().all())
        assert len(notices)==11,len(notices) # 1 new + 2 start + 1 resource + 1 action + 2 endsoon + 2 finished + 2 winner
        assert len({n.event_key for n in notices})==len(notices)
        assert not any(n.user_id==users[2].id and n.battle_id==battle.id for n in notices)
        inbox=await battle_inbox(user=users[0],session=s)
        assert inbox["unread_count"]==7,inbox
        assert all(n["battle_id"] in (battle.id,new_battle.id) for n in inbox["messages"])
        mine=inbox["messages"][0]["id"]
        await read_battle_message(mine,user=users[0],session=s)
        assert (await battle_inbox(user=users[0],session=s))["unread_count"]==6
        assert (await battle_inbox(user=users[2],session=s))["unread_count"]==0
        deliveries=list((await s.execute(select(BattleEventPushDelivery))).scalars().all())
        assert len(deliveries)==7,"Only owner with registered phone gets pushes"
        with patch.object(battle_push_worker,"SessionLocal",sessions),\
             patch.object(battle_push_worker,"firebase_ready",return_value=True),\
             patch.object(battle_push_worker,"send_one",return_value=None) as send:
            result=await battle_push_worker.deliver_pending(now=end+timedelta(hours=1))
            assert result["sent"]==7,result
            assert send.call_count==7
            assert (await battle_push_worker.deliver_pending(now=end+timedelta(hours=1)))["attempted"]==0
    await engine.dispose()
    print("PASS: all 7 events, targets, no duplicates, opt-in, opt-out, date window, inbox, read access, FCM queue")

if __name__=="__main__":
    asyncio.run(main())
