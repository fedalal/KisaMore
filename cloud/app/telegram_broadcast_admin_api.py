from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .admin_models import AdminAuditLog
from .config import get_settings
from .models import User
from .security import get_admin_user, get_session
from .telegram.broadcast_media import media_kind, media_mime
from .telegram.broadcast_models import (
    TelegramBroadcast,
    TelegramBroadcastAnswer,
    TelegramBroadcastDelivery,
    TelegramBroadcastOption,
)
from .telegram.models import TelegramUser


router = APIRouter(prefix="/api/v1/admin/telegram-broadcasts", tags=["admin-telegram-broadcasts"])
SUPPORTED_LANGUAGES = ("ru", "en", "de", "fr", "es", "it", "pt", "pl", "zh")
ANSWER_MODES = ("none", "single", "multiple")


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _base_language(value: str | None) -> str:
    raw = (value or "").strip().lower().replace("_", "-")
    return raw.split("-", 1)[0] if raw else ""


def _upload_media_kind(
    header: bytes,
    filename: str | None,
    content_type: str | None,
) -> tuple[str, str, str]:
    suffix = Path(str(filename or "")).suffix.lower()
    mime = (content_type or "").lower()

    if header.startswith(b"\xff\xd8\xff"):
        return "photo", ".jpg", "image/jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "photo", ".png", "image/png"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "photo", ".webp", "image/webp"
    if header.startswith((b"GIF87a", b"GIF89a")):
        return "animation", ".gif", "image/gif"
    if header.startswith(b"\x1aE\xdf\xa3") or suffix == ".webm" or mime == "video/webm":
        return "video", ".webm", "video/webm"
    if len(header) >= 12 and header[4:8] == b"ftyp":
        if suffix == ".mov" or mime == "video/quicktime":
            return "video", ".mov", "video/quicktime"
        return "video", ".mp4", "video/mp4"

    raise HTTPException(
        status_code=422,
        detail="Supported media formats: JPEG, PNG, WEBP, GIF, MP4, MOV, WEBM",
    )


async def _save_upload(upload: UploadFile, target: Path, max_bytes: int) -> int:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    size = 0
    try:
        with temporary.open("wb") as handle:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Media is too large (max {max_bytes // 1024 // 1024} MB)",
                    )
                handle.write(chunk)
        temporary.replace(target)
        return size
    finally:
        await upload.close()
        if temporary.exists():
            temporary.unlink(missing_ok=True)




def _parse_options(raw: str, answer_mode: str) -> list[str]:
    if answer_mode == "none":
        return []
    try:
        values = json.loads(raw or "[]")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="Invalid poll options") from exc
    if not isinstance(values, list):
        raise HTTPException(status_code=422, detail="Poll options must be a list")
    options: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        if len(text) > 120:
            raise HTTPException(status_code=422, detail="Each poll option is limited to 120 characters")
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        options.append(text)
    if len(options) < 2:
        raise HTTPException(status_code=422, detail="A poll needs at least two answer options")
    if len(options) > 10:
        raise HTTPException(status_code=422, detail="A poll supports up to 10 answer options")
    return options


async def _audience_users(session: AsyncSession, language_code: str) -> list[TelegramUser]:
    rows = list(
        (
            await session.execute(
                select(TelegramUser)
                .where(TelegramUser.is_active.is_(True))
                .order_by(TelegramUser.id)
            )
        ).scalars().all()
    )
    if language_code == "all":
        return rows
    return [item for item in rows if _base_language(item.language_code) == language_code]


