from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta, timezone
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, mapped_column

from ..config import get_settings
from ..db import SessionLocal
from ..models import Base, Plant
from .models import SocialComment, SocialReaction, WalletAccount, WalletTransaction
from .service import localized_value


LIKE_TARGET = 3
COMMENT_TARGET = 2
DAILY_REWARD_KISA = 1
XP_PER_ACTIVITY = 10
PLANT_IMAGE_DIR = Path("/srv/kisamore/data/plant-images")
settings = get_settings()


TEXTS = {
    "en": {
        "button": "🎮 Game", "title": "🎮 <b>KisaMore game</b>",
        "open": "Complete any activity today to earn <b>+Ⓚ 1</b>.",
        "done": "✅ Today's <b>+Ⓚ 1</b> reward has already been received.",
        "likes": "❤️ Like 3 plants", "comments": "💬 Write 2 comments", "quiz": "🧠 Guess the plant",
        "quiz_button": "🧠 Daily quiz", "plants_button": "🌱 Open plants", "back": "◀️ Main menu",
        "streak": "🔥 Streak: <b>{days} days</b>", "xp": "⭐ XP: <b>{xp}</b> · {level}",
        "goal": "🌱 Your plant: <b>Ⓚ {balance} / Ⓚ {target}</b>",
        "goal_ready": "🌱 You already have enough Kisa for the cheapest plant.",
        "goal_days": "About <b>{days}</b> more daily rewards to your first plant.",
        "quiz_title": "🧠 <b>Guess the plant</b>", "quiz_photo": "Which plant is shown in the photo?",
        "quiz_desc": "Which plant matches this description?\n\n<i>{description}</i>",
        "quiz_correct": "✅ Correct!", "quiz_wrong": "Not quite. Try another answer 🌱",
        "quiz_done": "✅ Today's quiz is already completed.",
        "quiz_unavailable": "There are not enough plants with quiz data yet.",
        "reward": "🎉 <b>Daily goal completed!</b>\nYou received <b>+Ⓚ 1</b>.\nNew balance: <b>Ⓚ {balance}</b>\n🔥 Streak: <b>{streak} days</b>",
        "activity": "✅ Activity completed! +{xp} XP.",
        "levels": ["🌱 Beginner", "🌿 Gardener", "🪴 Skilled gardener", "🌾 Farmer", "🏡 Greenhouse master"],
    },
    "ru": {
        "button": "🎮 Игра", "title": "🎮 <b>Игра KisaMore</b>",
        "open": "Выполните любое задание дня и получите сегодня <b>+Ⓚ 1</b>.",
        "done": "✅ Сегодняшняя награда <b>+Ⓚ 1</b> уже получена.",
        "likes": "❤️ Поставить 3 лайка растениям", "comments": "💬 Написать 2 комментария", "quiz": "🧠 Угадать растение",
        "quiz_button": "🧠 Викторина дня", "plants_button": "🌱 Открыть растения", "back": "◀️ Главное меню",
        "streak": "🔥 Серия: <b>{days} дн.</b>", "xp": "⭐ Опыт: <b>{xp} XP</b> · {level}",
        "goal": "🌱 Своё растение: <b>Ⓚ {balance} / Ⓚ {target}</b>",
        "goal_ready": "🌱 У вас уже хватает Kisa на самое доступное растение.",
        "goal_days": "Ещё примерно <b>{days}</b> ежедневных наград до первого растения.",
        "quiz_title": "🧠 <b>Угадайте растение</b>", "quiz_photo": "Какое растение изображено на фотографии?",
        "quiz_desc": "Какому растению подходит это описание?\n\n<i>{description}</i>",
        "quiz_correct": "✅ Верно!", "quiz_wrong": "Пока неверно. Попробуйте другой вариант 🌱",
        "quiz_done": "✅ Сегодняшняя викторина уже выполнена.",
        "quiz_unavailable": "Пока недостаточно растений с данными для викторины.",
        "reward": "🎉 <b>Задание дня выполнено!</b>\nНачислено <b>+Ⓚ 1</b>.\nНовый баланс: <b>Ⓚ {balance}</b>\n🔥 Серия: <b>{streak} дн.</b>",
        "activity": "✅ Активность выполнена! +{xp} XP.",
        "levels": ["🌱 Новичок", "🌿 Садовник", "🪴 Опытный садовник", "🌾 Фермер", "🏡 Мастер теплицы"],
    },
    "de": {"button":"🎮 Spiel","title":"🎮 <b>KisaMore Spiel</b>","open":"Schließe heute eine Aktivität ab und erhalte <b>+Ⓚ 1</b>.","done":"✅ Die heutige Belohnung <b>+Ⓚ 1</b> wurde bereits erhalten.","likes":"❤️ 3 Pflanzen liken","comments":"💬 2 Kommentare schreiben","quiz":"🧠 Pflanze erraten","quiz_button":"🧠 Tagesquiz","plants_button":"🌱 Pflanzen öffnen","back":"◀️ Hauptmenü","streak":"🔥 Serie: <b>{days} Tage</b>","xp":"⭐ XP: <b>{xp}</b> · {level}","goal":"🌱 Eigene Pflanze: <b>Ⓚ {balance} / Ⓚ {target}</b>","goal_ready":"🌱 Du hast genug Kisa für die günstigste Pflanze.","goal_days":"Noch etwa <b>{days}</b> Tagesbelohnungen.","quiz_title":"🧠 <b>Errate die Pflanze</b>","quiz_photo":"Welche Pflanze ist auf dem Foto?","quiz_desc":"Welche Pflanze passt zu dieser Beschreibung?\n\n<i>{description}</i>","quiz_correct":"✅ Richtig!","quiz_wrong":"Versuche eine andere Antwort 🌱","quiz_done":"✅ Das heutige Quiz ist abgeschlossen.","quiz_unavailable":"Noch nicht genug Pflanzen für das Quiz.","reward":"🎉 <b>Tagesziel erreicht!</b>\nDu erhältst <b>+Ⓚ 1</b>.\nNeuer Kontostand: <b>Ⓚ {balance}</b>\n🔥 Serie: <b>{streak} Tage</b>","activity":"✅ Aktivität abgeschlossen! +{xp} XP.","levels":["🌱 Anfänger","🌿 Gärtner","🪴 Erfahrener Gärtner","🌾 Farmer","🏡 Gewächshausmeister"]},
    "fr": {"button":"🎮 Jeu","title":"🎮 <b>Jeu KisaMore</b>","open":"Terminez une activité aujourd’hui pour gagner <b>+Ⓚ 1</b>.","done":"✅ La récompense du jour <b>+Ⓚ 1</b> est déjà reçue.","likes":"❤️ Aimer 3 plantes","comments":"💬 Écrire 2 commentaires","quiz":"🧠 Deviner la plante","quiz_button":"🧠 Quiz du jour","plants_button":"🌱 Ouvrir les plantes","back":"◀️ Menu principal","streak":"🔥 Série : <b>{days} jours</b>","xp":"⭐ XP : <b>{xp}</b> · {level}","goal":"🌱 Votre plante : <b>Ⓚ {balance} / Ⓚ {target}</b>","goal_ready":"🌱 Vous avez assez de Kisa pour la plante la moins chère.","goal_days":"Encore environ <b>{days}</b> récompenses quotidiennes.","quiz_title":"🧠 <b>Devinez la plante</b>","quiz_photo":"Quelle plante apparaît sur la photo ?","quiz_desc":"Quelle plante correspond à cette description ?\n\n<i>{description}</i>","quiz_correct":"✅ Correct !","quiz_wrong":"Essayez une autre réponse 🌱","quiz_done":"✅ Le quiz du jour est terminé.","quiz_unavailable":"Pas encore assez de plantes pour le quiz.","reward":"🎉 <b>Objectif du jour atteint !</b>\nVous recevez <b>+Ⓚ 1</b>.\nNouveau solde : <b>Ⓚ {balance}</b>\n🔥 Série : <b>{streak} jours</b>","activity":"✅ Activité terminée ! +{xp} XP.","levels":["🌱 Débutant","🌿 Jardinier","🪴 Jardinier expérimenté","🌾 Fermier","🏡 Maître de serre"]},
    "es": {"button":"🎮 Juego","title":"🎮 <b>Juego KisaMore</b>","open":"Completa una actividad hoy y gana <b>+Ⓚ 1</b>.","done":"✅ La recompensa de hoy <b>+Ⓚ 1</b> ya fue recibida.","likes":"❤️ Dar 3 me gusta","comments":"💬 Escribir 2 comentarios","quiz":"🧠 Adivinar la planta","quiz_button":"🧠 Quiz diario","plants_button":"🌱 Abrir plantas","back":"◀️ Menú principal","streak":"🔥 Racha: <b>{days} días</b>","xp":"⭐ XP: <b>{xp}</b> · {level}","goal":"🌱 Tu planta: <b>Ⓚ {balance} / Ⓚ {target}</b>","goal_ready":"🌱 Ya tienes Kisa suficiente para la planta más económica.","goal_days":"Unas <b>{days}</b> recompensas diarias más.","quiz_title":"🧠 <b>Adivina la planta</b>","quiz_photo":"¿Qué planta aparece en la foto?","quiz_desc":"¿Qué planta corresponde a esta descripción?\n\n<i>{description}</i>","quiz_correct":"✅ ¡Correcto!","quiz_wrong":"Prueba otra respuesta 🌱","quiz_done":"✅ El quiz de hoy ya está completado.","quiz_unavailable":"Todavía no hay suficientes plantas para el quiz.","reward":"🎉 <b>¡Objetivo diario completado!</b>\nRecibiste <b>+Ⓚ 1</b>.\nNuevo saldo: <b>Ⓚ {balance}</b>\n🔥 Racha: <b>{streak} días</b>","activity":"✅ ¡Actividad completada! +{xp} XP.","levels":["🌱 Principiante","🌿 Jardinero","🪴 Jardinero experto","🌾 Agricultor","🏡 Maestro del invernadero"]},
    "it": {"button":"🎮 Gioco","title":"🎮 <b>Gioco KisaMore</b>","open":"Completa un’attività oggi e ottieni <b>+Ⓚ 1</b>.","done":"✅ La ricompensa di oggi <b>+Ⓚ 1</b> è già stata ricevuta.","likes":"❤️ Metti 3 mi piace","comments":"💬 Scrivi 2 commenti","quiz":"🧠 Indovina la pianta","quiz_button":"🧠 Quiz del giorno","plants_button":"🌱 Apri piante","back":"◀️ Menu principale","streak":"🔥 Serie: <b>{days} giorni</b>","xp":"⭐ XP: <b>{xp}</b> · {level}","goal":"🌱 La tua pianta: <b>Ⓚ {balance} / Ⓚ {target}</b>","goal_ready":"🌱 Hai abbastanza Kisa per la pianta più economica.","goal_days":"Circa <b>{days}</b> ricompense giornaliere.","quiz_title":"🧠 <b>Indovina la pianta</b>","quiz_photo":"Quale pianta è mostrata nella foto?","quiz_desc":"Quale pianta corrisponde a questa descrizione?\n\n<i>{description}</i>","quiz_correct":"✅ Esatto!","quiz_wrong":"Prova un’altra risposta 🌱","quiz_done":"✅ Il quiz di oggi è già completato.","quiz_unavailable":"Non ci sono ancora abbastanza piante per il quiz.","reward":"🎉 <b>Obiettivo giornaliero completato!</b>\nHai ricevuto <b>+Ⓚ 1</b>.\nNuovo saldo: <b>Ⓚ {balance}</b>\n🔥 Serie: <b>{streak} giorni</b>","activity":"✅ Attività completata! +{xp} XP.","levels":["🌱 Principiante","🌿 Giardiniere","🪴 Giardiniere esperto","🌾 Coltivatore","🏡 Maestro della serra"]},
    "pt": {"button":"🎮 Jogo","title":"🎮 <b>Jogo KisaMore</b>","open":"Conclua uma atividade hoje e ganhe <b>+Ⓚ 1</b>.","done":"✅ A recompensa de hoje <b>+Ⓚ 1</b> já foi recebida.","likes":"❤️ Curtir 3 plantas","comments":"💬 Escrever 2 comentários","quiz":"🧠 Adivinhar a planta","quiz_button":"🧠 Quiz diário","plants_button":"🌱 Abrir plantas","back":"◀️ Menu principal","streak":"🔥 Sequência: <b>{days} dias</b>","xp":"⭐ XP: <b>{xp}</b> · {level}","goal":"🌱 Sua planta: <b>Ⓚ {balance} / Ⓚ {target}</b>","goal_ready":"🌱 Você já tem Kisa suficiente para a planta mais barata.","goal_days":"Cerca de <b>{days}</b> recompensas diárias.","quiz_title":"🧠 <b>Adivinhe a planta</b>","quiz_photo":"Qual planta aparece na foto?","quiz_desc":"Qual planta corresponde a esta descrição?\n\n<i>{description}</i>","quiz_correct":"✅ Certo!","quiz_wrong":"Tente outra resposta 🌱","quiz_done":"✅ O quiz de hoje já foi concluído.","quiz_unavailable":"Ainda não há plantas suficientes para o quiz.","reward":"🎉 <b>Meta diária concluída!</b>\nVocê recebeu <b>+Ⓚ 1</b>.\nNovo saldo: <b>Ⓚ {balance}</b>\n🔥 Sequência: <b>{streak} dias</b>","activity":"✅ Atividade concluída! +{xp} XP.","levels":["🌱 Iniciante","🌿 Jardineiro","🪴 Jardineiro experiente","🌾 Agricultor","🏡 Mestre da estufa"]},
    "pl": {"button":"🎮 Gra","title":"🎮 <b>Gra KisaMore</b>","open":"Ukończ dziś jedną aktywność i zdobądź <b>+Ⓚ 1</b>.","done":"✅ Dzisiejsza nagroda <b>+Ⓚ 1</b> została już odebrana.","likes":"❤️ Polub 3 rośliny","comments":"💬 Napisz 2 komentarze","quiz":"🧠 Zgadnij roślinę","quiz_button":"🧠 Quiz dnia","plants_button":"🌱 Otwórz rośliny","back":"◀️ Menu główne","streak":"🔥 Seria: <b>{days} dni</b>","xp":"⭐ XP: <b>{xp}</b> · {level}","goal":"🌱 Twoja roślina: <b>Ⓚ {balance} / Ⓚ {target}</b>","goal_ready":"🌱 Masz już dość Kisa na najtańszą roślinę.","goal_days":"Jeszcze około <b>{days}</b> dziennych nagród.","quiz_title":"🧠 <b>Zgadnij roślinę</b>","quiz_photo":"Jaka roślina jest na zdjęciu?","quiz_desc":"Jaka roślina pasuje do tego opisu?\n\n<i>{description}</i>","quiz_correct":"✅ Dobrze!","quiz_wrong":"Spróbuj innej odpowiedzi 🌱","quiz_done":"✅ Dzisiejszy quiz jest już ukończony.","quiz_unavailable":"Brakuje jeszcze roślin do quizu.","reward":"🎉 <b>Cel dnia ukończony!</b>\nOtrzymujesz <b>+Ⓚ 1</b>.\nNowe saldo: <b>Ⓚ {balance}</b>\n🔥 Seria: <b>{streak} dni</b>","activity":"✅ Aktywność ukończona! +{xp} XP.","levels":["🌱 Początkujący","🌿 Ogrodnik","🪴 Doświadczony ogrodnik","🌾 Rolnik","🏡 Mistrz szklarni"]},
    "zh": {"button":"🎮 游戏","title":"🎮 <b>KisaMore 游戏</b>","open":"今天完成任意一项任务即可获得 <b>+Ⓚ 1</b>。","done":"✅ 今天的 <b>+Ⓚ 1</b> 奖励已经领取。","likes":"❤️ 给 3 株植物点赞","comments":"💬 写 2 条评论","quiz":"🧠 猜植物","quiz_button":"🧠 每日问答","plants_button":"🌱 查看植物","back":"◀️ 主菜单","streak":"🔥 连续：<b>{days} 天</b>","xp":"⭐ XP：<b>{xp}</b> · {level}","goal":"🌱 你的植物：<b>Ⓚ {balance} / Ⓚ {target}</b>","goal_ready":"🌱 你的 Kisa 已足够租用价格最低的植物。","goal_days":"距离第一株植物大约还需 <b>{days}</b> 次每日奖励。","quiz_title":"🧠 <b>猜植物</b>","quiz_photo":"照片中是哪种植物？","quiz_desc":"哪种植物符合下面的描述？\n\n<i>{description}</i>","quiz_correct":"✅ 回答正确！","quiz_wrong":"再试一个答案吧 🌱","quiz_done":"✅ 今天的问答已经完成。","quiz_unavailable":"目前还没有足够的植物数据用于问答。","reward":"🎉 <b>每日目标完成！</b>\n获得 <b>+Ⓚ 1</b>。\n新余额：<b>Ⓚ {balance}</b>\n🔥 连续：<b>{streak} 天</b>","activity":"✅ 任务完成！+{xp} XP。","levels":["🌱 新手","🌿 园丁","🪴 熟练园丁","🌾 农场主","🏡 温室大师"]},
}


