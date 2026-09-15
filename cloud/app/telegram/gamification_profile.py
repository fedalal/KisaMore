from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, mapped_column

from ..db import SessionLocal
from ..models import Base
from .gamification import (
    TEXTS as GAME_TEXTS,
    TelegramDailyProgress,
    TelegramDailyQuiz,
    TelegramGamificationProfile,
)
from .models import TelegramUser


class TelegramAchievement(Base):
    __tablename__ = "telegram_achievements"
    __table_args__ = (
        UniqueConstraint("user_id", "code", name="uq_telegram_achievement_user_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_users.id"), index=True, nullable=False
    )
    code: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    earned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


ACHIEVEMENTS = {
    "first_reward": {
        "en": "🎯 First daily goal",
        "ru": "🎯 Первое задание дня",
        "de": "🎯 Erstes Tagesziel",
        "fr": "🎯 Premier objectif quotidien",
        "es": "🎯 Primer objetivo diario",
        "it": "🎯 Primo obiettivo giornaliero",
        "pt": "🎯 Primeira meta diária",
        "pl": "🎯 Pierwszy cel dnia",
        "zh": "🎯 首个每日目标",
    },
    "first_quiz": {
        "en": "🧠 Young botanist",
        "ru": "🧠 Юный ботаник",
        "de": "🧠 Junger Botaniker",
        "fr": "🧠 Jeune botaniste",
        "es": "🧠 Joven botánico",
        "it": "🧠 Giovane botanico",
        "pt": "🧠 Jovem botânico",
        "pl": "🧠 Młody botanik",
        "zh": "🧠 小小植物学家",
    },
    "likes_task": {
        "en": "❤️ Friend of plants",
        "ru": "❤️ Друг растений",
        "de": "❤️ Freund der Pflanzen",
        "fr": "❤️ Ami des plantes",
        "es": "❤️ Amigo de las plantas",
        "it": "❤️ Amico delle piante",
        "pt": "❤️ Amigo das plantas",
        "pl": "❤️ Przyjaciel roślin",
        "zh": "❤️ 植物之友",
    },
    "comments_task": {
        "en": "💬 Community voice",
        "ru": "💬 Голос сообщества",
        "de": "💬 Stimme der Community",
        "fr": "💬 Voix de la communauté",
        "es": "💬 Voz de la comunidad",
        "it": "💬 Voce della community",
        "pt": "💬 Voz da comunidade",
        "pl": "💬 Głos społeczności",
        "zh": "💬 社区之声",
    },
    "streak_3": {
        "en": "🔥 3 days in a row",
        "ru": "🔥 3 дня подряд",
        "de": "🔥 3 Tage in Folge",
        "fr": "🔥 3 jours de suite",
        "es": "🔥 3 días seguidos",
        "it": "🔥 3 giorni di fila",
        "pt": "🔥 3 dias seguidos",
        "pl": "🔥 3 dni z rzędu",
        "zh": "🔥 连续 3 天",
    },
    "streak_7": {
        "en": "🌿 Week with KisaMore",
        "ru": "🌿 Неделя с KisaMore",
        "de": "🌿 Eine Woche mit KisaMore",
        "fr": "🌿 Une semaine avec KisaMore",
        "es": "🌿 Una semana con KisaMore",
        "it": "🌿 Una settimana con KisaMore",
        "pt": "🌿 Uma semana com KisaMore",
        "pl": "🌿 Tydzień z KisaMore",
        "zh": "🌿 KisaMore 一周",
    },
    "streak_20": {
        "en": "🏆 20-day gardener",
        "ru": "🏆 Садовник 20 дней",
        "de": "🏆 20-Tage-Gärtner",
        "fr": "🏆 Jardinier 20 jours",
        "es": "🏆 Jardinero de 20 días",
        "it": "🏆 Giardiniere da 20 giorni",
        "pt": "🏆 Jardineiro de 20 dias",
        "pl": "🏆 Ogrodnik 20 dni",
        "zh": "🏆 20 天园丁",
    },
}

