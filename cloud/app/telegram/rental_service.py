from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from ..db import SessionLocal
from ..models import Allocation, Offer, Plant, RackSlot
from .models import TelegramRentalRequest, WalletAccount, WalletTransaction


ACTIVE_REQUEST_STATUSES = ("requested", "approved")


class InsufficientRentalBalance(ValueError):
    def __init__(self, price: int, balance: int):
        super().__init__("insufficient_kisa")
        self.price = int(price)
        self.balance = int(balance)


def _resource_blocks_slot(item, slot: RackSlot) -> bool:
    if item.device_id != slot.device_id or item.rack_id != slot.rack_id:
        return False
    return item.resource_type == "rack" or item.slot_number == slot.slot_number


async def list_available_slots(limit: int = 20) -> list[RackSlot]:
    """Return truly free slots, including pending Telegram and marketplace reservations."""
    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        slots = list(
            (
                await session.execute(
                    select(RackSlot)
                    .where(
                        RackSlot.enabled.is_(True),
                        RackSlot.physical_status == "available",
                    )
                    .order_by(RackSlot.rack_id, RackSlot.slot_number)
                )
            ).scalars().all()
        )
        if not slots:
            return []

        reserved_slot_ids = set(
            (
                await session.execute(
                    select(TelegramRentalRequest.slot_id).where(
                        TelegramRentalRequest.status.in_(ACTIVE_REQUEST_STATUSES)
                    )
                )
            ).scalars().all()
        )
        allocations = list(
            (
                await session.execute(
                    select(Allocation).where(Allocation.status == "active")
                )
            ).scalars().all()
        )
        offers = list(
            (
                await session.execute(
                    select(Offer).where(
                        Offer.status == "pending",
                        Offer.expires_at > now,
                    )
                )
            ).scalars().all()
        )

        result: list[RackSlot] = []
        for slot in slots:
            if slot.id in reserved_slot_ids:
                continue
            if any(_resource_blocks_slot(item, slot) for item in allocations):
                continue
            if any(_resource_blocks_slot(item, slot) for item in offers):
                continue
            result.append(slot)
            if len(result) >= max(1, min(limit, 50)):
                break
        return result


async def create_rental_request(
    user_id: int,
    slot_id: int,
    plant_id: str,
) -> TelegramRentalRequest:
    """Atomically reserve the slot and charge the plant rental price in Kisa."""
    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        slot = (
            await session.execute(
                select(RackSlot).where(RackSlot.id == slot_id).with_for_update()
            )
        ).scalar_one_or_none()
        plant = await session.get(Plant, plant_id)
        if slot is None or not slot.enabled or slot.physical_status != "available":
            raise ValueError("slot_unavailable")
        if plant is None or not plant.active:
            raise ValueError("plant_unavailable")

        # A repeated Telegram callback must be idempotent and never charge twice.
        existing = (
            await session.execute(
                select(TelegramRentalRequest)
                .where(
                    TelegramRentalRequest.user_id == user_id,
                    TelegramRentalRequest.slot_id == slot_id,
                    TelegramRentalRequest.status.in_(ACTIVE_REQUEST_STATUSES),
                )
                .order_by(TelegramRentalRequest.created_at)
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing

        other_request = (
            await session.execute(
                select(TelegramRentalRequest.id)
                .where(
                    TelegramRentalRequest.slot_id == slot_id,
                    TelegramRentalRequest.status.in_(ACTIVE_REQUEST_STATUSES),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if other_request is not None:
            raise ValueError("slot_unavailable")

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
        if any(_resource_blocks_slot(item, slot) for item in allocations):
            raise ValueError("slot_unavailable")

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
        if any(_resource_blocks_slot(item, slot) for item in offers):
            raise ValueError("slot_unavailable")

        wallet = (
            await session.execute(
                select(WalletAccount).where(WalletAccount.user_id == user_id).with_for_update()
            )
        ).scalar_one_or_none()
        if wallet is None:
            wallet = WalletAccount(user_id=user_id, balance=0)
            session.add(wallet)
            await session.flush()

        price = max(0, int(plant.rental_price_kisa or 0))
        if wallet.balance < price:
            raise InsufficientRentalBalance(price=price, balance=wallet.balance)

        request = TelegramRentalRequest(
            user_id=user_id,
            slot_id=slot_id,
            plant_id=plant_id,
            price_kisa=price,
            status="requested",
        )
        session.add(request)
        await session.flush()

        if price:
            wallet.balance -= price
            session.add(
                WalletTransaction(
                    user_id=user_id,
                    amount=-price,
                    balance_after=wallet.balance,
                    kind="rental_request",
                    reference_type="telegram_rental_request",
                    reference_id=str(request.id),
                    details={"plant_id": plant.id, "slot_id": slot.id, "price_kisa": price},
                )
            )

        await session.commit()
        await session.refresh(request)
        return request