class TelegramGamificationProfile(Base):
    __tablename__ = "telegram_gamification_profiles"
    user_id: Mapped[int] = mapped_column(ForeignKey("telegram_users.id"), primary_key=True)
    xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    streak_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    best_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_reward_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TelegramDailyProgress(Base):
    __tablename__ = "telegram_daily_progress"
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_telegram_daily_progress"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("telegram_users.id"), index=True, nullable=False)
    day: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    likes_done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    comments_done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    quiz_done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reward_claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reward_source: Mapped[str | None] = mapped_column(String(24), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TelegramDailyQuiz(Base):
    __tablename__ = "telegram_daily_quizzes"
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_telegram_daily_quiz"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("telegram_users.id"), index=True, nullable=False)
    day: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    plant_id: Mapped[str] = mapped_column(ForeignKey("plants.id"), index=True, nullable=False)
    option_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    clue_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def _tr(lang: str):
    return TEXTS.get(lang) or TEXTS["en"]


def _today_bounds():
    try:
        tz = ZoneInfo(settings.farm_timezone)
    except Exception:
        tz = ZoneInfo("UTC")
    local_now = datetime.now(tz)
    day = local_now.date()
    start = datetime.combine(day, time.min, tzinfo=tz)
    return day, start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)


def _level(xp: int, lang: str) -> str:
    idx = 4 if xp >= 600 else 3 if xp >= 300 else 2 if xp >= 150 else 1 if xp >= 50 else 0
    return _tr(lang)["levels"][idx]


