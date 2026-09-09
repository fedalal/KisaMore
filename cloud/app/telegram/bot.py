from __future__ import annotations

import httpx


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
            raise TelegramAPIError(f"Telegram API {method} failed: {data.get('description', 'unknown error')}")
        return data.get("result")

    async def prepare_long_polling(self) -> None:
        await self.call("deleteWebhook", {"drop_pending_updates": False})
        await self.call("setMyCommands", {"commands": [
            {"command": "start", "description": "Открыть KisaMore"},
            {"command": "plants", "description": "Текущие растения"},
            {"command": "garden", "description": "Мой сад"},
            {"command": "wallet", "description": "Кошелёк Kisa"},
            {"command": "profile", "description": "Мой профиль"},
            {"command": "terms", "description": "Условия использования"},
            {"command": "paysupport", "description": "Поддержка по платежам"},
        ]})

    async def get_updates(self, *, offset: int | None, timeout_seconds: int = 30) -> list[dict]:
        payload = {"timeout": timeout_seconds, "allowed_updates": ["message", "callback_query", "pre_checkout_query"]}
        if offset is not None:
            payload["offset"] = offset
        return await self.call("getUpdates", payload, timeout=float(timeout_seconds + 10)) or []

    async def send_message(self, chat_id: int, text: str, *, reply_markup: dict | None = None):
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "link_preview_options": {"is_disabled": True}}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return await self.call("sendMessage", payload)

    async def answer_callback_query(self, callback_query_id: str, *, text: str | None = None, show_alert: bool = False):
        payload = {"callback_query_id": callback_query_id, "show_alert": show_alert}
        if text:
            payload["text"] = text
        return await self.call("answerCallbackQuery", payload)

    async def send_invoice(self, chat_id: int, *, title: str, description: str, payload: str, stars: int):
        return await self.call("sendInvoice", {
            "chat_id": chat_id,
            "title": title[:32],
            "description": description[:255],
            "payload": payload[:128],
            "provider_token": "",
            "currency": "XTR",
            "prices": [{"label": title[:32], "amount": stars}],
        })

    async def answer_pre_checkout_query(self, pre_checkout_query_id: str, *, ok: bool, error_message: str | None = None):
        payload = {"pre_checkout_query_id": pre_checkout_query_id, "ok": ok}
        if error_message:
            payload["error_message"] = error_message
        return await self.call("answerPreCheckoutQuery", payload)
