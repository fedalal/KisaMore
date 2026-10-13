"""Event-driven Battle notifications. Caller commits changes and outbox atomically."""
from __future__ import annotations

from datetime import datetime, timedelta, time, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .battle_models import PlantBattle, PlantBattleEntry
from .battle_event_models import (
    BattleEventNotification, BattleEventPushDelivery, BattleNotificationPreferences,
)
from .battle_push_models import BattlePushDevice
from .config import get_settings
from .models import User


# Never notify on replays or repeated background scans. Event keys are unique
# per user and semantic occurrence in the database, even across process restarts.
ENABLED_BY_DEFAULT = ("start", "end_soon", "finished", "winner", "resource_low", "action_done")
KINDS = (*ENABLED_BY_DEFAULT, "new_battles")
RESOURCE_LABELS = {
    "ru": {"water": "воды", "nutrient": "питательного раствора", "shade": "затемнения"},
    "en": {"water": "water", "nutrient": "nutrient solution", "shade": "shade"},
}
ACTION_LABELS = {
    "ru": {"water": "полив", "nutrient": "питательный раствор", "shade": "затемнение"},
    "en": {"water": "watering", "nutrient": "nutrient solution", "shade": "shade"},
}


def lang(user: User) -> str:
    return "ru" if (user.preferred_language or "").startswith("ru") else "en"


async def enqueue_battle_event(
    session: AsyncSession,
    *,
    battle: PlantBattle,
    user: User,
    kind: str,
    event_key: str,
    ru: str,
    en: str,
    entry_id: str | None = None,
    now: datetime | None = None,
    pref: BattleNotificationPreferences | None = None,
) -> bool:
    if kind not in KINDS:
        raise ValueError("Unsupported battle notification event")
    if pref is None:
        pref = await session.get(BattleNotificationPreferences, user.id)
    if (pref is None and kind == "new_battles") or (pref is not None and not getattr(pref, kind)):
        return False
    if (await session.execute(
        select(BattleEventNotification.id).where(BattleEventNotification.event_key == event_key).limit(1)
    )).scalar_one_or_none() is not None:
        return False
    now = now or datetime.now(timezone.utc)
    notification = BattleEventNotification(
        id=str(uuid4()), event_key=event_key, user_id=user.id,
        battle_id=battle.id, entry_id=entry_id,
        body=ru if lang(user) == "ru" else en, created_at=now,
    )
    session.add(notification)
    devices=list((await session.execute(
        select(BattlePushDevice).where(
            BattlePushDevice.user_id == user.id, BattlePushDevice.active.is_(True))
    )).scalars().all())
    for device in devices:
        session.add(BattleEventPushDelivery(
            id=str(uuid4()),notification_id=notification.id,token_hash=device.token_hash,
            next_attempt_at=now,status="pending",attempts=0,
        ))
    # Entries without Android still see the event in their website inbox.
    return True


async def notify_battle_members(
    session: AsyncSession, *, battle: PlantBattle, kind: str,
    key_suffix: str = "", ru: str, en: str,
    now: datetime | None = None,
) -> int:
    entries=list((await session.execute(select(PlantBattleEntry).where(
        PlantBattleEntry.battle_id==battle.id,
        PlantBattleEntry.status.in_(("active","finished")),
    ))).scalars().all())
    users={u.id:u for u in (await session.execute(
        select(User).where(User.id.in_({e.user_id for e in entries}))
    )).scalars().all()} if entries else {}
    count=0
    for entry in entries:
        user=users.get(entry.user_id)
        if user and user.is_active and await enqueue_battle_event(
            session,battle=battle,user=user,kind=kind,
            event_key=f"battle:{battle.id}:{kind}:{key_suffix}:{entry.user_id}",
            ru=ru,en=en,entry_id=entry.id,now=now,
        ):
            count+=1
    return count


async def notify_new_battle(session: AsyncSession, battle: PlantBattle) -> int:
    # Explicit opt-in only; inactive accounts and battle creator excluded.
    recipients=list((await session.execute(
        select(User,BattleNotificationPreferences)
        .join(BattleNotificationPreferences,User.id==BattleNotificationPreferences.user_id)
        .where(User.is_active.is_(True),
               User.id!=battle.created_by_user_id,
               BattleNotificationPreferences.new_battles.is_(True))
    )).all())
    count=0
    for user,pref in recipients:
        if await enqueue_battle_event(
            session,battle=battle,user=user,pref=pref,kind="new_battles",
            event_key=f"battle:{battle.id}:new_battles:{user.id}",
            ru=f"🌱 Открыта новая битва «{battle.title}». Можно занять место!",
            en=f"🌱 New Battle open: {battle.title}. Join now!",
        ):
            count+=1
    return count


async def notify_resource_low(
    session: AsyncSession, *,battle:PlantBattle,entry:PlantBattleEntry,
    kind:str, remaining:int, budget:int,
):
    if budget<=0 or remaining>budget*0.2:
        return False
    user=await session.get(User,entry.user_id)
    if user is None or not user.is_active:
        return False
    unit="мин" if kind=="shade" else "мл"
    english_unit="min" if kind=="shade" else "ml"
    return await enqueue_battle_event(
        session,battle=battle,user=user,kind="resource_low",
        event_key=f"battle:{battle.id}:resource_low:{entry.id}:{kind}",
        entry_id=entry.id,
        ru=f"⚠️ Осталось {remaining} {unit} {RESOURCE_LABELS['ru'][kind]} для вашего контейнера.",
        en=f"⚠️ Only {remaining} {english_unit} of {RESOURCE_LABELS['en'][kind]} remain for your plant.",
    )


async def notify_action_done(session: AsyncSession, *,battle:PlantBattle,entry:PlantBattleEntry, action) -> bool:
    user=await session.get(User,entry.user_id)
    if user is None or not user.is_active:
        return False
    unit="мин" if action.kind=="shade" else "мл"
    english_unit="min" if action.kind=="shade" else "ml"
    return await enqueue_battle_event(
        session,battle=battle,user=user,kind="action_done",
        event_key=f"battle:{battle.id}:action_done:{action.id}:{entry.user_id}",
        entry_id=entry.id,
        ru=f"✅ Действие выполнено: {ACTION_LABELS['ru'][action.kind]}, {action.amount} {unit}.",
        en=f"✅ Action completed: {ACTION_LABELS['en'][action.kind]}, {action.amount} {english_unit}.",
    )


def planned_end_utc(battle: PlantBattle) -> datetime | None:
    if not battle.end_date:
        return None
    # end_date is a DATE: interpret it as the END of the local farm day, not 00:00.
    tz=ZoneInfo(get_settings().farm_timezone)
    return datetime.combine(battle.end_date+timedelta(days=1),time.min,tz).astimezone(timezone.utc)


async def notify_end_soon(session: AsyncSession, *,now:datetime|None=None) -> int:
    now=now or datetime.now(timezone.utc)
    battles=list((await session.execute(select(PlantBattle)
        .where(PlantBattle.status=="growing",PlantBattle.end_date.is_not(None))
    )).scalars().all())
    total=0
    for battle in battles:
        end=planned_end_utc(battle)
        if end is None or not(end-timedelta(hours=24)<=now<end):
            continue
        total+=await notify_battle_members(
            session,battle=battle,kind="end_soon",now=now,
            ru=f"⏳ До планового окончания битвы «{battle.title}» осталось менее 24 часов.",
            en=f"⏳ Less than 24 hours until the planned end of {battle.title}.",
        )
    return total
