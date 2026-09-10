from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .admin_models import AdminAuditLog
from .marketplace_service import process_waitlist
from .models import Allocation, Offer, Plant, RackSlot, User
from .security import get_admin_user, get_session
from .telegram.models import (
    TelegramRentalRequest,
    TelegramUser,
    WalletAccount,
    WalletTransaction,
)


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


async def _refund_request(
    session: AsyncSession,
    request: TelegramRentalRequest,
    *,
    reason: str,
) -> int:
    """Refund a charged request once. Old pre-payment requests have price_kisa=0."""
    price = max(0, int(request.price_kisa or 0))
    if price == 0 or request.refunded_at is not None:
        return 0

    wallet = (
        await session.execute(
            select(WalletAccount)
            .where(WalletAccount.user_id == request.user_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if wallet is None:
        wallet = WalletAccount(user_id=request.user_id, balance=0)
        session.add(wallet)
        await session.flush()

    wallet.balance += price
    now = datetime.now(timezone.utc)
    request.refunded_at = now
    session.add(
        WalletTransaction(
            user_id=request.user_id,
            amount=price,
            balance_after=wallet.balance,
            kind="rental_refund",
            reference_type="telegram_rental_request",
            reference_id=str(request.id),
            details={"reason": reason, "price_kisa": price},
        )
    )
    return price


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
    """Resolve the allocation created for this request, including completed rentals."""
    note = (request.note or "").strip()
    if note.startswith("allocation:"):
        allocation_id = note.split(":", 1)[1].strip()
        if allocation_id:
            exact = await session.get(Allocation, allocation_id)
            if exact is not None:
                return exact

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
                "price_kisa": int(request.price_kisa or 0),
                "refunded_at": _aware(request.refunded_at),
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
                "allocation_status": allocation.status if allocation else None,
                "allocation_ends_at": _aware(allocation.ends_at) if allocation else None,
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
    duplicate_refund = 0
    for duplicate in duplicates:
        duplicate.status = "rejected"
        duplicate.note = "Container allocated to another request"
        duplicate.updated_at = now
        duplicate_refund += await _refund_request(
            session,
            duplicate,
            reason="Container allocated to another request",
        )

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
                "price_kisa": int(request.price_kisa or 0),
                "duplicate_refund_kisa": duplicate_refund,
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
        return {"ok": True, "status": "rejected", "refunded_kisa": 0}
    if request.status != "requested":
        raise HTTPException(status_code=409, detail="Only a pending request can be rejected")

    reason = payload.reason.strip() or "Rejected by administrator"
    request.status = "rejected"
    request.note = reason
    request.updated_at = datetime.now(timezone.utc)
    refunded = await _refund_request(session, request, reason=reason)
    session.add(
        AdminAuditLog(
            admin_user_id=admin.id,
            action="reject_rental",
            target_type="telegram_rental_request",
            target_id=str(request.id),
            details={"reason": request.note, "refunded_kisa": refunded},
        )
    )
    await session.commit()
    return {"ok": True, "status": "rejected", "refunded_kisa": refunded}


@router.post("/{request_id}/complete")
async def complete_rental_request(
    request_id: int,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    """End an approved rental without refunding its already consumed rental fee."""
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
    if telegram_user is None or slot is None:
        raise HTTPException(status_code=409, detail="Rental request data is incomplete")

    allocation = await _allocation_for_request(session, request, telegram_user, slot)
    if allocation is None:
        if request.status == "completed":
            return {"ok": True, "status": "completed", "allocation_id": None, "ends_at": None}
        raise HTTPException(status_code=409, detail="Rental allocation was not found")

    if allocation.status not in ("active", "completed"):
        raise HTTPException(status_code=409, detail=f"Allocation is already {allocation.status}")
    if request.status not in ("approved", "completed"):
        raise HTTPException(status_code=409, detail="Only an approved rental can be completed")

    now = datetime.now(timezone.utc)
    if allocation.status == "active":
        allocation.status = "completed"
        allocation.ends_at = now
    elif allocation.ends_at is None:
        allocation.ends_at = now

    request.status = "completed"
    request.note = f"allocation:{allocation.id}"
    request.updated_at = now

    await process_waitlist(session, allocation.device_id)
    session.add(
        AdminAuditLog(
            admin_user_id=admin.id,
            action="complete_rental",
            target_type="telegram_rental_request",
            target_id=str(request.id),
            details={
                "allocation_id": allocation.id,
                "telegram_user_id": telegram_user.telegram_user_id,
                "device_id": slot.device_id,
                "rack_id": slot.rack_id,
                "slot_number": slot.slot_number,
                "plant_id": request.plant_id,
                "price_kisa": int(request.price_kisa or 0),
            },
        )
    )
    await session.commit()
    return {
        "ok": True,
        "status": "completed",
        "allocation_id": allocation.id,
        "ends_at": _aware(allocation.ends_at),
    }
