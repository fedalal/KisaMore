from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User
from .battle_message_models import BattleAdminMessage, BattleMessageReceipt
from .battle_models import PlantBattle, PlantBattleEntry
from .security import get_admin_user, get_current_user, get_session
from .telegram.activity_notifier import TelegramActivityDelivery
from .telegram.models import TelegramUser
from html import escape

router=APIRouter(prefix="/api/v1",tags=["battle-messages"])


class ComposeBattleMessage(BaseModel):
    body:str=Field(min_length=1,max_length=2000)
    recipient_entry_ids:list[str]|None=Field(default=None,max_length=6)


def _receipt_data(message:BattleAdminMessage,receipt:BattleMessageReceipt,battle:PlantBattle)->dict:
    return {"id":receipt.id,"battle_id":battle.id,"battle_title":battle.title,
            "entry_id":receipt.entry_id,"body":message.body,
            "created_at":message.created_at,"read_at":receipt.read_at}


@router.post("/admin/battles/{battle_id}/messages",status_code=201)
async def compose_battle_message(
    battle_id:str, payload:ComposeBattleMessage,
    admin:User=Depends(get_admin_user),session:AsyncSession=Depends(get_session)
):
    battle=await session.get(PlantBattle,battle_id)
    if battle is None:
        raise HTTPException(status_code=404,detail="Battle not found")
    content=payload.body.strip()
    if not content:
        raise HTTPException(status_code=422,detail="Message must not be blank")
    entries=list((await session.execute(
        select(PlantBattleEntry).where(
            PlantBattleEntry.battle_id==battle_id,
            PlantBattleEntry.status.in_(("active","finished")),
        ).order_by(PlantBattleEntry.slot_number)
    )).scalars().all())
    ids=payload.recipient_entry_ids
    if ids is not None:
        if len(ids)!=len(set(ids)) or not ids or not set(ids).issubset({e.id for e in entries}):
            raise HTTPException(status_code=422,detail="Invalid Battle participants")
        entries=[e for e in entries if e.id in set(ids)]
    if not entries:
        raise HTTPException(status_code=409,detail="Battle has no active participants")
    user_ids={e.user_id for e in entries}
    related_tg_ids={e.telegram_user_id for e in entries if e.telegram_user_id is not None}
    telegram=list((await session.execute(
        select(TelegramUser).where(
            TelegramUser.is_active.is_(True),
            (TelegramUser.marketplace_user_id.in_(user_ids)) |
            (TelegramUser.id.in_(related_tg_ids)) if related_tg_ids else
            TelegramUser.marketplace_user_id.in_(user_ids),
        )
    )).scalars().all())
    linked_by_user={tg.marketplace_user_id:tg for tg in telegram if tg.marketplace_user_id}
    direct_by_id={tg.id:tg for tg in telegram}
    now=datetime.now(timezone.utc)
    message=BattleAdminMessage(id=str(uuid4()),battle_id=battle_id,
       author_user_id=admin.id,body=content,created_at=now)
    session.add(message)
    sent_to_tg=0
    for entry in entries:
        receipt=BattleMessageReceipt(id=str(uuid4()),message_id=message.id,
                           entry_id=entry.id,user_id=entry.user_id)
        session.add(receipt)
        tg=linked_by_user.get(entry.user_id) or direct_by_id.get(entry.telegram_user_id)
        if tg is not None:
            session.add(TelegramActivityDelivery(
                event_key="battle_admin:"+receipt.id,
                telegram_user_id=tg.telegram_user_id,
                kind="battle_admin_message",
                payload={
                    "text":"📨 <b>KisaMore · "+escape(battle.title)+"</b>\n\n"+
                           escape(content),
                    "button":"🌱 Открыть моё растение" if (tg.language_code or "").startswith("ru")
                           else "🌱 Open my Battle plant",
                    "callback_data":"battle:open:"+entry.id,
                },status="pending",attempts=0,created_at=now,
            ))
            sent_to_tg+=1
    await session.commit()
    return {"message_id":message.id,"recipients":len(entries),
            "telegram_queued":sent_to_tg,"inbox_saved":len(entries)}


@router.get("/admin/battles/{battle_id}/messages")
async def admin_battle_message_history(
    battle_id:str, _:User=Depends(get_admin_user),
    session:AsyncSession=Depends(get_session),
):
    battle=await session.get(PlantBattle,battle_id)
    if battle is None: raise HTTPException(404,"Battle not found")
    rows=list((await session.execute(
       select(BattleAdminMessage).where(BattleAdminMessage.battle_id==battle_id)
       .order_by(BattleAdminMessage.created_at.desc()).limit(60)
    )).scalars().all())
    result=[]
    for msg in rows:
        receipts=list((await session.execute(
            select(BattleMessageReceipt,PlantBattleEntry.slot_number)
            .join(PlantBattleEntry,PlantBattleEntry.id==BattleMessageReceipt.entry_id)
            .where(BattleMessageReceipt.message_id==msg.id)
            .order_by(PlantBattleEntry.slot_number)
        )).all())
        keys=["battle_admin:"+r.id for r,_ in receipts]
        deliveries=list((await session.execute(
             select(TelegramActivityDelivery.event_key,TelegramActivityDelivery.status)
             .where(TelegramActivityDelivery.event_key.in_(keys))
        )).all()) if keys else []
        tg_status={k:v for k,v in deliveries}
        result.append({"id":msg.id,"body":msg.body,"created_at":msg.created_at,
            "recipients":[{"slot_number":number,"entry_id":r.entry_id,
              "read_at":r.read_at,"telegram_status":tg_status.get("battle_admin:"+r.id)}
              for r,number in receipts]})
    return result


@router.get("/battles/inbox")
async def battle_inbox(
    user:User=Depends(get_current_user),
    session:AsyncSession=Depends(get_session)
):
    rows=list((await session.execute(
      select(BattleMessageReceipt,BattleAdminMessage,PlantBattle)
      .join(BattleAdminMessage,BattleAdminMessage.id==BattleMessageReceipt.message_id)
      .join(PlantBattle,PlantBattle.id==BattleAdminMessage.battle_id)
      .where(BattleMessageReceipt.user_id==user.id)
      .order_by(BattleAdminMessage.created_at.desc()).limit(100)
    )).all())
    return {"messages":[_receipt_data(m,r,b) for r,m,b in rows],
            "unread_count":sum(r.read_at is None for r,m,b in rows)}


@router.post("/battles/inbox/{receipt_id}/read")
async def read_battle_message(receipt_id:str,
    user:User=Depends(get_current_user),session:AsyncSession=Depends(get_session)
):
    receipt=await session.get(BattleMessageReceipt,receipt_id)
    if receipt is None or receipt.user_id!=user.id:
        raise HTTPException(status_code=404,detail="Message not found")
    if receipt.read_at is None:
        receipt.read_at=datetime.now(timezone.utc)
        await session.commit()
    return {"id":receipt.id,"read_at":receipt.read_at}
