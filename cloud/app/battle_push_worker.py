"""Durable Firebase push delivery. FCM secrets never enter the repository."""
from __future__ import annotations
import asyncio
import logging
import os
from datetime import datetime,timedelta,timezone
from pathlib import Path
from sqlalchemy import select
from .db import SessionLocal,create_tables
from .battle_message_models import BattleAdminMessage,BattleMessageReceipt
from .battle_models import PlantBattle
from .battle_push_models import BattlePushDevice,BattlePushDelivery
from .battle_event_models import BattleEventNotification,BattleEventPushDelivery
from .battle_events import notify_end_soon

logger=logging.getLogger(__name__)
RETRY_LIMIT=6

def credentials_path()->Path:
    return Path(os.getenv("KISAMORE_FIREBASE_CREDENTIALS_PATH",
        "/run/secrets/kisamore/firebase-service-account.json"))

def firebase_ready()->bool:
    return credentials_path().is_file()

_firebase_app=None
def get_firebase_app():
    global _firebase_app
    if _firebase_app is None:
        import firebase_admin
        from firebase_admin import credentials
        _firebase_app=firebase_admin.initialize_app(
            credentials.Certificate(str(credentials_path())),
            name="kisamore-battle-push",
        )
    return _firebase_app

def send_one(token:str,receipt_id:str,battle_name:str,body:str)->None:
    from firebase_admin import messaging
    # Data-only avoids OS auto-notification + an additional local notification.
    # Android owns notification presentation and cross-channel deduplication.
    message=messaging.Message(
        token=token,
        # Do NOT send message content in FCM data: the device may have
        # switched accounts before a delayed push arrives. Android fetches
        # the receipt through the authenticated inbox before showing text.
        data={"type":"battle_admin_message","receipt_id":receipt_id},
        android=messaging.AndroidConfig(priority="high",ttl=timedelta(hours=1)),
    )
    messaging.send(message,app=get_firebase_app())

def invalid_device(exc:Exception)->bool:
    from firebase_admin import messaging
    return isinstance(exc,(messaging.UnregisteredError,messaging.SenderIdMismatchError))

def safe_error(exc:Exception)->str:
    # Do not log token or exception arguments from remote services.
    return type(exc).__name__[:80]

async def deliver_pending(*,now:datetime|None=None,limit:int=50)->dict:
    if not firebase_ready():
        return {"disabled":True,"reason":"credentials missing"}
    now=now or datetime.now(timezone.utc)
    attempted=success=failed=0
    async with SessionLocal() as session:
        rows=list((await session.execute(
            select(BattlePushDelivery,BattlePushDevice,BattleMessageReceipt,
                   BattleAdminMessage,PlantBattle)
            .join(BattlePushDevice,BattlePushDevice.token_hash==BattlePushDelivery.token_hash)
            .join(BattleMessageReceipt,BattleMessageReceipt.id==BattlePushDelivery.receipt_id)
            .join(BattleAdminMessage,BattleAdminMessage.id==BattleMessageReceipt.message_id)
            .join(PlantBattle,PlantBattle.id==BattleAdminMessage.battle_id)
            .where(BattlePushDelivery.status=="pending",
                   BattlePushDelivery.next_attempt_at<=now)
            .order_by(BattlePushDelivery.next_attempt_at)
            .limit(limit)
            .with_for_update(of=BattlePushDelivery,skip_locked=True)
        )).all())
        for delivery,device,receipt,message,battle in rows:
            attempted+=1
            if not device.active or device.user_id!=receipt.user_id:
                delivery.status="skipped"
                continue
            try:
                await asyncio.to_thread(send_one,device.token,receipt.id,battle.title,message.body)
            except Exception as exc:
                delivery.attempts+=1
                delivery.last_error=safe_error(exc)
                if invalid_device(exc):
                    delivery.status="failed"
                    device.active=False
                elif delivery.attempts>=RETRY_LIMIT:
                    delivery.status="failed"
                else:
                    # bounded exponential backoff; retry transient network errors
                    delivery.next_attempt_at=now+timedelta(
                        seconds=min(3600,30*2**(delivery.attempts-1))
                    )
                failed+=1
                logger.warning("FCM attempt failed: %s",delivery.last_error)
            else:
                delivery.status="sent"
                delivery.sent_at=datetime.now(timezone.utc)
                success+=1
        # Automatic events have a dedicated outbox, while admin messages keep
        # using the original receipts and delivery table.
        events=list((await session.execute(
            select(BattleEventPushDelivery,BattlePushDevice,BattleEventNotification,PlantBattle)
            .join(BattlePushDevice,BattlePushDevice.token_hash==BattleEventPushDelivery.token_hash)
            .join(BattleEventNotification,BattleEventNotification.id==BattleEventPushDelivery.notification_id)
            .join(PlantBattle,PlantBattle.id==BattleEventNotification.battle_id)
            .where(BattleEventPushDelivery.status=="pending",
                   BattleEventPushDelivery.next_attempt_at<=now)
            .order_by(BattleEventPushDelivery.next_attempt_at)
            .limit(limit)
            .with_for_update(of=BattleEventPushDelivery,skip_locked=True)
        )).all())
        for delivery,device,notification,battle in events:
            attempted+=1
            if not device.active or device.user_id!=notification.user_id:
                delivery.status="skipped"
                continue
            try:
                await asyncio.to_thread(send_one,device.token,notification.id,battle.title,notification.body)
            except Exception as exc:
                delivery.attempts+=1
                delivery.last_error=safe_error(exc)
                if invalid_device(exc):
                    delivery.status="failed"
                    device.active=False
                elif delivery.attempts>=RETRY_LIMIT:
                    delivery.status="failed"
                else:
                    delivery.next_attempt_at=now+timedelta(
                        seconds=min(3600,30*2**(delivery.attempts-1))
                    )
                failed+=1
                logger.warning("FCM event attempt failed: %s",delivery.last_error)
            else:
                delivery.status="sent"
                delivery.sent_at=datetime.now(timezone.utc)
                success+=1
        await session.commit()
    return {"attempted":attempted,"sent":success,"failed":failed}

async def main():
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
    await create_tables()
    if not firebase_ready():
        logger.warning("Firebase service account not configured; push worker idle")
    next_deadline_check=datetime.now(timezone.utc)
    while True:
        try:
            now=datetime.now(timezone.utc)
            if now>=next_deadline_check:
                async with SessionLocal() as session:
                    count=await notify_end_soon(session,now=now)
                    await session.commit()
                    if count:
                        logger.info("Scheduled Battle notices: %s",count)
                next_deadline_check=now+timedelta(minutes=5)
            result=await deliver_pending()
            if result.get("attempted"):
                logger.info("FCM delivery: %s sent, %s failed",
                            result["sent"],result["failed"])
        except Exception:
            logger.exception("FCM worker pass failed")
        await asyncio.sleep(5)

if __name__=="__main__":
    asyncio.run(main())
