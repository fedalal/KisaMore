from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import floor
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from .db import SessionLocal
from .models import Allocation, Base, Plant, Planting, ReservationRequest
from .telegram.models import TelegramRentalRequest


class SeedInventorySetting(Base):
    __tablename__ = "seed_inventory_settings"

    plant_id: Mapped[str] = mapped_column(ForeignKey("plants.id"), primary_key=True)
    seed_rate_g: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SeedInventoryTransaction(Base):
    __tablename__ = "seed_inventory_transactions"
    __table_args__ = (
        UniqueConstraint(
            "movement_type",
            "reference_type",
            "reference_id",
            name="uq_seed_inventory_reference",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    plant_id: Mapped[str] = mapped_column(ForeignKey("plants.id"), index=True, nullable=False)
    amount_g: Mapped[float] = mapped_column(Float, nullable=False)
    movement_type: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reference_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    admin_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)


@dataclass(frozen=True)
class SeedAvailability:
    plant_id: str
    seed_rate_g: float
    balance_g: float
    reserved_plantings: int
    reserved_g: float
    available_g: float
    available_plantings: int
    in_stock: bool


class SeedUnavailable(ValueError):
    def __init__(self, availability: SeedAvailability):
        super().__init__("seed_unavailable")
        self.availability = availability


def _round_g(value: float) -> float:
    return round(float(value or 0.0), 3)


async def seed_rate_g(session: AsyncSession, plant_id: str) -> float:
    setting = await session.get(SeedInventorySetting, plant_id)
    return _round_g(setting.seed_rate_g if setting else 0.0)


async def seed_balance_g(session: AsyncSession, plant_id: str) -> float:
    value = (
        await session.execute(
            select(func.coalesce(func.sum(SeedInventoryTransaction.amount_g), 0.0)).where(
                SeedInventoryTransaction.plant_id == plant_id
            )
        )
    ).scalar_one()
    return _round_g(value)


async def reserved_plantings(session: AsyncSession, plant_id: str) -> int:
    """Return seed portions promised but not yet physically planted.

    Requested Telegram rentals and generic marketplace reservations reserve one
    planting portion. Approved/direct purchases are represented by an active
    Allocation; once Raspberry reports a Planting for that allocation the seed
    is consumed automatically and no longer counted as reserved.
    """
    telegram_requested = int(
        (
            await session.execute(
                select(func.count(TelegramRentalRequest.id)).where(
                    TelegramRentalRequest.plant_id == plant_id,
                    TelegramRentalRequest.status == "requested",
                )
            )
        ).scalar_one()
        or 0
    )

    marketplace_reserved = int(
        (
            await session.execute(
                select(func.count(ReservationRequest.id)).where(
                    ReservationRequest.plant_id == plant_id,
                    ReservationRequest.status.in_(("waiting", "offered")),
                )
            )
        ).scalar_one()
        or 0
    )

    active_allocations = list(
        (
            await session.execute(
                select(Allocation.id).where(
                    Allocation.plant_id == plant_id,
                    Allocation.status == "active",
                )
            )
        ).scalars().all()
    )
    unplanted_allocations = 0
    if active_allocations:
        planted_allocation_ids = set(
            (
                await session.execute(
                    select(Planting.cloud_allocation_id).where(
                        Planting.cloud_allocation_id.in_(active_allocations)
                    )
                )
            ).scalars().all()
        )
        unplanted_allocations = sum(
            1 for allocation_id in active_allocations if allocation_id not in planted_allocation_ids
        )

    return telegram_requested + marketplace_reserved + unplanted_allocations


async def seed_availability(session: AsyncSession, plant_id: str) -> SeedAvailability:
    rate = await seed_rate_g(session, plant_id)
    balance = await seed_balance_g(session, plant_id)
    reserved_count = await reserved_plantings(session, plant_id)
    reserved_g = _round_g(rate * reserved_count)
    available_g = _round_g(max(0.0, balance - reserved_g))
    available_plantings = 0
    if rate > 0:
        available_plantings = max(0, floor((available_g + 1e-9) / rate))
    return SeedAvailability(
        plant_id=plant_id,
        seed_rate_g=rate,
        balance_g=balance,
        reserved_plantings=reserved_count,
        reserved_g=reserved_g,
        available_g=available_g,
        available_plantings=available_plantings,
        in_stock=rate > 0 and available_plantings > 0,
    )


async def require_seed_available(session: AsyncSession, plant_id: str) -> SeedAvailability:
    availability = await seed_availability(session, plant_id)
    if not availability.in_stock:
        raise SeedUnavailable(availability)
    return availability


async def list_rentable_plants(limit: int = 30) -> list[Plant]:
    async with SessionLocal() as session:
        plants = list(
            (
                await session.execute(
                    select(Plant)
                    .where(Plant.active.is_(True))
                    .order_by(Plant.code)
                    .limit(max(1, min(limit, 100)))
                )
            ).scalars().all()
        )
        result: list[Plant] = []
        for plant in plants:
            if (await seed_availability(session, plant.id)).in_stock:
                result.append(plant)
        return result


async def set_seed_rate(
    session: AsyncSession,
    plant_id: str,
    seed_rate: float,
) -> SeedInventorySetting:
    value = _round_g(seed_rate)
    if value < 0 or value > 5000:
        raise ValueError("invalid_seed_rate")
    setting = await session.get(SeedInventorySetting, plant_id)
    now = datetime.now(timezone.utc)
    if setting is None:
        setting = SeedInventorySetting(
            plant_id=plant_id,
            seed_rate_g=value,
            updated_at=now,
        )
        session.add(setting)
    else:
        setting.seed_rate_g = value
        setting.updated_at = now
    await session.flush()
    return setting


async def add_seed_movement(
    session: AsyncSession,
    *,
    plant_id: str,
    movement_type: str,
    amount_g: float,
    note: str = "",
    admin_user_id: str | None = None,
) -> SeedInventoryTransaction:
    if movement_type not in ("receipt", "writeoff"):
        raise ValueError("invalid_movement_type")
    amount = _round_g(amount_g)
    if amount <= 0 or amount > 1_000_000:
        raise ValueError("invalid_seed_amount")

    # Serialize manual stock changes and rental reservations for this plant.
    plant = (
        await session.execute(
            select(Plant).where(Plant.id == plant_id).with_for_update()
        )
    ).scalar_one_or_none()
    if plant is None:
        raise ValueError("plant_not_found")

    availability = await seed_availability(session, plant_id)
    if movement_type == "writeoff" and amount > availability.available_g + 1e-9:
        raise SeedUnavailable(availability)

    signed = amount if movement_type == "receipt" else -amount
    movement = SeedInventoryTransaction(
        id=str(uuid4()),
        plant_id=plant_id,
        amount_g=signed,
        movement_type=movement_type,
        note=(note or "").strip() or None,
        admin_user_id=admin_user_id,
        created_at=datetime.now(timezone.utc),
    )
    session.add(movement)
    await session.flush()
    return movement


async def consume_seed_for_planting(
    session: AsyncSession,
    *,
    planting: Planting,
    plant: Plant,
) -> SeedInventoryTransaction | None:
    """Write off one configured seed portion exactly once per real planting."""
    if planting.status not in ("growing", "ready", "harvested"):
        return None

    rate = await seed_rate_g(session, plant.id)
    if rate <= 0:
        return None

    existing = (
        await session.execute(
            select(SeedInventoryTransaction.id).where(
                SeedInventoryTransaction.movement_type == "planting",
                SeedInventoryTransaction.reference_type == "planting",
                SeedInventoryTransaction.reference_id == planting.id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return None

    # Physical planting is the source of truth. If stock bookkeeping was wrong,
    # allow the ledger to become negative instead of hiding the real consumption.
    movement = SeedInventoryTransaction(
        id=str(uuid4()),
        plant_id=plant.id,
        amount_g=-rate,
        movement_type="planting",
        note="Automatic write-off when planting started",
        reference_type="planting",
        reference_id=planting.id,
        created_at=datetime.now(timezone.utc),
    )
    session.add(movement)
    await session.flush()
    return movement