PROFILE_TEXT = {
    "en": {"title": "🎮 <b>Game progress</b>", "level": "Level", "xp": "XP", "streak": "Current streak", "best": "Best streak", "ach": "🏅 <b>Achievements</b>", "empty": "No achievements yet — complete a daily activity to earn the first one."},
    "ru": {"title": "🎮 <b>Игровой прогресс</b>", "level": "Уровень", "xp": "Опыт", "streak": "Текущая серия", "best": "Лучшая серия", "ach": "🏅 <b>Достижения</b>", "empty": "Пока нет достижений — выполните первое ежедневное задание."},
    "de": {"title": "🎮 <b>Spielfortschritt</b>", "level": "Level", "xp": "XP", "streak": "Aktuelle Serie", "best": "Beste Serie", "ach": "🏅 <b>Erfolge</b>", "empty": "Noch keine Erfolge."},
    "fr": {"title": "🎮 <b>Progression</b>", "level": "Niveau", "xp": "XP", "streak": "Série actuelle", "best": "Meilleure série", "ach": "🏅 <b>Succès</b>", "empty": "Aucun succès pour le moment."},
    "es": {"title": "🎮 <b>Progreso del juego</b>", "level": "Nivel", "xp": "XP", "streak": "Racha actual", "best": "Mejor racha", "ach": "🏅 <b>Logros</b>", "empty": "Aún no hay logros."},
    "it": {"title": "🎮 <b>Progressi di gioco</b>", "level": "Livello", "xp": "XP", "streak": "Serie attuale", "best": "Serie migliore", "ach": "🏅 <b>Obiettivi</b>", "empty": "Nessun obiettivo ancora."},
    "pt": {"title": "🎮 <b>Progresso no jogo</b>", "level": "Nível", "xp": "XP", "streak": "Sequência atual", "best": "Melhor sequência", "ach": "🏅 <b>Conquistas</b>", "empty": "Ainda não há conquistas."},
    "pl": {"title": "🎮 <b>Postęp w grze</b>", "level": "Poziom", "xp": "XP", "streak": "Aktualna seria", "best": "Najlepsza seria", "ach": "🏅 <b>Osiągnięcia</b>", "empty": "Brak osiągnięć."},
    "zh": {"title": "🎮 <b>游戏进度</b>", "level": "等级", "xp": "XP", "streak": "当前连续", "best": "最佳连续", "ach": "🏅 <b>成就</b>", "empty": "暂时还没有成就。"},
}

TRY_AGAIN = {
    "en": "🧠 Try again", "ru": "🧠 Попробовать ещё раз", "de": "🧠 Noch einmal",
    "fr": "🧠 Réessayer", "es": "🧠 Intentar de nuevo", "it": "🧠 Riprova",
    "pt": "🧠 Tentar novamente", "pl": "🧠 Spróbuj ponownie", "zh": "🧠 再试一次",
}


def _lang(core, tg: dict) -> str:
    code = core.language_for(tg)
    return code if code in PROFILE_TEXT else "en"


def _level(xp: int, lang: str) -> str:
    levels = (GAME_TEXTS.get(lang) or GAME_TEXTS["en"])["levels"]
    idx = 4 if xp >= 600 else 3 if xp >= 300 else 2 if xp >= 150 else 1 if xp >= 50 else 0
    return levels[idx]


def _effective_streak(profile: TelegramGamificationProfile) -> int:
    if profile.last_reward_date is None:
        return 0
    today = datetime.now(timezone.utc).date()
    if profile.last_reward_date < today - timedelta(days=1):
        return 0
    return int(profile.streak_days or 0)


async def _sync_achievements(user_id: int) -> list[str]:
    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        profile = await session.get(TelegramGamificationProfile, user_id)
        progress = list((await session.execute(
            select(TelegramDailyProgress).where(TelegramDailyProgress.user_id == user_id)
        )).scalars().all())

        desired: set[str] = set()
        if any(row.reward_claimed_at is not None for row in progress):
            desired.add("first_reward")
        if any(row.quiz_done for row in progress):
            desired.add("first_quiz")
        if any(row.likes_done for row in progress):
            desired.add("likes_task")
        if any(row.comments_done for row in progress):
            desired.add("comments_task")

        best = int(profile.best_streak or 0) if profile is not None else 0
        if best >= 3:
            desired.add("streak_3")
        if best >= 7:
            desired.add("streak_7")
        if best >= 20:
            desired.add("streak_20")

        existing = set((await session.execute(
            select(TelegramAchievement.code).where(TelegramAchievement.user_id == user_id)
        )).scalars().all())
        for code in sorted(desired - existing):
            session.add(TelegramAchievement(user_id=user_id, code=code, earned_at=now))
        if desired - existing:
            await session.commit()

        return list((await session.execute(
            select(TelegramAchievement.code)
            .where(TelegramAchievement.user_id == user_id)
            .order_by(TelegramAchievement.earned_at, TelegramAchievement.id)
        )).scalars().all())