def _bar(balance: int, target: int) -> str:
    target = max(1, target)
    filled = max(0, min(10, int(max(0, balance) / target * 10)))
    return "█" * filled + "░" * (10 - filled)


async def _profile(session, user_id: int, lock: bool = False):
    stmt = select(TelegramGamificationProfile).where(TelegramGamificationProfile.user_id == user_id)
    if lock:
        stmt = stmt.with_for_update()
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        row = TelegramGamificationProfile(user_id=user_id, xp=0, streak_days=0, best_streak=0, updated_at=datetime.now(timezone.utc))
        session.add(row)
        await session.flush()
    return row


async def _daily(session, user_id: int, day: date, lock: bool = False):
    stmt = select(TelegramDailyProgress).where(TelegramDailyProgress.user_id == user_id, TelegramDailyProgress.day == day)
    if lock:
        stmt = stmt.with_for_update()
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        now = datetime.now(timezone.utc)
        row = TelegramDailyProgress(user_id=user_id, day=day, likes_done=False, comments_done=False, quiz_done=False, created_at=now, updated_at=now)
        session.add(row)
        await session.flush()
    return row


async def _complete(session, user_id: int, day: date, task: str):
    now = datetime.now(timezone.utc)
    daily = await _daily(session, user_id, day, True)
    profile = await _profile(session, user_id, True)
    attr = {"likes":"likes_done", "comments":"comments_done", "quiz":"quiz_done"}[task]
    new = not bool(getattr(daily, attr))
    if new:
        setattr(daily, attr, True)
        profile.xp += XP_PER_ACTIVITY
        profile.updated_at = now
    rewarded = False
    balance = None
    if new and daily.reward_claimed_at is None:
        wallet = (await session.execute(select(WalletAccount).where(WalletAccount.user_id == user_id).with_for_update())).scalar_one_or_none()
        if wallet is None:
            wallet = WalletAccount(user_id=user_id, balance=0)
            session.add(wallet)
            await session.flush()
        wallet.balance += DAILY_REWARD_KISA
        balance = int(wallet.balance)
        daily.reward_claimed_at = now
        daily.reward_source = task
        yesterday = day - timedelta(days=1)
        if profile.last_reward_date == yesterday:
            profile.streak_days += 1
        elif profile.last_reward_date != day:
            profile.streak_days = 1
        profile.last_reward_date = day
        profile.best_streak = max(profile.best_streak, profile.streak_days)
        session.add(WalletTransaction(user_id=user_id, amount=DAILY_REWARD_KISA, balance_after=wallet.balance, kind="daily_reward", reference_type="gamification", reference_id=day.isoformat(), details={"task":task,"day":day.isoformat()}))
        rewarded = True
    daily.updated_at = now
    return {"new":new, "rewarded":rewarded, "balance":balance, "streak":int(profile.streak_days)}


