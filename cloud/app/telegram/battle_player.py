"""Private Plant Battle participant view inside Telegram, not an external website."""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from pathlib import Path

from sqlalchemy import select

from ..battle_models import PlantBattle, PlantBattleAction, PlantBattleEntry
from ..camera_timelapse_service import camera_battle_timelapse_path
from ..config import get_settings
from ..db import SessionLocal
from ..models import Plant, RackCameraCalibration, RackCameraPhoto
from .activity_notifier import _highlight_battle_slot
from .battle_notifications import _aware, _lang, _zone
from .models import TelegramUser


TEXTS = {
    "ru": {
        "heading": "🌱 <b>Моё растение в Битве</b>", "rack": "Полка", "slot": "Контейнер",
        "day": "День выращивания", "water": "Вода", "nutrient": "Питание",
        "shade": "Затемнение", "left": "Осталось ресурсов", "latest": "Последний кадр",
        "actions": "Последние действия", "pending": "ожидает", "completed": "выполнено",
        "rejected": "отклонено", "refresh": "🔄 Обновить", "photo": "📷 Камера",
        "unavailable": "Растение недоступно или не принадлежит вашему Telegram-аккаунту.",
        "no_video": "Таймлапс пока не готов.", "no_photo": "Свежее фото полки пока недоступно.",
        "video": "Таймлапс всей полки", "minutes": "мин", "ml": "мл",
        "water_action": "Полив", "nutrient_action": "Питание", "shade_action": "Затемнение",
    },
    "en": {
        "heading": "🌱 <b>My Plant Battle plant</b>", "rack": "Rack", "slot": "Container",
        "day": "Growing day", "water": "Water", "nutrient": "Nutrients",
        "shade": "Shade", "left": "Resources left", "latest": "Latest photo",
        "actions": "Recent actions", "pending": "pending", "completed": "completed",
        "rejected": "rejected", "refresh": "🔄 Refresh", "photo": "📷 Camera",
        "unavailable": "This Battle plant is unavailable or does not belong to your Telegram account.",
        "no_video": "The timelapse is not ready yet.", "no_photo": "No current shelf photo is available.",
        "video": "Whole-rack timelapse", "minutes": "min", "ml": "ml",
        "water_action": "Water", "nutrient_action": "Nutrients", "shade_action": "Shade",
    },
}


def labels(lang: str) -> dict:
    return TEXTS["ru"] if _lang(lang) == "ru" else TEXTS["en"]


def open_callback(entry_id: str) -> str:
    return f"battle:open:{entry_id}"


def video_callback(entry_id: str, period: str, camera_id: str) -> str:
    return f"battle:tl:{entry_id}:{period}:{camera_id}"


def camera_callback(entry_id: str, camera_id: str) -> str:
    return f"battle:cam:{entry_id}:{camera_id}"


async def _owned_entry(session, telegram_user_id: int, entry_id: str):
    """Always authorize the *live* ownership, not data from a callback or outbox."""
    tg = (await session.execute(
        select(TelegramUser).where(
            TelegramUser.telegram_user_id == telegram_user_id,
            TelegramUser.is_active.is_(True),
        )
    )).scalar_one_or_none()
    if tg is None:
        return None
    row = (await session.execute(
        select(PlantBattleEntry, PlantBattle, Plant)
        .join(PlantBattle, PlantBattle.id == PlantBattleEntry.battle_id)
        .join(Plant, Plant.id == PlantBattle.plant_id)
        .where(PlantBattleEntry.id == entry_id,
               PlantBattleEntry.status.in_(("active", "finished")))
    )).one_or_none()
    if row is None:
        return None
    entry, battle, plant = row
    # A later account relink must not grant access to a different website account.
    if tg.marketplace_user_id:
        if entry.user_id != tg.marketplace_user_id:
            return None
    elif entry.telegram_user_id != tg.id:
        return None
    return entry, battle, plant


async def _camera_photos(session, battle: PlantBattle):
    return list((await session.execute(
        select(RackCameraPhoto).where(
            RackCameraPhoto.device_id == battle.device_id,
            RackCameraPhoto.rack_id == battle.rack_id,
        ).order_by(RackCameraPhoto.is_primary.desc(), RackCameraPhoto.camera_id)
    )).scalars().all())