async def _game_profile(user_id: int, lang: str) -> str:
    codes = await _sync_achievements(user_id)
    async with SessionLocal() as session:
        profile = await session.get(TelegramGamificationProfile, user_id)
    xp = int(profile.xp or 0) if profile is not None else 0
    streak = _effective_streak(profile) if profile is not None else 0
    best = int(profile.best_streak or 0) if profile is not None else 0
    tr = PROFILE_TEXT.get(lang) or PROFILE_TEXT["en"]
    achievements = [
        (ACHIEVEMENTS.get(code, {}).get(lang) or ACHIEVEMENTS.get(code, {}).get("en") or code)
        for code in codes
    ]
    achievement_text = "\n".join(f"• {item}" for item in achievements) if achievements else tr["empty"]
    return (
        f"{tr['title']}\n"
        f"{tr['level']}: <b>{_level(xp, lang)}</b>\n"
        f"{tr['xp']}: <b>{xp}</b>\n"
        f"🔥 {tr['streak']}: <b>{streak}</b>\n"
        f"🏆 {tr['best']}: <b>{best}</b>\n\n"
        f"{tr['ach']}\n{achievement_text}"
    )


async def _is_wrong_quiz_answer(user_id: int, plant_id: str) -> bool:
    async with SessionLocal() as session:
        quiz = (await session.execute(
            select(TelegramDailyQuiz)
            .where(TelegramDailyQuiz.user_id == user_id)
            .order_by(TelegramDailyQuiz.day.desc())
            .limit(1)
        )).scalar_one_or_none()
        if quiz is None or quiz.correct_at is not None:
            return False
        if str(quiz.plant_id) == str(plant_id):
            return False
        quiz.attempts += 1
        await session.commit()
        return True


def install(core) -> None:
    previous_handle_callback = core.handle_callback
    previous_show_profile = core.show_profile

    async def show_profile(bot, chat_id: int, tg: dict) -> None:
        lang = _lang(core, tg)
        user, wallet = await core.get_or_create_user(tg)
        username = f"@{escape(user.username)}" if user.username else "—"
        stats = await core.profile_stats(user.id)
        text = core.t(
            lang,
            "profile",
            name=escape(user.first_name or "—"),
            username=username,
            balance=wallet.balance,
        )
        text += core.st(
            lang,
            "profile_stats",
            likes=stats["likes"],
            comments=stats["comments"],
            follows=stats["follows"],
            gifts=stats["gifts"],
            spent=stats["kisa_spent"],
        )
        text += "\n\n" + await _game_profile(user.id, lang)
        await bot.send_message(chat_id, text, reply_markup=core.back_keyboard(lang))

    async def handle_callback(bot, query: dict) -> None:
        data = str(query.get("data") or "")
        if not data.startswith("game:answer:"):
            await previous_handle_callback(bot, query)
            return

        qid = query.get("id")
        tg = query.get("from")
        chat_id = ((query.get("message") or {}).get("chat") or {}).get("id")
        if not qid or tg is None or chat_id is None:
            return

        user, _ = await core.get_or_create_user(tg)
        plant_id = data.split(":", 2)[2]
        if not await _is_wrong_quiz_answer(user.id, plant_id):
            await previous_handle_callback(bot, query)
            return

        lang = _lang(core, tg)
        tr = GAME_TEXTS.get(lang) or GAME_TEXTS["en"]
        await bot.answer_callback_query(qid)
        await bot.send_message(
            chat_id,
            f"❌ {tr['quiz_wrong']}",
            reply_markup={
                "inline_keyboard": [[
                    {"text": TRY_AGAIN.get(lang, TRY_AGAIN["en"]), "callback_data": "game:quiz"}
                ]]
            },
        )

    core.show_profile = show_profile
    core.handle_callback = handle_callback