async def _sync_social(user_id: int):
    day, start, end = _today_bounds()
    async with SessionLocal() as session:
        likes = int((await session.execute(select(func.count(SocialReaction.id)).where(SocialReaction.user_id == user_id, SocialReaction.reaction == "like", SocialReaction.created_at >= start, SocialReaction.created_at < end))).scalar_one() or 0)
        comments = int((await session.execute(select(func.count(SocialComment.id)).where(SocialComment.user_id == user_id, SocialComment.status == "published", SocialComment.created_at >= start, SocialComment.created_at < end))).scalar_one() or 0)
        results = []
        if likes >= LIKE_TARGET:
            results.append(await _complete(session, user_id, day, "likes"))
        if comments >= COMMENT_TARGET:
            results.append(await _complete(session, user_id, day, "comments"))
        await _daily(session, user_id, day)
        await _profile(session, user_id)
        await session.commit()
    reward = next((r for r in results if r["rewarded"]), None)
    return {"likes":likes, "comments":comments, "new":any(r["new"] for r in results), "rewarded":bool(reward), "balance":reward["balance"] if reward else None, "streak":reward["streak"] if reward else None}


async def _complete_quiz(user_id: int):
    day, _, _ = _today_bounds()
    async with SessionLocal() as session:
        result = await _complete(session, user_id, day, "quiz")
        await session.commit()
        return result


