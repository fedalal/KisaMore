from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .admin_models import AdminAuditLog, PlantingPhoto
from .config import get_settings
from .models import Allocation, Plant, Planting, RackPhoto, RackSlot, User
from .security import get_admin_user, get_session
from .telegram.models import SocialComment, TelegramRentalRequest, TelegramUser, WalletAccount, WalletTransaction
from .telegram.plant_sos import TelegramPlantSosReport
from .timelapse_service import generate_slot_timelapse, planting_timelapse_path


router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
ACTIVE_PLANTING_STATUSES = ("planned", "growing", "ready")


class KisaGiftIn(BaseModel):
    amount: int = Field(ge=1, le=1_000_000)
    reason: str = Field(min_length=2, max_length=300)


class CommentStatusIn(BaseModel):
    status: str = Field(pattern="^(published|hidden)$")


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _display_name(plant: Plant) -> str:
    names = plant.names or {}
    for key in ("ru", "en"):
        if names.get(key):
            return str(names[key])
    for value in names.values():
        if value:
            return str(value)
    return plant.code


def _image_kind(content: bytes, content_type: str | None) -> tuple[str, str]:
    if content.startswith(b"\xff\xd8\xff"):
        return ".jpg", "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png", "image/png"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return ".webp", "image/webp"
    raise HTTPException(status_code=422, detail="Supported image formats: JPEG, PNG, WEBP")


