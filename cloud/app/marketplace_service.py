from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .models import (
    Allocation,
    Notification,
    Offer,
    Plant,
    Planting,
    RackSlot,
    ReservationRequest,
)
from .seed_inventory import consume_seed_for_planting


def aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def sync_edge_inventory(session: AsyncSession, device_id: str, payload, now: datetime) -> None:
    """Upsert the plant catalog and six physical slots reported by an edge device."""
    planting_inputs = [
        incoming.planting
        for rack in payload.racks
        for incoming in rack.slots
        if incoming.planting is not None
    ]
    required_plant_ids = {
        *(incoming.plant_id for incoming in payload.plants),
        *(incoming.plant_id for incoming in planting_inputs),
    }
    plants_by_id: dict[str, Plant] = {}
    if required_plant_ids:
        plants = (
            await session.execute(select(Plant).where(Plant.id.in_(required_plant_ids)))
        ).scalars().all()
        plants_by_id = {plant.id: plant for plant in plants}

    for incoming in payload.plants:
        plant = plants_by_id.get(incoming.plant_id)
        if plant is None:
            plant = Plant(id=incoming.plant_id, code=incoming.code)
            session.add(plant)
            plants_by_id[plant.id] = plant
        plant.code = incoming.code
        plant.names = incoming.names
        plant.descriptions = incoming.descriptions
        plant.seed_image_name = incoming.seed_image_name
        plant.microgreen_image_name = incoming.microgreen_image_name
        plant.grow_days = incoming.grow_days
        plant.rental_price_kisa = incoming.rental_price_kisa
        plant.watering_schedule = [item.model_dump() for item in incoming.watering_schedule]
        plant.watering_adjustment_limit_percent = incoming.watering_adjustment_limit_percent
        plant.watering_adjustment_step_percent = incoming.watering_adjustment_step_percent
        plant.watering_min_interval_minutes = incoming.watering_min_interval_minutes
        plant.extra_watering_options = [item.model_dump() for item in incoming.extra_watering_options]
        plant.active = incoming.active
        plant.edge_updated_at = incoming.updated_at
    await session.flush()

    rack_ids = {rack.rack_id for rack in payload.racks}
    slots_by_key: dict[tuple[int, int], RackSlot] = {}
    if rack_ids:
        slots = (
            await session.execute(
                select(RackSlot).where(
                    RackSlot.device_id == device_id,
                    RackSlot.rack_id.in_(rack_ids),
                )
            )
        ).scalars().all()
        slots_by_key = {
            (slot.rack_id, slot.slot_number): slot
            for slot in slots
        }

    planting_slots: list[tuple[RackSlot, object]] = []
    for rack in payload.racks:
        for incoming in rack.slots:
            slot_key = (rack.rack_id, incoming.slot_number)
            slot = slots_by_key.get(slot_key)
            if slot is None:
                slot = RackSlot(
                    device_id=device_id,
                    rack_id=rack.rack_id,
                    slot_number=incoming.slot_number,
                    observed_at=payload.observed_at,
                )
                session.add(slot)
                slots_by_key[slot_key] = slot
            slot.physical_status = incoming.status
            slot.enabled = incoming.enabled
            slot.edge_allocation_id = incoming.cloud_allocation_id
            slot.requested_plant_id = incoming.requested_plant_id
            slot.observed_at = payload.observed_at
            slot.expected_available_at = (
                incoming.planting.expected_harvest_at
                if incoming.planting and incoming.planting.status in ("planned", "growing", "ready")
                else None
            )

            if incoming.planting:
                planting_slots.append((slot, incoming.planting))

    # One flush assigns IDs to every newly discovered slot instead of flushing
    # once per container. This keeps a four-rack snapshot well below the edge
    # request timeout even on a small VPS.
    await session.flush()

    planting_ids = {incoming.planting_id for _, incoming in planting_slots}
    plantings_by_id: dict[str, Planting] = {}
    if planting_ids:
        plantings = (
            await session.execute(
                select(Planting).where(Planting.id.in_(planting_ids))
            )
        ).scalars().all()
        plantings_by_id = {planting.id: planting for planting in plantings}

    for slot, incoming in planting_slots:
        if incoming.plant_id not in plants_by_id:
            if getattr(payload, "inventory_sync_id", None):
                raise ValueError("cannot confirm inventory with an unknown plant")
            # Rejecting the whole sensor snapshot would hide healthy telemetry.
            # The next snapshot will repair this after the edge catalog is synced.
            continue
        planting = plantings_by_id.get(incoming.planting_id)
        if planting is None:
            planting = Planting(
                id=incoming.planting_id,
                slot_id=slot.id,
                plant_id=incoming.plant_id,
                planted_at=incoming.planted_at,
                expected_harvest_at=incoming.expected_harvest_at,
                status=incoming.status,
                observed_at=payload.observed_at,
            )
            session.add(planting)
            plantings_by_id[planting.id] = planting
        planting.slot_id = slot.id
        planting.plant_id = incoming.plant_id
        planting.planted_at = incoming.planted_at
        planting.expected_harvest_at = incoming.expected_harvest_at
        planting.actual_harvest_at = incoming.actual_harvest_at
        planting.status = incoming.status
        planting.cloud_allocation_id = incoming.cloud_allocation_id
        planting.observed_at = payload.observed_at

        # Seed is physically consumed only when Raspberry reports that the
        # planting has actually started. The unique planting reference makes
        # repeated delta/full snapshots idempotent.
        await consume_seed_for_planting(
            session,
            planting=planting,
            plant=plants_by_id[incoming.plant_id],
        )

    # Finishing the physical growing cycle is also the natural end of a slot
    # rental. This keeps Telegram's "My Garden" in sync with what the operator
    # did on the Raspberry Pi and removes watering controls immediately after
    # the harvested state reaches the cloud.
    completed = await complete_harvested_allocations(session, device_id=device_id, now=now)
    if completed:
        await process_waitlist(session, device_id)