async def _snapshot(user_id: int):
    social = await _sync_social(user_id)
    day, _, _ = _today_bounds()
    async with SessionLocal() as session:
        daily = await _daily(session, user_id, day)
        profile = await _profile(session, user_id)
        wallet = (await session.execute(select(WalletAccount).where(WalletAccount.user_id == user_id))).scalar_one_or_none()
        target = int((await session.execute(select(func.min(Plant.rental_price_kisa)).where(Plant.active.is_(True), Plant.rental_price_kisa > 0))).scalar_one_or_none() or 20)
        await session.commit()
        return {"likes":min(social["likes"],LIKE_TARGET), "comments":min(social["comments"],COMMENT_TARGET), "likes_done":daily.likes_done, "comments_done":daily.comments_done, "quiz_done":daily.quiz_done, "reward_done":daily.reward_claimed_at is not None, "balance":int(wallet.balance if wallet else 0), "target":max(1,target), "xp":int(profile.xp), "streak":int(profile.streak_days)}


def _image(plant: Plant):
    for raw in (plant.microgreen_image_name, plant.seed_image_name):
        name = Path(str(raw or "")).name
        if name and (PLANT_IMAGE_DIR / name).is_file():
            return PLANT_IMAGE_DIR / name
    return None


def _name(plant: Plant, lang: str):
    return localized_value(plant.names or {}, lang, plant.code)


