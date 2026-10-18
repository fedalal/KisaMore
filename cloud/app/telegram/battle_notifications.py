from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import or_, select

from ..battle_models import PlantBattle, PlantBattleEntry
from ..battle_event_models import BattleEventNotification
from ..battle_events import planned_end_utc
from ..config import get_settings
from ..models import Plant, RackCameraCalibration, RackCameraPhoto
from .activity_notifier import TelegramActivityDelivery
from .models import TelegramUser


TEXTS = {
    "en": {
        "text": "🌿 <b>Plant Battle · day {day}</b>\n\n{plant}\nRack {rack} · Container {slot}\n\nResources left:\n💧 water: <b>{water} ml</b>\n🧪 nutrient solution: <b>{nutrient} ml</b>\n🌘 shade: <b>{shade} min</b>\n\nOpen your plant for the latest photo and timelapse.",
        "button": "🌱 Open my battle plant",
    },
    "ru": {
        "text": "🌿 <b>Битва растений · день {day}</b>\n\n{plant}\nПолка {rack} · контейнер {slot}\n\nОсталось ресурсов:\n💧 вода: <b>{water} мл</b>\n🧪 питательный раствор: <b>{nutrient} мл</b>\n🌘 закрытие от света: <b>{shade} мин</b>\n\nОткройте растение, чтобы увидеть свежее фото и таймлапс.",
        "button": "🌱 Открыть моё растение",
    },
    "de": {
        "text": "🌿 <b>Pflanzenbattle · Tag {day}</b>\n\n{plant}\nRegal {rack} · Behälter {slot}\n\nVerbleibend: 💧 {water} ml · 🧪 {nutrient} ml · 🌘 {shade} min\n\nÖffne deine Pflanze für Foto und Zeitraffer.",
        "button": "🌱 Meine Pflanze öffnen",
    },
    "fr": {
        "text": "🌿 <b>Bataille des plantes · jour {day}</b>\n\n{plant}\nÉtagère {rack} · bac {slot}\n\nRestant : 💧 {water} ml · 🧪 {nutrient} ml · 🌘 {shade} min\n\nOuvrez votre plante pour la photo et le timelapse.",
        "button": "🌱 Ouvrir ma plante",
    },
    "es": {
        "text": "🌿 <b>Batalla de plantas · día {day}</b>\n\n{plant}\nEstante {rack} · contenedor {slot}\n\nRestante: 💧 {water} ml · 🧪 {nutrient} ml · 🌘 {shade} min\n\nAbre tu planta para ver la foto y el timelapse.",
        "button": "🌱 Abrir mi planta",
    },
    "it": {
        "text": "🌿 <b>Battaglia delle piante · giorno {day}</b>\n\n{plant}\nScaffale {rack} · contenitore {slot}\n\nRisorse rimaste: 💧 {water} ml · 🧪 {nutrient} ml · 🌘 {shade} min\n\nApri la pianta per foto e timelapse.",
        "button": "🌱 Apri la mia pianta",
    },
    "pt": {
        "text": "🌿 <b>Batalha de plantas · dia {day}</b>\n\n{plant}\nPrateleira {rack} · recipiente {slot}\n\nRestante: 💧 {water} ml · 🧪 {nutrient} ml · 🌘 {shade} min\n\nAbra sua planta para ver foto e timelapse.",
        "button": "🌱 Abrir minha planta",
    },
    "pl": {
        "text": "🌿 <b>Bitwa roślin · dzień {day}</b>\n\n{plant}\nPółka {rack} · pojemnik {slot}\n\nPozostało: 💧 {water} ml · 🧪 {nutrient} ml · 🌘 {shade} min\n\nOtwórz roślinę, aby zobaczyć zdjęcie i timelapse.",
        "button": "🌱 Otwórz moją roślinę",
    },
    "zh": {
        "text": "🌿 <b>植物对战 · 第 {day} 天</b>\n\n{plant}\n架子 {rack} · 容器 {slot}\n\n剩余资源：💧 {water} ml · 🧪 {nutrient} ml · 🌘 {shade} 分钟\n\n打开植物查看最新照片和延时视频。",
        "button": "🌱 打开我的植物",
    },
}


