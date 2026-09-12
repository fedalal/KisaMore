from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx

from .message_models import TelegramOutboundMessage
from .profile_locales import BOT_PROFILE_LOCALIZATIONS, DEFAULT_LANGUAGE


logger = logging.getLogger(__name__)

HELP_COMMAND_DESCRIPTIONS = {
    "en": "Help",
    "ru": "Помощь",
    "de": "Hilfe",
    "fr": "Aide",
    "es": "Ayuda",
    "it": "Aiuto",
    "pt": "Ajuda",
    "pl": "Pomoc",
    "zh": "帮助",
}


def _commands_for(language_code: str, locale: dict) -> list[dict]:
    commands = list(locale["commands"])
    if not any(item.get("command") == "help" for item in commands):
        commands.append(
            {
                "command": "help",
                "description": HELP_COMMAND_DESCRIPTIONS.get(language_code, "Help"),
            }
        )
    return commands


async def _record_outbound_message(
    chat_id: int,
    *,
    message_type: str,
    text: str = "",
    media_name: str | None = None,
    media_path: str | None = None,
    telegram_result: dict | None = None,
) -> None:
    """Persist a successfully sent Telegram message without affecting delivery.

    Logging is deliberately best-effort: if PostgreSQL is temporarily
    unavailable after Telegram has accepted a message, the user must not receive
    a duplicate just because storing the audit copy failed.
    """
    try:
        from ..db import SessionLocal

        message_id = None
        if isinstance(telegram_result, dict):
            raw_id = telegram_result.get("message_id")
            if raw_id is not None:
                try:
                    message_id = int(raw_id)
                except (TypeError, ValueError):
                    message_id = None

        async with SessionLocal() as session:
            session.add(
                TelegramOutboundMessage(
                    telegram_user_id=int(chat_id),
                    message_type=str(message_type)[:24],
                    text=str(text or "") or None,
                    media_name=(str(media_name)[:255] if media_name else None),
                    media_path=(str(media_path) if media_path else None),
                    telegram_message_id=message_id,
                )
            )
            await session.commit()
    except Exception:
        logger.exception(
            "Could not persist outbound Telegram %s for chat %s",
            message_type,
            chat_id,
        )


class TelegramAPIError(RuntimeError):
    pass