async def complete_harvested_allocations(
    session: AsyncSession,
    *,
    device_id: str | None = None,
    now: datetime | None = None,
) -> int:
    """Complete active allocations whose linked planting has been harvested.

    The allocation id stored on the planting is used deliberately. Matching by
    rack/slot alone could accidentally close a newer rental after a container is
    reused. Telegram rental requests are marked completed as part of the same
    transaction, so the completed rental disappears from My Garden and its
    watering button becomes unavailable.
    """
    from .telegram.models import TelegramRentalRequest

    completed_at = aware_utc(now or datetime.now(timezone.utc)) or datetime.now(timezone.utc)
    query = (
        select(Allocation, Planting)
        .join(Planting, Planting.cloud_allocation_id == Allocation.id)
        .where(
            Allocation.status == "active",
            Planting.status == "harvested",
        )
        .order_by(Planting.observed_at)
    )
    if device_id:
        query = query.where(Allocation.device_id == device_id)

    rows = (await session.execute(query)).all()
    count = 0
    for allocation, planting in rows:
        end_at = (
            aware_utc(planting.actual_harvest_at)
            or aware_utc(planting.observed_at)
            or completed_at
        )
        allocation.status = "completed"
        allocation.ends_at = end_at

        requests = list(
            (
                await session.execute(
                    select(TelegramRentalRequest).where(
                        TelegramRentalRequest.note == f"allocation:{allocation.id}",
                        TelegramRentalRequest.status == "approved",
                    )
                )
            ).scalars().all()
        )
        for request in requests:
            request.status = "completed"
            request.updated_at = completed_at

        count += 1

    if count:
        await session.flush()
    return count


async def active_inventory(session: AsyncSession, device_id: str):
    now = datetime.now(timezone.utc)
    slots = (
        await session.execute(
            select(RackSlot)
            .where(RackSlot.device_id == device_id)
            .order_by(RackSlot.rack_id, RackSlot.slot_number)
        )
    ).scalars().all()
    allocations = (
        await session.execute(
            select(Allocation).where(
                Allocation.device_id == device_id,
                Allocation.status == "active",
            )
        )
    ).scalars().all()
    offers = (
        await session.execute(
            select(Offer).where(
                Offer.device_id == device_id,
                Offer.status == "pending",
                Offer.expires_at > now,
            )
        )
    ).scalars().all()
    return slots, allocations, offers