def _description(plant: Plant, lang: str):
    return localized_value(plant.descriptions or {}, lang, "")


async def _quiz(user_id: int, lang: str):
    day, _, _ = _today_bounds()
    async with SessionLocal() as session:
        row = (await session.execute(select(TelegramDailyQuiz).where(TelegramDailyQuiz.user_id == user_id, TelegramDailyQuiz.day == day))).scalar_one_or_none()
        plants = list((await session.execute(select(Plant).where(Plant.active.is_(True)).order_by(Plant.code))).scalars().all())
        by_id = {p.id:p for p in plants}
        if row is not None:
            correct = by_id.get(row.plant_id)
            options = [by_id[x] for x in row.option_ids if x in by_id]
            if correct is not None and len(options) >= 2:
                return row, correct, options
        eligible = [p for p in plants if _image(p) is not None or _description(p, lang)]
        if len(plants) < 2 or not eligible:
            return None
        rng = random.Random(f"{user_id}:{day.isoformat()}")
        correct = rng.choice(eligible)
        others = [p for p in plants if p.id != correct.id]
        rng.shuffle(others)
        options = [correct] + others[:3]
        rng.shuffle(options)
        now = datetime.now(timezone.utc)
        row = TelegramDailyQuiz(user_id=user_id, day=day, plant_id=correct.id, option_ids=[p.id for p in options], clue_mode="photo" if _image(correct) else "description", attempts=0, created_at=now)
        session.add(row)
        await session.commit()
        return row, correct, options