def _zone() -> ZoneInfo:
    try:
        return ZoneInfo(get_settings().farm_timezone)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _lang(value: str | None) -> str:
    code = (value or "en").lower().replace("_", "-").split("-", 1)[0]
    return code if code in TEXTS else "en"


async def discover_battle_daily_updates(activity_notifier, session, now: datetime) -> int:
    local_now = now.astimezone(_zone())
    # Send the daily summary after 10:00 greenhouse time. The event key makes
    # retries and bot restarts idempotent for the rest of that day.
    if local_now.hour < 10:
        return 0

    rows = (
        await session.execute(
            select(PlantBattleEntry, PlantBattle, Plant)
            .join(PlantBattle, PlantBattle.id == PlantBattleEntry.battle_id)
            .join(Plant, Plant.id == PlantBattle.plant_id)
            .where(
                PlantBattle.status == "growing",
                PlantBattleEntry.status == "active",
            )
            .order_by(PlantBattle.id, PlantBattleEntry.slot_number)
        )
    ).all()

    # Battle entries can predate Telegram linking. Resolve both direct
    # participants and linked website accounts; ordinary rentals are excluded.
    user_ids = {entry.user_id for entry, _, _ in rows}
    telegram_ids = {entry.telegram_user_id for entry, _, _ in rows if entry.telegram_user_id}
    telegram_users = []
    if user_ids or telegram_ids:
        telegram_users = list((await session.execute(
            select(TelegramUser)
            .where(
                TelegramUser.is_active.is_(True),
                or_(
                    TelegramUser.marketplace_user_id.in_(user_ids),
                    TelegramUser.id.in_(telegram_ids),
                ),
            )
        )).scalars().all())
    by_account = {tg.marketplace_user_id: tg for tg in telegram_users if tg.marketplace_user_id}
    by_telegram = {tg.id: tg for tg in telegram_users}

    camera_rows = list((await session.execute(
        select(RackCameraPhoto)
        .where(RackCameraPhoto.is_primary.is_(True))
        .order_by(RackCameraPhoto.captured_at.desc())
    )).scalars().all()) if rows else []
    primary_photo = {(photo.device_id, photo.rack_id): photo for photo in reversed(camera_rows)}
    calibration_rows = list((await session.execute(
        select(RackCameraCalibration)
    )).scalars().all()) if rows else []
    calibrations = {
        (item.device_id, item.rack_id, item.camera_id): item.slot_outlines
        for item in calibration_rows
    }

    created = 0
    for entry, battle, plant in rows:
        telegram_user = by_account.get(entry.user_id) or by_telegram.get(entry.telegram_user_id)
        if telegram_user is None or not entry.planting_id:
            continue
        planted = _aware(battle.planted_at)
        if planted is None:
            continue
        planted_local = planted.astimezone(_zone()).date()
        day = (local_now.date() - planted_local).days + 1
        # Planting-start notification already covers day 1.
        if day <= 1:
            continue

        event_key = f"battle_daily:{entry.id}:{local_now.date().isoformat()}"
        if await session.get(TelegramActivityDelivery, event_key) is not None:
            continue

        lang = _lang(telegram_user.language_code)
        tr = TEXTS[lang]
        names = plant.names or {}
        plant_name = names.get(lang) or names.get("en") or names.get("ru") or plant.code
        text = tr["text"].format(
            day=day,
            plant=escape(str(plant_name)),
            rack=battle.rack_id,
            slot=entry.slot_number,
            water=max(0, battle.water_budget_ml - entry.water_used_ml),
            nutrient=max(0, battle.nutrient_budget_ml - entry.nutrient_used_ml),
            shade=max(0, battle.shade_budget_minutes - entry.shade_used_minutes),
        )
        photo = primary_photo.get((battle.device_id, battle.rack_id))
        # The bot mounts the shared photo volume. A missing file is handled
        # by the sender, which falls back to the text version.
        session.add(
            TelegramActivityDelivery(
                event_key=event_key,
                telegram_user_id=telegram_user.telegram_user_id,
                kind="battle_daily",
                payload={
                    "text": text,
                    "photo_path": photo.file_path if photo else None,
                    "slot_polygon": (
                        calibrations.get(
                            (battle.device_id, battle.rack_id, photo.camera_id), {}
                        ).get(str(entry.slot_number))
                        if photo else None
                    ),
                    "button": tr["button"],
                    # Telegram callback, not a URL. Opens the participant's
                    # Battle information inside this bot.
                    "callback_data": f"battle:open:{entry.id}",
                    "planting_id": entry.planting_id,
                    "battle_id": battle.id,
                },
                status="pending",
                attempts=0,
                created_at=now,
            )
        )
        created += 1

    if created:
        await session.commit()
    return created



