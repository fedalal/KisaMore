"""Permanent public QR certificates and immutable growth snapshots.

Certificate URLs were issued before this redesign; never change their paths.
Only finished battles can be viewed through these public endpoints.
"""
from __future__ import annotations

import asyncio
import os
import subprocess
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .battle_api import _certificate_context
from .battle_models import PlantBattleAction
from .battle_final_video_api import final_video_exists, final_video_path
from .battle_certificate_urls import certificate_base_url
from .telegram_link import linked_telegram_user
from .config import get_settings
from .models import Planting
from .security import get_session
from .timelapse_service import (
    _frame_datetime, _prepare_timelapse_frame, archive_frames,
    planting_final_photo_path, planting_media_dir, planting_timelapse_path,
)

router = APIRouter(prefix="/api/v1", tags=["battle-certificates"])
template_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "static"),
    autoescape=select_autoescape(["html"]), auto_reload=False,
)

I18N = {
    "ru": {
        "page_description": "История настоящего растения в KisaMore: диплом, фотографии роста, таймлапс и действия участника.",
        "change_language": "Change language", "all_battles": "Все битвы",
        "hall_of_fame": "ЗАЛ СЛАВЫ / ИСТОРИИ РАСТЕНИЙ", "story_title": "История одного",
        "story_accent": "растения.", "story_subtitle": "Настоящее растение. Настоящие решения. Весь путь от семечка до результата сохранён здесь.",
        "diploma": "Цифровой диплом", "official_result": "Подтверждённый результат",
        "certifies": "Этот диплом подтверждает участие в соревновании",
        "grew": "Выращенное растение:", "best_gardener": "Лучший садовод", "participant": "Участник битвы",
        "battle": "Соревнование", "position": "Контейнер", "start": "Посадка", "finish": "Завершение",
        "rack": "Полка", "container": "Контейнер", "qr_alt": "QR-ссылка на постоянную страницу результата",
        "scan_qr": "Сканируйте для просмотра истории",
        "digital_record": "Постоянная цифровая запись", "permanent_record": "Этот диплом доступен по постоянной ссылке",
        "share": "Поделиться", "save_print": "Сохранить PDF / Печать",
        "archive": "ВИДЕОАРХИВ", "video_title": "Весь рост за несколько минут",
        "video_description": "Таймлапс построен из настоящих кадров полки, снятых во время выращивания именно этого растения.",
        "real_footage": "РЕАЛЬНЫЕ КАДРЫ ТЕПЛИЦЫ", "open_video": "Открыть видео",
        "video_unavailable": "Таймлапс пока готовится",
        "video_unavailable_detail": "Видеофайл может появиться после окончательной обработки кадров.",
        "video_unsupported": "Ваш браузер не поддерживает видео.", "plant_diary": "ФОТОДНЕВНИК",
        "growth_title": "Как росло растение", "growth_description": "Пять контрольных моментов от начала выращивания до финала. Нажмите на фотографию, чтобы рассмотреть крупнее.",
        "day": "День", "photo_note": "Кадры получены с камеры реальной полки; доступность отдельных снимков зависит от фотоархива.",
        "enlarge": "Увеличить фотографию", "close": "Закрыть",
        "strategy": "СТРАТЕГИЯ", "resources_title": "Как использовались ресурсы",
        "resources_description": "Каждый игрок начинал с одинаковыми лимитами воды, питания и времени без света.",
        "water": "Полив", "nutrient": "Питательный раствор", "shade": "Укрытие от света",
        "remaining": "Осталось", "ml": "мл", "minutes": "мин",
        "actions_completed": "выполненных команд", "strategy_note": "Показаны итоговые значения по данному контейнеру.",
        "activity": "ЖУРНАЛ", "timeline_title": "Хронология решений",
        "timeline_description": "Когда игрок поливал растение, добавлял питательный раствор и закрывал его от света.",
        "completed": "Выполнено", "pending": "Ожидает", "rejected": "Отклонено",
        "no_actions": "Участник не отправлял собственных команд в этой битве.",
        "final_title": "Каждое растение — своя история.",
        "final_text": "В KisaMore растения выращиваются на настоящей полке, а результат зависит от решений игроков. Присоединяйтесь к следующей битве!",
        "explore_battles": "Смотреть битвы", "footer_text": "Настоящие растения · Настоящие решения",
        "link_copied": "Ссылка скопирована",
        "premium_heading": "СЕРТИФИКАТ",
        "premium_awarded": "НАГРАЖДАЕТСЯ",
        "premium_plant_prefix": "за выращивание",
        "premium_first_frame": "ПЕРВЫЙ КАДР",
        "premium_battle": "ПЕРВАЯ БИТВА РАСТЕНИЙ",
        "premium_slogan": "ВЫРАЩИВАЙ. НАБЛЮДАЙ. ПОБЕЖДАЙ.",
        "premium_no_photo": "Итоговое фото пока недоступно",

        "certificate_heading": "СЕРТИФИКАТ",
        "awarded_to": "НАГРАЖДАЕТСЯ",
        "certificate_grew": "за выращивание растения",
        "first_frame": "ПЕРВЫЙ КАДР",
        "plant_photo_alt": "Первый кадр итогового видео выращенного растения",
        "certificate_slogan": "ВЫРАЩИВАЙ. НАБЛЮДАЙ. ПОБЕЖДАЙ.",
        "final_video_label": "ИТОГОВЫЙ ВИДЕОПОРТРЕТ",
        "final_video_title": "Ваше растение во всей красе",
        "final_video_description": "Профессиональная съёмка выращенного растения на поворотном столе. Это ваше итоговое видео после завершения битвы.",
    },
    "en": {
        "page_description": "A real KisaMore plant's story: certificate, growth photos, timelapse and player actions.",
        "change_language": "Сменить язык", "all_battles": "All battles",
        "hall_of_fame": "HALL OF FAME / PLANT STORIES", "story_title": "The story of",
        "story_accent": "one plant.", "story_subtitle": "A real plant. Real decisions. Every step from seed to result, preserved here.",
        "diploma": "Digital certificate", "official_result": "Verified result",
        "certifies": "This certificate confirms participation in",
        "grew": "Plant grown:", "best_gardener": "Best Gardener", "participant": "Battle participant",
        "battle": "Competition", "position": "Container", "start": "Planted", "finish": "Finished",
        "rack": "Rack", "container": "Container", "qr_alt": "QR link to permanent result page",
        "scan_qr": "Scan to see the growth story",
        "digital_record": "Permanent digital record", "permanent_record": "This certificate has a permanent URL",
        "share": "Share", "save_print": "Save PDF / Print",
        "archive": "VIDEO ARCHIVE", "video_title": "Every day in minutes",
        "video_description": "This timelapse uses real greenhouse frames captured while this plant was growing.",
        "real_footage": "REAL GREENHOUSE FOOTAGE", "open_video": "Open video",
        "video_unavailable": "Timelapse is being prepared",
        "video_unavailable_detail": "The video may appear after the final frames are processed.",
        "video_unsupported": "Your browser does not support video.", "plant_diary": "PHOTO JOURNAL",
        "growth_title": "How the plant grew", "growth_description": "Five moments from planting through the finish. Tap any photo to enlarge.",
        "day": "Day", "photo_note": "Photos come from the real rack camera. Individual frames depend on the available archive.",
        "enlarge": "Enlarge photo", "close": "Close",
        "strategy": "THE STRATEGY", "resources_title": "Resources used",
        "resources_description": "Every player started with the same water, nutrients and shade-time limits.",
        "water": "Water", "nutrient": "Nutrient solution", "shade": "Shade",
        "remaining": "Remaining", "ml": "ml", "minutes": "min",
        "actions_completed": "completed commands", "strategy_note": "Final values for this container.",
        "activity": "ACTIVITY LOG", "timeline_title": "Decision timeline",
        "timeline_description": "When the player watered, added nutrients or shaded the plant.",
        "completed": "Completed", "pending": "Pending", "rejected": "Rejected",
        "no_actions": "This player did not send their own commands in this battle.",
        "final_title": "Every plant has a story.",
        "final_text": "KisaMore plants grow on real racks, and the outcome depends on player choices. Join the next battle!",
        "explore_battles": "Explore battles", "footer_text": "Real plants · Real decisions",
        "link_copied": "Link copied",
        "premium_heading": "CERTIFICATE",
        "premium_awarded": "AWARDED TO",
        "premium_plant_prefix": "for growing",
        "premium_first_frame": "FIRST FRAME",
        "premium_battle": "PLANT BATTLE",
        "premium_slogan": "GROW. WATCH. COMPETE.",
        "premium_no_photo": "Final plant photo unavailable",

        "certificate_heading": "CERTIFICATE",
        "awarded_to": "AWARDED TO",
        "certificate_grew": "for growing",
        "first_frame": "FIRST FRAME",
        "plant_photo_alt": "First frame of the plant's final turntable video",
        "certificate_slogan": "GROW. WATCH. COMPETE.",
        "final_video_label": "FINAL PLANT PORTRAIT",
        "final_video_title": "Your plant in all its glory",
        "final_video_description": "A close-up turntable video of your real, fully grown plant, filmed at the end of the competition.",
    },
}