def _keyboard(entry_id: str, photos: list, selected_camera_id: str, lang: str) -> dict:
    tr = labels(lang)
    rows = []
    if len(photos) > 1:
        rows.append([
            {"text": ("✅ " if x.camera_id == selected_camera_id else "") +
                     f"{tr['photo']} {i + 1}",
             "callback_data": camera_callback(entry_id, x.camera_id)}
            for i, x in enumerate(photos)
            if len(camera_callback(entry_id, x.camera_id).encode("utf-8")) <= 64
        ])
    rows.append([
        {"text": label, "callback_data": video_callback(entry_id, period, selected_camera_id)}
        for period, label in [("24h", "🎞 24h"), ("3d", "🎞 3d"), ("full", "🎞 Full" if _lang(lang) != "ru" else "🎞 Весь рост")]
        if len(video_callback(entry_id, period, selected_camera_id).encode("utf-8")) <= 64
    ])
    rows.append([{"text": tr["refresh"], "callback_data": open_callback(entry_id)}])
    return {"inline_keyboard": [row for row in rows if row]}


def _brief(entry, battle, plant, actions, photo, lang: str) -> str:
    tr = labels(lang)
    names = plant.names or {}
    language = _lang(lang)
    name = names.get(language) or names.get("en") or names.get("ru") or plant.code
    start = _aware(battle.planted_at)
    day = (datetime.now(timezone.utc).astimezone(_zone()).date() -
           start.astimezone(_zone()).date()).days + 1 if start else 0
    result = [
        tr["heading"], f"<b>{escape(str(name))}</b>",
        f"{tr['rack']} {battle.rack_id} · {tr['slot']} {entry.slot_number}",
        f"{tr['day']}: {max(day, 0)}",
        "", f"<b>{tr['left']}:</b>",
        f"💧 {tr['water']}: <b>{max(0, battle.water_budget_ml - entry.water_used_ml)} {tr['ml']}</b>",
        f"🧪 {tr['nutrient']}: <b>{max(0, battle.nutrient_budget_ml - entry.nutrient_used_ml)} {tr['ml']}</b>",
        f"🌘 {tr['shade']}: <b>{max(0, battle.shade_budget_minutes - entry.shade_used_minutes)} {tr['minutes']}</b>",
    ]
    if photo:
        captured = _aware(photo.captured_at)
        if captured:
            result.append(f"\n{tr['latest']}: {captured.astimezone(_zone()):%d.%m %H:%M}")
    if actions:
        result.append(f"\n<b>{tr['actions']}:</b>")
        for action in actions[:3]:
            unit = tr["minutes"] if action.kind == "shade" else tr["ml"]
            result.append(f"• {tr.get(action.kind + '_action', action.kind)}: "
                          f"{action.amount} {unit} — {tr.get(action.status, escape(action.status))}")
    return "\n".join(result)


async def _show_entry(bot, chat_id: int, telegram_user_id: int, entry_id: str, lang: str,
                      camera_id: str | None = None) -> bool:
    async with SessionLocal() as session:
        row = await _owned_entry(session, telegram_user_id, entry_id)
        if row is None:
            return False
        entry, battle, plant = row
        photos = await _camera_photos(session, battle)
        photo = (next((p for p in photos if p.camera_id == camera_id), None) if camera_id
                 else None) or (photos[0] if photos else None)
        calibration = None
        if photo:
            calibration = (await session.execute(
                select(RackCameraCalibration).where(
                    RackCameraCalibration.device_id == battle.device_id,
                    RackCameraCalibration.rack_id == battle.rack_id,
                    RackCameraCalibration.camera_id == photo.camera_id,
                )
            )).scalar_one_or_none()
        actions = list((await session.execute(
            select(PlantBattleAction).where(PlantBattleAction.entry_id == entry.id)
            .order_by(PlantBattleAction.requested_at.desc()).limit(3)
        )).scalars().all())
        text = _brief(entry, battle, plant, actions, photo, lang)
        markup = _keyboard(entry.id, photos, photo.camera_id if photo else "", lang)
        path = Path(photo.file_path) if photo else None
        polygon = (calibration.slot_outlines or {}).get(str(entry.slot_number)) if calibration else None
    if path and path.is_file() and path.stat().st_size <= 10 * 1024 * 1024:
        highlighted = _highlight_battle_slot(path, polygon)
        try:
            await bot.send_photo(chat_id, highlighted or path,
                                 caption=text[:1024], reply_markup=markup)
        finally:
            if highlighted:
                highlighted.unlink(missing_ok=True)
    else:
        await bot.send_message(chat_id, text + "\n\n" + labels(lang)["no_photo"],
                               reply_markup=markup)
    return True


