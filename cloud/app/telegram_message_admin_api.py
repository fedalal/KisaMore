from __future__ import annotations

import html
import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
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


def _existing_path(value: str | None) -> Path | None:
    raw = (value or "").strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_file() else None


def _legacy_media_map(rows: list[TelegramActivityDelivery]) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in rows:
        payload = row.payload or {}
        raw = str(payload.get("photo_path") or payload.get("video_path") or "").strip()
        path = _existing_path(raw)
        if path is not None:
            result.setdefault(path.name, str(path))
    return result


async def _user_or_404(session: AsyncSession, user_id: int) -> TelegramUser:
    user = await session.get(TelegramUser, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Telegram user not found")
    return user


async def _legacy_rows_for_user(
    session: AsyncSession,
    telegram_user_id: int,
    limit: int = 500,
) -> list[TelegramActivityDelivery]:
    return list(
        (
            await session.execute(
                select(TelegramActivityDelivery)
                .where(
                    TelegramActivityDelivery.telegram_user_id == telegram_user_id,
                    TelegramActivityDelivery.status == "sent",
                    TelegramActivityDelivery.sent_at.is_not(None),
                )
                .order_by(TelegramActivityDelivery.sent_at.desc())
                .limit(max(1, min(limit, 1000)))
            )
        ).scalars().all()
    )


@router.get("/{user_id}/messages")
async def telegram_user_messages(
    user_id: int,
    limit: int = 200,
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    """Return outbound Telegram history for one KisaMore user."""
    user = await _user_or_404(session, user_id)

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

    legacy_rows = await _legacy_rows_for_user(session, user.telegram_user_id, row_limit)
    legacy_media = _legacy_media_map(legacy_rows)

    items = []
    for row in sent_rows:
        media_path = _existing_path(row.media_path)
        if media_path is None and row.media_name:
            media_path = _existing_path(legacy_media.get(row.media_name))
        items.append(
            {
                "id": f"outbound:{row.id}",
                "sent_at": _aware(row.created_at),
                "message_type": row.message_type,
                "text": _plain_text(row.text),
                "media_name": row.media_name,
                "media_url": (
                    f"/api/v1/admin/telegram-users/{user.id}/messages/{row.id}/media"
                    if media_path is not None
                    else None
                ),
                "telegram_message_id": row.telegram_message_id,
                "source": "outbound_log",
            }
        )

    # Before the complete transport-level log existed, lifecycle notifications
    # were already persisted in the activity outbox. Include those older rows so
    # the admin page can show as much existing history as is actually available.
    first_full_log_at = None
    if sent_rows:
        dates = [_aware(row.created_at) for row in sent_rows if row.created_at is not None]
        if dates:
            first_full_log_at = min(dates)

    for row in legacy_rows:
        sent_at = _aware(row.sent_at)
        if first_full_log_at is not None and sent_at is not None and sent_at >= first_full_log_at:
            continue
        payload = row.payload or {}
        media_path_raw = str(payload.get("photo_path") or payload.get("video_path") or "").strip()
        media_path = _existing_path(media_path_raw)
        media_name = media_path.name if media_path is not None else (Path(media_path_raw).name if media_path_raw else None)
        items.append(
            {
                "id": f"legacy:{row.event_key}",
                "sent_at": sent_at,
                "message_type": "photo" if payload.get("photo_path") else ("video" if payload.get("video_path") else str(row.kind or "notification")),
                "text": _plain_text(str(payload.get("text") or "")),
                "media_name": media_name,
                "media_url": (
                    f"/api/v1/admin/telegram-users/{user.id}/messages/legacy/{quote(row.event_key, safe='')}/media"
                    if media_path is not None
                    else None
                ),
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


@router.get("/{user_id}/messages/{message_id}/media")
async def download_outbound_media(
    user_id: int,
    message_id: int,
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    user = await _user_or_404(session, user_id)
    row = await session.get(TelegramOutboundMessage, message_id)
    if row is None or row.telegram_user_id != user.telegram_user_id:
        raise HTTPException(status_code=404, detail="Message media not found")

    path = _existing_path(row.media_path)
    if path is None and row.media_name:
        legacy_rows = await _legacy_rows_for_user(session, user.telegram_user_id, 1000)
        path = _existing_path(_legacy_media_map(legacy_rows).get(row.media_name))
    if path is None:
        raise HTTPException(status_code=404, detail="Media file is no longer available")

    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=row.media_name or path.name)


@router.get("/{user_id}/messages/legacy/{event_key:path}/media")
async def download_legacy_media(
    user_id: int,
    event_key: str,
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    user = await _user_or_404(session, user_id)
    row = await session.get(TelegramActivityDelivery, event_key)
    if row is None or row.telegram_user_id != user.telegram_user_id or row.status != "sent":
        raise HTTPException(status_code=404, detail="Message media not found")

    payload = row.payload or {}
    path = _existing_path(str(payload.get("photo_path") or payload.get("video_path") or ""))
    if path is None:
        raise HTTPException(status_code=404, detail="Media file is no longer available")

    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=path.name)