def _date(value: datetime | None, *, lang: str, show_time: bool = False) -> str:
    if value is None:
        return "—"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    try:
        local = value.astimezone(ZoneInfo(get_settings().farm_timezone))
    except ZoneInfoNotFoundError:
        local = value.astimezone(timezone.utc)
    return local.strftime("%d.%m.%Y %H:%M" if show_time and lang == "ru"
                          else "%d %b %Y %H:%M" if show_time
                          else "%d.%m.%Y" if lang == "ru" else "%d %b %Y")


def _safe_period(planting: Planting | None, battle) -> tuple[datetime, datetime]:
    start = (planting.planted_at if planting else None) or battle.planted_at or battle.created_at
    end = (planting.actual_harvest_at if planting else None) or battle.finished_at or battle.updated_at
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    if end < start:
        end = start
    return start, end


def _photo_file(*, photo_dir: str, device_id: str, rack_id: int,
                slot_number: int, planting_id: str, start: datetime,
                end: datetime, index: int) -> Path | None:
    """Cache immutable 5-frame snapshots under the planting's permanent ID."""
    if index not in range(5):
        return None
    folder = planting_media_dir(photo_dir, planting_id)
    target = folder / f"growth_{index}.jpg"
    if target.is_file() and target.stat().st_size > 0:
        return target

    # Prefer the photo already sealed when the grow cycle ended.
    final = planting_final_photo_path(photo_dir, planting_id)
    if index == 4 and final.is_file() and final.stat().st_size > 0:
        return final

    requested = start + (end - start) * (index / 4)
    # Fetch frames near this milestone, strictly inside the planting period.
    search_start = max(start, requested - timedelta(hours=20))
    search_end = min(end, requested + timedelta(hours=20))
    frames = archive_frames(photo_dir, device_id, rack_id, search_start, search_end)
    if not frames:
        return None
    frame = min(frames, key=lambda x: abs((_frame_datetime(x) or requested) - requested))
    captured = _frame_datetime(frame)
    if captured is None:
        return None
    folder.mkdir(parents=True, exist_ok=True)
    temporary = folder / f"growth_{index}.tmp.jpg"
    _prepare_timelapse_frame(frame, temporary,
                             slot_number=slot_number, captured_at=captured)
    # Thumbnails need not be larger than 800px, and remain immutable.
    from PIL import Image
    with Image.open(temporary) as image:
        if max(image.size) > 800:
            image.thumbnail((800, 800))
            image.save(temporary, "JPEG", quality=85, optimize=True)
    temporary.replace(target)
    return target


