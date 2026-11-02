"""Private Telegram approval cards for bookmaker *proposals* only.

An approval records user feedback; it NEVER creates/submits a wager.
"""
from __future__ import annotations

import asyncio
import argparse
import logging
import secrets
from datetime import datetime, timedelta, timezone
from html import escape

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from ..config import get_settings
from ..db import SessionLocal
from ..models import Base
from .admin_models import TelegramAdmin
from .bot import TelegramBotAPI
from .models import TelegramUser

log = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BookmakerProposal(Base):
    __tablename__ = "telegram_bookmaker_proposals"

    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    stake_rub: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


def buttons(proposal_id: str) -> dict:
    return {"inline_keyboard": [[
        {"text": "✅ Одобряю", "callback_data": f"betvote:{proposal_id}:yes"},
        {"text": "❌ Нет", "callback_data": f"betvote:{proposal_id}:no"},
    ]]}


async def handle_proposal_click(bot: TelegramBotAPI, query: dict) -> None:
    qid = str(query.get("id") or "")
    raw = str(query.get("data") or "")
    parts = raw.split(":")
    if len(parts) != 3 or parts[0] != "betvote" or parts[2] not in ("yes", "no"):
        if qid:
            await bot.answer_callback_query(qid, text="Неизвестная кнопка.", show_alert=True)
        return
    tg = query.get("from") or {}
    message = query.get("message") or {}
    chat = message.get("chat") or {}
    try:
        user_id = int(tg.get("id"))
        chat_id = int(chat.get("id"))
        message_id = int(message.get("message_id"))
    except (TypeError, ValueError):
        if qid:
            await bot.answer_callback_query(qid, text="Не удалось проверить сообщение.", show_alert=True)
        return

    state = "unavailable"
    decision = None
    async with SessionLocal() as session:
        result = await session.execute(
            select(BookmakerProposal).where(BookmakerProposal.id == parts[1]).with_for_update()
        )
        row = result.scalar_one_or_none()
        if row is None or row.telegram_user_id != user_id or row.chat_id != chat_id or row.message_id != message_id:
            state = "forbidden"
        elif row.status != "pending":
            state = "already"
        elif utcnow() >= row.expires_at:
            row.status = "expired"
            await session.commit()
            state = "expired"
        else:
            decision = "approved" if parts[2] == "yes" else "rejected"
            row.status = decision
            row.decided_at = utcnow()
            await session.commit()
            state = "recorded"

    if state == "forbidden":
        await bot.answer_callback_query(qid, text="Это подтверждение не для вашего аккаунта.", show_alert=True)
    elif state == "already":
        await bot.answer_callback_query(qid, text="Решение уже записано.", show_alert=True)
    elif state == "expired":
        await bot.answer_callback_query(qid, text="Предложение устарело. Запросите новый купон.", show_alert=True)
    elif state == "recorded":
        response = (
            "✅ Одобрение записано. Пари НЕ оформлено и деньги НЕ списаны."
            if decision == "approved" else
            "❌ Отклонено. Пари НЕ оформлено и деньги НЕ списаны."
        )
        await bot.answer_callback_query(qid, text=response, show_alert=True)
        try:
            await bot.call("editMessageReplyMarkup", {
                "chat_id": chat_id, "message_id": message_id,
                "reply_markup": {"inline_keyboard": []},
            })
        except Exception:
            log.exception("Could not remove bookmaker proposal keyboard: %s", parts[1])
        await bot.send_message(chat_id, response)
    else:
        await bot.answer_callback_query(qid, text="Не удалось найти предложение.", show_alert=True)


def install(core) -> None:
    previous = core.handle_callback

    async def handle_callback(bot, query: dict) -> None:
        if str(query.get("data") or "").startswith("betvote:"):
            await handle_proposal_click(bot, query)
            return
        await previous(bot, query)

    core.handle_callback = handle_callback


async def send_demo() -> None:
    """Send an interactive demo/proposal to the single active Telegram administrator."""
    async with SessionLocal() as session:
        admins = (await session.execute(
            select(TelegramUser.telegram_user_id)
            .join(TelegramAdmin, TelegramAdmin.user_id == TelegramUser.id)
            .where(TelegramAdmin.enabled.is_(True), TelegramUser.is_active.is_(True))
        )).scalars().all()
        if len(admins) != 1:
            raise RuntimeError(f"Expected exactly one active administrator, got {len(admins)}")
        recipient = int(admins[0])
        proposal_id = secrets.token_hex(8)
        text = (
            "📋 <b>Тест кнопок управления ставками</b>\n\n"
            "Пример: Наполи — Буде/Глимт, П1 (основное время).\n"
            "Сумма: <b>100 ₽</b>. Коэффициент из предыдущей проверки: 1,77.\n\n"
            "Нажмите <b>«Одобряю»</b> или <b>«Нет»b>, чтобы проверить "
            "сохранение решения.\n\n"
            "⚠️ <b>Это проверка кнопок, не реальная ставка.</b> "
            "Нажатие НЕ отправит купон букмекеру и НЕ спишет средства. "
            "Предложение действительно 30 минут."
        )
        text = text.replace("<b>«Нет»b>", "<b>«Нет»</b>")
        row = BookmakerProposal(
            id=proposal_id, telegram_user_id=recipient, chat_id=recipient,
            message_id=None, description="DEMO: Наполи — Буде/Глимт П1, кф 1.77",
            stake_rub=100, expires_at=utcnow() + timedelta(minutes=30),
        )
        session.add(row)
        await session.flush()
        bot = TelegramBotAPI(get_settings().telegram_bot_token)
        result = await bot.send_message(recipient, text, reply_markup=buttons(proposal_id))
        row.message_id = int(result["message_id"])
        await session.commit()
        print(f"BUTTON_CARD_SENT id={proposal_id} message_id={row.message_id}")


async def show_status() -> None:
    async with SessionLocal() as session:
        rows = (await session.execute(
            select(BookmakerProposal).order_by(BookmakerProposal.created_at.desc()).limit(5)
        )).scalars().all()
        for row in rows:
            print(f"id={row.id} status={row.status} stake={row.stake_rub} message_id={row.message_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("send-demo", "status"))
    args = parser.parse_args()
    asyncio.run(send_demo() if args.command == "send-demo" else show_status())
