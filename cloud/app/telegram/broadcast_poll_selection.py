from __future__ import annotations

import logging

from sqlalchemy import select

from ..db import SessionLocal
from . import broadcast_service as broadcasts
from .broadcast_models import (
    TelegramBroadcast,
    TelegramBroadcastAnswer,
    TelegramBroadcastOption,
)


logger = logging.getLogger(__name__)


def _keyboard(
    row: TelegramBroadcast,
    options: list[TelegramBroadcastOption],
    selected_ids: set[int],
) -> dict:
    rows = []
    for option in options:
        selected = int(option.id) in selected_ids
        label = f"✅ {option.text}" if selected else option.text
        rows.append(
            [
                {
                    "text": label[:60],
                    "callback_data": f"bc:{row.id}:{option.id}",
                }
            ]
        )

    rows.append(
        [
            {
                "text": broadcasts._ui(row, "done"),
                "callback_data": f"bcdone:{row.id}",
            }
        ]
    )
    if row.show_results_to_users:
        rows.append(
            [
                {
                    "text": broadcasts._ui(row, "results"),
                    "callback_data": f"bcres:{row.id}",
                }
            ]
        )
    return {"inline_keyboard": rows}


async def _handle_multiple(bot, query: dict, broadcast_id: int, option_id: int) -> bool:
    qid = query.get("id")
    tg = query.get("from") or {}
    telegram_user_id = tg.get("id")
    message = query.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    message_id = message.get("message_id")

    if not qid or telegram_user_id is None:
        return True

    async with SessionLocal() as session:
        row = await session.get(TelegramBroadcast, broadcast_id)
        if row is None or row.answer_mode != "multiple":
            return False

        option = await session.get(TelegramBroadcastOption, option_id)
        user, delivery = await broadcasts._target_user(
            session,
            broadcast_id,
            int(telegram_user_id),
        )
        if (
            option is None
            or option.broadcast_id != broadcast_id
            or user is None
            or delivery is None
        ):
            await bot.answer_callback_query(
                qid,
                text="This poll is not available",
                show_alert=True,
            )
            return True

        existing = (
            await session.execute(
                select(TelegramBroadcastAnswer).where(
                    TelegramBroadcastAnswer.broadcast_id == broadcast_id,
                    TelegramBroadcastAnswer.user_id == user.id,
                    TelegramBroadcastAnswer.option_id == option_id,
                )
            )
        ).scalar_one_or_none()

        if existing is None:
            session.add(
                TelegramBroadcastAnswer(
                    broadcast_id=broadcast_id,
                    option_id=option_id,
                    user_id=user.id,
                    created_at=broadcasts._now(),
                )
            )
        else:
            await session.delete(existing)

        await session.commit()

        selected_ids = {
            int(value)
            for value in (
                await session.execute(
                    select(TelegramBroadcastAnswer.option_id).where(
                        TelegramBroadcastAnswer.broadcast_id == broadcast_id,
                        TelegramBroadcastAnswer.user_id == user.id,
                    )
                )
            ).scalars().all()
        }
        options = await broadcasts._load_options(session, broadcast_id)
        markup = _keyboard(row, options, selected_ids)

    # Stop Telegram's loading spinner immediately. The persistent check mark in
    # the keyboard is the confirmation instead of a short-lived popup.
    await bot.answer_callback_query(qid)

    if chat_id is None or message_id is None:
        return True

    try:
        await bot.call(
            "editMessageReplyMarkup",
            {
                "chat_id": int(chat_id),
                "message_id": int(message_id),
                "reply_markup": markup,
            },
        )
    except Exception:
        # The answer is already safely stored. A Telegram edit failure should not
        # undo the vote; log it so we can diagnose old/deleted messages separately.
        logger.exception(
            "Could not refresh multi-select broadcast %s keyboard for Telegram user %s",
            broadcast_id,
            telegram_user_id,
        )
    return True


def install(core) -> None:
    previous_handle_callback = core.handle_callback

    async def handle_callback(bot, query: dict) -> None:
        data = str(query.get("data") or "")
        if data.startswith("bc:"):
            parts = data.split(":", 2)
            try:
                broadcast_id = int(parts[1])
                option_id = int(parts[2])
            except (IndexError, ValueError):
                await previous_handle_callback(bot, query)
                return

            if await _handle_multiple(bot, query, broadcast_id, option_id):
                return

        await previous_handle_callback(bot, query)

    core.handle_callback = handle_callback
