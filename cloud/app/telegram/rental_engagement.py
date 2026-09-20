from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from html import escape
import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import DateTime, ForeignKey, Integer, String, select
from sqlalchemy.orm import Mapped, mapped_column

from ..config import get_settings
from ..db import SessionLocal
from ..models import Allocation, Base, Plant, Planting, RackSlot
from ..rack_photo_storage import slot_latest_path
from ..timelapse_service import slot_timelapse_path
from .models import TelegramRentalRequest, TelegramUser, WalletAccount
from .service import localized_value


ACTIVE_PLANTING_STATUSES = ("growing", "ready")
INTERVAL_DAYS = max(1, int(os.getenv("KISAMORE_RENTAL_ENGAGEMENT_DAYS", "3")))
SEND_HOUR = min(23, max(0, int(os.getenv("KISAMORE_RENTAL_ENGAGEMENT_HOUR", "11"))))
CHECK_SECONDS = max(300, int(os.getenv("KISAMORE_RENTAL_ENGAGEMENT_CHECK_SECONDS", "600")))
MAX_PER_PASS = max(1, min(100, int(os.getenv("KISAMORE_RENTAL_ENGAGEMENT_MAX_PER_PASS", "20"))))


TEXTS = {
    "en": {
        "photo": "🌱 <b>Look how {plant} is growing</b>\nDay {day} · Rack {rack} · Container {slot}\n\nYour balance: <b>Ⓚ {balance}</b>. You already have enough Kisa to start your own plant.",
        "video": "🎞 <b>Three days of growth: {plant}</b>\nDay {day} · Rack {rack} · Container {slot}\n\nYour balance: <b>Ⓚ {balance}</b>. You can start your own plant whenever you like.",
        "need": "🌱 <b>Look how {plant} is growing</b>\nDay {day} · Rack {rack} · Container {slot}\n\nYour balance: <b>Ⓚ {balance}</b>. Only <b>Ⓚ {missing}</b> more to the most affordable plant.",
        "rent": "🌱 Choose my plant",
        "view": "👀 View this plant",
        "game": "🎮 Earn Kisa",
    },
    "ru": {
        "photo": "🌱 <b>Посмотрите, как выросло растение {plant}</b>\nДень {day} · Полка {rack} · контейнер {slot}\n\nУ вас на балансе <b>Ⓚ {balance}</b> — этого уже хватает, чтобы начать выращивать своё растение.",
        "video": "🎞 <b>Три дня роста: {plant}</b>\nДень {day} · Полка {rack} · контейнер {slot}\n\nУ вас на балансе <b>Ⓚ {balance}</b>. Вы уже можете выбрать своё растение.",
        "need": "🌱 <b>Посмотрите, как растёт {plant}</b>\nДень {day} · Полка {rack} · контейнер {slot}\n\nНа балансе <b>Ⓚ {balance}</b>. До самого доступного растения осталось всего <b>Ⓚ {missing}</b>.",
        "rent": "🌱 Выбрать своё растение",
        "view": "👀 Посмотреть это растение",
        "game": "🎮 Заработать Kisa",
    },
    "de": {
        "photo": "🌱 <b>Schau, wie {plant} wächst</b>\nTag {day} · Regal {rack} · Behälter {slot}\n\nDein Guthaben: <b>Ⓚ {balance}</b>. Es reicht bereits für deine eigene Pflanze.",
        "video": "🎞 <b>Drei Tage Wachstum: {plant}</b>\nTag {day} · Regal {rack} · Behälter {slot}\n\nDein Guthaben: <b>Ⓚ {balance}</b>. Du kannst jetzt deine eigene Pflanze wählen.",
        "need": "🌱 <b>Schau, wie {plant} wächst</b>\nTag {day} · Regal {rack} · Behälter {slot}\n\nDein Guthaben: <b>Ⓚ {balance}</b>. Nur noch <b>Ⓚ {missing}</b> bis zur günstigsten Pflanze.",
        "rent": "🌱 Eigene Pflanze wählen", "view": "👀 Pflanze ansehen", "game": "🎮 Kisa verdienen",
    },
    "fr": {
        "photo": "🌱 <b>Regardez pousser {plant}</b>\nJour {day} · Étagère {rack} · bac {slot}\n\nVotre solde : <b>Ⓚ {balance}</b>. Vous avez déjà assez de Kisa pour votre propre plante.",
        "video": "🎞 <b>Trois jours de croissance : {plant}</b>\nJour {day} · Étagère {rack} · bac {slot}\n\nVotre solde : <b>Ⓚ {balance}</b>. Vous pouvez choisir votre plante.",
        "need": "🌱 <b>Regardez pousser {plant}</b>\nJour {day} · Étagère {rack} · bac {slot}\n\nVotre solde : <b>Ⓚ {balance}</b>. Il ne manque que <b>Ⓚ {missing}</b> pour la plante la moins chère.",
        "rent": "🌱 Choisir ma plante", "view": "👀 Voir cette plante", "game": "🎮 Gagner des Kisa",
    },
    "es": {
        "photo": "🌱 <b>Mira cómo crece {plant}</b>\nDía {day} · Estante {rack} · contenedor {slot}\n\nTu saldo: <b>Ⓚ {balance}</b>. Ya tienes Kisa suficiente para empezar tu propia planta.",
        "video": "🎞 <b>Tres días de crecimiento: {plant}</b>\nDía {day} · Estante {rack} · contenedor {slot}\n\nTu saldo: <b>Ⓚ {balance}</b>. Ya puedes elegir tu propia planta.",
        "need": "🌱 <b>Mira cómo crece {plant}</b>\nDía {day} · Estante {rack} · contenedor {slot}\n\nTu saldo: <b>Ⓚ {balance}</b>. Solo faltan <b>Ⓚ {missing}</b> para la planta más económica.",
        "rent": "🌱 Elegir mi planta", "view": "👀 Ver esta planta", "game": "🎮 Ganar Kisa",
    },
    "it": {
        "photo": "🌱 <b>Guarda come cresce {plant}</b>\nGiorno {day} · Scaffale {rack} · contenitore {slot}\n\nSaldo: <b>Ⓚ {balance}</b>. Hai già abbastanza Kisa per iniziare la tua pianta.",
        "video": "🎞 <b>Tre giorni di crescita: {plant}</b>\nGiorno {day} · Scaffale {rack} · contenitore {slot}\n\nSaldo: <b>Ⓚ {balance}</b>. Puoi già scegliere la tua pianta.",
        "need": "🌱 <b>Guarda come cresce {plant}</b>\nGiorno {day} · Scaffale {rack} · contenitore {slot}\n\nSaldo: <b>Ⓚ {balance}</b>. Mancano solo <b>Ⓚ {missing}</b> alla pianta più economica.",
        "rent": "🌱 Scegli la mia pianta", "view": "👀 Vedi questa pianta", "game": "🎮 Guadagna Kisa",
    },
    "pt": {
        "photo": "🌱 <b>Veja como {plant} está crescendo</b>\nDia {day} · Prateleira {rack} · recipiente {slot}\n\nSeu saldo: <b>Ⓚ {balance}</b>. Você já tem Kisa suficiente para começar sua própria planta.",
        "video": "🎞 <b>Três dias de crescimento: {plant}</b>\nDia {day} · Prateleira {rack} · recipiente {slot}\n\nSeu saldo: <b>Ⓚ {balance}</b>. Você já pode escolher sua planta.",
        "need": "🌱 <b>Veja como {plant} está crescendo</b>\nDia {day} · Prateleira {rack} · recipiente {slot}\n\nSeu saldo: <b>Ⓚ {balance}</b>. Faltam apenas <b>Ⓚ {missing}</b> para a planta mais acessível.",
        "rent": "🌱 Escolher minha planta", "view": "👀 Ver esta planta", "game": "🎮 Ganhar Kisa",
    },
    "pl": {
        "photo": "🌱 <b>Zobacz, jak rośnie {plant}</b>\nDzień {day} · Półka {rack} · pojemnik {slot}\n\nSaldo: <b>Ⓚ {balance}</b>. Masz już dość Kisa, aby zacząć własną roślinę.",
        "video": "🎞 <b>Trzy dni wzrostu: {plant}</b>\nDzień {day} · Półka {rack} · pojemnik {slot}\n\nSaldo: <b>Ⓚ {balance}</b>. Możesz już wybrać własną roślinę.",
        "need": "🌱 <b>Zobacz, jak rośnie {plant}</b>\nDzień {day} · Półka {rack} · pojemnik {slot}\n\nSaldo: <b>Ⓚ {balance}</b>. Do najtańszej rośliny brakuje tylko <b>Ⓚ {missing}</b>.",
        "rent": "🌱 Wybierz moją roślinę", "view": "👀 Zobacz tę roślinę", "game": "🎮 Zdobądź Kisa",
    },
    "zh": {
        "photo": "🌱 <b>看看 {plant} 长得多快</b>\n第 {day} 天 · 架子 {rack} · 容器 {slot}\n\n你的余额：<b>Ⓚ {balance}</b>。已经足够开始种自己的植物。",
        "video": "🎞 <b>{plant} 的三天生长</b>\n第 {day} 天 · 架子 {rack} · 容器 {slot}\n\n你的余额：<b>Ⓚ {balance}</b>。现在就可以选择自己的植物。",
        "need": "🌱 <b>看看 {plant} 正在生长</b>\n第 {day} 天 · 架子 {rack} · 容器 {slot}\n\n你的余额：<b>Ⓚ {balance}</b>。距离最便宜的植物只差 <b>Ⓚ {missing}</b>。",
        "rent": "🌱 选择我的植物", "view": "👀 查看这株植物", "game": "🎮 赚取 Kisa",
    },
}


