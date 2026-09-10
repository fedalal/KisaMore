from __future__ import annotations

import asyncio
from html import escape
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import select

from ..config import get_settings
from ..db import SessionLocal
from ..models import Plant, Planting, RackPhoto, RackSlot
from ..rack_photo_storage import slot_latest_path
from ..timelapse_service import planting_timelapse_path, slot_timelapse_path
from . import worker as existing


core = existing.core
# Keep Kisa as a large internal unit: roughly $1 of developer reward per Kisa.
# The larger packs progressively reduce the Stars-per-Kisa rate. The 20 Kisa
# pack is intentionally priced at 1,540 Stars (~$20.02 at $0.013/Star), which
# matches the default 10-day container rental price of 20 Kisa.
core.PACKAGES = {
    85: 1,
    410: 5,
    800: 10,
    1540: 20,
}
_original_get_plant_card = core.get_plant_card
_original_handle_callback = core.handle_callback


TIMELAPSE_TEXT = {
    "en": {"title": "🎞 <b>Timelapse</b>\nChoose a period:", "24h": "24 hours", "3d": "3 days", "full": "Full growth", "not_ready": "⏳ This timelapse is still being prepared. Please try again later.", "caption_24h": "🎞 Last 24 hours", "caption_3d": "🎞 Last 3 days", "caption_full": "🎞 Full growth timelapse"},
    "ru": {"title": "🎞 <b>Таймлапс</b>\nВыберите период:", "24h": "24 часа", "3d": "3 дня", "full": "Всё выращивание", "not_ready": "⏳ Этот таймлапс ещё готовится. Попробуйте немного позже.", "caption_24h": "🎞 Последние 24 часа", "caption_3d": "🎞 Последние 3 дня", "caption_full": "🎞 Таймлапс всего выращивания"},
    "de": {"title": "🎞 <b>Zeitraffer</b>\nZeitraum wählen:", "24h": "24 Stunden", "3d": "3 Tage", "full": "Gesamtes Wachstum", "not_ready": "⏳ Dieser Zeitraffer wird noch erstellt. Bitte später erneut versuchen.", "caption_24h": "🎞 Letzte 24 Stunden", "caption_3d": "🎞 Letzte 3 Tage", "caption_full": "🎞 Gesamtes Wachstum"},
    "fr": {"title": "🎞 <b>Timelapse</b>\nChoisissez une période :", "24h": "24 heures", "3d": "3 jours", "full": "Toute la croissance", "not_ready": "⏳ Ce timelapse est encore en préparation. Réessayez plus tard.", "caption_24h": "🎞 Dernières 24 heures", "caption_3d": "🎞 3 derniers jours", "caption_full": "🎞 Toute la croissance"},
    "es": {"title": "🎞 <b>Timelapse</b>\nElige un período:", "24h": "24 horas", "3d": "3 días", "full": "Todo el crecimiento", "not_ready": "⏳ Este timelapse todavía se está preparando. Inténtalo más tarde.", "caption_24h": "🎞 Últimas 24 horas", "caption_3d": "🎞 Últimos 3 días", "caption_full": "🎞 Todo el crecimiento"},
    "it": {"title": "🎞 <b>Timelapse</b>\nScegli un periodo:", "24h": "24 ore", "3d": "3 giorni", "full": "Intera crescita", "not_ready": "⏳ Questo timelapse è ancora in preparazione. Riprova più tardi.", "caption_24h": "🎞 Ultime 24 ore", "caption_3d": "🎞 Ultimi 3 giorni", "caption_full": "🎞 Intera crescita"},
    "pt": {"title": "🎞 <b>Timelapse</b>\nEscolha um período:", "24h": "24 horas", "3d": "3 dias", "full": "Crescimento completo", "not_ready": "⏳ Este timelapse ainda está sendo preparado. Tente novamente mais tarde.", "caption_24h": "🎞 Últimas 24 horas", "caption_3d": "🎞 Últimos 3 dias", "caption_full": "🎞 Crescimento completo"},
    "pl": {"title": "🎞 <b>Timelapse</b>\nWybierz okres:", "24h": "24 godziny", "3d": "3 dni", "full": "Cały wzrost", "not_ready": "⏳ Ten timelapse jest jeszcze przygotowywany. Spróbuj ponownie później.", "caption_24h": "🎞 Ostatnie 24 godziny", "caption_3d": "🎞 Ostatnie 3 dni", "caption_full": "🎞 Cały wzrost"},
    "zh": {"title": "🎞 <b>延时视频</b>\n请选择时间范围：", "24h": "24 小时", "3d": "3 天", "full": "完整生长周期", "not_ready": "⏳ 此延时视频仍在生成中，请稍后再试。", "caption_24h": "🎞 最近 24 小时", "caption_3d": "🎞 最近 3 天", "caption_full": "🎞 完整生长周期"},
}