class TelegramBotAPI:
    def __init__(self, token: str):
        self.token = token.strip()
        self.base_url = f"https://api.telegram.org/bot{self.token}" if self.token else ""

    async def call(self, method: str, payload: dict | None = None, *, timeout: float = 15.0):
        if not self.token:
            raise TelegramAPIError("Telegram bot token is not configured")
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{self.base_url}/{method}", json=payload or {})
            response.raise_for_status()
            data = response.json()
        if not data.get("ok"):
            raise TelegramAPIError(
                f"Telegram API {method} failed: {data.get('description', 'unknown error')}"
            )
        return data.get("result")

    async def configure_localized_profile(self) -> None:
        fallback = BOT_PROFILE_LOCALIZATIONS[DEFAULT_LANGUAGE]
        await self.call("setMyShortDescription", {"short_description": fallback["short_description"]})
        await self.call("setMyDescription", {"description": fallback["description"]})
        await self.call(
            "setMyCommands",
            {"commands": _commands_for(DEFAULT_LANGUAGE, fallback)},
        )
        for language_code, locale in BOT_PROFILE_LOCALIZATIONS.items():
            await self.call(
                "setMyShortDescription",
                {"short_description": locale["short_description"], "language_code": language_code},
            )
            await self.call(
                "setMyDescription",
                {"description": locale["description"], "language_code": language_code},
            )
            await self.call(
                "setMyCommands",
                {
                    "commands": _commands_for(language_code, locale),
                    "language_code": language_code,
                },
            )

    async def prepare_long_polling(self) -> None:
        await self.call("deleteWebhook", {"drop_pending_updates": False})
        await self.configure_localized_profile()

    async def get_updates(self, *, offset: int | None, timeout_seconds: int = 30) -> list[dict]:
        payload = {
            "timeout": timeout_seconds,
            "allowed_updates": ["message", "callback_query", "pre_checkout_query"],
        }
        if offset is not None:
            payload["offset"] = offset
        return await self.call("getUpdates", payload, timeout=float(timeout_seconds + 10)) or []

    async def send_message(self, chat_id: int, text: str, *, reply_markup: dict | None = None):
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        result = await self.call("sendMessage", payload)
        await _record_outbound_message(
            chat_id,
            message_type="text",
            text=text,
            telegram_result=result if isinstance(result, dict) else None,
        )
        return result

    async def send_photo(
        self,
        chat_id: int,
        photo_path: str | Path,
        *,
        caption: str = "",
        reply_markup: dict | None = None,
    ):
        if not self.token:
            raise TelegramAPIError("Telegram bot token is not configured")
        path = Path(photo_path)
        if not path.is_file():
            raise FileNotFoundError(path)
        data = {"chat_id": str(chat_id), "caption": caption, "parse_mode": "HTML"}
        if reply_markup is not None:
            data["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
        mime = "image/jpeg"
        if path.suffix.lower() == ".png":
            mime = "image/png"
        elif path.suffix.lower() == ".webp":
            mime = "image/webp"
        async with httpx.AsyncClient(timeout=30.0) as client:
            with path.open("rb") as fh:
                response = await client.post(
                    f"{self.base_url}/sendPhoto",
                    data=data,
                    files={"photo": (path.name, fh, mime)},
                )
            response.raise_for_status()
            payload = response.json()
        if not payload.get("ok"):
            raise TelegramAPIError(
                f"Telegram API sendPhoto failed: {payload.get('description', 'unknown error')}"
            )
        result = payload.get("result")
        await _record_outbound_message(
            chat_id,
            message_type="photo",
            text=caption,
            media_name=path.name,
            media_path=str(path),
            telegram_result=result if isinstance(result, dict) else None,
        )
        return result

    async def send_video(
        self,
        chat_id: int,
        video_path: str | Path,
        *,
        caption: str = "",
        reply_markup: dict | None = None,
    ):
        if not self.token:
            raise TelegramAPIError("Telegram bot token is not configured")
        path = Path(video_path)
        if not path.is_file():
            raise FileNotFoundError(path)
        data = {
            "chat_id": str(chat_id),
            "caption": caption,
            "parse_mode": "HTML",
            "supports_streaming": "true",
        }
        if reply_markup is not None:
            data["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
        async with httpx.AsyncClient(timeout=90.0) as client:
            with path.open("rb") as fh:
                response = await client.post(
                    f"{self.base_url}/sendVideo",
                    data=data,
                    files={"video": (path.name, fh, "video/mp4")},
                )
            response.raise_for_status()
            payload = response.json()
        if not payload.get("ok"):
            raise TelegramAPIError(
                f"Telegram API sendVideo failed: {payload.get('description', 'unknown error')}"
            )
        result = payload.get("result")
        await _record_outbound_message(
            chat_id,
            message_type="video",
            text=caption,
            media_name=path.name,
            media_path=str(path),
            telegram_result=result if isinstance(result, dict) else None,
        )
        return result

    async def answer_callback_query(
        self,
        callback_query_id: str,
        *,
        text: str | None = None,
        show_alert: bool = False,
    ):
        payload = {"callback_query_id": callback_query_id, "show_alert": show_alert}
        if text:
            payload["text"] = text[:200]
        return await self.call("answerCallbackQuery", payload)

    async def send_invoice(
        self,
        chat_id: int,
        *,
        title: str,
        description: str,
        payload: str,
        stars: int,
    ):
        result = await self.call(
            "sendInvoice",
            {
                "chat_id": chat_id,
                "title": title[:32],
                "description": description[:255],
                "payload": payload[:128],
                "provider_token": "",
                "currency": "XTR",
                "prices": [{"label": title[:32], "amount": stars}],
            },
        )
        await _record_outbound_message(
            chat_id,
            message_type="invoice",
            text=f"{title}\n{description}\n⭐ {stars}",
            telegram_result=result if isinstance(result, dict) else None,
        )
        return result

    async def answer_pre_checkout_query(
        self,
        pre_checkout_query_id: str,
        *,
        ok: bool,
        error_message: str | None = None,
    ):
        payload = {"pre_checkout_query_id": pre_checkout_query_id, "ok": ok}
        if error_message:
            payload["error_message"] = error_message[:200]
        return await self.call("answerPreCheckoutQuery", payload)
