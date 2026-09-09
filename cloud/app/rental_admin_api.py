from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .admin_models import AdminAuditLog
from .models import Allocation, Offer, Plant, RackSlot, User
from .security import get_admin_user, get_session
from .telegram.models import TelegramRentalRequest, TelegramUser


router = APIRouter(prefix="/api/v1/admin/rental-requests", tags=["admin-rentals"])


class RejectRentalIn(BaseModel):
    reason: str = Field(default="", max_length=300)


def _aware(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _plant_name(plant: Plant) -> str:
    names = plant.names or {}
    for key in ("ru", "en"):
        if names.get(key):
            return str(names[key])
    return next((str(v) for v in names.values() if v), plant.code)


def _blocks_slot(item, slot: RackSlot) -> bool:
    if item.device_id != slot.device_id or item.rack_id != slot.rack_id:
        return False
    return item.resource_type == "rack" or item.slot_number == slot.slot_number


async def _ensure_marketplace_user(
    session: AsyncSession,
    telegram_user: TelegramUser,
) -> User:
    if telegram_user.marketplace_user_id:
        existing = await session.get(User, telegram_user.marketplace_user_id)
        if existing is not None:
            return existing

    internal_email = f"telegram-{telegram_user.telegram_user_id}@internal.kisamore.local"
    existing = (
        await session.execute(select(User).where(User.email == internal_email))
    ).scalar_one_or_none()
    if existing is None:
        display_name = " ".join(
            value for value in (telegram_user.first_name, telegram_user.last_name) if value
        ).strip()
        if not display_name:
            display_name = telegram_user.username or f"Telegram {telegram_user.telegram_user_id}"
        language = (telegram_user.language_code or "en").lower().replace("_", "-").split("-", 1)[0]
        existing = User(
            id=str(uuid4()),
            email=internal_email,
            display_name=display_name[:120],
            password_hash="disabled",
            preferred_language=language[:10],
            role="customer",
            email_verified=False,
            is_active=False,
            created_at=datetime.now(timezone.utc),
        )
        session.add(existing)
        await session.flush()

    telegram_user.marketplace_user_id = existing.id
    await session.flush()
    return existing


async def _allocation_for_request(
    session: AsyncSession,
    request: TelegramRentalRequest,
    telegram_user: TelegramUser,
    slot: RackSlot,
):
    if not telegram_user.marketplace_user_id:
        return None
    return (
        await session.execute(
            select(Allocation)
            .where(
                Allocation.user_id == telegram_user.marketplace_user_id,
                Allocation.device_id == slot.device_id,
                Allocation.rack_id == slot.rack_id,
                Allocation.slot_number == slot.slot_number,
                Allocation.plant_id == request.plant_id,
                Allocation.status == "active",
            )
            .order_by(Allocation.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


@router.get("")
async def list_rental_requests(
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(
            select(TelegramRentalRequest, TelegramUser, RackSlot, Plant)
            .join(TelegramUser, TelegramUser.id == TelegramRentalRequest.user_id)
            .join(RackSlot, RackSlot.id == TelegramRentalRequest.slot_id)
            .join(Plant, Plant.id == TelegramRentalRequest.plant_id)
            .order_by(TelegramRentalRequest.created_at.desc())
            .limit(300)
        )
    ).all()
    result = []
    for request, telegram_user, slot, plant in rows:
        allocation = await _allocation_for_request(session, request, telegram_user, slot)
        result.append(
            {
                "id": request.id,
                "status": request.status,
                "note": request.note,
                "created_at": _aware(request.created_at),
                "updated_at": _aware(request.updated_at),
                "telegram_user_id": telegram_user.telegram_user_id,
                "username": telegram_user.username,
                "first_name": telegram_user.first_name,
                "last_name": telegram_user.last_name,
                "language_code": telegram_user.language_code,
                "plant_id": plant.id,
                "plant_name": _plant_name(plant),
                "device_id": slot.device_id,
                "rack_id": slot.rack_id,
                "slot_number": slot.slot_number,
                "physical_status": slot.physical_status,
                "allocation_id": allocation.id if allocation else None,
            }
        )
    return result


@router.post("/{request_id}/approve")
async def approve_rental_request(
    request_id: int,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    request = (
        await session.execute(
            select(TelegramRentalRequest)
            .where(TelegramRentalRequest.id == request_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if request is None:
        raise HTTPException(status_code=404, detail="Rental request not found")

    telegram_user = await session.get(TelegramUser, request.user_id)
    slot = (
        await session.execute(
            select(RackSlot).where(RackSlot.id == request.slot_id).with_for_update()
        )
    ).scalar_one_or_none()
    plant = await session.get(Plant, request.plant_id)
    if telegram_user is None or slot is None or plant is None:
        raise HTTPException(status_code=409, detail="Rental request data is incomplete")

    if request.status == "approved":
        allocation = await _allocation_for_request(session, request, telegram_user, slot)
        return {"ok": True, "status": "approved", "allocation_id": allocation.id if allocation else None}
    if request.status != "requested":
        raise HTTPException(status_code=409, detail=f"Request is already {request.status}")
    if not slot.enabled or slot.physical_status != "available":
        raise HTTPException(status_code=409, detail="Container is no longer physically available")
    if not plant.active:
        raise HTTPException(status_code=409, detail="Selected plant is no longer active")

    earlier = (
        await session.execute(
            select(TelegramRentalRequest.id).where(
                TelegramRentalRequest.slot_id == slot.id,
                TelegramRentalRequest.status == "requested",
                TelegramRentalRequest.id != request.id,
                TelegramRentalRequest.created_at < request.created_at,
            ).limit(1)
        )
    ).scalar_one_or_none()
    if earlier is not None:
        raise HTTPException(status_code=409, detail="An earlier request already exists for this container")

    now = datetime.now(timezone.utc)
    allocations = list(
        (
            await session.execute(
                select(Allocation).where(
                    Allocation.device_id == slot.device_id,
                    Allocation.rack_id == slot.rack_id,
                    Allocation.status == "active",
                )
            )
        ).scalars().all()
    )
    if any(_blocks_slot(item, slot) for item in allocations):
        raise HTTPException(status_code=409, detail="Container already has an active allocation")

    offers = list(
        (
            await session.execute(
                select(Offer).where(
                    Offer.device_id == slot.device_id,
                    Offer.rack_id == slot.rack_id,
                    Offer.status == "pending",
                    Offer.expires_at > now,
                )
            )
        ).scalars().all()
    )
    if any(_blocks_slot(item, slot) for item in offers):
        raise HTTPException(status_code=409, detail="Container is reserved by a marketplace offer")

    marketplace_user = await _ensure_marketplace_user(session, telegram_user)
    allocation = Allocation(
        id=str(uuid4()),
        user_id=marketplace_user.id,
        device_id=slot.device_id,
        resource_type="slot",
        rack_id=slot.rack_id,
        slot_number=slot.slot_number,
        plant_id=plant.id,
        status="active",
        starts_at=now,
        created_at=now,
    )
    session.add(allocation)
    request.status = "approved"
    request.note = f"allocation:{allocation.id}"
    request.updated_at = now

    duplicates = list(
        (
            await session.execute(
                select(TelegramRentalRequest).where(
                    TelegramRentalRequest.slot_id == slot.id,
                    TelegramRentalRequest.id != request.id,
                    TelegramRentalRequest.status == "requested",
                )
            )
        ).scalars().all()
    )
    for duplicate in duplicates:
        duplicate.status = "rejected"
        duplicate.note = "Container allocated to another request"
        duplicate.updated_at = now

    session.add(
        AdminAuditLog(
            admin_user_id=admin.id,
            action="approve_rental",
            target_type="telegram_rental_request",
            target_id=str(request.id),
            details={
                "allocation_id": allocation.id,
                "telegram_user_id": telegram_user.telegram_user_id,
                "device_id": slot.device_id,
                "rack_id": slot.rack_id,
                "slot_number": slot.slot_number,
                "plant_id": plant.id,
            },
        )
    )
    await session.commit()
    return {"ok": True, "status": "approved", "allocation_id": allocation.id}


@router.post("/{request_id}/reject")
async def reject_rental_request(
    request_id: int,
    payload: RejectRentalIn,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    request = (
        await session.execute(
            select(TelegramRentalRequest)
            .where(TelegramRentalRequest.id == request_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if request is None:
        raise HTTPException(status_code=404, detail="Rental request not found")
    if request.status == "rejected":
        return {"ok": True, "status": "rejected"}
    if request.status != "requested":
        raise HTTPException(status_code=409, detail="Only a pending request can be rejected")

    request.status = "rejected"
    request.note = payload.reason.strip() or "Rejected by administrator"
    request.updated_at = datetime.now(timezone.utc)
    session.add(
        AdminAuditLog(
            admin_user_id=admin.id,
            action="reject_rental",
            target_type="telegram_rental_request",
            target_id=str(request.id),
            details={"reason": request.note},
        )
    )
    await session.commit()
    return {"ok": True, "status": "rejected"}