def tt(lang: str, key: str) -> str:
    locale = TIMELAPSE_TEXT.get(lang) or TIMELAPSE_TEXT["en"]
    return locale.get(key) or TIMELAPSE_TEXT["en"][key]


async def get_plant_card(planting_id: str, user_id: int):
    """Use the automatically derived container crop for ordinary rack photos.

    The existing worker already replaces card.photo with an administrator-published
    PlantingPhoto when one exists. In that case we keep the administrator photo.
    """
    card = await _original_get_plant_card(planting_id, user_id)
    if card is None:
        return None

    if isinstance(card.photo, RackPhoto):
        path = slot_latest_path(
            get_settings().photo_dir,
            card.slot.device_id,
            card.slot.rack_id,
            card.slot.slot_number,
        )
        if Path(path).is_file():
            card.photo = SimpleNamespace(file_path=str(path))
    return card


async def show_garden(bot, chat_id: int, tg: dict) -> None:
    """Keep the localized garden view and add a photo button for active rentals."""
    lang = core.language_for(tg)
    user, _ = await core.get_or_create_user(tg)
    followed = await core.list_followed_plantings(user.id, 6)
    requests = [
        row for row in await core.rental_requests(user.id, 20)
        if row[0].status in ("requested", "approved")
    ][:6]
    allocations = await core.linked_allocations(user, 6)
    parts = [core.t(lang, "garden")]
    buttons = []

    if followed:
        parts.append("\n" + core.st(lang, "garden_following"))
        for planting, plant, slot in followed:
            name = core.plant_name(plant, lang)
            parts.append(f"• 🌱 {escape(name)} · #{slot.rack_id}/{slot.slot_number}")
            buttons.append([{"text": f"🌱 {name}"[:60], "callback_data": f"plant:show:{planting.id}:0"}])

    if requests:
        parts.append(core.st(lang, "garden_requests"))
        for req, slot, plant in requests:
            parts.append(
                core.st(
                    lang,
                    "rent_status",
                    rack=slot.rack_id,
                    slot=slot.slot_number,
                    plant=escape(core.plant_name(plant, lang)),
                    status=escape(core.st(lang, f"status_{req.status}")),
                )
            )

    if allocations:
        plant_ids = {item.plant_id for item in allocations if item.plant_id}
        device_ids = {item.device_id for item in allocations if item.device_id}
        plants_by_id = {}
        planting_by_position = {}
        async with SessionLocal() as session:
            if plant_ids:
                plant_rows = (
                    await session.execute(select(Plant).where(Plant.id.in_(plant_ids)))
                ).scalars().all()
                plants_by_id = {item.id: item for item in plant_rows}
            if device_ids:
                planting_rows = (
                    await session.execute(
                        select(Planting, RackSlot)
                        .join(RackSlot, RackSlot.id == Planting.slot_id)
                        .where(
                            RackSlot.device_id.in_(device_ids),
                            Planting.status.in_(("planned", "growing", "ready")),
                        )
                    )
                ).all()
                planting_by_position = {
                    (slot.device_id, slot.rack_id, slot.slot_number): planting
                    for planting, slot in planting_rows
                }

        parts.append("\n" + existing.rt(lang, "active"))
        for allocation in allocations:
            plant = plants_by_id.get(allocation.plant_id)
            name = core.plant_name(plant, lang) if plant else "🌱"
            parts.append(
                existing.rt(
                    lang,
                    "allocation",
                    plant=escape(name),
                    rack=allocation.rack_id,
                    slot=allocation.slot_number or "—",
                )
            )
            if allocation.slot_number:
                planting = planting_by_position.get(
                    (allocation.device_id, allocation.rack_id, allocation.slot_number)
                )
                if planting is not None:
                    buttons.append([
                        {
                            "text": f"📷 {name} · {allocation.rack_id}/{allocation.slot_number}"[:60],
                            "callback_data": f"plant:show:{planting.id}:0",
                        }
                    ])

    if not followed and not requests and not allocations:
        parts.append("\n" + core.st(lang, "garden_empty"))
    buttons.append([{"text": core.st(lang, "rent_button"), "callback_data": "rent:start"}])
    buttons.append([{"text": core.t(lang, "back_home"), "callback_data": "menu:home"}])
    await bot.send_message(chat_id, "\n".join(parts), reply_markup={"inline_keyboard": buttons})


