from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .battle_models import BATTLE_BLOCKING_STATUSES, PlantBattle, PlantBattleEntry
from .models import Planting
from .telegram.activity_notifier import TelegramActivityDelivery, user_language
from .telegram.admin_models import TelegramAdmin
from .telegram.models import TelegramUser


BATTLE_MESSAGES = {
    "en": {
        "full": "🏁 <b>Plant Battle is full!</b>\n\nRack {rack}: all {count} places are taken. The administrator will plant all six containers from the same seed batch. You will be notified when growing starts.",
        "started": "🌱 <b>Plant Battle has started!</b>\n\nRack {rack}. All six plants have been planted. You can now manage your resource allowance and follow photos and timelapses.",
        "cancelled": "↩️ <b>Plant Battle was cancelled.</b>\n\nⓀ {refund} were returned for container {slot}.",
        "action_done": "✅ <b>Your Plant Battle action was completed.</b>\n\nRack {rack} · Container {slot}\n{action}: {amount} {unit}",
        "winner": "🏆 <b>You won the Plant Battle!</b>\n\nPrize: Ⓚ {reward}\nBadge: <b>Best Gardener</b>\n\nYour digital diploma: {certificate}",
        "finished": "🏁 <b>Plant Battle is finished.</b>\n\nContainer #{winner_slot} won. Thank you for participating. Your growth history, timelapse and digital diploma remain available: {certificate}",
    },
    "ru": {
        "full": "🏁 <b>Набор в «Битву растений» завершён!</b>\n\nПолка {rack}: все {count} мест заняты. Администратор посадит все шесть контейнеров семенами из одной партии. После посадки вы получите уведомление.",
        "started": "🌱 <b>Битва растений началась!</b>\n\nПолка {rack}. Все 6 растений посажены. Теперь вы можете управлять лимитами ресурсов и следить за фото и таймлапсами.",
        "cancelled": "↩️ <b>Битва растений отменена.</b>\n\nЗа контейнер {slot} возвращено Ⓚ {refund}.",
        "action_done": "✅ <b>Действие для вашего растения выполнено.</b>\n\nПолка {rack} · контейнер {slot}\n{action}: {amount} {unit}",
        "winner": "🏆 <b>Вы победили в «Битве растений»!</b>\n\nНаграда: Ⓚ {reward}\nЗначок: <b>Лучший садовод</b>\n\nВаш цифровой диплом: {certificate}",
        "finished": "🏁 <b>«Битва растений» завершена.</b>\n\nПобедил контейнер №{winner_slot}. Спасибо за участие. История роста, таймлапс и цифровой диплом доступны здесь: {certificate}",
    },
}


def battle_message(user: TelegramUser, key: str, **kwargs) -> str:
    lang = user_language(user.language_code)
    values = BATTLE_MESSAGES["ru"] if lang == "ru" else BATTLE_MESSAGES["en"]
    return values[key].format(**kwargs)


def aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def active_battle_blockers(
    session: AsyncSession,
    device_id: str | None = None,
) -> list[PlantBattle]:
    query = select(PlantBattle).where(PlantBattle.status.in_(BATTLE_BLOCKING_STATUSES))
    if device_id:
        query = query.where(PlantBattle.device_id == device_id)
    return list((await session.execute(query)).scalars().all())


async def rack_has_blocking_battle(
    session: AsyncSession,
    *,
    device_id: str,
    rack_id: int,
    exclude_battle_id: str | None = None,
) -> bool:
    query = select(PlantBattle.id).where(
        PlantBattle.device_id == device_id,
        PlantBattle.rack_id == rack_id,
        PlantBattle.status.in_(BATTLE_BLOCKING_STATUSES),
    )
    if exclude_battle_id:
        query = query.where(PlantBattle.id != exclude_battle_id)
    return (await session.execute(query.limit(1))).scalar_one_or_none() is not None