async def _answer(user_id: int, plant_id: str):
    day, _, _ = _today_bounds()
    async with SessionLocal() as session:
        row = (await session.execute(select(TelegramDailyQuiz).where(TelegramDailyQuiz.user_id == user_id, TelegramDailyQuiz.day == day).with_for_update())).scalar_one_or_none()
        if row is None:
            return False, False
        if row.correct_at is not None:
            return True, True
        row.attempts += 1
        correct = str(row.plant_id) == str(plant_id)
        if correct:
            row.correct_at = datetime.now(timezone.utc)
        await session.commit()
        return True, correct


def _task(label: str, current: int, target: int, done: bool):
    return f"{'✅' if done else '▫️'} {label} — <b>{min(current,target)}/{target}</b>"


async def _show_game(core, bot, chat_id: int, tg: dict):
    lang = core.language_for(tg)
    tr = _tr(lang)
    user, _ = await core.get_or_create_user(tg)
    s = await _snapshot(user.id)
    remaining = max(0, s["target"] - s["balance"])
    text = (
        f"{tr['title']}\n\n{tr['done'] if s['reward_done'] else tr['open']}\n\n"
        f"{_task(tr['likes'],s['likes'],LIKE_TARGET,s['likes_done'])}\n"
        f"{_task(tr['comments'],s['comments'],COMMENT_TARGET,s['comments_done'])}\n"
        f"{'✅' if s['quiz_done'] else '▫️'} {tr['quiz']}\n\n"
        f"{tr['streak'].format(days=s['streak'])}\n{tr['xp'].format(xp=s['xp'],level=_level(s['xp'],lang))}\n\n"
        f"{tr['goal'].format(balance=s['balance'],target=s['target'])}\n<code>{_bar(s['balance'],s['target'])}</code>\n"
        f"{tr['goal_ready'] if remaining == 0 else tr['goal_days'].format(days=remaining)}"
    )
    await bot.send_message(chat_id, text, reply_markup={"inline_keyboard":[[{"text":tr["quiz_button"],"callback_data":"game:quiz"}],[{"text":tr["plants_button"],"callback_data":"menu:plants"}],[{"text":tr["back"],"callback_data":"menu:home"}]]})