END_SOON_TEXTS = {
    "ru": (
        "⏳ <b>Сегодня последний день битвы растений!</b>\n\n"
        "<b>{battle}</b>\n"
        "До планового завершения осталось менее 24 часов. "
        "Проверьте растение и используйте оставшиеся ресурсы."
    ),
    "en": (
        "⏳ <b>Last day of your Plant Battle!</b>\n\n"
        "<b>{battle}</b>\n"
        "Less than 24 hours remain until the planned end. "
        "Check your plant and use your remaining resources."
    ),
}


async def discover_end_soon_telegram(session, now: datetime) -> int:
    """Deliver existing end_soon inbox events via Telegram, once per event.

    The push worker creates the shared notice for each participating user,
    regardless of device. Telegram only mirrors that durable notice, never
    creates a second inbox item or a second FCM notification.
    """
    notices = list((await session.execute(
        select(BattleEventNotification, PlantBattle)
        .join(PlantBattle, PlantBattle.id == BattleEventNotification.battle_id)
        .where(
            BattleEventNotification.event_key.like("%:end_soon:%"),
            BattleEventNotification.created_at >= now - timedelta(days=2),
            PlantBattle.status == "growing",
        )
    )).all())
    notices = [
        (notice, battle) for notice, battle in notices
        if (end := planned_end_utc(battle)) is not None
        and end - timedelta(hours=24) <= now < end
    ]
    if not notices:
        return 0

    entry_ids = {n.entry_id for n, _ in notices if n.entry_id}
    entries = list((await session.execute(
        select(PlantBattleEntry).where(PlantBattleEntry.id.in_(entry_ids))
    )).scalars().all()) if entry_ids else []
    by_entry = {entry.id: entry for entry in entries}
    user_ids = {notice.user_id for notice, _ in notices}
    direct_ids = {
        entry.telegram_user_id for entry in entries if entry.telegram_user_id
    }
    linked = list((await session.execute(
        select(TelegramUser).where(
            TelegramUser.is_active.is_(True),
            or_(
                TelegramUser.marketplace_user_id.in_(user_ids),
                TelegramUser.id.in_(direct_ids),
            ),
        )
    )).scalars().all())
    by_account = {tg.marketplace_user_id: tg for tg in linked if tg.marketplace_user_id}
    by_id = {tg.id: tg for tg in linked}

    created = 0
    for notice, battle in notices:
        entry = by_entry.get(notice.entry_id)
        tg = by_account.get(notice.user_id)
        if tg is None and entry is not None and entry.user_id == notice.user_id:
            tg = by_id.get(entry.telegram_user_id)
        if tg is None:
            continue
        key = f"battle_end_soon:{notice.id}"
        if await session.get(TelegramActivityDelivery, key) is not None:
            continue
        language = _lang(tg.language_code)
        locale = "ru" if language == "ru" else "en"
        session.add(TelegramActivityDelivery(
            event_key=key,
            telegram_user_id=tg.telegram_user_id,
            kind="battle_end_soon",
            payload={
                "text": END_SOON_TEXTS[locale].format(battle=escape(battle.title)),
                "button": "🌱 Открыть битву" if locale == "ru" else "🌱 Open Battle",
                "url": "https://ru.kisamore.farm/battle" if locale == "ru"
                       else "https://kisamore.farm/battle",
                "battle_id": battle.id,
            },
            status="pending",
            attempts=0,
            created_at=now,
        ))
        created += 1
    if created:
        await session.commit()
    return created

def install(activity_notifier) -> None:
    if getattr(activity_notifier, "_battle_notifications_installed", False):
        return
    original_discover = activity_notifier.discover_activity

    async def discover_activity(session, now):
        created = await original_discover(session, now)
        created += await discover_battle_daily_updates(activity_notifier, session, now)
        created += await discover_end_soon_telegram(session, now)
        return created

    activity_notifier.discover_activity = discover_activity
    activity_notifier._battle_notifications_installed = True