async def telegram_user_for_marketplace(
    session: AsyncSession,
    marketplace_user_id: str,
) -> TelegramUser | None:
    return (
        await session.execute(
            select(TelegramUser).where(
                TelegramUser.marketplace_user_id == marketplace_user_id,
                TelegramUser.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()


async def queue_telegram_text(
    session: AsyncSession,
    *,
    telegram_user_id: int,
    event_key: str,
    text: str,
) -> None:
    if await session.get(TelegramActivityDelivery, event_key) is not None:
        return
    session.add(
        TelegramActivityDelivery(
            event_key=event_key,
            telegram_user_id=telegram_user_id,
            kind="battle",
            payload={"text": text},
            status="pending",
            attempts=0,
            created_at=datetime.now(timezone.utc),
        )
    )


async def queue_admin_text(
    session: AsyncSession,
    *,
    event_prefix: str,
    text: str,
) -> None:
    rows = (
        await session.execute(
            select(TelegramAdmin, TelegramUser)
            .join(TelegramUser, TelegramUser.id == TelegramAdmin.user_id)
            .where(
                TelegramAdmin.enabled.is_(True),
                TelegramUser.is_active.is_(True),
            )
        )
    ).all()
    for admin, telegram_user in rows:
        await queue_telegram_text(
            session,
            telegram_user_id=telegram_user.telegram_user_id,
            event_key=f"{event_prefix}:{admin.user_id}",
            text=text,
        )


async def sync_battles_from_plantings(
    session: AsyncSession,
    *,
    device_id: str,
) -> int:
    battles = list(
        (
            await session.execute(
                select(PlantBattle).where(
                    PlantBattle.device_id == device_id,
                    PlantBattle.status.in_(("planting", "growing")),
                )
            )
        ).scalars().all()
    )
    changed = 0
    now = datetime.now(timezone.utc)

    for battle in battles:
        entries = list(
            (
                await session.execute(
                    select(PlantBattleEntry)
                    .where(
                        PlantBattleEntry.battle_id == battle.id,
                        PlantBattleEntry.status == "active",
                    )
                    .order_by(PlantBattleEntry.slot_number)
                )
            ).scalars().all()
        )
        allocation_ids = [entry.allocation_id for entry in entries if entry.allocation_id]
        if len(allocation_ids) != battle.max_entries:
            continue

        plantings = list(
            (
                await session.execute(
                    select(Planting).where(Planting.cloud_allocation_id.in_(allocation_ids))
                )
            ).scalars().all()
        )
        by_allocation = {item.cloud_allocation_id: item for item in plantings}
        for entry in entries:
            planting = by_allocation.get(entry.allocation_id)
            if planting is not None:
                entry.planting_id = planting.id

        active = [
            item
            for item in plantings
            if item.status in ("planned", "growing", "ready", "harvested")
        ]
        if battle.status == "planting" and len(active) == battle.max_entries:
            battle.status = "growing"
            planted_times = [aware_utc(item.planted_at) for item in active if item.planted_at]
            battle.planted_at = min(planted_times) if planted_times else now
            battle.updated_at = now
            changed += 1

            seen_users: set[str] = set()
            for entry in entries:
                if entry.user_id in seen_users:
                    continue
                seen_users.add(entry.user_id)
                tg = await session.get(TelegramUser, entry.telegram_user_id)
                if tg is not None and tg.is_active:
                    text = battle_message(
                        tg,
                        "started",
                        rack=battle.rack_id,
                    )
                    await queue_telegram_text(
                        session,
                        telegram_user_id=tg.telegram_user_id,
                        event_key=f"battle_started:{battle.id}:{tg.id}",
                        text=text,
                    )

        if battle.status == "growing" and len(plantings) == battle.max_entries:
            if all(item.status == "harvested" for item in plantings):
                battle.status = "judging"
                battle.updated_at = now
                changed += 1
                await queue_admin_text(
                    session,
                    event_prefix=f"battle_judging:{battle.id}",
                    text=(
                        "🏁 <b>Битва растений завершила выращивание.</b>\n\n"
                        f"Полка {battle.rack_id}. Все 6 растений собраны. "
                        "Выберите победителя в админке KisaMore."
                    ),
                )

    if changed:
        await session.flush()
    return changed