async def _show_quiz(core, bot, chat_id: int, tg: dict):
    lang = core.language_for(tg)
    tr = _tr(lang)
    user, _ = await core.get_or_create_user(tg)
    s = await _snapshot(user.id)
    back = {"inline_keyboard":[[{"text":tr["back"],"callback_data":"game:menu"}]]}
    if s["quiz_done"]:
        await bot.send_message(chat_id, tr["quiz_done"], reply_markup=back)
        return
    item = await _quiz(user.id, lang)
    if item is None:
        await bot.send_message(chat_id, tr["quiz_unavailable"], reply_markup=back)
        return
    row, correct, options = item
    keyboard = {"inline_keyboard":[[{"text":f"🌱 {_name(p,lang)}"[:60],"callback_data":f"game:answer:{p.id}"}] for p in options] + [[{"text":tr["back"],"callback_data":"game:menu"}]]}
    if row.clue_mode == "photo" and _image(correct) is not None:
        await bot.send_photo(chat_id, _image(correct), caption=f"{tr['quiz_title']}\n\n{tr['quiz_photo']}", reply_markup=keyboard)
        return
    desc = escape(_description(correct, lang))
    if not desc:
        await bot.send_message(chat_id, tr["quiz_unavailable"], reply_markup=back)
        return
    await bot.send_message(chat_id, f"{tr['quiz_title']}\n\n{tr['quiz_desc'].format(description=desc)}", reply_markup=keyboard)


async def _notify(core, bot, chat_id: int, tg: dict, result: dict):
    tr = _tr(core.language_for(tg))
    if result.get("rewarded"):
        await bot.send_message(chat_id, tr["reward"].format(balance=int(result.get("balance") or 0),streak=int(result.get("streak") or 0)), reply_markup={"inline_keyboard":[[{"text":tr["button"],"callback_data":"game:menu"}]]})
    elif result.get("new"):
        await bot.send_message(chat_id, tr["activity"].format(xp=XP_PER_ACTIVITY), reply_markup={"inline_keyboard":[[{"text":tr["button"],"callback_data":"game:menu"}]]})


def install(core) -> None:
    previous_main_keyboard = core.main_keyboard
    previous_handle_callback = core.handle_callback
    previous_handle_update = core.handle_update

    def main_keyboard(lang: str):
        markup = previous_main_keyboard(lang)
        rows = list(markup.get("inline_keyboard") or [])
        rows.append([{"text":_tr(lang)["button"],"callback_data":"game:menu"}])
        return {"inline_keyboard":rows}

    async def handle_callback(bot, query: dict):
        data = str(query.get("data") or "")
        if not data.startswith("game:"):
            await previous_handle_callback(bot, query)
            return
        qid = query.get("id")
        tg = query.get("from")
        chat_id = ((query.get("message") or {}).get("chat") or {}).get("id")
        if not qid or tg is None or chat_id is None:
            return
        if data == "game:menu":
            await bot.answer_callback_query(qid)
            await _show_game(core, bot, chat_id, tg)
            return
        if data == "game:quiz":
            await bot.answer_callback_query(qid)
            await _show_quiz(core, bot, chat_id, tg)
            return
        if data.startswith("game:answer:"):
            user, _ = await core.get_or_create_user(tg)
            exists, correct = await _answer(user.id, data.split(":",2)[2])
            tr = _tr(core.language_for(tg))
            if not exists:
                await bot.answer_callback_query(qid)
                await _show_quiz(core, bot, chat_id, tg)
                return
            if not correct:
                await bot.answer_callback_query(qid, text=tr["quiz_wrong"])
                return
            await bot.answer_callback_query(qid, text=tr["quiz_correct"])
            result = await _complete_quiz(user.id)
            await _notify(core, bot, chat_id, tg, result)
            await _show_game(core, bot, chat_id, tg)
            return
        await bot.answer_callback_query(qid)

    async def handle_update(bot, update: dict):
        await previous_handle_update(bot, update)
        tg = None
        chat_id = None
        should_sync = False
        if "callback_query" in update:
            q = update.get("callback_query") or {}
            data = str(q.get("data") or "")
            tg = q.get("from")
            chat_id = ((q.get("message") or {}).get("chat") or {}).get("id")
            should_sync = data.startswith(("vote:","comment:"))
        elif "message" in update:
            m = update.get("message") or {}
            tg = m.get("from")
            chat_id = (m.get("chat") or {}).get("id")
            should_sync = bool(m.get("text"))
        if not should_sync or tg is None or chat_id is None:
            return
        try:
            user, _ = await core.get_or_create_user(tg)
            result = await _sync_social(user.id)
            await _notify(core, bot, int(chat_id), tg, result)
        except Exception:
            core.logger.exception("Telegram gamification activity sync failed")

    core.main_keyboard = main_keyboard
    core.handle_callback = handle_callback
    core.handle_update = handle_update
