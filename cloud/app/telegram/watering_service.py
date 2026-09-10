from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from ..db import SessionLocal
from ..models import Plant, Planting, RackSlot, WateringTask
from ..watering_service import (
    adjustment_values,
    allocation_context,
    clamp_adjustment,
    effective_schedule,
    normalized_extra_options,
    refresh_watering_tasks,
    watering_conflict,
)
from .models import TelegramUser, WalletAccount, WalletTransaction


class WateringUnavailable(ValueError):
    pass


class ExtraWateringTooClose(ValueError):
    def __init__(self, conflict_at: datetime):
        super().__init__("watering_too_close")
        self.conflict_at = conflict_at


class ExtraWateringInsufficientBalance(ValueError):
    def __init__(self, price: int, balance: int):
        super().__init__("insufficient_kisa")
        self.price = int(price)
        self.balance = int(balance)


@dataclass
class WateringContext:
    allocation_id: str
    rack_id: int
    slot_number: int
    plant: Plant
    planting: Planting | None
    adjustment_percent: int
    allowed_adjustments: list[int]
    schedule: list[dict]
    extra_options: list[dict]
    min_interval_minutes: int


async def _telegram_marketplace_id(session, user_id: int) -> str:
    user = await session.get(TelegramUser, user_id)
    if user is None or not user.marketplace_user_id:
        raise WateringUnavailable("allocation_not_linked")
    return user.marketplace_user_id


async def _context(session, user_id: int, allocation_id: str):
    marketplace_id = await _telegram_marketplace_id(session, user_id)
    row = await allocation_context(
        session,
        marketplace_user_id=marketplace_id,
        allocation_id=allocation_id,
    )
    if row is None:
        raise WateringUnavailable("allocation_not_found")
    return row


def _out(allocation, plant: Plant, slot: RackSlot, planting: Planting | None) -> WateringContext:
    adjustment = int(allocation.watering_adjustment_percent or 0)
    try:
        adjustment = clamp_adjustment(plant, adjustment)
    except ValueError:
        adjustment = 0
    return WateringContext(
        allocation_id=allocation.id,
        rack_id=slot.rack_id,
        slot_number=slot.slot_number,
        plant=plant,
        planting=planting,
        adjustment_percent=adjustment,
        allowed_adjustments=adjustment_values(plant),
        schedule=effective_schedule(plant, adjustment),
        extra_options=normalized_extra_options(plant),
        min_interval_minutes=max(30, int(plant.watering_min_interval_minutes or 240)),
    )


async def get_watering_context(user_id: int, allocation_id: str) -> WateringContext:
    async with SessionLocal() as session:
        allocation, plant, slot, planting = await _context(session, user_id, allocation_id)
        return _out(allocation, plant, slot, planting)


async def set_watering_adjustment(
    user_id: int,
    allocation_id: str,
    percent: int,
) -> WateringContext:
    async with SessionLocal() as session:
        allocation, plant, slot, planting = await _context(session, user_id, allocation_id)
        allocation.watering_adjustment_percent = clamp_adjustment(plant, percent)
        await refresh_watering_tasks(session)
        await session.commit()
        return _out(allocation, plant, slot, planting)


async def buy_extra_watering(
    user_id: int,
    allocation_id: str,
    ml: int,
) -> tuple[WateringContext, WateringTask, int, int]:
    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        allocation, plant, slot, planting = await _context(session, user_id, allocation_id)
        if planting is None:
            raise WateringUnavailable("planting_not_started")

        option = next((item for item in normalized_extra_options(plant) if item["ml"] == int(ml)), None)
        if option is None:
            raise WateringUnavailable("extra_option_not_found")

        await refresh_watering_tasks(session, now=now)
        conflict_at = await watering_conflict(
            session,
            planting=planting,
            plant=plant,
            now=now,
        )
        if conflict_at is not None:
            raise ExtraWateringTooClose(conflict_at)

        wallet = (
            await session.execute(
                select(WalletAccount)
                .where(WalletAccount.user_id == user_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if wallet is None:
            wallet = WalletAccount(user_id=user_id, balance=0)
            session.add(wallet)
            await session.flush()

        price = int(option["price_kisa"])
        if wallet.balance < price:
            raise ExtraWateringInsufficientBalance(price=price, balance=int(wallet.balance))

        task = WateringTask(
            id=str(uuid4()),
            planting_id=planting.id,
            allocation_id=allocation.id,
            device_id=slot.device_id,
            rack_id=slot.rack_id,
            slot_number=slot.slot_number,
            scheduled_at=now,
            planned_ml=int(option["ml"]),
            task_type="extra",
            status="pending",
            note="Extra watering purchased by user",
            created_at=now,
        )
        session.add(task)

        if price:
            wallet.balance -= price
            session.add(
                WalletTransaction(
                    user_id=user_id,
                    amount=-price,
                    balance_after=wallet.balance,
                    kind="extra_watering",
                    reference_type="watering_task",
                    reference_id=task.id,
                    details={
                        "allocation_id": allocation.id,
                        "planting_id": planting.id,
                        "rack_id": slot.rack_id,
                        "slot_number": slot.slot_number,
                        "ml": int(option["ml"]),
                        "price_kisa": price,
                    },
                )
            )

        await session.commit()
        return _out(allocation, plant, slot, planting), task, int(wallet.balance), price
