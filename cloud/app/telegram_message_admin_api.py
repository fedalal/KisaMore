from __future__ import annotations

import html
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User
from .security import get_admin_user, get_session
from .telegram.activity_notifier import TelegramActivityDelivery
from .telegram.message_models import TelegramOutboundMessage
from .telegram.models import TelegramUser


router = APIRouter(prefix="/api/v1/admin/telegram-users", tags=["admin-telegram-messages"])
_TAG_RE = re.compile(r"<[^>]+>")


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _plain_text(value: str | None) -> str:
    if not value:
        return ""
    return html.unescape(_TAG_RE.sub("", str(value))).strip()


@router.get("/{user_id}/messages")
async def telegram_user_messages(
    user_id: int,
    limit: int = 200,
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    """Return outbound Telegram history for one KisaMore user.

    New messages come from telegram_outbound_messages, which records every
    successful sendMessage/sendPhoto/sendVideo/sendInvoice call. Older lifecycle
    notifications are also shown from telegram_activity_deliveries when they
    predate the first full outbound-log row for this user.
    """
    user = await session.get(TelegramUser, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Telegram user not found")

    row_limit = max(1, min(int(limit), 500))
    sent_rows = list(
        (
            await session.execute(
                select(TelegramOutboundMessage)
                .where(TelegramOutboundMessage.telegram_user_id == user.telegram_user_id)
                .order_by(TelegramOutboundMessage.created_at.desc(), TelegramOutboundMessage.id.desc())
                .limit(row_limit)
            )
        ).scalars().all()
    )

    items = [
        {
            "id": f"outbound:{row.id}",
            "sent_at": _aware(row.created_at),
            "message_type": row.message_type,
            "text": _plain_text(row.text),
            "media_name": row.media_name,
            "telegram_message_id": row.telegram_message_id,
            "source": "outbound_log",
        }
        for row in sent_rows
    ]

    # Before the complete transport-level log existed, lifecycle notifications
    # were already persisted in the activity outbox. Include those older rows so
    # the admin page can show as much existing history as is actually available.
    first_full_log_at = None
    if sent_rows:
        first_full_log_at = min(_aware(row.created_at) for row in sent_rows if row.created_at is not None)

    legacy_stmt = (
        select(TelegramActivityDelivery)
        .where(
            TelegramActivityDelivery.telegram_user_id == user.telegram_user_id,
            TelegramActivityDelivery.status == "sent",
            TelegramActivityDelivery.sent_at.is_not(None),
        )
        .order_by(TelegramActivityDelivery.sent_at.desc())
        .limit(row_limit)
    )
    legacy_rows = list((await session.execute(legacy_stmt)).scalars().all())
    for row in legacy_rows:
        sent_at = _aware(row.sent_at)
        if first_full_log_at is not None and sent_at is not None and sent_at >= first_full_log_at:
            continue
        payload = row.payload or {}
        media_name = None
        photo_path = str(payload.get("photo_path") or "").strip()
        if photo_path:
            media_name = photo_path.rsplit("/", 1)[-1]
        items.append(
            {
                "id": f"legacy:{row.event_key}",
                "sent_at": sent_at,
                "message_type": "photo" if photo_path else str(row.kind or "notification"),
                "text": _plain_text(str(payload.get("text") or "")),
                "media_name": media_name,
                "telegram_message_id": None,
                "source": "legacy_notification",
            }
        )

    items.sort(
        key=lambda item: item.get("sent_at") or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return {
        "user_id": user.id,
        "telegram_user_id": user.telegram_user_id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "messages": items[:row_limit],
        "complete_history_since": first_full_log_at,
    }
