from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from html import escape
import os

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError

from ..db import SessionLocal
from .models import TelegramUser, WalletAccount, WalletTransaction
from .promotion_models import TelegramPromotion, TelegramPromotionGrant


CHECK_SECONDS = max(5, int(os.getenv("KISAMORE_PROMOTION_CHECK_SECONDS", "20")))
GRANT_BATCH = max(1, min(500, int(os.getenv("KISAMORE_PROMOTION_GRANT_BATCH", "100"))))
NOTIFY_BATCH = max(1, min(200, int(os.getenv("KISAMORE_PROMOTION_NOTIFY_BATCH", "30"))))
MAX_NOTIFY_ATTEMPTS = 5


TEXTS = {
    "en": {"credited": "🎁 Added to your balance: <b>Ⓚ {amount}</b>\nNew balance: <b>Ⓚ {balance}</b>", "wallet": "💰 Open wallet"},
    "ru": {"credited": "🎁 Начислено на баланс: <b>Ⓚ {amount}</b>\nНовый баланс: <b>Ⓚ {balance}</b>", "wallet": "💰 Открыть кошелёк"},
    "de": {"credited": "🎁 Deinem Guthaben gutgeschrieben: <b>Ⓚ {amount}</b>\nNeuer Kontostand: <b>Ⓚ {balance}</b>", "wallet": "💰 Wallet öffnen"},
    "fr": {"credited": "🎁 Ajouté à votre solde : <b>Ⓚ {amount}</b>\nNouveau solde : <b>Ⓚ {balance}</b>", "wallet": "💰 Ouvrir le portefeuille"},
    "es": {"credited": "🎁 Añadido a tu saldo: <b>Ⓚ {amount}</b>\nNuevo saldo: <b>Ⓚ {balance}</b>", "wallet": "💰 Abrir monedero"},
    "it": {"credited": "🎁 Aggiunto al saldo: <b>Ⓚ {amount}</b>\nNuovo saldo: <b>Ⓚ {balance}</b>", "wallet": "💰 Apri portafoglio"},
    "pt": {"credited": "🎁 Adicionado ao saldo: <b>Ⓚ {amount}</b>\nNovo saldo: <b>Ⓚ {balance}</b>", "wallet": "💰 Abrir carteira"},
    "pl": {"credited": "🎁 Dodano do salda: <b>Ⓚ {amount}</b>\nNowe saldo: <b>Ⓚ {balance}</b>", "wallet": "💰 Otwórz portfel"},
    "zh": {"credited": "🎁 已添加到余额：<b>Ⓚ {amount}</b>\n新余额：<b>Ⓚ {balance}</b>", "wallet": "💰 打开钱包"},
}


def _language(value: str | None) -> str:
    code = (value or "en").lower().replace("_", "-").split("-", 1)[0]
    return code if code in TEXTS else "en"


def _candidate_query(promotion: TelegramPromotion):
    stmt = (
        select(TelegramUser.id)
        .outerjoin(
            TelegramPromotionGrant,
            and_(
                TelegramPromotionGrant.promotion_id == promotion.id,
                TelegramPromotionGrant.user_id == TelegramUser.id,
            ),
        )
        .where(
            TelegramUser.is_active.is_(True),
            TelegramPromotionGrant.user_id.is_(None),
        )
        .order_by(TelegramUser.id)
        .limit(GRANT_BATCH)
    )
    if promotion.audience == "new":
        stmt = stmt.where(
            TelegramUser.created_at >= promotion.start_at,
            TelegramUser.created_at < promotion.end_at,
        )
    elif promotion.audience == "existing":
        stmt = stmt.where(TelegramUser.created_at < promotion.start_at)
    else:
        # "all" means everybody who existed at any point through the promotion.
        stmt = stmt.where(TelegramUser.created_at < promotion.end_at)
    return stmt


