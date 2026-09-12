from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .admin_models import AdminAuditLog
from .config import get_settings
from .models import Plant, RackSlot, User
from .security import get_admin_user, get_session
from .telegram.activity_notifier import TelegramActivityDelivery
from .telegram.models import TelegramRentalRequest, TelegramUser


router = APIRouter(prefix="/api/v1/admin/rental-requests", tags=["admin-rental-progress"])

MAX_PHOTO_BYTES = 8 * 1024 * 1024
MAX_MESSAGE_LENGTH = 700


def _image_kind(content: bytes) -> tuple[str, str]:
    if content.startswith(b"\xff\xd8\xff"):
        return ".jpg", "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png", "image/png"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return ".webp", "image/webp"
    raise HTTPException(status_code=422, detail="Supported image formats: JPEG, PNG, WEBP")


def _plant_name(plant: Plant, language_code: str | None) -> str:
    names = plant.names or {}
    lang = (language_code or "en").lower().replace("_", "-").split("-", 1)[0]
    value = names.get(lang) or names.get("en") or names.get("ru")
    if not value:
        value = next((item for item in names.values() if item), plant.code)
    return str(value)


def _caption(message: str, plant: Plant, slot: RackSlot, language_code: str | None) -> str:
    # Admin text is intentionally sent exactly as entered (apart from HTML escaping),
    # while the short technical header makes it clear which rental the photo belongs to.
    plant_name = escape(_plant_name(plant, language_code))
    body = escape(message.strip())
    return (
        "🌱 <b>KisaMore</b>\n"
        f"<b>{plant_name}</b> · {slot.rack_id}/{slot.slot_number}\n\n"
        f"{body}"
    )


@router.post("/{request_id}/progress")
async def send_rental_progress(
    request_id: int,
    photo: UploadFile = File(),
    message: str = Form(...),
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    text = message.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Message is required")
    if len(text) > MAX_MESSAGE_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"Message is too long (max {MAX_MESSAGE_LENGTH} characters)",
        )

    row = (
        await session.execute(
            select(TelegramRentalRequest, TelegramUser, RackSlot, Plant)
            .join(TelegramUser, TelegramUser.id == TelegramRentalRequest.user_id)
            .join(RackSlot, RackSlot.id == TelegramRentalRequest.slot_id)
            .join(Plant, Plant.id == TelegramRentalRequest.plant_id)
            .where(TelegramRentalRequest.id == request_id)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Rental request not found")

    request, telegram_user, slot, plant = row
    if not telegram_user.is_active:
        raise HTTPException(status_code=409, detail="Telegram user is inactive")

    content = await photo.read(MAX_PHOTO_BYTES + 1)
    await photo.close()
    if not content:
        raise HTTPException(status_code=422, detail="Photo is required")
    if len(content) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="Image is too large (max 8 MB)")

    extension, media_type = _image_kind(content)
    now = datetime.now(timezone.utc)
    settings = get_settings()
    target_dir = Path(settings.photo_dir) / "admin" / "rental-updates" / str(request_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{now.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}{extension}"
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(target)

    event_key = f"rental_progress:{request_id}:{uuid4().hex}"
    caption = _caption(text, plant, slot, telegram_user.language_code)
    session.add(
        TelegramActivityDelivery(
            event_key=event_key,
            telegram_user_id=telegram_user.telegram_user_id,
            kind="rental_progress",
            payload={
                "text": caption,
                "photo_path": str(target),
                "content_type": media_type,
                "rental_request_id": request.id,
                "plant_id": plant.id,
                "rack_id": slot.rack_id,
                "slot_number": slot.slot_number,
            },
            # Existing text-only activity sender only consumes `pending`.
            # The Telegram bot's rental-progress loop consumes this dedicated status.
            status="photo_pending",
            attempts=0,
            created_at=now,
        )
    )
    session.add(
        AdminAuditLog(
            admin_user_id=admin.id,
            action="rental_progress_message",
            target_type="telegram_rental_request",
            target_id=str(request.id),
            details={
                "event_key": event_key,
                "file": target.name,
                "message": text,
                "telegram_user_id": telegram_user.telegram_user_id,
                "rack_id": slot.rack_id,
                "slot_number": slot.slot_number,
                "plant_id": plant.id,
            },
        )
    )
    await session.commit()

    return {
        "ok": True,
        "queued": True,
        "event_key": event_key,
        "request_id": request.id,
        "photo_name": target.name,
    }