def slot_is_blocked(rack_id: int, slot_number: int, allocations, offers) -> bool:
    for item in [*allocations, *offers]:
        if item.rack_id != rack_id:
            continue
        if item.resource_type == "rack" or item.slot_number == slot_number:
            return True
    return False


def find_available_target(resource_type: str, rack_id: int | None, slot_number: int | None, slots, allocations, offers):
    usable = [slot for slot in slots if slot.enabled and slot.physical_status == "available"]
    if resource_type == "slot":
        for slot in usable:
            if rack_id is not None and slot.rack_id != rack_id:
                continue
            if slot_number is not None and slot.slot_number != slot_number:
                continue
            if not slot_is_blocked(slot.rack_id, slot.slot_number, allocations, offers):
                return slot.rack_id, slot.slot_number
        return None

    rack_ids = sorted({slot.rack_id for slot in slots})
    for candidate_rack_id in rack_ids:
        if rack_id is not None and candidate_rack_id != rack_id:
            continue
        rack_slots = [slot for slot in usable if slot.rack_id == candidate_rack_id]
        if {slot.slot_number for slot in rack_slots} != set(range(1, 7)):
            continue
        if any(
            slot_is_blocked(candidate_rack_id, candidate_slot, allocations, offers)
            for candidate_slot in range(1, 7)
        ):
            continue
        return candidate_rack_id, None
    return None


async def expire_offers(session: AsyncSession, now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    offers = (
        await session.execute(
            select(Offer).where(Offer.status == "pending", Offer.expires_at <= now)
        )
    ).scalars().all()
    for offer in offers:
        offer.status = "expired"
        reservation = await session.get(ReservationRequest, offer.reservation_id)
        if reservation:
            reservation.status = "expired"
            reservation.updated_at = now
        session.add(
            Notification(
                id=str(uuid4()),
                user_id=offer.user_id,
                kind="offer_expired",
                payload={"offer_id": offer.id},
                created_at=now,
            )
        )


async def process_waitlist(session: AsyncSession, device_id: str | None = None) -> None:
    """Create FIFO, time-limited offers for requests that can now be fulfilled."""
    now = datetime.now(timezone.utc)
    await expire_offers(session, now)
    query = select(ReservationRequest).where(ReservationRequest.status == "waiting")
    if device_id:
        query = query.where(ReservationRequest.device_id == device_id)
    reservations = (
        await session.execute(query.order_by(ReservationRequest.created_at))
    ).scalars().all()

    inventory_cache: dict[str, tuple] = {}
    for reservation in reservations:
        if reservation.device_id not in inventory_cache:
            inventory_cache[reservation.device_id] = await active_inventory(
                session, reservation.device_id
            )
        slots, allocations, offers = inventory_cache[reservation.device_id]
        target = find_available_target(
            reservation.resource_type,
            reservation.rack_id,
            reservation.slot_number,
            slots,
            allocations,
            offers,
        )
        if target is None:
            continue
        rack_id, slot_number = target
        offer = Offer(
            id=str(uuid4()),
            reservation_id=reservation.id,
            user_id=reservation.user_id,
            device_id=reservation.device_id,
            resource_type=reservation.resource_type,
            rack_id=rack_id,
            slot_number=slot_number,
            plant_id=reservation.plant_id,
            status="pending",
            expires_at=now + timedelta(hours=get_settings().offer_hours),
            created_at=now,
        )
        session.add(offer)
        offers.append(offer)
        reservation.status = "offered"
        reservation.updated_at = now
        session.add(
            Notification(
                id=str(uuid4()),
                user_id=reservation.user_id,
                kind="availability_offer",
                payload={
                    "offer_id": offer.id,
                    "resource_type": offer.resource_type,
                    "rack_id": rack_id,
                    "slot_number": slot_number,
                    "expires_at": offer.expires_at.isoformat(),
                },
                created_at=now,
            )
        )
