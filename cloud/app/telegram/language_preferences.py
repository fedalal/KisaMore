from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, delete, select
from sqlalchemy.orm import Mapped, mapped_column

from ..db import SessionLocal
from ..models import Base
from .models import TelegramUser


SUPPORTED_LANGUAGES = ("en", "ru", "de", "fr", "es", "it", "pt", "pl", "zh")

LANGUAGE_NAMES = {
    "en": "🇬🇧 English",
    "ru": "🇷🇺 Русский",
    "de": "🇩🇪 Deutsch",
    "fr": "🇫🇷 Français",
    "es": "🇪🇸 Español",
    "it": "🇮🇹 Italiano",
    "pt": "🇵🇹 Português",
    "pl": "🇵🇱 Polski",
    "zh": "🇨🇳 中文",
}

BUTTON_TEXT = {
    "en": "🌐 Language",
    "ru": "🌐 Язык",
    "de": "🌐 Sprache",
    "fr": "🌐 Langue",
    "es": "🌐 Idioma",
    "it": "🌐 Lingua",
    "pt": "🌐 Idioma",
    "pl": "🌐 Język",
    "zh": "🌐 语言",
}

TITLE_TEXT = {
    "en": "🌐 <b>Language</b>\n\nChoose the language KisaMore should use.",
    "ru": "🌐 <b>Язык</b>\n\nВыберите язык, на котором KisaMore будет общаться с вами.",
    "de": "🌐 <b>Sprache</b>\n\nWähle die Sprache für KisaMore.",
    "fr": "🌐 <b>Langue</b>\n\nChoisissez la langue de KisaMore.",
    "es": "🌐 <b>Idioma</b>\n\nElige el idioma de KisaMore.",
    "it": "🌐 <b>Lingua</b>\n\nScegli la lingua di KisaMore.",
    "pt": "🌐 <b>Idioma</b>\n\nEscolha o idioma do KisaMore.",
    "pl": "🌐 <b>Język</b>\n\nWybierz język KisaMore.",
    "zh": "🌐 <b>语言</b>\n\n请选择 KisaMore 使用的语言。",
}

SAVED_TEXT = {
    "en": "✅ Language changed to English.",
    "ru": "✅ Язык изменён на русский.",
    "de": "✅ Sprache auf Deutsch geändert.",
    "fr": "✅ Langue changée en français.",
    "es": "✅ Idioma cambiado a español.",
    "it": "✅ Lingua impostata su italiano.",
    "pt": "✅ Idioma alterado para português.",
    "pl": "✅ Język zmieniono na polski.",
    "zh": "✅ 语言已切换为中文。",
}

AUTO_TEXT = {
    "en": "✅ KisaMore will now follow your Telegram language.",
    "ru": "✅ Теперь KisaMore будет использовать язык Telegram.",
    "de": "✅ KisaMore verwendet jetzt die Telegram-Sprache.",
    "fr": "✅ KisaMore utilise maintenant la langue de Telegram.",
    "es": "✅ KisaMore usará ahora el idioma de Telegram.",
    "it": "✅ KisaMore userà ora la lingua di Telegram.",
    "pt": "✅ O KisaMore agora usará o idioma do Telegram.",
    "pl": "✅ KisaMore będzie teraz używać języka Telegrama.",
    "zh": "✅ KisaMore 现在将跟随 Telegram 的语言。",
}