class TelegramRentalEngagementState(Base):
    __tablename__ = "telegram_rental_engagement_state"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_users.id"), primary_key=True
    )
    last_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_planting_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    sequence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


def _language(value: str | None) -> str:
    lang = str(value or "en").lower().replace("_", "-").split("-", 1)[0]
    return lang if lang in TEXTS else "en"


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


def _day_number(planted_at: datetime) -> int:
    planted = _aware(planted_at) or datetime.now(timezone.utc)
    return max(1, (datetime.now(timezone.utc) - planted).days + 1)


async def _has_active_rental(session, user: TelegramUser) -> bool:
    if user.marketplace_user_id:
        active = (
            await session.execute(
                select(Allocation.id)
                .where(
                    Allocation.user_id == user.marketplace_user_id,
                    Allocation.status == "active",
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if active is not None:
            return True

    pending = (
        await session.execute(
            select(TelegramRentalRequest.id)
            .where(
                TelegramRentalRequest.user_id == user.id,
                TelegramRentalRequest.status.in_(("requested", "approved")),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    return pending is not None


async def _candidates(session):
    rows = (
        await session.execute(
            select(Planting, Plant, RackSlot)
            .join(Plant, Plant.id == Planting.plant_id)
            .join(RackSlot, RackSlot.id == Planting.slot_id)
            .where(
                Planting.status.in_(ACTIVE_PLANTING_STATUSES),
                Plant.active.is_(True),
            )
            .order_by(Planting.planted_at.desc())
        )
    ).all()

    preferred = []
    fallback = []
    photo_dir = get_settings().photo_dir
    for planting, plant, slot in rows:
        photo = slot_latest_path(
            photo_dir,
            slot.device_id,
            slot.rack_id,
            slot.slot_number,
        )
        if not photo.is_file():
            continue
        item = (planting, plant, slot, photo)
        day = _day_number(planting.planted_at)
        if 4 <= day <= 12:
            preferred.append(item)
        else:
            fallback.append(item)
    return preferred or fallback


def _choose_candidate(candidates, previous_planting_id: str | None):
    if not candidates:
        return None
    for item in candidates:
        if str(item[0].id) != str(previous_planting_id or ""):
            return item
    return candidates[0]


async def _eligible_users(session):
    cutoff = datetime.now(timezone.utc) - timedelta(days=INTERVAL_DAYS)
    rows = (
        await session.execute(
            select(TelegramUser, WalletAccount)
            .join(WalletAccount, WalletAccount.user_id == TelegramUser.id)
            .where(
                TelegramUser.is_active.is_(True),
                WalletAccount.balance > 0,
            )
            .order_by(TelegramUser.id)
        )
    ).all()

    result = []
    for user, wallet in rows:
        if await _has_active_rental(session, user):
            continue
        state = await session.get(TelegramRentalEngagementState, user.id)
        last_sent = _aware(state.last_sent_at) if state else None
        if last_sent is not None and last_sent > cutoff:
            continue
        result.append((user, wallet, state))
        if len(result) >= MAX_PER_PASS:
            break
    return result


async def _send_one(bot, core, session, user, wallet, state, candidates, min_price: int):
    candidate = _choose_candidate(
        candidates,
        state.last_planting_id if state else None,
    )
    if candidate is None:
        return False

    planting, plant, slot, photo_path = candidate
    lang = _language(user.language_code)
    tr = TEXTS[lang]
    name = escape(localized_value(plant.names, lang, plant.code))
    balance = int(wallet.balance or 0)
    missing = max(0, int(min_price) - balance)
    day = _day_number(planting.planted_at)

    sequence = int(state.sequence if state else 0)
    use_video = sequence % 2 == 1
    video_path = slot_timelapse_path(
        get_settings().photo_dir,
        slot.device_id,
        slot.rack_id,
        slot.slot_number,
        "3d",
    )

    if missing > 0:
        text = tr["need"].format(
            plant=name,
            day=day,
            rack=slot.rack_id,
            slot=slot.slot_number,
            balance=balance,
            missing=missing,
        )
    else:
        key = "video" if use_video and video_path.is_file() else "photo"
        text = tr[key].format(
            plant=name,
            day=day,
            rack=slot.rack_id,
            slot=slot.slot_number,
            balance=balance,
        )

    rows = [
        [{"text": tr["rent"], "callback_data": "rent:start"}],
        [{"text": tr["view"], "callback_data": f"plant:show:{planting.id}:0"}],
    ]
    if missing > 0:
        rows.insert(1, [{"text": tr["game"], "callback_data": "game:menu"}])
    markup = {"inline_keyboard": rows}

    try:
        if use_video and video_path.is_file():
            await bot.send_video(
                int(user.telegram_user_id),
                video_path,
                caption=text[:1024],
                reply_markup=markup,
            )
        else:
            await bot.send_photo(
                int(user.telegram_user_id),
                photo_path,
                caption=text[:1024],
                reply_markup=markup,
            )
    except Exception:
        core.logger.exception(
            "Telegram rental engagement send failed for user=%s planting=%s",
            user.id,
            planting.id,
        )
        return False

    now = datetime.now(timezone.utc)
    if state is None:
        state = TelegramRentalEngagementState(
            user_id=user.id,
            last_sent_at=now,
            last_planting_id=str(planting.id),
            sequence=1,
        )
        session.add(state)
    else:
        state.last_sent_at = now
        state.last_planting_id = str(planting.id)
        state.sequence = sequence + 1
    await session.commit()
    return True


async def rental_engagement_loop(bot, core) -> None:
    while True:
        try:
            local_now = datetime.now(timezone.utc).astimezone(_zone())
            if local_now.hour >= SEND_HOUR:
                rentable = await core.list_active_plants(100)
                min_price = min(
                    (int(plant.rental_price_kisa or 0) for plant in rentable),
                    default=0,
                )
                if rentable and min_price >= 0:
                    async with SessionLocal() as session:
                        candidates = await _candidates(session)
                        eligible = await _eligible_users(session)
                        sent = 0
                        for user, wallet, state in eligible:
                            if await _send_one(
                                bot,
                                core,
                                session,
                                user,
                                wallet,
                                state,
                                candidates,
                                min_price,
                            ):
                                sent += 1
                            await asyncio.sleep(0.12)
                        if sent:
                            core.logger.info(
                                "Telegram rental engagement pass: sent=%s interval_days=%s",
                                sent,
                                INTERVAL_DAYS,
                            )
        except asyncio.CancelledError:
            raise
        except Exception:
            core.logger.exception("Telegram rental engagement pass failed")

        await asyncio.sleep(CHECK_SECONDS)


def install(core) -> None:
    previous_loop = core.follow_notification_loop

    async def combined_loop(bot) -> None:
        await asyncio.gather(
            previous_loop(bot),
            rental_engagement_loop(bot, core),
        )

    core.follow_notification_loop = combined_loop