@router.get("/overview")
async def overview(
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    telegram_users = int((await session.execute(select(func.count(TelegramUser.id)))).scalar_one() or 0)
    total_kisa = int((await session.execute(select(func.coalesce(func.sum(WalletAccount.balance), 0)))).scalar_one() or 0)
    active_plantings = int((await session.execute(select(func.count(Planting.id)).where(Planting.status.in_(ACTIVE_PLANTING_STATUSES)))).scalar_one() or 0)
    comments = int((await session.execute(select(func.count(SocialComment.id)).where(SocialComment.status == "published"))).scalar_one() or 0)
    rental_requests = int((await session.execute(select(func.count(TelegramRentalRequest.id)).where(TelegramRentalRequest.status == "requested"))).scalar_one() or 0)
    sos_open = int((await session.execute(select(func.count(TelegramPlantSosReport.id)).where(TelegramPlantSosReport.status.in_(("new", "open"))))).scalar_one() or 0)
    return {
        "telegram_users": telegram_users,
        "total_kisa": total_kisa,
        "active_plantings": active_plantings,
        "published_comments": comments,
        "rental_requests": rental_requests,
        "sos_open": sos_open,
    }


@router.get("/telegram-users")
async def telegram_users(
    q: str = "",
    limit: int = 200,
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(TelegramUser, WalletAccount)
        .outerjoin(WalletAccount, WalletAccount.user_id == TelegramUser.id)
        .order_by(TelegramUser.created_at.desc())
        .limit(max(1, min(limit, 500)))
    )
    query = q.strip()
    if query:
        conditions = [
            TelegramUser.username.ilike(f"%{query}%"),
            TelegramUser.first_name.ilike(f"%{query}%"),
            TelegramUser.last_name.ilike(f"%{query}%"),
        ]
        if query.isdigit():
            conditions.append(TelegramUser.telegram_user_id == int(query))
        stmt = stmt.where(or_(*conditions))
    rows = (await session.execute(stmt)).all()
    return [
        {
            "id": user.id,
            "telegram_user_id": user.telegram_user_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "language_code": user.language_code,
            "is_active": user.is_active,
            "terms_accepted_at": _aware(user.terms_accepted_at),
            "created_at": _aware(user.created_at),
            "balance": int(wallet.balance if wallet else 0),
        }
        for user, wallet in rows
    ]


@router.post("/telegram-users/{telegram_user_id}/gift-kisa")
async def gift_kisa(
    telegram_user_id: int,
    payload: KisaGiftIn,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    user = await session.get(TelegramUser, telegram_user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Telegram user not found")
    wallet = (
        await session.execute(
            select(WalletAccount).where(WalletAccount.user_id == user.id).with_for_update()
        )
    ).scalar_one_or_none()
    if wallet is None:
        wallet = WalletAccount(user_id=user.id, balance=0)
        session.add(wallet)
        await session.flush()
    wallet.balance += payload.amount
    session.add(
        WalletTransaction(
            user_id=user.id,
            amount=payload.amount,
            balance_after=wallet.balance,
            kind="admin_gift",
            reference_type="admin",
            reference_id=admin.id,
            details={"reason": payload.reason, "admin_email": admin.email},
        )
    )
    session.add(
        AdminAuditLog(
            admin_user_id=admin.id,
            action="gift_kisa",
            target_type="telegram_user",
            target_id=str(user.id),
            details={"amount": payload.amount, "reason": payload.reason, "balance_after": wallet.balance},
        )
    )
    await session.commit()
    return {"ok": True, "balance": int(wallet.balance)}


@router.get("/plantings")
async def plantings(
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(
            select(Planting, Plant, RackSlot)
            .join(Plant, Plant.id == Planting.plant_id)
            .join(RackSlot, RackSlot.id == Planting.slot_id)
            .where(Planting.status.in_(ACTIVE_PLANTING_STATUSES))
            .order_by(Planting.planted_at.desc())
            .limit(200)
        )
    ).all()
    result = []
    for planting, plant, slot in rows:
        photo = (
            await session.execute(
                select(PlantingPhoto)
                .where(PlantingPhoto.planting_id == planting.id, PlantingPhoto.is_public.is_(True))
                .order_by(PlantingPhoto.published_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        result.append(
            {
                "id": planting.id,
                "plant_id": plant.id,
                "plant_name": _display_name(plant),
                "plant_names": plant.names,
                "rack_id": slot.rack_id,
                "slot_number": slot.slot_number,
                "status": planting.status,
                "planted_at": _aware(planting.planted_at),
                "expected_harvest_at": _aware(planting.expected_harvest_at),
                "has_admin_photo": photo is not None,
                "photo_url": f"/api/v1/admin/plantings/{planting.id}/photo" if photo else None,
            }
        )
    return result


@router.get("/plantings/history")
async def planting_history(
    limit: int = 500,
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(
            select(Planting, Plant, RackSlot, Allocation, User, TelegramUser)
            .join(Plant, Plant.id == Planting.plant_id)
            .join(RackSlot, RackSlot.id == Planting.slot_id)
            .outerjoin(Allocation, Allocation.id == Planting.cloud_allocation_id)
            .outerjoin(User, User.id == Allocation.user_id)
            .outerjoin(TelegramUser, TelegramUser.marketplace_user_id == User.id)
            .where(or_(Planting.status == "harvested", Planting.actual_harvest_at.is_not(None)))
            .order_by(func.coalesce(Planting.actual_harvest_at, Planting.observed_at).desc())
            .limit(max(1, min(limit, 2000)))
        )
    ).all()
    settings = get_settings()
    result = []
    for planting, plant, slot, allocation, user, telegram_user in rows:
        planted_at = _aware(planting.planted_at)
        harvested_at = _aware(planting.actual_harvest_at) or _aware(planting.observed_at)
        duration_seconds = None
        if planted_at is not None and harvested_at is not None:
            duration_seconds = max(0, int((harvested_at - planted_at).total_seconds()))

        telegram_name = ""
        if telegram_user is not None:
            telegram_name = " ".join(
                value for value in (telegram_user.first_name, telegram_user.last_name) if value
            ).strip()
        owner_name = telegram_name or (user.display_name if user is not None else "") or "Неизвестно"
        owner_username = telegram_user.username if telegram_user is not None else None
        owner_telegram_id = telegram_user.telegram_user_id if telegram_user is not None else None
        owner_email = None
        if user is not None and not user.email.endswith("@internal.kisamore.local"):
            owner_email = user.email

        timelapse = planting_timelapse_path(settings.photo_dir, planting.id)
        result.append(
            {
                "id": planting.id,
                "plant_id": plant.id,
                "plant_name": _display_name(plant),
                "device_id": slot.device_id,
                "rack_id": slot.rack_id,
                "slot_number": slot.slot_number,
                "status": planting.status,
                "planted_at": planted_at,
                "harvested_at": harvested_at,
                "harvested_at_estimated": planting.actual_harvest_at is None,
                "duration_seconds": duration_seconds,
                "allocation_id": allocation.id if allocation is not None else planting.cloud_allocation_id,
                "owner_name": owner_name,
                "owner_username": owner_username,
                "owner_telegram_id": owner_telegram_id,
                "owner_email": owner_email,
                "timelapse_ready": timelapse.is_file(),
                "timelapse_url": f"/api/v1/admin/plantings/{planting.id}/timelapse/full",
            }
        )
    return result


@router.get("/plantings/{planting_id}/timelapse/full")
async def admin_planting_timelapse(
    planting_id: str,
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    row = (
        await session.execute(
            select(Planting, RackSlot)
            .join(RackSlot, RackSlot.id == Planting.slot_id)
            .where(Planting.id == planting_id)
            .limit(1)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Planting not found")

    planting, slot = row
    start_at = _aware(planting.planted_at)
    end_at = _aware(planting.actual_harvest_at) or _aware(planting.observed_at)
    if start_at is None or end_at is None or end_at < start_at:
        raise HTTPException(status_code=409, detail="Planting dates are incomplete")

    settings = get_settings()
    target = planting_timelapse_path(settings.photo_dir, planting.id)
    if not target.is_file():
        try:
            generated = await asyncio.to_thread(
                generate_slot_timelapse,
                photo_dir=settings.photo_dir,
                device_id=slot.device_id,
                rack_id=slot.rack_id,
                slot_number=slot.slot_number,
                period="full",
                start_at=start_at,
                end_at=end_at,
                target=target,
                final=True,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Could not generate timelapse: {exc}") from exc
        if generated is None:
            raise HTTPException(status_code=404, detail="Not enough archived frames for this timelapse")

    return FileResponse(target, media_type="video/mp4", headers={"Cache-Control": "no-store"})


@router.post("/plantings/{planting_id}/photo")
async def publish_planting_photo(
    planting_id: str,
    photo: UploadFile = File(),
    caption: str = Form(default=""),
    captured_at: datetime | None = Form(default=None),
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    planting = await session.get(Planting, planting_id)
    if planting is None:
        raise HTTPException(status_code=404, detail="Planting not found")
    content = await photo.read(8 * 1024 * 1024 + 1)
    await photo.close()
    if len(content) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image is too large (max 8 MB)")
    extension, media_type = _image_kind(content, photo.content_type)
    now = datetime.now(timezone.utc)
    captured = _aware(captured_at) or now
    settings = get_settings()
    target_dir = Path(settings.photo_dir) / "admin" / "plantings" / planting_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{now.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}{extension}"
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(target)
    record = PlantingPhoto(
        planting_id=planting_id,
        file_path=str(target),
        content_type=media_type,
        size_bytes=len(content),
        caption=caption.strip()[:1000] or None,
        captured_at=captured,
        published_at=now,
        uploaded_by_user_id=admin.id,
        is_public=True,
    )
    session.add(record)
    session.add(
        AdminAuditLog(
            admin_user_id=admin.id,
            action="publish_planting_photo",
            target_type="planting",
            target_id=planting_id,
            details={"file": target.name, "caption": record.caption or ""},
        )
    )
    await session.commit()
    await session.refresh(record)
    return {"ok": True, "photo_id": record.id, "photo_url": f"/api/v1/admin/plantings/{planting_id}/photo"}


@router.get("/plantings/{planting_id}/photo")
async def planting_photo(
    planting_id: str,
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    photo = (
        await session.execute(
            select(PlantingPhoto)
            .where(PlantingPhoto.planting_id == planting_id, PlantingPhoto.is_public.is_(True))
            .order_by(PlantingPhoto.published_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if photo is not None:
        path = Path(photo.file_path)
        if path.is_file():
            return FileResponse(path, media_type=photo.content_type, headers={"Cache-Control": "no-store"})
    row = (
        await session.execute(
            select(RackPhoto)
            .join(RackSlot, (RackSlot.device_id == RackPhoto.device_id) & (RackSlot.rack_id == RackPhoto.rack_id))
            .join(Planting, Planting.slot_id == RackSlot.id)
            .where(Planting.id == planting_id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None or not Path(row.file_path).is_file():
        raise HTTPException(status_code=404, detail="Photo not found")
    return FileResponse(row.file_path, media_type=row.content_type, headers={"Cache-Control": "no-store"})


@router.get("/comments")
async def comments(
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(
            select(SocialComment, TelegramUser)
            .join(TelegramUser, TelegramUser.id == SocialComment.user_id)
            .order_by(SocialComment.created_at.desc())
            .limit(200)
        )
    ).all()
    return [
        {
            "id": comment.id,
            "user_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "target_type": comment.target_type,
            "target_id": comment.target_id,
            "body": comment.body,
            "status": comment.status,
            "created_at": _aware(comment.created_at),
        }
        for comment, user in rows
    ]


@router.patch("/comments/{comment_id}")
async def update_comment(
    comment_id: int,
    payload: CommentStatusIn,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    comment = await session.get(SocialComment, comment_id)
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    comment.status = payload.status
    session.add(
        AdminAuditLog(
            admin_user_id=admin.id,
            action="comment_status",
            target_type="social_comment",
            target_id=str(comment.id),
            details={"status": payload.status},
        )
    )
    await session.commit()
    return {"ok": True, "status": comment.status}
