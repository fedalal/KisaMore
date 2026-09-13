from __future__ import annotations

from html import escape

from sqlalchemy import select

from ..models import Planting, WateringTask
from ..plant_fact_models import PlantFactPool
from .models import TelegramUser


FACT_TITLE = {
    "en": "🌿 <b>Did you know?</b>",
    "ru": "🌿 <b>Интересный факт</b>",
    "de": "🌿 <b>Schon gewusst?</b>",
    "fr": "🌿 <b>Le saviez-vous ?</b>",
    "es": "🌿 <b>¿Sabías que...?</b>",
    "it": "🌿 <b>Lo sapevi?</b>",
    "pt": "🌿 <b>Sabia que?</b>",
    "pl": "🌿 <b>Czy wiesz, że?</b>",
    "zh": "🌿 <b>你知道吗？</b>",
}


def _localized_facts(values: dict | None, lang: str) -> list[str]:
    values = values or {}
    candidates = values.get(lang) or values.get("en") or values.get("ru")
    if not candidates:
        candidates = next((items for items in values.values() if items), [])
    return [str(item).strip() for item in candidates or [] if str(item).strip()]


async def _fact_index(session, task: WateringTask) -> int:
    ids = list(
        (
            await session.execute(
                select(WateringTask.id)
                .where(
                    WateringTask.planting_id == task.planting_id,
                    WateringTask.status == "done",
                    WateringTask.completed_at.is_not(None),
                )
                .order_by(WateringTask.completed_at, WateringTask.id)
            )
        ).scalars().all()
    )
    try:
        return ids.index(task.id)
    except ValueError:
        return max(0, len(ids) - 1)


async def enrich_pending_watering_facts(activity_notifier, session) -> int:
    deliveries = list(
        (
            await session.execute(
                select(activity_notifier.TelegramActivityDelivery)
                .where(
                    activity_notifier.TelegramActivityDelivery.kind == "watering_done",
                    activity_notifier.TelegramActivityDelivery.status == "pending",
                )
                .order_by(activity_notifier.TelegramActivityDelivery.created_at)
                .limit(100)
            )
        ).scalars().all()
    )
    changed = 0
    for delivery in deliveries:
        payload = dict(delivery.payload or {})
        if payload.get("plant_fact_added"):
            continue
        planting_id = str(payload.get("planting_id") or "")
        task_id = str(payload.get("watering_task_id") or "")
        if not planting_id or not task_id:
            payload["plant_fact_added"] = True
            delivery.payload = payload
            changed += 1
            continue

        planting = await session.get(Planting, planting_id)
        task = await session.get(WateringTask, task_id)
        if planting is None or task is None:
            payload["plant_fact_added"] = True
            delivery.payload = payload
            changed += 1
            continue

        fact_pool = await session.get(PlantFactPool, planting.plant_id)
        user = (
            await session.execute(
                select(TelegramUser).where(
                    TelegramUser.telegram_user_id == delivery.telegram_user_id
                )
            )
        ).scalar_one_or_none()
        lang = activity_notifier.user_language(user.language_code if user else None)
        facts = _localized_facts(fact_pool.facts if fact_pool else {}, lang)
        if facts:
            index = await _fact_index(session, task)
            fact = facts[index % len(facts)]
            text = str(payload.get("text") or "")
            payload["text"] = (
                f"{text}\n\n{FACT_TITLE.get(lang, FACT_TITLE['en'])}\n{escape(fact)}"
            )
            payload["plant_fact_index"] = index % len(facts)
        payload["plant_fact_added"] = True
        delivery.payload = payload
        changed += 1

    if changed:
        await session.commit()
    return changed


def install(activity_notifier) -> None:
    if getattr(activity_notifier, "_watering_facts_installed", False):
        return
    original_discover = activity_notifier.discover_activity

    async def discover_activity(session, now):
        created = await original_discover(session, now)
        await enrich_pending_watering_facts(activity_notifier, session)
        return created

    activity_notifier.discover_activity = discover_activity
    activity_notifier._watering_facts_installed = True
