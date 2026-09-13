from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime, timezone

from ..config import get_settings
from ..db import SessionLocal, create_tables
from .bot import TelegramBotAPI
from .models import TelegramStarAccount, TelegramStarTransaction


logger = logging.getLogger(__name__)

SYNC_SECONDS = max(60, int(os.getenv("KISAMORE_TELEGRAM_STARS_SYNC_SECONDS", "300")))
MAX_TRANSACTIONS = max(100, min(2000, int(os.getenv("KISAMORE_TELEGRAM_STARS_MAX_TRANSACTIONS", "500"))))
PAGE_SIZE = 100


def _aware_from_unix(value) -> datetime:
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        timestamp = 0
    return datetime.fromtimestamp(max(0, timestamp), tz=timezone.utc)


def _transaction_parts(item: dict) -> tuple[str, dict]:
    source = item.get("source")
    if isinstance(source, dict):
        return "incoming", source
    receiver = item.get("receiver")
    if isinstance(receiver, dict):
        return "outgoing", receiver
    return "unknown", {}


def _identity(item: dict, direction: str) -> str:
    # Refunds can intentionally reuse the original Telegram transaction id.
    # Direction/date/amount keep the incoming purchase and outgoing refund as
    # separate ledger rows while still allowing a later refresh to update raw
    # metadata for the same operation.
    value = "|".join(
        (
            str(item.get("id") or ""),
            direction,
            str(item.get("date") or ""),
            str(item.get("amount") or 0),
            str(item.get("nanostar_amount") or 0),
        )
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


async def _fetch_transactions(bot: TelegramBotAPI) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while len(rows) < MAX_TRANSACTIONS:
        limit = min(PAGE_SIZE, MAX_TRANSACTIONS - len(rows))
        result = await bot.call(
            "getStarTransactions",
            {"offset": offset, "limit": limit},
        ) or {}
        batch = result.get("transactions") if isinstance(result, dict) else None
        if not isinstance(batch, list) or not batch:
            break
        rows.extend(item for item in batch if isinstance(item, dict))
        if len(batch) < limit:
            break
        offset += len(batch)
    return rows


async def sync_telegram_stars_once(bot: TelegramBotAPI) -> None:
    balance = await bot.call("getMyStarBalance") or {}
    transactions = await _fetch_transactions(bot)
    now = datetime.now(timezone.utc)

    async with SessionLocal() as session:
        account = await session.get(TelegramStarAccount, 1)
        if account is None:
            account = TelegramStarAccount(id=1)
            session.add(account)
        account.balance_stars = int(balance.get("amount") or 0)
        account.balance_nanostars = int(balance.get("nanostar_amount") or 0)
        account.synced_at = now
        account.last_error = None

        for item in transactions:
            direction, partner = _transaction_parts(item)
            identity_key = _identity(item, direction)
            row = await session.get(TelegramStarTransaction, identity_key)
            if row is None:
                row = TelegramStarTransaction(
                    identity_key=identity_key,
                    transaction_id=str(item.get("id") or ""),
                    amount_stars=int(item.get("amount") or 0),
                    direction=direction,
                    occurred_at=_aware_from_unix(item.get("date")),
                )
                session.add(row)

            user = partner.get("user") if isinstance(partner.get("user"), dict) else {}
            row.transaction_id = str(item.get("id") or "")
            row.amount_stars = int(item.get("amount") or 0)
            row.nanostar_amount = int(item.get("nanostar_amount") or 0)
            row.direction = direction
            row.partner_type = str(partner.get("type") or "") or None
            row.transaction_type = str(partner.get("transaction_type") or "") or None
            raw_user_id = user.get("id") if isinstance(user, dict) else None
            try:
                row.telegram_user_id = int(raw_user_id) if raw_user_id is not None else None
            except (TypeError, ValueError):
                row.telegram_user_id = None
            row.invoice_payload = (
                str(partner.get("invoice_payload"))[:128]
                if partner.get("invoice_payload") is not None
                else None
            )
            # JSON roundtrip guarantees that only plain JSON-compatible values
            # are persisted even if the Telegram client changes its internals.
            row.raw = json.loads(json.dumps(item, ensure_ascii=False))
            row.occurred_at = _aware_from_unix(item.get("date"))
            row.synced_at = now

        await session.commit()

    logger.info(
        "Telegram Stars synchronized: balance=%s, transactions=%s",
        int(balance.get("amount") or 0),
        len(transactions),
    )


async def _save_sync_error(exc: Exception) -> None:
    try:
        async with SessionLocal() as session:
            account = await session.get(TelegramStarAccount, 1)
            if account is None:
                account = TelegramStarAccount(id=1)
                session.add(account)
            account.last_error = f"{type(exc).__name__}: {exc}"[:1000]
            await session.commit()
    except Exception:
        logger.exception("Could not store Telegram Stars synchronization error")


async def telegram_stars_sync_loop() -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        logger.warning("Telegram Stars synchronization disabled: bot token is not configured")
        return

    # create_tables is idempotent and makes this worker safe to start before the
    # API container has created the new Stars accounting tables.
    await create_tables()
    bot = TelegramBotAPI(settings.telegram_bot_token)

    while True:
        try:
            await sync_telegram_stars_once(bot)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Telegram Stars synchronization failed: %s", exc)
            await _save_sync_error(exc)
        await asyncio.sleep(SYNC_SECONDS)
