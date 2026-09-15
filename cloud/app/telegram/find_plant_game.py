from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

from sqlalchemy import Date, DateTime, ForeignKey, Integer, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column

from ..config import get_settings
from ..db import SessionLocal
from ..models import Allocation, Base, Plant, Planting, RackPhoto, RackSlot
from . import gamification as game
from . import gamification_profile as game_profile
from .models import TelegramUser, WalletAccount, WalletTransaction
from .service import localized_value, resolve_photo_path


ACTIVE_PLANTING_STATUSES = ("planned", "growing", "ready")
settings = get_settings()


TEXTS = {
    "en": {
        "label": "🔍 Find your plant",
        "locked": "available after your plant is planted",
        "button": "🔍 Find your plant",
        "title": "🔍 <b>Find your plant</b>",
        "question": "This is rack <b>{rack}</b>. Where is your <b>{plant}</b>?\n\nThe buttons repeat the real rack layout: <b>2 columns × 3 rows</b>.",
        "unavailable": "🔒 This game becomes available when you have an active planted plant and a fresh photo of its rack.",
        "done": "✅ You have already found your plant today.",
        "wrong": "❌ Container <b>{slot}</b> is not yours. Look at the photo and try again 🌱",
        "retry": "🔍 Show the rack again",
        "correct": "✅ <b>Correct! You found your plant.</b> 🌱",
        "xp": "+<b>{xp} XP</b>",
        "reward": "+<b>Ⓚ 1</b> daily reward\nNew balance: <b>Ⓚ {balance}</b>\n🔥 Streak: <b>{streak} days</b>",
        "reward_already": "Today's <b>Ⓚ 1</b> reward was already earned from another activity.",
        "game": "🎮 Game",
    },
    "ru": {
        "label": "🔍 Найти своё растение",
        "locked": "доступно после посадки вашего растения",
        "button": "🔍 Найти своё растение",
        "title": "🔍 <b>Найдите своё растение</b>",
        "question": "На фото полка <b>{rack}</b>. Где находится ваше растение <b>{plant}</b>?\n\nРасположение кнопок повторяет реальную полку: <b>2 столбца × 3 ряда</b>.",
        "unavailable": "🔒 Игра станет доступна, когда у вас будет активное посаженное растение и свежая фотография его полки.",
        "done": "✅ Сегодня вы уже нашли своё растение.",
        "wrong": "❌ Контейнер <b>{slot}</b> — не ваш. Посмотрите на фото и попробуйте ещё раз 🌱",
        "retry": "🔍 Показать полку ещё раз",
        "correct": "✅ <b>Верно! Вы нашли своё растение.</b> 🌱",
        "xp": "+<b>{xp} XP</b>",
        "reward": "+<b>Ⓚ 1</b> за задание дня\nНовый баланс: <b>Ⓚ {balance}</b>\n🔥 Серия: <b>{streak} дн.</b>",
        "reward_already": "Сегодняшняя награда <b>Ⓚ 1</b> уже была получена за другое задание.",
        "game": "🎮 Игра",
    },
    "de": {
        "label": "🔍 Finde deine Pflanze", "locked": "nach dem Einpflanzen verfügbar", "button": "🔍 Finde deine Pflanze",
        "title": "🔍 <b>Finde deine Pflanze</b>", "question": "Das ist Regal <b>{rack}</b>. Wo ist deine <b>{plant}</b>?\n\nDie Tasten entsprechen dem Regal: <b>2 Spalten × 3 Reihen</b>.",
        "unavailable": "🔒 Das Spiel wird verfügbar, sobald du eine aktive Pflanze und ein aktuelles Foto des Regals hast.", "done": "✅ Du hast deine Pflanze heute bereits gefunden.",
        "wrong": "❌ Behälter <b>{slot}</b> ist nicht deiner. Versuch es noch einmal 🌱", "retry": "🔍 Regal erneut zeigen", "correct": "✅ <b>Richtig! Du hast deine Pflanze gefunden.</b> 🌱",
        "xp": "+<b>{xp} XP</b>", "reward": "+<b>Ⓚ 1</b> Tagesbelohnung\nNeues Guthaben: <b>Ⓚ {balance}</b>\n🔥 Serie: <b>{streak} Tage</b>",
        "reward_already": "Die heutige <b>Ⓚ 1</b>-Belohnung wurde bereits durch eine andere Aktivität verdient.", "game": "🎮 Spiel",
    },
    "fr": {
        "label": "🔍 Trouver votre plante", "locked": "disponible après la plantation", "button": "🔍 Trouver votre plante",
        "title": "🔍 <b>Trouvez votre plante</b>", "question": "Voici l’étagère <b>{rack}</b>. Où se trouve votre <b>{plant}</b> ?\n\nLes boutons reproduisent l’étagère : <b>2 colonnes × 3 rangées</b>.",
        "unavailable": "🔒 Le jeu sera disponible lorsque vous aurez une plante active et une photo récente de son étagère.", "done": "✅ Vous avez déjà trouvé votre plante aujourd’hui.",
        "wrong": "❌ Le bac <b>{slot}</b> n’est pas le vôtre. Réessayez 🌱", "retry": "🔍 Revoir l’étagère", "correct": "✅ <b>Correct ! Vous avez trouvé votre plante.</b> 🌱",
        "xp": "+<b>{xp} XP</b>", "reward": "+<b>Ⓚ 1</b> récompense quotidienne\nNouveau solde : <b>Ⓚ {balance}</b>\n🔥 Série : <b>{streak} jours</b>",
        "reward_already": "La récompense quotidienne de <b>Ⓚ 1</b> a déjà été gagnée avec une autre activité.", "game": "🎮 Jeu",
    },
    "es": {
        "label": "🔍 Encuentra tu planta", "locked": "disponible después de plantar", "button": "🔍 Encuentra tu planta",
        "title": "🔍 <b>Encuentra tu planta</b>", "question": "Este es el estante <b>{rack}</b>. ¿Dónde está tu <b>{plant}</b>?\n\nLos botones reproducen el estante: <b>2 columnas × 3 filas</b>.",
        "unavailable": "🔒 El juego estará disponible cuando tengas una planta activa y una foto reciente del estante.", "done": "✅ Ya encontraste tu planta hoy.",
        "wrong": "❌ El contenedor <b>{slot}</b> no es el tuyo. Inténtalo otra vez 🌱", "retry": "🔍 Mostrar el estante otra vez", "correct": "✅ <b>¡Correcto! Encontraste tu planta.</b> 🌱",
        "xp": "+<b>{xp} XP</b>", "reward": "+<b>Ⓚ 1</b> recompensa diaria\nNuevo saldo: <b>Ⓚ {balance}</b>\n🔥 Racha: <b>{streak} días</b>",
        "reward_already": "La recompensa diaria de <b>Ⓚ 1</b> ya se obtuvo con otra actividad.", "game": "🎮 Juego",
    },
    "it": {
        "label": "🔍 Trova la tua pianta", "locked": "disponibile dopo la semina", "button": "🔍 Trova la tua pianta",
        "title": "🔍 <b>Trova la tua pianta</b>", "question": "Questo è lo scaffale <b>{rack}</b>. Dov’è la tua <b>{plant}</b>?\n\nI pulsanti riproducono lo scaffale: <b>2 colonne × 3 righe</b>.",
        "unavailable": "🔒 Il gioco sarà disponibile quando avrai una pianta attiva e una foto recente dello scaffale.", "done": "✅ Oggi hai già trovato la tua pianta.",
        "wrong": "❌ Il contenitore <b>{slot}</b> non è il tuo. Riprova 🌱", "retry": "🔍 Mostra di nuovo lo scaffale", "correct": "✅ <b>Esatto! Hai trovato la tua pianta.</b> 🌱",
        "xp": "+<b>{xp} XP</b>", "reward": "+<b>Ⓚ 1</b> ricompensa giornaliera\nNuovo saldo: <b>Ⓚ {balance}</b>\n🔥 Serie: <b>{streak} giorni</b>",
        "reward_already": "La ricompensa giornaliera di <b>Ⓚ 1</b> è già stata ottenuta con un’altra attività.", "game": "🎮 Gioco",
    },
    "pt": {
        "label": "🔍 Encontre sua planta", "locked": "disponível após o plantio", "button": "🔍 Encontre sua planta",
        "title": "🔍 <b>Encontre sua planta</b>", "question": "Esta é a prateleira <b>{rack}</b>. Onde está sua <b>{plant}</b>?\n\nOs botões repetem a prateleira: <b>2 colunas × 3 linhas</b>.",
        "unavailable": "🔒 O jogo estará disponível quando você tiver uma planta ativa e uma foto recente da prateleira.", "done": "✅ Você já encontrou sua planta hoje.",
        "wrong": "❌ O recipiente <b>{slot}</b> não é o seu. Tente novamente 🌱", "retry": "🔍 Mostrar a prateleira novamente", "correct": "✅ <b>Certo! Você encontrou sua planta.</b> 🌱",
        "xp": "+<b>{xp} XP</b>", "reward": "+<b>Ⓚ 1</b> recompensa diária\nNovo saldo: <b>Ⓚ {balance}</b>\n🔥 Sequência: <b>{streak} dias</b>",
        "reward_already": "A recompensa diária de <b>Ⓚ 1</b> já foi obtida em outra atividade.", "game": "🎮 Jogo",
    },
    "pl": {
        "label": "🔍 Znajdź swoją roślinę", "locked": "dostępne po posadzeniu", "button": "🔍 Znajdź swoją roślinę",
        "title": "🔍 <b>Znajdź swoją roślinę</b>", "question": "To półka <b>{rack}</b>. Gdzie jest Twoja <b>{plant}</b>?\n\nPrzyciski odpowiadają półce: <b>2 kolumny × 3 rzędy</b>.",
        "unavailable": "🔒 Gra będzie dostępna, gdy będziesz mieć aktywną roślinę i aktualne zdjęcie półki.", "done": "✅ Dzisiaj już znalazłeś swoją roślinę.",
        "wrong": "❌ Pojemnik <b>{slot}</b> nie jest Twój. Spróbuj ponownie 🌱", "retry": "🔍 Pokaż półkę ponownie", "correct": "✅ <b>Dobrze! Znalazłeś swoją roślinę.</b> 🌱",
        "xp": "+<b>{xp} XP</b>", "reward": "+<b>Ⓚ 1</b> nagrody dziennej\nNowe saldo: <b>Ⓚ {balance}</b>\n🔥 Seria: <b>{streak} dni</b>",
        "reward_already": "Dzisiejsza nagroda <b>Ⓚ 1</b> została już zdobyta w innym zadaniu.", "game": "🎮 Gra",
    },
    "zh": {
        "label": "🔍 找到你的植物", "locked": "种植后可用", "button": "🔍 找到你的植物",
        "title": "🔍 <b>找到你的植物</b>", "question": "这是第 <b>{rack}</b> 层架。你的 <b>{plant}</b> 在哪里？\n\n按钮与真实层架一致：<b>2 列 × 3 行</b>。",
        "unavailable": "🔒 当你拥有正在生长的植物并且有最新的层架照片时即可开始游戏。", "done": "✅ 今天你已经找到自己的植物了。",
        "wrong": "❌ <b>{slot}</b> 号容器不是你的。再试一次 🌱", "retry": "🔍 再看一次层架", "correct": "✅ <b>答对了！你找到了自己的植物。</b> 🌱",
        "xp": "+<b>{xp} XP</b>", "reward": "+<b>Ⓚ 1</b> 每日奖励\n新余额：<b>Ⓚ {balance}</b>\n🔥 连续：<b>{streak} 天</b>",
        "reward_already": "今天的 <b>Ⓚ 1</b> 已通过其他任务获得。", "game": "🎮 游戏",
    },
}