async def _grant_one(promotion_id: int, user_id: int) -> bool:
    async with SessionLocal() as session:
        try:
            promotion = await session.get(TelegramPromotion, promotion_id)
            user = await session.get(TelegramUser, user_id)
            if promotion is None or user is None or not promotion.enabled or not user.is_active:
                return False
            now = datetime.now(timezone.utc)
            start = promotion.start_at
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            if now < start:
                return False

            existing = await session.get(
                TelegramPromotionGrant,
                {"promotion_id": promotion_id, "user_id": user_id},
            )
            if existing is not None:
                return False

            created = user.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            end = promotion.end_at
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)

            eligible = (
                (promotion.audience == "new" and start <= created < end)
                or (promotion.audience == "existing" and created < start)
                or (promotion.audience == "all" and created < end)
            )
            if not eligible:
                return False

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

            wallet.balance += int(promotion.amount_kisa)
            tx = WalletTransaction(
                user_id=user_id,
                amount=int(promotion.amount_kisa),
                balance_after=int(wallet.balance),
                kind="promotion_bonus",
                reference_type="promotion",
                reference_id=str(promotion.id),
                details={
                    "promotion_name": promotion.name,
                    "message": promotion.message,
                },
            )
            session.add(tx)
            await session.flush()
            session.add(
                TelegramPromotionGrant(
                    promotion_id=promotion.id,
                    user_id=user_id,
                    transaction_id=tx.id,
                    balance_after=int(wallet.balance),
                    granted_at=now,
                    notification_status="pending",
                    notification_attempts=0,
                )
            )
            await session.commit()
            return True
        except IntegrityError:
            # Unique promotion/user grant makes a retry or second worker harmless.
            await session.rollback()
            return False


async def discover_and_grant() -> int:
    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        promotions = list(
            (
                await session.execute(
                    select(TelegramPromotion)
                    .where(
                        TelegramPromotion.enabled.is_(True),
                        TelegramPromotion.start_at <= now,
                    )
                    .order_by(TelegramPromotion.id)
                )
            ).scalars().all()
        )

        work: list[tuple[int, int]] = []
        for promotion in promotions:
            user_ids = list(
                (await session.execute(_candidate_query(promotion))).scalars().all()
            )
            work.extend((promotion.id, int(user_id)) for user_id in user_ids)

    granted = 0
    for promotion_id, user_id in work:
        if await _grant_one(promotion_id, user_id):
            granted += 1
        await asyncio.sleep(0)
    return granted


async def send_pending(bot) -> tuple[int, int]:
    sent = 0
    failed = 0
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(TelegramPromotionGrant, TelegramPromotion, TelegramUser)
                .join(
                    TelegramPromotion,
                    TelegramPromotion.id == TelegramPromotionGrant.promotion_id,
                )
                .join(
                    TelegramUser,
                    TelegramUser.id == TelegramPromotionGrant.user_id,
                )
                .where(
                    TelegramPromotionGrant.notification_status == "pending",
                    TelegramPromotionGrant.notification_attempts < MAX_NOTIFY_ATTEMPTS,
                )
                .order_by(TelegramPromotionGrant.granted_at)
                .limit(NOTIFY_BATCH)
            )
        ).all()

        for grant, promotion, user in rows:
            try:
                lang = _language(user.language_code)
                locale = TEXTS[lang]
                text = (
                    f"🎉 <b>{escape(promotion.name)}</b>\n\n"
                    f"{escape(promotion.message)}\n\n"
                    + locale["credited"].format(
                        amount=int(promotion.amount_kisa),
                        balance=int(grant.balance_after),
                    )
                )
                await bot.send_message(
                    int(user.telegram_user_id),
                    text,
                    reply_markup={
                        "inline_keyboard": [[
                            {
                                "text": locale["wallet"],
                                "callback_data": "menu:wallet",
                            }
                        ]]
                    },
                )
                grant.notification_status = "sent"
                grant.notified_at = datetime.now(timezone.utc)
                grant.notification_error = None
                sent += 1
            except Exception as exc:
                grant.notification_attempts += 1
                grant.notification_error = f"{type(exc).__name__}: {exc}"[:2000]
                if grant.notification_attempts >= MAX_NOTIFY_ATTEMPTS:
                    grant.notification_status = "failed"
                failed += 1
            await session.commit()

    return sent, failed


async def promotion_loop(bot, core) -> None:
    while True:
        try:
            granted = await discover_and_grant()
            sent, failed = await send_pending(bot)
            if granted or sent or failed:
                core.logger.info(
                    "Telegram promotion pass: granted=%s sent=%s failed=%s",
                    granted,
                    sent,
                    failed,
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            core.logger.exception("Telegram promotion pass failed")
        await asyncio.sleep(CHECK_SECONDS)


def install(core) -> None:
    previous_loop = core.follow_notification_loop

    async def combined_loop(bot) -> None:
        await asyncio.gather(
            previous_loop(bot),
            promotion_loop(bot, core),
        )

    core.follow_notification_loop = combined_loop
