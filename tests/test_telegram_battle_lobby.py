"""End-to-end isolated Telegram Battle checkout and account-link preservation."""
import asyncio
from datetime import datetime,timezone
from uuid import uuid4
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from cloud.app import db
from cloud.app.models import Base,Farm,Device,Plant,User
from cloud.app.battle_models import PlantBattle,PlantBattleEntry
from cloud.app.telegram.models import TelegramUser,WalletAccount,WalletTransaction
from cloud.app.telegram import battle_lobby
from cloud.app.telegram_link import create_telegram_link_token,consume_telegram_link_token

now=datetime.now(timezone.utc)
uid=str(uuid4())
battle_id=str(uuid4())
expensive_battle_id=str(uuid4())
plant_id=str(uuid4())
tg_data={"id":44414,"first_name":"Test Telegram","username":"battle_test","language_code":"ru"}

class Bot:
    def __init__(self):self.messages=[];self.acks=[]
    async def send_message(self,chat_id,text,*,reply_markup=None):
        self.messages.append((chat_id,text,reply_markup))
    async def answer_callback_query(self,*args,**kwargs):self.acks.append((args,kwargs))

async def main():
    engine=create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Factory=async_sessionmaker(engine,expire_on_commit=False)
    async with Factory() as session:
        farm=Farm(slug="test-farm",name="Test")
        session.add(farm);await session.flush()
        admin=User(id=str(uuid4()),email="admin-test@example.invalid",display_name="admin",
                   password_hash="hash",created_at=now)
        regular=User(id=str(uuid4()),email="real-test@example.invalid",display_name="Website participant",
                     password_hash="hash",created_at=now)
        tg=TelegramUser(telegram_user_id=tg_data["id"],first_name="Test Telegram",
                        username="battle_test",language_code="ru",terms_accepted_at=now)
        session.add_all([admin,regular,tg,
            Device(id="dev-test",farm_id=farm.id,name="test",token_hash="hash"),
            Plant(id=plant_id,code="test-crop",names={"ru":"Редис","en":"Radish"})])
        await session.flush()
        session.add_all([
            WalletAccount(user_id=tg.id,balance=30),
            PlantBattle(id=battle_id,device_id="dev-test",rack_id=1,plant_id=plant_id,
                        title="Test Battle",status="open",entry_price_kisa=10,max_entries=6,
                        winner_reward_kisa=20,water_budget_ml=1000,nutrient_budget_ml=100,
                        shade_budget_minutes=2000,created_by_user_id=admin.id,
                        created_at=now,updated_at=now),
            PlantBattle(id=expensive_battle_id,device_id="dev-test",rack_id=2,plant_id=plant_id,
                        title="Expensive Battle",status="open",entry_price_kisa=40,max_entries=6,
                        winner_reward_kisa=20,created_by_user_id=admin.id,
                        created_at=now,updated_at=now)
        ])
        await session.commit()

    async def fake_create_user(payload):
        async with Factory() as session:
            tg=(await session.execute(
                select(TelegramUser).where(TelegramUser.telegram_user_id==payload["id"])
            )).scalar_one()
            balance=(await session.execute(
                select(WalletAccount).where(WalletAccount.user_id==tg.id)
            )).scalar_one()
            session.expunge(tg);session.expunge(balance)
            return tg,balance

    bot=Bot()
    with patch.object(battle_lobby,"SessionLocal",new=Factory),\
         patch.object(battle_lobby.core,"get_or_create_user",new=fake_create_user):
        await battle_lobby.show_lobby(bot,tg_data["id"],tg_data)
        assert bot.messages and "Test Battle" in bot.messages[-1][1]
        keyboard=bot.messages[-1][2]["inline_keyboard"]
        assert any(b.get("callback_data")=="battle:join:"+battle_id for row in keyboard for b in row)
        assert "Ⓚ" in bot.messages[-1][1] and "Свободных мест" in bot.messages[-1][1]
        await battle_lobby.show_details(bot,tg_data["id"],tg_data,battle_id,confirmation=True)
        assert any(b.get("callback_data")=="battle:confirm:"+battle_id for row in bot.messages[-1][2]["inline_keyboard"] for b in row)
        async with Factory() as session:
            assert (await session.execute(select(PlantBattleEntry))).scalars().all()==[], "Confirmation preview must not debit user"
        await battle_lobby.join(bot,tg_data["id"],tg_data,battle_id)
        assert "Вы участвуете" in bot.messages[-1][1]
        assert "Ⓚ 10" in bot.messages[-1][1]
        assert "Ⓚ 20" in bot.messages[-1][1]
        async with Factory() as session:
            entries=(await session.execute(select(PlantBattleEntry))).scalars().all()
            assert len(entries)==1 and entries[0].slot_number==1
            tg=(await session.execute(select(TelegramUser))).scalar_one()
            assert entries[0].telegram_user_id==tg.id
            internal=await session.get(User,tg.marketplace_user_id)
            assert internal and not internal.is_active and internal.email.endswith("@internal.kisamore.local")
            wallet=(await session.execute(select(WalletAccount))).scalar_one()
            assert wallet.balance==20
            tx=(await session.execute(select(WalletTransaction))).scalars().all()
            assert len(tx)==1 and tx[0].kind=="battle_entry" and tx[0].amount==-10
        await battle_lobby.join(bot,tg_data["id"],tg_data,battle_id)
        async with Factory() as session:
            assert len((await session.execute(select(PlantBattleEntry))).scalars().all())==1
            assert (await session.execute(select(WalletAccount))).scalar_one().balance==20
        # An insufficient balance never reserves a slot or debits the wallet.
        await battle_lobby.join(bot,tg_data["id"],tg_data,expensive_battle_id)
        assert "Недостаточно Kisa" in bot.messages[-1][1]
        assert "Ⓚ 40" in bot.messages[-1][1] and "Ⓚ 20" in bot.messages[-1][1]
        assert any(b.get("callback_data")=="menu:wallet" for row in bot.messages[-1][2]["inline_keyboard"] for b in row)
        async with Factory() as session:
            assert len((await session.execute(select(PlantBattleEntry))).scalars().all())==1
            assert (await session.execute(select(WalletAccount))).scalar_one().balance==20

        # Linking to an actual website account transfers Battle entry.
        async with Factory() as session:
            raw,_=await create_telegram_link_token(session,user_id=regular.id)
            await session.commit()
        async with Factory() as session:
            result=await consume_telegram_link_token(session,raw_token=raw,
                                telegram_user_id=tg_data["id"])
            assert result.id==regular.id
            await session.commit()
        async with Factory() as session:
            entry=(await session.execute(select(PlantBattleEntry))).scalar_one()
            assert entry.user_id==regular.id and entry.telegram_user_id==tg.id
            assert (await session.execute(select(WalletAccount))).scalar_one().balance==20
        await battle_lobby.show_lobby(bot,tg_data["id"],tg_data,mine_only=True)
        assert "Test Battle" in bot.messages[-1][1]
        assert any(b.get("callback_data")==f"battle:open:{entry.id}" for row in bot.messages[-1][2]["inline_keyboard"] for b in row)
    print("PASS: /battle list, two-step confirmation, Telegram-only purchase Kisa wallet, single entry, replay safe, later website-link retains plant")
    await engine.dispose()

if __name__=="__main__":asyncio.run(main())
