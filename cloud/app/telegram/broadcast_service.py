from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

from sqlalchemy import delete, func, select, update

from ..db import SessionLocal
from .broadcast_models import (
    TelegramBroadcast,
    TelegramBroadcastAnswer,
    TelegramBroadcastDelivery,
    TelegramBroadcastOption,
)
from .models import TelegramUser


CHECK_SECONDS = 2
BATCH_SIZE = 20
MAX_ATTEMPTS = 3
STALE_SENDING_MINUTES = 15
RATE_DELAY_SECONDS = 0.06
_RETRY_AFTER_RE = re.compile(r"retry_after=(\d+)s", re.IGNORECASE)
logger = logging.getLogger(__name__)

_UI = {
    "en": {"done": "✅ Done", "results": "📊 Results"},
    "ru": {"done": "✅ Готово", "results": "📊 Результаты"},
    "de": {"done": "✅ Fertig", "results": "📊 Ergebnisse"},
    "fr": {"done": "✅ Terminé", "results": "📊 Résultats"},
    "es": {"done": "✅ Listo", "results": "📊 Resultados"},
    "it": {"done": "✅ Fatto", "results": "📊 Risultati"},
    "pt": {"done": "✅ Concluir", "results": "📊 Resultados"},
    "pl": {"done": "✅ Gotowe", "results": "📊 Wyniki"},
    "zh": {"done": "✅ 完成", "results": "📊 结果"},
}


def _ui(row: TelegramBroadcast, key: str) -> str:
    lang = row.language_code if row.language_code in _UI else "en"
    return _UI[lang][key]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _message_text(row: TelegramBroadcast) -> str:
    parts: list[str] = []
    if row.text:
        parts.append(escape(row.text))
    if row.question:
        parts.append(f"<b>{escape(row.question)}</b>")
    return "\n\n".join(parts).strip()


def _keyboard(row: TelegramBroadcast, options: list[TelegramBroadcastOption]) -> dict | None:
    if row.answer_mode not in ("single", "multiple") or not options:
        return None
    rows = [
        [{"text": option.text[:60], "callback_data": f"bc:{row.id}:{option.id}"}]
        for option in options
    ]
    if row.answer_mode == "multiple":
        rows.append([{"text": _ui(row, "done"), "callback_data": f"bcdone:{row.id}"}])
    if row.show_results_to_users:
        rows.append([{"text": _ui(row, "results"), "callback_data": f"bcres:{row.id}"}])
    return {"inline_keyboard": rows}


async def _load_options(session, broadcast_id: int) -> list[TelegramBroadcastOption]:
    return list(
        (
            await session.execute(
                select(TelegramBroadcastOption)
                .where(TelegramBroadcastOption.broadcast_id == broadcast_id)
                .order_by(TelegramBroadcastOption.position)
            )
        ).scalars().all()
    )


async def _refresh_stats(session, row: TelegramBroadcast) -> None:
    counts = dict(
        (
            await session.execute(
                select(TelegramBroadcastDelivery.status, func.count(TelegramBroadcastDelivery.id))
                .where(TelegramBroadcastDelivery.broadcast_id == row.id)
                .group_by(TelegramBroadcastDelivery.status)
            )
        ).all()
    )
    row.sent_count = int(counts.get("sent", 0) or 0)
    row.failed_count = int(counts.get("failed", 0) or 0)
    if row.status != "cancelled" and not counts.get("pending", 0) and not counts.get("sending", 0):
        row.status = "completed"
        row.finished_at = row.finished_at or _now()
    row.updated_at = _now()


async def _next_batch() -> tuple[int | None, list[int]]:
    now = _now()
    stale_before = now - timedelta(minutes=STALE_SENDING_MINUTES)
    async with SessionLocal() as session:
        await session.execute(
            update(TelegramBroadcastDelivery)
            .where(
                TelegramBroadcastDelivery.status == "sending",
                TelegramBroadcastDelivery.updated_at < stale_before,
                TelegramBroadcastDelivery.attempts < MAX_ATTEMPTS,
            )
            .values(
                status="pending",
                last_error="Recovered after interrupted Telegram worker",
                updated_at=now,
            )
        )
        await session.execute(
            update(TelegramBroadcastDelivery)
            .where(
                TelegramBroadcastDelivery.status == "sending",
                TelegramBroadcastDelivery.updated_at < stale_before,
                TelegramBroadcastDelivery.attempts >= MAX_ATTEMPTS,
            )
            .values(
                status="failed",
                last_error="Telegram worker was interrupted during delivery",
                updated_at=now,
            )
        )

        row = (
            await session.execute(
                select(TelegramBroadcast)
                .where(TelegramBroadcast.status.in_(("pending", "sending")))
                .order_by(TelegramBroadcast.created_at, TelegramBroadcast.id)
                .limit(1)
            )
        ).scalar_one_or_none()
        if row is None:
            await session.commit()
            return None, []

        if row.status == "pending":
            row.status = "sending"
            row.started_at = row.started_at or now
            row.updated_at = now

        delivery_ids = list(
            (
                await session.execute(
                    select(TelegramBroadcastDelivery.id)
                    .where(
                        TelegramBroadcastDelivery.broadcast_id == row.id,
                        TelegramBroadcastDelivery.status == "pending",
                    )
                    .order_by(TelegramBroadcastDelivery.id)
                    .limit(BATCH_SIZE)
                )
            ).scalars().all()
        )
        if not delivery_ids:
            await _refresh_stats(session, row)
        await session.commit()
        return row.id, delivery_ids