FIND_ACHIEVEMENT = {
    "en": "🔍 Plant detective",
    "ru": "🔍 Следопыт растений",
    "de": "🔍 Pflanzendetektiv",
    "fr": "🔍 Détective des plantes",
    "es": "🔍 Detective de plantas",
    "it": "🔍 Detective delle piante",
    "pt": "🔍 Detetive de plantas",
    "pl": "🔍 Detektyw roślin",
    "zh": "🔍 植物侦探",
}


class TelegramDailyFindPlant(Base):
    __tablename__ = "telegram_daily_find_plant"
    __table_args__ = (
        UniqueConstraint("user_id", "day", name="uq_telegram_daily_find_plant"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_users.id"), index=True, nullable=False
    )
    day: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    planting_id: Mapped[str] = mapped_column(
        ForeignKey("plantings.id"), index=True, nullable=False
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activity_awarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def _tr(lang: str) -> dict:
    return TEXTS.get(lang) or TEXTS["en"]


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _grid_box(width: int, height: int, slot_number: int) -> tuple[int, int, int, int]:
    slot = int(slot_number)
    if slot < 1 or slot > 6:
        raise ValueError("slot_number must be 1..6")
    index = slot - 1
    row = index // 2
    column = index % 2
    return (
        round(width * column / 2),
        round(height * row / 3),
        round(width * (column + 1) / 2),
        round(height * (row + 1) / 3),
    )


def _visual_box(width: int, height: int, slot_number: int) -> tuple[int, int, int, int]:
    left, top, right, bottom = _grid_box(width, height, slot_number)
    inset = max(5, round(min(right - left, bottom - top) * 0.025))
    return left + inset, top + inset, right - inset, bottom - inset


def _annotate_correct(source: Path, target: Path, slot_number: int) -> None:
    from PIL import Image, ImageDraw, ImageOps

    with Image.open(source) as opened:
        opened.load()
        image = ImageOps.exif_transpose(opened).convert("RGB")

    width, height = image.size
    line_width = max(5, round(min(width, height) * 0.009))
    radius = max(10, round(min(width, height) * 0.02))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        _visual_box(width, height, slot_number),
        radius=radius,
        outline=(34, 197, 94),
        width=line_width,
    )

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    image.save(temporary, format="JPEG", quality=93, optimize=True)
    temporary.replace(target)


def _target_path(telegram_user_id: int, day: date) -> Path:
    return (
        Path(settings.photo_dir)
        / "telegram"
        / "find-plant"
        / f"user_{int(telegram_user_id)}"
        / f"{day.isoformat()}.jpg"
    )


async def _fresh_photo(session, planting: Planting, slot: RackSlot):
    photo = (
        await session.execute(
            select(RackPhoto).where(
                RackPhoto.device_id == slot.device_id,
                RackPhoto.rack_id == slot.rack_id,
            )
        )
    ).scalar_one_or_none()
    if photo is None:
        return None, None

    planted = _aware(planting.planted_at)
    captured = _aware(photo.captured_at)
    updated = _aware(photo.updated_at)
    if planted is not None:
        newest = max((v for v in (captured, updated) if v is not None), default=None)
        if newest is None or newest < planted:
            return photo, None

    return photo, resolve_photo_path(photo)


async def _planting_row(session, planting_id: str):
    return (
        await session.execute(
            select(Planting, Plant, RackSlot)
            .join(Plant, Plant.id == Planting.plant_id)
            .join(RackSlot, RackSlot.id == Planting.slot_id)
            .where(Planting.id == planting_id)
            .limit(1)
        )
    ).first()


async def _challenge(user_id: int, *, create: bool = True):
    day, _, _ = game._today_bounds()
    async with SessionLocal() as session:
        challenge = (
            await session.execute(
                select(TelegramDailyFindPlant).where(
                    TelegramDailyFindPlant.user_id == user_id,
                    TelegramDailyFindPlant.day == day,
                )
            )
        ).scalar_one_or_none()

        if challenge is None:
            if not create:
                return None
            telegram_user = await session.get(TelegramUser, user_id)
            if telegram_user is None or not telegram_user.marketplace_user_id:
                return None

            rows = list(
                (
                    await session.execute(
                        select(Planting, Plant, RackSlot)
                        .join(Plant, Plant.id == Planting.plant_id)
                        .join(RackSlot, RackSlot.id == Planting.slot_id)
                        .join(Allocation, Allocation.id == Planting.cloud_allocation_id)
                        .where(
                            Allocation.user_id == telegram_user.marketplace_user_id,
                            Allocation.status == "active",
                            Planting.status.in_(ACTIVE_PLANTING_STATUSES),
                            RackSlot.slot_number >= 1,
                            RackSlot.slot_number <= 6,
                        )
                        .order_by(Planting.planted_at, Planting.id)
                    )
                ).all()
            )
            if not rows:
                return None

            rng = random.Random(f"find-plant:{user_id}:{day.isoformat()}")
            planting, plant, slot = rng.choice(rows)
            challenge = TelegramDailyFindPlant(
                user_id=user_id,
                day=day,
                planting_id=planting.id,
                attempts=0,
                created_at=datetime.now(timezone.utc),
            )
            session.add(challenge)
            await session.commit()
            await session.refresh(challenge)
        else:
            row = await _planting_row(session, challenge.planting_id)
            if row is None:
                return None
            planting, plant, slot = row

        if challenge is not None and 'planting' not in locals():
            row = await _planting_row(session, challenge.planting_id)
            if row is None:
                return None
            planting, plant, slot = row

        if planting.status not in ACTIVE_PLANTING_STATUSES:
            return None

        photo, source = await _fresh_photo(session, planting, slot)
        return challenge, planting, plant, slot, photo, source


async def _status(user_id: int) -> dict:
    item = await _challenge(user_id, create=True)
    if item is None:
        return {"available": False, "done": False}
    challenge, _planting, _plant, _slot, _photo, source = item
    return {
        "available": source is not None,
        "done": challenge.correct_at is not None,
    }


def _slot_keyboard(lang: str) -> dict:
    rows = []
    for start in (1, 3, 5):
        rows.append([
            {"text": f"{start}", "callback_data": f"game:findanswer:{start}"},
            {"text": f"{start + 1}", "callback_data": f"game:findanswer:{start + 1}"},
        ])
    rows.append([{"text": _tr(lang)["game"], "callback_data": "game:menu"}])
    return {"inline_keyboard": rows}


async def _show_find(core, bot, chat_id: int, tg: dict) -> None:
    lang = core.language_for(tg)
    tr = _tr(lang)
    user, _ = await core.get_or_create_user(tg)
    item = await _challenge(user.id, create=True)
    if item is None:
        await bot.send_message(
            chat_id,
            tr["unavailable"],
            reply_markup={"inline_keyboard": [[{"text": tr["game"], "callback_data": "game:menu"}]]},
        )
        return

    challenge, _planting, plant, slot, _photo, source = item
    if challenge.correct_at is not None:
        await bot.send_message(
            chat_id,
            tr["done"],
            reply_markup={"inline_keyboard": [[{"text": tr["game"], "callback_data": "game:menu"}]]},
        )
        return
    if source is None:
        await bot.send_message(
            chat_id,
            tr["unavailable"],
            reply_markup={"inline_keyboard": [[{"text": tr["game"], "callback_data": "game:menu"}]]},
        )
        return

    name = escape(localized_value(plant.names or {}, lang, plant.code))
    caption = f"{tr['title']}\n\n{tr['question'].format(rack=slot.rack_id, plant=name)}"
    await bot.send_photo(
        chat_id,
        source,
        caption=caption,
        reply_markup=_slot_keyboard(lang),
    )


async def _mark_wrong(user_id: int) -> None:
    day, _, _ = game._today_bounds()
    async with SessionLocal() as session:
        challenge = (
            await session.execute(
                select(TelegramDailyFindPlant)
                .where(
                    TelegramDailyFindPlant.user_id == user_id,
                    TelegramDailyFindPlant.day == day,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if challenge is not None and challenge.correct_at is None:
            challenge.attempts += 1
            await session.commit()


async def _ensure_achievement(session, user_id: int, now: datetime) -> None:
    exists = (
        await session.execute(
            select(game_profile.TelegramAchievement.id).where(
                game_profile.TelegramAchievement.user_id == user_id,
                game_profile.TelegramAchievement.code == "find_plant",
            )
        )
    ).scalar_one_or_none()
    if exists is None:
        session.add(
            game_profile.TelegramAchievement(
                user_id=user_id,
                code="find_plant",
                earned_at=now,
            )
        )


async def _complete_find(user_id: int) -> dict:
    day, _, _ = game._today_bounds()
    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        challenge = (
            await session.execute(
                select(TelegramDailyFindPlant)
                .where(
                    TelegramDailyFindPlant.user_id == user_id,
                    TelegramDailyFindPlant.day == day,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if challenge is None:
            return {"ok": False}

        profile = await game._profile(session, user_id, True)
        daily = await game._daily(session, user_id, day, True)
        rewarded = False
        balance = None
        new_activity = challenge.activity_awarded_at is None

        if challenge.correct_at is None:
            challenge.correct_at = now
        if new_activity:
            challenge.activity_awarded_at = now
            profile.xp += game.XP_PER_ACTIVITY
            profile.updated_at = now
            await _ensure_achievement(session, user_id, now)

            if daily.reward_claimed_at is None:
                wallet = (
                    await session.execute(
                        select(WalletAccount)
                        .where(WalletAccount.user_id == user_id)
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if wallet is None:
                    wallet = WalletAccount(user_id=user_id, balance=0)
                    session.add(wallet)
                    await session.flush()

                wallet.balance += game.DAILY_REWARD_KISA
                balance = int(wallet.balance)
                daily.reward_claimed_at = now
                daily.reward_source = "find_plant"

                yesterday = day - timedelta(days=1)
                if profile.last_reward_date == yesterday:
                    profile.streak_days += 1
                elif profile.last_reward_date != day:
                    profile.streak_days = 1
                profile.last_reward_date = day
                profile.best_streak = max(profile.best_streak, profile.streak_days)

                session.add(
                    WalletTransaction(
                        user_id=user_id,
                        amount=game.DAILY_REWARD_KISA,
                        balance_after=wallet.balance,
                        kind="daily_reward",
                        reference_type="gamification",
                        reference_id=day.isoformat(),
                        details={"task": "find_plant", "day": day.isoformat()},
                    )
                )
                rewarded = True

        daily.updated_at = now
        await session.commit()
        return {
            "ok": True,
            "new": new_activity,
            "rewarded": rewarded,
            "balance": balance,
            "streak": int(profile.streak_days or 0),
            "xp": int(profile.xp or 0),
            "planting_id": challenge.planting_id,
        }


async def _answer(core, bot, query: dict, selected_slot: int) -> None:
    qid = query.get("id")
    tg = query.get("from")
    chat_id = ((query.get("message") or {}).get("chat") or {}).get("id")
    if not qid or tg is None or chat_id is None:
        return

    lang = core.language_for(tg)
    tr = _tr(lang)
    user, _ = await core.get_or_create_user(tg)
    item = await _challenge(user.id, create=True)
    if item is None:
        await bot.answer_callback_query(qid)
        await bot.send_message(chat_id, tr["unavailable"])
        return

    challenge, _planting, plant, slot, _photo, source = item
    if challenge.correct_at is not None:
        await bot.answer_callback_query(qid)
        await bot.send_message(chat_id, tr["done"])
        return

    if int(selected_slot) != int(slot.slot_number):
        await _mark_wrong(user.id)
        await bot.answer_callback_query(qid)
        await bot.send_message(
            chat_id,
            tr["wrong"].format(slot=selected_slot),
            reply_markup={
                "inline_keyboard": [
                    [{"text": tr["retry"], "callback_data": "game:find"}],
                    [{"text": tr["game"], "callback_data": "game:menu"}],
                ]
            },
        )
        return

    await bot.answer_callback_query(qid)
    result = await _complete_find(user.id)
    if not result.get("ok"):
        await bot.send_message(chat_id, tr["unavailable"])
        return

    name = escape(localized_value(plant.names or {}, lang, plant.code))
    lines = [tr["correct"], f"<b>{name}</b> · #{slot.rack_id}/{slot.slot_number}", tr["xp"].format(xp=game.XP_PER_ACTIVITY)]
    if result.get("rewarded"):
        lines.append(
            tr["reward"].format(
                balance=int(result.get("balance") or 0),
                streak=int(result.get("streak") or 0),
            )
        )
    else:
        lines.append(tr["reward_already"])
    caption = "\n\n".join(lines)

    markup = {"inline_keyboard": [[{"text": tr["game"], "callback_data": "game:menu"}]]}
    if source is not None:
        target = _target_path(user.telegram_user_id, challenge.day)
        try:
            _annotate_correct(source, target, slot.slot_number)
            await bot.send_photo(chat_id, target, caption=caption, reply_markup=markup)
            return
        except Exception:
            core.logger.exception("Could not annotate find-your-plant photo for user %s", user.id)

    await bot.send_message(chat_id, caption, reply_markup=markup)


async def _extended_game_menu(core, bot, chat_id: int, tg: dict) -> None:
    lang = core.language_for(tg)
    tr = game._tr(lang)
    ftr = _tr(lang)
    user, _ = await core.get_or_create_user(tg)
    snapshot = await game._snapshot(user.id)
    find_status = await _status(user.id)
    remaining = max(0, snapshot["target"] - snapshot["balance"])

    if find_status["done"]:
        find_line = f"✅ {ftr['label']}"
    elif find_status["available"]:
        find_line = f"▫️ {ftr['label']}"
    else:
        find_line = f"🔒 {ftr['label']} — {ftr['locked']}"

    text = (
        f"{tr['title']}\n\n{tr['done'] if snapshot['reward_done'] else tr['open']}\n\n"
        f"{game._task(tr['likes'], snapshot['likes'], game.LIKE_TARGET, snapshot['likes_done'])}\n"
        f"{game._task(tr['comments'], snapshot['comments'], game.COMMENT_TARGET, snapshot['comments_done'])}\n"
        f"{'✅' if snapshot['quiz_done'] else '▫️'} {tr['quiz']}\n"
        f"{find_line}\n\n"
        f"{tr['streak'].format(days=snapshot['streak'])}\n"
        f"{tr['xp'].format(xp=snapshot['xp'], level=game._level(snapshot['xp'], lang))}\n\n"
        f"{tr['goal'].format(balance=snapshot['balance'], target=snapshot['target'])}\n"
        f"<code>{game._bar(snapshot['balance'], snapshot['target'])}</code>\n"
        f"{tr['goal_ready'] if remaining == 0 else tr['goal_days'].format(days=remaining)}"
    )

    await bot.send_message(
        chat_id,
        text,
        reply_markup={
            "inline_keyboard": [
                [{"text": tr["quiz_button"], "callback_data": "game:quiz"}],
                [{"text": ftr["button"], "callback_data": "game:find"}],
                [{"text": tr["plants_button"], "callback_data": "menu:plants"}],
                [{"text": tr["back"], "callback_data": "menu:home"}],
            ]
        },
    )


def install(core) -> None:
    previous_handle_callback = core.handle_callback

    # The original game handler calls this module-global function after quiz
    # completion as well, so patching it keeps the fourth task visible everywhere.
    async def show_game(bot, chat_id: int, tg: dict) -> None:
        await _extended_game_menu(core, bot, chat_id, tg)

    game._show_game = show_game
    game_profile.ACHIEVEMENTS["find_plant"] = FIND_ACHIEVEMENT

    async def handle_callback(bot, query: dict) -> None:
        data = str(query.get("data") or "")
        if data == "game:find":
            qid = query.get("id")
            if qid:
                await bot.answer_callback_query(qid)
            tg = query.get("from")
            chat_id = ((query.get("message") or {}).get("chat") or {}).get("id")
            if tg is not None and chat_id is not None:
                await _show_find(core, bot, chat_id, tg)
            return

        if data.startswith("game:findanswer:"):
            try:
                selected = int(data.rsplit(":", 1)[-1])
            except ValueError:
                selected = 0
            if 1 <= selected <= 6:
                await _answer(core, bot, query, selected)
                return

        await previous_handle_callback(bot, query)

    core.handle_callback = handle_callback