def _first_video_frame(entry_id: str) -> Path | None:
    """Extract exactly frame zero; cache it on the persistent shared photo volume.

    A missing video has no thumbnail. QR links and other archival media do not
    change. The first frame deliberately uses no timestamp seeking.
    """
    video = final_video_path(entry_id)
    if not video.is_file():
        return None
    target = video.with_suffix(".first.jpg")
    if target.is_file() and target.stat().st_size > 0:
        return target
    temporary = target.parent / f".{entry_id}-{uuid4().hex}.jpg"
    try:
        subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-i", str(video), "-frames:v", "1",
                "-vf", "scale='min(960,iw)':-2", "-q:v", "3",
                "-y", str(temporary),
            ],
            check=True, capture_output=True, timeout=40,
        )
        if not temporary.is_file() or temporary.stat().st_size <= 0:
            return None
        from PIL import Image
        with Image.open(temporary) as image:
            image.convert("RGB").save(temporary, "JPEG", quality=86, optimize=True)
        os.replace(temporary, target)
        return target
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError):
        return None
    finally:
        temporary.unlink(missing_ok=True)


@router.get("/public/battle-entries/{entry_id}/first-frame", include_in_schema=False)
async def battle_first_frame(entry_id: str, session: AsyncSession = Depends(get_session)):
    entry, _battle, _plant, _user = await _certificate_context(session, entry_id)
    path = await asyncio.to_thread(_first_video_frame, entry.id)
    if path is None:
        raise HTTPException(404, "Final video first frame is not available")
    return FileResponse(path, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400",
                                 "X-Content-Type-Options": "nosniff"})