async def _show_video(bot, chat_id: int, telegram_user_id: int, entry_id: str,
                      period: str, camera_id: str, lang: str) -> bool:
    if period not in ("24h", "3d", "full"):
        return False
    async with SessionLocal() as session:
        row = await _owned_entry(session, telegram_user_id, entry_id)
        if row is None:
            return False
        entry, battle, plant = row
        cameras = await _camera_photos(session, battle)
        if camera_id not in {p.camera_id for p in cameras}:
            return False
        # Path and camera are verified against this Battle before serving.
        video = camera_battle_timelapse_path(
            get_settings().photo_dir, battle.id, camera_id, period
        )
        tr = labels(lang)
        names = plant.names or {}
        name = names.get(_lang(lang)) or names.get("en") or names.get("ru") or plant.code
        caption = f"🎞 <b>{tr['video']}</b>\n{escape(str(name))} · {tr['rack']} {battle.rack_id} · " \
                  f"{tr['slot']} {entry.slot_number}"
    if not video.is_file():
        await bot.send_message(chat_id, labels(lang)["no_video"])
    else:
        await bot.send_video(chat_id, video, caption=caption,
                             reply_markup={"inline_keyboard": [[
                                 {"text": labels(lang)["refresh"], "callback_data": open_callback(entry_id)}
                             ]]})
    return True


async def handle_callback(bot, query: dict) -> bool:
    data = str(query.get("data") or "")
    if not data.startswith("battle:"):
        return False
    qid = query.get("id")
    tg = query.get("from") or {}
    chat_id = ((query.get("message") or {}).get("chat") or {}).get("id")
    if not qid or not tg.get("id") or chat_id is None:
        return True
    from .battle_notifications import _lang
    lang = _lang(tg.get("language_code"))
    if int(chat_id) != int(tg["id"]):
        # Never post private participant resources/photos in a forwarded group.
        await bot.answer_callback_query(
            qid, text=("Откройте растение в личном чате с ботом."
                       if lang == "ru" else "Open the plant in a private chat with the bot."),
            show_alert=True,
        )
        return True
    parts = data.split(":")
    if len(parts) < 3 or len(parts[2]) != 36:
        await bot.answer_callback_query(qid, text=labels(lang)["unavailable"], show_alert=True)
        return True
    entry_id = parts[2]
    operation = parts[1]
    # Telegram spinners should stop immediately, even on a large video upload.
    await bot.answer_callback_query(qid)
    try:
        if operation == "open" and len(parts) == 3:
            ok = await _show_entry(bot, chat_id, int(tg["id"]), entry_id, lang)
        elif operation == "cam" and len(parts) == 4:
            ok = await _show_entry(bot, chat_id, int(tg["id"]), entry_id, lang, camera_id=parts[3])
        elif operation == "tl" and len(parts) == 5:
            ok = await _show_video(bot, chat_id, int(tg["id"]), entry_id, parts[3], parts[4], lang)
        else:
            ok = False
        if not ok:
            await bot.send_message(chat_id, labels(lang)["unavailable"])
    except Exception:
        from .worker_core import logger
        logger.exception("Could not show Battle entry in Telegram")
        await bot.send_message(chat_id, "⚠️ " + (
            "Не удалось открыть растение. Попробуйте ещё раз." if lang == "ru"
            else "Could not open your plant. Please try again."
        ))
    return True


def install(core) -> None:
    if getattr(core, "_battle_player_installed", False):
        return
    previous = core.handle_callback

    async def handle_callback_wrapper(bot, query):
        if await handle_callback(bot, query):
            return
        await previous(bot, query)

    core.handle_callback = handle_callback_wrapper
    core._battle_player_installed = True