async def _broadcast_payload(session: AsyncSession, row: TelegramBroadcast) -> dict:
    options = list(
        (
            await session.execute(
                select(TelegramBroadcastOption)
                .where(TelegramBroadcastOption.broadcast_id == row.id)
                .order_by(TelegramBroadcastOption.position)
            )
        ).scalars().all()
    )
    vote_rows = (
        await session.execute(
            select(TelegramBroadcastAnswer.option_id, func.count(TelegramBroadcastAnswer.id))
            .where(TelegramBroadcastAnswer.broadcast_id == row.id)
            .group_by(TelegramBroadcastAnswer.option_id)
        )
    ).all()
    vote_counts = {int(option_id): int(count) for option_id, count in vote_rows}
    answered_users = int(
        (
            await session.execute(
                select(func.count(func.distinct(TelegramBroadcastAnswer.user_id))).where(
                    TelegramBroadcastAnswer.broadcast_id == row.id
                )
            )
        ).scalar_one()
        or 0
    )
    response_rate = round((answered_users / row.total_recipients * 100.0), 1) if row.total_recipients else 0.0
    return {
        "id": row.id,
        "language_code": row.language_code,
        "text": row.text,
        "question": row.question,
        "answer_mode": row.answer_mode,
        "show_results_to_users": row.show_results_to_users,
        "has_media": bool(row.photo_path),
        "media_kind": (
            media_kind(row.photo_path, row.photo_name)
            if row.photo_path
            else None
        ),
        "media_name": row.photo_name,
        "media_size_bytes": (
            Path(row.photo_path).stat().st_size
            if row.photo_path and Path(row.photo_path).is_file()
            else None
        ),
        "media_url": (
            f"/api/v1/admin/telegram-broadcasts/{row.id}/media"
            if row.photo_path
            else None
        ),
        # Backwards-compatible fields for older admin JavaScript.
        "has_photo": bool(
            row.photo_path
            and media_kind(row.photo_path, row.photo_name) == "photo"
        ),
        "photo_name": row.photo_name,
        "photo_url": (
            f"/api/v1/admin/telegram-broadcasts/{row.id}/photo"
            if row.photo_path
            and media_kind(row.photo_path, row.photo_name) == "photo"
            else None
        ),
        "status": row.status,
        "total_recipients": row.total_recipients,
        "sent_count": row.sent_count,
        "failed_count": row.failed_count,
        "answered_users": answered_users,
        "response_rate": response_rate,
        "created_at": _aware(row.created_at),
        "started_at": _aware(row.started_at),
        "finished_at": _aware(row.finished_at),
        "options": [
            {
                "id": option.id,
                "position": option.position,
                "text": option.text,
                "vote_count": vote_counts.get(option.id, 0),
                "percentage_of_respondents": (
                    round(vote_counts.get(option.id, 0) / answered_users * 100.0, 1)
                    if answered_users
                    else 0.0
                ),
            }
            for option in options
        ],
    }