class TelegramLanguagePreference(Base):
    __tablename__ = "telegram_language_preferences"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_users.id"), primary_key=True
    )
    language: Mapped[str] = mapped_column(String(10), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


def _normalize(value: str | None) -> str:
    raw = (value or "en").strip().lower().replace("_", "-")
    base = raw.split("-", 1)[0]
    return base if base in SUPPORTED_LANGUAGES else "en"


async def _preference_for_tg_id(telegram_user_id: int) -> str | None:
    async with SessionLocal() as session:
        return (
            await session.execute(
                select(TelegramLanguagePreference.language)
                .join(TelegramUser, TelegramUser.id == TelegramLanguagePreference.user_id)
                .where(TelegramUser.telegram_user_id == telegram_user_id)
            )
        ).scalar_one_or_none()


async def _apply_preference(tg: dict | None) -> None:
    if not tg or tg.get("id") is None:
        return
    if "_kisamore_telegram_language" not in tg:
        tg["_kisamore_telegram_language"] = tg.get("language_code")
    preferred = await _preference_for_tg_id(int(tg["id"]))
    if preferred:
        tg["language_code"] = preferred


async def _get_preference(user_id: int) -> str | None:
    async with SessionLocal() as session:
        row = await session.get(TelegramLanguagePreference, user_id)
        return row.language if row is not None else None


async def _set_preference(user_id: int, language: str) -> None:
    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        row = await session.get(TelegramLanguagePreference, user_id)
        if row is None:
            row = TelegramLanguagePreference(
                user_id=user_id,
                language=language,
                updated_at=now,
            )
            session.add(row)
        else:
            row.language = language
            row.updated_at = now

        user = await session.get(TelegramUser, user_id)
        if user is not None:
            # Background notifications use TelegramUser.language_code, so keep it
            # aligned with the explicit KisaMore preference as well.
            user.language_code = language
            user.updated_at = now
        await session.commit()


async def _clear_preference(user_id: int, telegram_language: str | None) -> str:
    language = _normalize(telegram_language)
    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        await session.execute(
            delete(TelegramLanguagePreference).where(
                TelegramLanguagePreference.user_id == user_id
            )
        )
        user = await session.get(TelegramUser, user_id)
        if user is not None:
            user.language_code = telegram_language or language
            user.updated_at = now
        await session.commit()
    return language


def _language_keyboard(selected: str | None, back_text: str) -> dict:
    def button(code: str) -> dict:
        marker = "✅ " if selected == code else ""
        return {
            "text": f"{marker}{LANGUAGE_NAMES[code]}",
            "callback_data": f"lang:set:{code}",
        }

    auto_marker = "✅ " if selected is None else ""
    return {
        "inline_keyboard": [
            [button("en"), button("ru")],
            [button("de"), button("fr")],
            [button("es"), button("it")],
            [button("pt"), button("pl")],
            [button("zh")],
            [{"text": f"{auto_marker}📱 Telegram / Auto", "callback_data": "lang:auto"}],
            [{"text": back_text, "callback_data": "menu:home"}],
        ]
    }


def install(core) -> None:
    previous_main_keyboard = core.main_keyboard
    previous_handle_callback = core.handle_callback
    previous_handle_update = core.handle_update

    def main_keyboard(lang: str) -> dict:
        markup = previous_main_keyboard(lang)
        rows = list(markup.get("inline_keyboard") or [])
        rows.append([
            {
                "text": BUTTON_TEXT.get(lang, BUTTON_TEXT["en"]),
                "callback_data": "lang:menu",
            }
        ])
        return {"inline_keyboard": rows}

    async def show_language_menu(bot, chat_id: int, tg: dict) -> None:
        user, _ = await core.get_or_create_user(tg)
        selected = await _get_preference(user.id)
        lang = core.language_for(tg)
        await bot.send_message(
            chat_id,
            TITLE_TEXT.get(lang, TITLE_TEXT["en"]),
            reply_markup=_language_keyboard(selected, core.t(lang, "back_home")),
        )

    async def handle_callback(bot, query: dict) -> None:
        data = str(query.get("data") or "")
        if not data.startswith("lang:"):
            await previous_handle_callback(bot, query)
            return

        qid = query.get("id")
        tg = query.get("from")
        chat_id = ((query.get("message") or {}).get("chat") or {}).get("id")
        if not qid or tg is None or chat_id is None:
            return

        user, _ = await core.get_or_create_user(tg)

        if data == "lang:menu":
            await bot.answer_callback_query(qid)
            await show_language_menu(bot, chat_id, tg)
            return

        if data == "lang:auto":
            telegram_language = tg.get("_kisamore_telegram_language")
            lang = await _clear_preference(user.id, telegram_language)
            tg["language_code"] = lang
            await bot.answer_callback_query(qid)
            await bot.send_message(chat_id, AUTO_TEXT.get(lang, AUTO_TEXT["en"]))
            await core.show_home(bot, chat_id, tg)
            return

        parts = data.split(":", 2)
        if len(parts) == 3 and parts[1] == "set" and parts[2] in SUPPORTED_LANGUAGES:
            lang = parts[2]
            await _set_preference(user.id, lang)
            tg["language_code"] = lang
            await bot.answer_callback_query(qid)
            await bot.send_message(chat_id, SAVED_TEXT[lang])
            await core.show_home(bot, chat_id, tg)
            return

        await bot.answer_callback_query(qid)

    async def handle_update(bot, update: dict) -> None:
        if "message" in update:
            await _apply_preference((update.get("message") or {}).get("from"))
        elif "callback_query" in update:
            await _apply_preference((update.get("callback_query") or {}).get("from"))
        elif "pre_checkout_query" in update:
            await _apply_preference((update.get("pre_checkout_query") or {}).get("from"))
        await previous_handle_update(bot, update)

    core.main_keyboard = main_keyboard
    core.handle_callback = handle_callback
    core.handle_update = handle_update
