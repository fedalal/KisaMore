from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from html import escape

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, mapped_column

from ..db import SessionLocal
from ..models import Base
from .models import TelegramUser, WalletAccount, WalletTransaction


CHECK_SECONDS = 5
MAX_ATTEMPTS = 5


class TelegramWalletGiftState(Base):
    """Cursor for discovering new admin gifts without replaying old history."""

    __tablename__ = "telegram_wallet_gift_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    last_seen_transaction_id: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    initialized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TelegramWalletGiftDelivery(Base):
    """Persistent delivery marker for one admin-gift wallet transaction."""

    __tablename__ = "telegram_wallet_gift_deliveries"

    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("wallet_transactions.id"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_users.id"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


TEXTS = {
    "en": {
        "message": "🎁 <b>A gift from KisaMore!</b>\n\nYour wallet has received <b>Ⓚ {amount}</b>.\nNew balance: <b>Ⓚ {balance}</b>",
        "note": "Message from KisaMore",
        "button": "💰 Open wallet",
    },
    "ru": {
        "message": "🎁 <b>Подарок от KisaMore!</b>\n\nНа ваш кошелёк начислено <b>Ⓚ {amount}</b>.\nНовый баланс: <b>Ⓚ {balance}</b>",
        "note": "Сообщение от KisaMore",
        "button": "💰 Открыть кошелёк",
    },
    "de": {
        "message": "🎁 <b>Ein Geschenk von KisaMore!</b>\n\nDeinem Wallet wurden <b>Ⓚ {amount}</b> gutgeschrieben.\nNeuer Kontostand: <b>Ⓚ {balance}</b>",
        "note": "Nachricht von KisaMore",
        "button": "💰 Wallet öffnen",
    },
    "fr": {
        "message": "🎁 <b>Un cadeau de KisaMore !</b>\n\nVotre portefeuille a reçu <b>Ⓚ {amount}</b>.\nNouveau solde : <b>Ⓚ {balance}</b>",
        "note": "Message de KisaMore",
        "button": "💰 Ouvrir le portefeuille",
    },
    "es": {
        "message": "🎁 <b>¡Un regalo de KisaMore!</b>\n\nSe han añadido <b>Ⓚ {amount}</b> a tu monedero.\nNuevo saldo: <b>Ⓚ {balance}</b>",
        "note": "Mensaje de KisaMore",
        "button": "💰 Abrir monedero",
    },
    "it": {
        "message": "🎁 <b>Un regalo da KisaMore!</b>\n\nSono stati aggiunti <b>Ⓚ {amount}</b> al tuo portafoglio.\nNuovo saldo: <b>Ⓚ {balance}</b>",
        "note": "Messaggio da KisaMore",
        "button": "💰 Apri portafoglio",
    },
    "pt": {
        "message": "🎁 <b>Um presente da KisaMore!</b>\n\nForam adicionados <b>Ⓚ {amount}</b> à sua carteira.\nNovo saldo: <b>Ⓚ {balance}</b>",
        "note": "Mensagem da KisaMore",
        "button": "💰 Abrir carteira",
    },
    "pl": {
        "message": "🎁 <b>Prezent od KisaMore!</b>\n\nDo Twojego portfela dodano <b>Ⓚ {amount}</b>.\nNowe saldo: <b>Ⓚ {balance}</b>",
        "note": "Wiadomość od KisaMore",
        "button": "💰 Otwórz portfel",
    },
    "zh": {
        "message": "🎁 <b>来自 KisaMore 的礼物！</b>\n\n您的钱包已收到 <b>Ⓚ {amount}</b>。\n新余额：<b>Ⓚ {balance}</b>",
        "note": "来自 KisaMore 的消息",
        "button": "💰 打开钱包",
    },
}


def _language(value: str | None) -> str:
    code = (value or "en").lower().replace("_", "-").split("-", 1)[0]
    return code if code in TEXTS else "en"


async def discover_new_gifts() -> int:
    """Create delivery rows for gifts created after notifier activation.

    On the first deployment we intentionally baseline at the newest existing
    admin-gift transaction so users do not receive notifications for historical
    gifts.
    """
    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        state = await session.get(TelegramWalletGiftState, 1)
        if state is None:
            latest = int(
                (
                    await session.execute(
                        select(func.coalesce(func.max(WalletTransaction.id), 0)).where(
                            WalletTransaction.kind == "admin_gift"
                        )
                    )
                ).scalar_one()
                or 0
            )
            session.add(
                TelegramWalletGiftState(
                    id=1,
                    last_seen_transaction_id=latest,
                    initialized_at=now,
                    updated_at=now,
                )
            )
            await session.commit()
            return 0

        rows = (
            await session.execute(
                select(WalletTransaction.id, WalletTransaction.user_id)
                .where(
                    WalletTransaction.kind == "admin_gift",
                    WalletTransaction.id > state.last_seen_transaction_id,
                )
                .order_by(WalletTransaction.id)
                .limit(100)
            )
        ).all()
        if not rows:
            return 0

        created = 0
        for transaction_id, user_id in rows:
            if await session.get(TelegramWalletGiftDelivery, int(transaction_id)) is None:
                session.add(
                    TelegramWalletGiftDelivery(
                        transaction_id=int(transaction_id),
                        user_id=int(user_id),
                        status="pending",
                        attempts=0,
                        created_at=now,
                    )
                )
                created += 1

        state.last_seen_transaction_id = int(rows[-1][0])
        state.updated_at = now
        await session.commit()
        return created


async def send_pending(bot) -> tuple[int, int]:
    sent = 0
    failed = 0
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(TelegramWalletGiftDelivery, WalletTransaction, TelegramUser)
                .join(
                    WalletTransaction,
                    WalletTransaction.id == TelegramWalletGiftDelivery.transaction_id,
                )
                .join(TelegramUser, TelegramUser.id == TelegramWalletGiftDelivery.user_id)
                .where(
                    TelegramWalletGiftDelivery.status == "pending",
                    TelegramWalletGiftDelivery.attempts < MAX_ATTEMPTS,
                )
                .order_by(TelegramWalletGiftDelivery.transaction_id)
                .limit(30)
            )
        ).all()

        for delivery, transaction, user in rows:
            try:
                balance = transaction.balance_after
                if balance is None:
                    balance = (
                        await session.execute(
                            select(WalletAccount.balance).where(WalletAccount.user_id == user.id)
                        )
                    ).scalar_one_or_none()
                lang = _language(user.language_code)
                locale = TEXTS[lang]
                text = locale["message"].format(
                    amount=int(transaction.amount),
                    balance=int(balance or 0),
                )
                reason = str((transaction.details or {}).get("reason") or "").strip()
                if reason:
                    text += f"\n\n💬 <b>{locale['note']}:</b>\n{escape(reason)}"
                await bot.send_message(
                    int(user.telegram_user_id),
                    text,
                    reply_markup={
                        "inline_keyboard": [[
                            {
                                "text": locale["button"],
                                "callback_data": "menu:wallet",
                            }
                        ]]
                    },
                )
                delivery.status = "sent"
                delivery.sent_at = datetime.now(timezone.utc)
                delivery.last_error = None
                sent += 1
            except Exception as exc:
                delivery.attempts += 1
                delivery.last_error = f"{type(exc).__name__}: {exc}"[:2000]
                if delivery.attempts >= MAX_ATTEMPTS:
                    delivery.status = "failed"
                failed += 1
            await session.commit()

    return sent, failed


def install(core) -> None:
    previous_loop = core.follow_notification_loop

    async def wallet_gift_loop(bot) -> None:
        while True:
            try:
                discovered = await discover_new_gifts()
                sent, failed = await send_pending(bot)
                if discovered or sent or failed:
                    core.logger.info(
                        "Telegram wallet gift pass: discovered=%s sent=%s failed=%s",
                        discovered,
                        sent,
                        failed,
                    )
            except asyncio.CancelledError:
                raise
            except Exception:
                core.logger.exception("Telegram wallet gift notification pass failed")
            await asyncio.sleep(CHECK_SECONDS)

    async def combined_loop(bot) -> None:
        await asyncio.gather(
            previous_loop(bot),
            wallet_gift_loop(bot),
        )

    core.follow_notification_loop = combined_loop
