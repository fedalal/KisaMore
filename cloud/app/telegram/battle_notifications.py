from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select

from ..battle_models import PlantBattle, PlantBattleEntry
from ..config import get_settings
from ..models import Plant
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
            select(PlantBattleEntry, PlantBattle, TelegramUser, Plant)
            .join(PlantBattle, PlantBattle.id == PlantBattleEntry.battle_id)
            .join(TelegramUser, TelegramUser.id == PlantBattleEntry.telegram_user_id)
            .join(Plant, Plant.id == PlantBattle.plant_id)
            .where(
                PlantBattle.status == "growing",
                PlantBattleEntry.status == "active",
                TelegramUser.is_active.is_(True),
            )
            .order_by(PlantBattle.id, PlantBattleEntry.slot_number)
        )
    ).all()

    created = 0
    for entry, battle, telegram_user, plant in rows:
        if not entry.planting_id:
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
        session.add(
            TelegramActivityDelivery(
                event_key=event_key,
                telegram_user_id=telegram_user.telegram_user_id,
                kind="battle_daily",
                payload={
                    "text": text,
                    "button": tr["button"],
                    "url": (
                        f"{get_settings().public_base_url.rstrip('/')}/battle?battle={battle.id}"
                        f"&entry={entry.id}"
                    ),
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


def install(activity_notifier) -> None:
    if getattr(activity_notifier, "_battle_notifications_installed", False):
        return
    original_discover = activity_notifier.discover_activity

    async def discover_activity(session, now):
        created = await original_discover(session, now)
        created += await discover_battle_daily_updates(activity_notifier, session, now)
        return created

    activity_notifier.discover_activity = discover_activity
    activity_notifier._battle_notifications_installed = True