@router.get("/public/battle-entries/{entry_id}/growth-photo/{index}",
            response_class=FileResponse, include_in_schema=False)
async def growth_photo(
    entry_id: str,
    index: int,
    session: AsyncSession = Depends(get_session),
):
    if index not in range(5):
        raise HTTPException(404, "Growth photo not found")
    entry, battle, _plant, _user = await _certificate_context(session, entry_id)
    if not entry.planting_id:
        raise HTTPException(404, "Planting photo not found")
    planting = await session.get(Planting, entry.planting_id)
    if planting is None or planting.cloud_allocation_id != entry.allocation_id:
        raise HTTPException(404, "Planting photo not found")
    start, end = _safe_period(planting, battle)
    path = await asyncio.to_thread(
        _photo_file,
        photo_dir=get_settings().photo_dir,
        device_id=battle.device_id,
        rack_id=battle.rack_id,
        slot_number=entry.slot_number,
        planting_id=planting.id,
        start=start, end=end, index=index,
    )
    if path is None:
        raise HTTPException(404, "Growth photo not available")
    return FileResponse(path, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400"})


async def _certificate_page_context(session, entry, battle, plant, user, lang):
    t = I18N[lang]
    actions = list((await session.execute(
        select(PlantBattleAction).where(PlantBattleAction.entry_id == entry.id)
        .order_by(PlantBattleAction.requested_at.asc())
    )).scalars().all())
    planting = await session.get(Planting, entry.planting_id) if entry.planting_id else None
    start, end = _safe_period(planting, battle)
    names = plant.names or {}
    plant_name = names.get(lang) or names.get("en") or names.get("ru") or plant.code
    count_completed = sum(1 for action in actions if action.status == "completed")
    resources = []
    for kind, icon, used, budget, unit in (
        ("water", "💧", entry.water_used_ml, battle.water_budget_ml, t["ml"]),
        ("nutrient", "🧪", entry.nutrient_used_ml, battle.nutrient_budget_ml, t["ml"]),
        ("shade", "◐", entry.shade_used_minutes, battle.shade_budget_minutes, t["minutes"]),
    ):
        used = max(0, int(used or 0))
        budget = max(0, int(budget or 0))
        resources.append({
            "name": t[kind], "icon": icon, "used": used, "budget": budget,
            "remaining": max(0, budget - used), "unit": unit,
            "percent": min(100, round(100 * used / budget)) if budget else 0,
        })
    entries = []
    descriptions = {"water": ("💧", t["water"], t["ml"]),
                    "nutrient": ("🧪", t["nutrient"], t["ml"]),
                    "shade": ("◐", t["shade"], t["minutes"])}
    for action in actions:
        icon, label, unit = descriptions.get(action.kind, ("·", action.kind, ""))
        entries.append({
            "kind": action.kind if action.kind in descriptions else "other",
            "icon": icon, "label": label, "unit": unit, "amount": action.amount,
            "date": _date(action.requested_at, lang=lang, show_time=True),
            "state": t.get(action.status, action.status),
        })
    photo_urls = []
    photos = []
    for index in range(5):
        url = f"/api/v1/public/battle-entries/{entry.id}/growth-photo/{index}"
        moment = start + (end - start) * (index / 4)
        photos.append({
            "url": url,
            "label": f"{t['day']} {(moment.date() - start.date()).days + 1}",
            "date": _date(moment, lang=lang),
        })
        photo_urls.append(url)
    video_url = (
        f"/api/v1/public/plantings/{entry.planting_id}/timelapse/full"
        if planting is not None and planting_timelapse_path(
            get_settings().photo_dir, planting.id).is_file() else None
    )
    telegram_user = await linked_telegram_user(session, user_id=user.id)
    public_base = certificate_base_url(
        user.preferred_language, telegram_user.language_code if telegram_user else None
    )
    return {
        "brand_website_url": f"{public_base}/",
        "brand_website_label": public_base.removeprefix("https://"),
        "telegram_bot_url": "https://t.me/KisaMoreBot",
        "first_frame_url": (
            f"/api/v1/public/battle-entries/{entry.id}/first-frame"
            if final_video_exists(entry.id) else None
        ),
        "fallback_photo_url": f"/api/v1/public/battle-entries/{entry.id}/growth-photo/4",
        "lang": lang, "alt_lang": "en" if lang == "ru" else "ru",
        "t": t,
        "battle": {
            "title": battle.title, "rack": battle.rack_id,
            "start_date": _date(start, lang=lang),
            "finished_date": _date(end, lang=lang),
            "finished_year": end.year,
        },
        "person": {
            "name": user.display_name, "plant": str(plant_name),
            "slot": entry.slot_number, "winner": bool(entry.is_winner),
        },
        "site_url": f"{public_base}/",
        "site_label": public_base.removeprefix("https://"),
        "qr_url": f"/api/v1/public/battle-entries/{entry.id}/qr",
        "video_url": video_url,
        "final_video_url": (
            f"/api/v1/public/battle-entries/{entry.id}/final-video"
            if final_video_exists(entry.id) else None
        ),
        "photo_urls": photo_urls,
        "photos": photos,
        "resources": resources, "actions": entries,
        "action_count": count_completed,
    }


@router.get("/battle-certificate/{entry_id}", response_class=HTMLResponse,
            include_in_schema=False)
async def battle_certificate_page(
    entry_id: str,
    lang: str | None = Query(default=None, max_length=5),
    session: AsyncSession = Depends(get_session),
):
    entry, battle, plant, user = await _certificate_context(session, entry_id)
    requested = (lang or user.preferred_language or "en").lower().split("-")[0]
    language = requested if requested in I18N else "en"
    context = await _certificate_page_context(session, entry, battle, plant, user, language)
    html = template_env.get_template("battle_certificate.html").render(**context)
    return HTMLResponse(html, headers={
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": (
            "default-src 'self'; img-src 'self' data:; media-src 'self'; "
            "script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; base-uri 'none'; frame-ancestors 'none'"
        ),
    })