async def _send_delivery(bot, delivery_id: int) -> float:
    async with SessionLocal() as session:
        delivery = (
            await session.execute(
                select(TelegramBroadcastDelivery)
                .where(TelegramBroadcastDelivery.id == delivery_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if delivery is None or delivery.status != "pending":
            return 0.0

        row = await session.get(TelegramBroadcast, delivery.broadcast_id)
        user = await session.get(TelegramUser, delivery.user_id)
        if row is None or row.status == "cancelled":
            delivery.status = "cancelled"
            delivery.updated_at = _now()
            await session.commit()
            return 0.0
        if user is None or not user.is_active:
            delivery.status = "failed"
            delivery.last_error = "Telegram user is inactive"
            delivery.updated_at = _now()
            await session.commit()
            return 0.0

        options = await _load_options(session, row.id)
        delivery.status = "sending"
        delivery.attempts += 1
        delivery.updated_at = _now()
        await session.commit()

        text = _message_text(row)
        markup = _keyboard(row, options)
        try:
            result = None
            if row.photo_path and Path(row.photo_path).is_file():
                if len(text) <= 900:
                    result = await bot.send_photo(
                        user.telegram_user_id,
                        row.photo_path,
                        caption=text,
                        reply_markup=markup,
                    )
                else:
                    await bot.send_photo(user.telegram_user_id, row.photo_path, caption="")
                    if text:
                        result = await bot.send_message(
                            user.telegram_user_id,
                            text,
                            reply_markup=markup,
                        )
            elif text:
                result = await bot.send_message(
                    user.telegram_user_id,
                    text,
                    reply_markup=markup,
                )
            else:
                raise RuntimeError("Broadcast has neither readable photo nor text")

            delivery.status = "sent"
            delivery.sent_at = _now()
            delivery.updated_at = delivery.sent_at
            delivery.last_error = None
            if isinstance(result, dict) and result.get("message_id") is not None:
                try:
                    delivery.telegram_message_id = int(result["message_id"])
                except (TypeError, ValueError):
                    delivery.telegram_message_id = None
            await session.commit()
            return RATE_DELAY_SECONDS
        except Exception as exc:
            message = str(exc)[:1000]
            lowered = message.lower()
            retry_match = _RETRY_AFTER_RE.search(message)
            blocked = any(
                marker in lowered
                for marker in (
                    "bot was blocked by the user",
                    "user is deactivated",
                    "chat not found",
                    "bot can't initiate conversation",
                )
            )
            delivery.last_error = message
            delivery.updated_at = _now()
            if blocked or delivery.attempts >= MAX_ATTEMPTS:
                delivery.status = "failed"
                if blocked:
                    user.is_active = False
            else:
                delivery.status = "pending"
            await session.commit()
            if retry_match:
                return float(min(max(int(retry_match.group(1)), 1), 60))
            return 0.5 if delivery.status == "pending" else RATE_DELAY_SECONDS


async def broadcast_delivery_loop(bot) -> None:
    while True:
        try:
            broadcast_id, delivery_ids = await _next_batch()
            if broadcast_id is None:
                await asyncio.sleep(CHECK_SECONDS)
                continue
            if not delivery_ids:
                await asyncio.sleep(0.5)
                continue
            for delivery_id in delivery_ids:
                delay = await _send_delivery(bot, delivery_id)
                if delay:
                    await asyncio.sleep(delay)
            async with SessionLocal() as session:
                row = await session.get(TelegramBroadcast, broadcast_id)
                if row is not None:
                    await _refresh_stats(session, row)
                    await session.commit()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Telegram broadcast delivery pass failed")
            await asyncio.sleep(CHECK_SECONDS)


async def _target_user(session, broadcast_id: int, telegram_user_id: int):
    user = (
        await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == telegram_user_id)
        )
    ).scalar_one_or_none()
    if user is None:
        return None, None
    delivery = (
        await session.execute(
            select(TelegramBroadcastDelivery).where(
                TelegramBroadcastDelivery.broadcast_id == broadcast_id,
                TelegramBroadcastDelivery.user_id == user.id,
                TelegramBroadcastDelivery.status.in_(("sent", "sending")),
            )
        )
    ).scalar_one_or_none()
    return user, delivery


async def _answer_option(bot, query: dict, broadcast_id: int, option_id: int) -> None:
    qid = query.get("id")
    tg = query.get("from") or {}
    telegram_user_id = tg.get("id")
    if not qid or telegram_user_id is None:
        return

    async with SessionLocal() as session:
        row = await session.get(TelegramBroadcast, broadcast_id)
        option = await session.get(TelegramBroadcastOption, option_id)
        user, delivery = await _target_user(session, broadcast_id, int(telegram_user_id))
        if (
            row is None
            or option is None
            or option.broadcast_id != broadcast_id
            or row.answer_mode not in ("single", "multiple")
            or user is None
            or delivery is None
        ):
            await bot.answer_callback_query(qid, text="This poll is not available", show_alert=True)
            return

        existing = (
            await session.execute(
                select(TelegramBroadcastAnswer).where(
                    TelegramBroadcastAnswer.broadcast_id == broadcast_id,
                    TelegramBroadcastAnswer.user_id == user.id,
                    TelegramBroadcastAnswer.option_id == option_id,
                )
            )
        ).scalar_one_or_none()

        if row.answer_mode == "single":
            await session.execute(
                delete(TelegramBroadcastAnswer).where(
                    TelegramBroadcastAnswer.broadcast_id == broadcast_id,
                    TelegramBroadcastAnswer.user_id == user.id,
                )
            )
            session.add(
                TelegramBroadcastAnswer(
                    broadcast_id=broadcast_id,
                    option_id=option_id,
                    user_id=user.id,
                    created_at=_now(),
                )
            )
            selected = True
        elif existing is not None:
            await session.delete(existing)
            selected = False
        else:
            session.add(
                TelegramBroadcastAnswer(
                    broadcast_id=broadcast_id,
                    option_id=option_id,
                    user_id=user.id,
                    created_at=_now(),
                )
            )
            selected = True
        await session.commit()

    prefix = "✅" if selected else "➖"
    await bot.answer_callback_query(qid, text=f"{prefix} {option.text[:160]}")


async def _show_results(bot, query: dict, broadcast_id: int) -> None:
    qid = query.get("id")
    tg = query.get("from") or {}
    telegram_user_id = tg.get("id")
    chat_id = ((query.get("message") or {}).get("chat") or {}).get("id")
    if not qid or telegram_user_id is None or chat_id is None:
        return

    async with SessionLocal() as session:
        row = await session.get(TelegramBroadcast, broadcast_id)
        user, delivery = await _target_user(session, broadcast_id, int(telegram_user_id))
        if row is None or not row.show_results_to_users or user is None or delivery is None:
            await bot.answer_callback_query(qid, text="Results are not available", show_alert=True)
            return
        options = await _load_options(session, broadcast_id)
        counts = dict(
            (
                await session.execute(
                    select(TelegramBroadcastAnswer.option_id, func.count(TelegramBroadcastAnswer.id))
                    .where(TelegramBroadcastAnswer.broadcast_id == broadcast_id)
                    .group_by(TelegramBroadcastAnswer.option_id)
                )
            ).all()
        )
        respondents = int(
            (
                await session.execute(
                    select(func.count(func.distinct(TelegramBroadcastAnswer.user_id))).where(
                        TelegramBroadcastAnswer.broadcast_id == broadcast_id
                    )
                )
            ).scalar_one()
            or 0
        )

    await bot.answer_callback_query(qid)
    lines = [f"📊 <b>{escape(row.question or 'Results')}</b>", ""]
    for option in options:
        count = int(counts.get(option.id, 0) or 0)
        percent = round(count / respondents * 100.0) if respondents else 0
        lines.append(f"• {escape(option.text)} — {count} ({percent}%)")
    lines.append("")
    lines.append(f"👥 {respondents}")
    await bot.send_message(chat_id, "\n".join(lines))


def install(core) -> None:
    previous_handle_callback = core.handle_callback
    previous_follow_notification_loop = core.follow_notification_loop

    async def handle_callback(bot, query: dict) -> None:
        data = str(query.get("data") or "")
        if data.startswith("bc:"):
            parts = data.split(":", 2)
            try:
                broadcast_id = int(parts[1])
                option_id = int(parts[2])
            except (IndexError, ValueError):
                return
            await _answer_option(bot, query, broadcast_id, option_id)
            return
        if data.startswith("bcdone:"):
            qid = query.get("id")
            if qid:
                await bot.answer_callback_query(qid, text="✅ OK")
            return
        if data.startswith("bcres:"):
            try:
                broadcast_id = int(data.split(":", 1)[1])
            except (IndexError, ValueError):
                return
            await _show_results(bot, query, broadcast_id)
            return
        await previous_handle_callback(bot, query)

    async def follow_notification_loop(bot) -> None:
        await asyncio.gather(
            previous_follow_notification_loop(bot),
            broadcast_delivery_loop(bot),
        )

    core.handle_callback = handle_callback
    core.follow_notification_loop = follow_notification_loop