async def _timelapse_context(planting_id: str):
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(Planting, RackSlot, Plant)
                .join(RackSlot, RackSlot.id == Planting.slot_id)
                .join(Plant, Plant.id == Planting.plant_id)
                .where(Planting.id == planting_id)
                .limit(1)
            )
        ).first()
    return row


async def _show_timelapse_menu(bot, chat_id: int, tg: dict, planting_id: str) -> None:
    lang = core.language_for(tg)
    markup = {
        "inline_keyboard": [
            [
                {"text": f"🎞 {tt(lang, '24h')}", "callback_data": f"timelapse:24h:{planting_id}"},
                {"text": f"🎞 {tt(lang, '3d')}", "callback_data": f"timelapse:3d:{planting_id}"},
            ],
            [{"text": f"🌱 {tt(lang, 'full')}", "callback_data": f"timelapse:full:{planting_id}"}],
            [{"text": core.st(lang, "back_plants"), "callback_data": f"plant:show:{planting_id}:0"}],
        ]
    }
    await bot.send_message(chat_id, tt(lang, "title"), reply_markup=markup)


async def _send_timelapse(bot, chat_id: int, tg: dict, planting_id: str, period: str) -> None:
    lang = core.language_for(tg)
    row = await _timelapse_context(planting_id)
    if row is None:
        await bot.send_message(chat_id, tt(lang, "not_ready"))
        return
    planting, slot, plant = row
    if period in ("24h", "3d"):
        path = slot_timelapse_path(
            get_settings().photo_dir,
            slot.device_id,
            slot.rack_id,
            slot.slot_number,
            period,
        )
    elif period == "full":
        path = planting_timelapse_path(get_settings().photo_dir, planting.id)
    else:
        await bot.send_message(chat_id, tt(lang, "not_ready"))
        return

    if not Path(path).is_file():
        await bot.send_message(chat_id, tt(lang, "not_ready"))
        return

    name = core.plant_name(plant, lang)
    caption = f"{tt(lang, f'caption_{period}')}\n🌱 {escape(name)} · {slot.rack_id}/{slot.slot_number}"
    markup = {"inline_keyboard": [[{"text": core.st(lang, "back_plants"), "callback_data": f"plant:show:{planting.id}:0"}]]}
    await bot.send_video(chat_id, path, caption=caption, reply_markup=markup)


async def handle_callback(bot, query: dict) -> None:
    data = str(query.get("data") or "")
    if not data.startswith("timelapse:"):
        await _original_handle_callback(bot, query)
        return

    qid = query.get("id")
    tg = query.get("from")
    chat_id = ((query.get("message") or {}).get("chat") or {}).get("id")
    if not qid or tg is None or chat_id is None:
        return
    await bot.answer_callback_query(qid)
    parts = data.split(":", 2)
    if len(parts) == 2:
        await _show_timelapse_menu(bot, chat_id, tg, parts[1])
        return
    if len(parts) == 3 and parts[1] in ("24h", "3d", "full"):
        await _send_timelapse(bot, chat_id, tg, parts[2], parts[1])
        return


core.get_plant_card = get_plant_card
core.show_garden = show_garden
core.handle_callback = handle_callback


if __name__ == "__main__":
    asyncio.run(core.run())