@router.get("/audience")
async def broadcast_audience(
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    users = await _audience_users(session, "all")
    counts = {code: 0 for code in SUPPORTED_LANGUAGES}
    other = 0
    for user in users:
        code = _base_language(user.language_code)
        if code in counts:
            counts[code] += 1
        else:
            other += 1
    return {
        "total": len(users),
        "languages": [{"code": code, "count": counts[code]} for code in SUPPORTED_LANGUAGES],
        "other": other,
    }


@router.get("")
async def list_broadcasts(
    limit: int = 100,
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    rows = list(
        (
            await session.execute(
                select(TelegramBroadcast)
                .order_by(TelegramBroadcast.created_at.desc(), TelegramBroadcast.id.desc())
                .limit(max(1, min(int(limit), 200)))
            )
        ).scalars().all()
    )
    return [await _broadcast_payload(session, row) for row in rows]


@router.get("/{broadcast_id}")
async def get_broadcast(
    broadcast_id: int,
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    row = await session.get(TelegramBroadcast, broadcast_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Broadcast not found")
    return await _broadcast_payload(session, row)


@router.get("/{broadcast_id}/media")
async def get_broadcast_media(
    broadcast_id: int,
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    row = await session.get(TelegramBroadcast, broadcast_id)
    if row is None or not row.photo_path:
        raise HTTPException(status_code=404, detail="Broadcast media not found")
    path = Path(row.photo_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Broadcast media file not found")
    return FileResponse(
        path,
        media_type=media_mime(path, row.photo_name),
    )


@router.get("/{broadcast_id}/photo")
async def get_broadcast_photo(
    broadcast_id: int,
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    # Kept for old admin pages and previously created photo broadcasts.
    row = await session.get(TelegramBroadcast, broadcast_id)
    if row is None or not row.photo_path:
        raise HTTPException(status_code=404, detail="Broadcast photo not found")
    path = Path(row.photo_path)
    if not path.is_file() or media_kind(path, row.photo_name) != "photo":
        raise HTTPException(status_code=404, detail="Broadcast photo not found")
    return FileResponse(path, media_type=media_mime(path, row.photo_name))




@router.post("")
async def create_broadcast(
    language_code: str = Form(default="all"),
    text: str = Form(default=""),
    question: str = Form(default=""),
    answer_mode: str = Form(default="none"),
    options_json: str = Form(default="[]"),
    show_results_to_users: bool = Form(default=False),
    media: UploadFile | None = File(default=None),
    photo: UploadFile | None = File(default=None),
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    language = _base_language(language_code)
    if (language_code or "").strip().lower() == "all":
        language = "all"
    if language != "all" and language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=422, detail="Unsupported audience language")

    mode = (answer_mode or "none").strip().lower()
    if mode not in ANSWER_MODES:
        raise HTTPException(status_code=422, detail="Unsupported poll mode")

    if media is not None and photo is not None:
        raise HTTPException(status_code=422, detail="Upload only one media file")
    upload = media or photo

    message_text = (text or "").strip()
    poll_question = (question or "").strip()
    if len(message_text) > 3500:
        raise HTTPException(status_code=422, detail="Message is limited to 3500 characters")
    if len(poll_question) > 500:
        raise HTTPException(status_code=422, detail="Question is limited to 500 characters")
    options = _parse_options(options_json, mode)
    if mode != "none" and not poll_question:
        raise HTTPException(status_code=422, detail="Poll question is required")
    if mode == "none":
        poll_question = ""
    if not message_text and not poll_question and upload is None:
        raise HTTPException(status_code=422, detail="Message text, question or media is required")

    now = datetime.now(timezone.utc)
    row = TelegramBroadcast(
        created_by_user_id=admin.id,
        language_code=language,
        text=message_text,
        question=poll_question or None,
        answer_mode=mode,
        show_results_to_users=bool(show_results_to_users),
        status="pending",
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    await session.flush()

    uploaded_kind = None
    uploaded_size = 0
    if upload is not None:
        settings = get_settings()
        header = await upload.read(64)
        await upload.seek(0)
        uploaded_kind, extension, _mime = _upload_media_kind(
            header,
            upload.filename,
            upload.content_type,
        )
        max_bytes = (
            settings.photo_max_bytes
            if uploaded_kind == "photo"
            else settings.broadcast_media_max_bytes
        )
        original_name = upload.filename or f"broadcast-{uploaded_kind}{extension}"
        target_dir = Path(settings.photo_dir) / "admin" / "broadcasts" / str(row.id)
        target = target_dir / (
            f"{now.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}{extension}"
        )
        uploaded_size = await _save_upload(upload, target, max_bytes)
        row.photo_path = str(target)
        row.photo_name = original_name[:255]


    for position, option_text in enumerate(options, start=1):
        session.add(
            TelegramBroadcastOption(
                broadcast_id=row.id,
                position=position,
                text=option_text,
            )
        )

    recipients = await _audience_users(session, language)
    row.total_recipients = len(recipients)
    for user in recipients:
        session.add(
            TelegramBroadcastDelivery(
                broadcast_id=row.id,
                user_id=user.id,
                status="pending",
                created_at=now,
                updated_at=now,
            )
        )

    if not recipients:
        row.status = "completed"
        row.finished_at = now

    session.add(
        AdminAuditLog(
            admin_user_id=admin.id,
            action="create_telegram_broadcast",
            target_type="telegram_broadcast",
            target_id=str(row.id),
            details={
                "language_code": language,
                "answer_mode": mode,
                "options": len(options),
                "recipients": len(recipients),
                "has_media": bool(row.photo_path),
                "media_kind": uploaded_kind,
                "media_size_bytes": uploaded_size or None,
            },
        )
    )
    await session.commit()
    await session.refresh(row)
    return await _broadcast_payload(session, row)


@router.post("/{broadcast_id}/cancel")
async def cancel_broadcast(
    broadcast_id: int,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    row = (
        await session.execute(
            select(TelegramBroadcast)
            .where(TelegramBroadcast.id == broadcast_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Broadcast not found")
    if row.status in ("completed", "cancelled"):
        return await _broadcast_payload(session, row)

    now = datetime.now(timezone.utc)
    row.status = "cancelled"
    row.finished_at = now
    row.updated_at = now
    await session.execute(
        update(TelegramBroadcastDelivery)
        .where(
            TelegramBroadcastDelivery.broadcast_id == row.id,
            TelegramBroadcastDelivery.status.in_(("pending", "sending")),
        )
        .values(status="cancelled", updated_at=now)
    )
    session.add(
        AdminAuditLog(
            admin_user_id=admin.id,
            action="cancel_telegram_broadcast",
            target_type="telegram_broadcast",
            target_id=str(row.id),
            details={},
        )
    )
    await session.commit()
    return await _broadcast_payload(session, row)
