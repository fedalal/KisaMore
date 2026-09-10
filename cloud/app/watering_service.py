from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .models import Allocation, Plant, Planting, RackSlot, WateringTask


# Watering is active only while the crop is actually growing. Once the
# operator marks it ready, no new scheduled watering is created and any
# remaining pending scheduled reminders are closed by refresh_watering_tasks().
ACTIVE_PLANTING_STATUSES = ("planned", "growing")


def aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def farm_zone() -> ZoneInfo:
    name = get_settings().farm_timezone
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def normalized_schedule(plant: Plant) -> list[dict]:
    result: list[dict] = []
    seen: set[str] = set()
    for raw in plant.watering_schedule or []:
        try:
            value = str(raw.get("time") or "")
            hour, minute = (int(part) for part in value.split(":", 1))
            ml = int(raw.get("ml") or 0)
        except (AttributeError, TypeError, ValueError):
            continue
        if not (0 <= hour <= 23 and 0 <= minute <= 59 and 1 <= ml <= 2000):
            continue
        key = f"{hour:02d}:{minute:02d}"
        if key in seen:
            continue
        seen.add(key)
        result.append({"time": key, "ml": ml})
    result.sort(key=lambda item: item["time"])
    return result


def normalized_extra_options(plant: Plant) -> list[dict]:
    result: list[dict] = []
    seen: set[int] = set()
    for raw in plant.extra_watering_options or []:
        try:
            ml = int(raw.get("ml") or 0)
            price = int(raw.get("price_kisa") or 0)
        except (AttributeError, TypeError, ValueError):
            continue
        if not (1 <= ml <= 2000 and 0 <= price <= 1_000_000) or ml in seen:
            continue
        seen.add(ml)
        result.append({"ml": ml, "price_kisa": price})
    result.sort(key=lambda item: item["ml"])
    return result


def adjustment_values(plant: Plant) -> list[int]:
    limit = max(0, min(50, int(plant.watering_adjustment_limit_percent or 0)))
    step = max(1, min(25, int(plant.watering_adjustment_step_percent or 10)))
    values = {0}
    value = step
    while value <= limit:
        values.add(value)
        values.add(-value)
        value += step
    if limit:
        values.add(limit)
        values.add(-limit)
    return sorted(values)


def clamp_adjustment(plant: Plant, value: int) -> int:
    requested = int(value)
    allowed = adjustment_values(plant)
    if requested not in allowed:
        raise ValueError("invalid_watering_adjustment")
    return requested


def effective_ml(base_ml: int, adjustment_percent: int) -> int:
    return max(1, int(round(int(base_ml) * (100 + int(adjustment_percent)) / 100)))


def effective_schedule(plant: Plant, adjustment_percent: int) -> list[dict]:
    return [
        {**item, "ml": effective_ml(item["ml"], adjustment_percent)}
        for item in normalized_schedule(plant)
    ]


def schedule_occurrences(
    plant: Plant,
    *,
    start_at: datetime,
    end_at: datetime,
) -> list[tuple[datetime, int]]:
    start = aware_utc(start_at)
    end = aware_utc(end_at)
    if start is None or end is None or end < start:
        return []
    zone = farm_zone()
    local_start = start.astimezone(zone)
    local_end = end.astimezone(zone)
    schedule = normalized_schedule(plant)
    if not schedule:
        return []

    result: list[tuple[datetime, int]] = []
    day = local_start.date()
    last_day = local_end.date()
    while day <= last_day:
        for item in schedule:
            hour, minute = (int(part) for part in item["time"].split(":", 1))
            local_value = datetime.combine(day, time(hour=hour, minute=minute), tzinfo=zone)
            utc_value = local_value.astimezone(timezone.utc)
            if start <= utc_value <= end:
                result.append((utc_value, item["ml"]))
        day += timedelta(days=1)
    result.sort(key=lambda item: item[0])
    return result


async def allocation_for_planting(
    session: AsyncSession,
    planting: Planting,
    slot: RackSlot,
) -> Allocation | None:
    if planting.cloud_allocation_id:
        allocation = await session.get(Allocation, planting.cloud_allocation_id)
        if allocation is not None and allocation.status == "active":
            return allocation
    return (
        await session.execute(
            select(Allocation)
            .where(
                Allocation.device_id == slot.device_id,
                Allocation.rack_id == slot.rack_id,
                Allocation.slot_number == slot.slot_number,
                Allocation.status == "active",
            )
            .order_by(Allocation.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def allocation_context(
    session: AsyncSession,
    *,
    marketplace_user_id: str,
    allocation_id: str,
):
    allocation = (
        await session.execute(
            select(Allocation)
            .where(
                Allocation.id == allocation_id,
                Allocation.user_id == marketplace_user_id,
                Allocation.status == "active",
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if allocation is None or allocation.resource_type != "slot" or allocation.slot_number is None:
        return None
    plant = await session.get(Plant, allocation.plant_id) if allocation.plant_id else None
    if plant is None:
        return None
    slot = (
        await session.execute(
            select(RackSlot).where(
                RackSlot.device_id == allocation.device_id,
                RackSlot.rack_id == allocation.rack_id,
                RackSlot.slot_number == allocation.slot_number,
            )
        )
    ).scalar_one_or_none()
    if slot is None:
        return None
    planting = (
        await session.execute(
            select(Planting)
            .where(
                Planting.slot_id == slot.id,
                Planting.plant_id == plant.id,
                Planting.status.in_(ACTIVE_PLANTING_STATUSES),
            )
            .order_by(Planting.planted_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return allocation, plant, slot, planting


async def refresh_watering_tasks(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    horizon_hours: int = 48,
    lookback_hours: int = 24,
) -> dict[str, int]:
    now_utc = aware_utc(now or datetime.now(timezone.utc))
    assert now_utc is not None
    start = now_utc - timedelta(hours=max(1, lookback_hours))
    end = now_utc + timedelta(hours=max(1, horizon_hours))

    rows = (
        await session.execute(
            select(Planting, Plant, RackSlot)
            .join(Plant, Plant.id == Planting.plant_id)
            .join(RackSlot, RackSlot.id == Planting.slot_id)
            .where(Planting.status.in_(ACTIVE_PLANTING_STATUSES))
            .order_by(RackSlot.rack_id, RackSlot.slot_number, Planting.planted_at)
        )
    ).all()
    active_ids = {planting.id for planting, _, _ in rows}

    existing = list(
        (
            await session.execute(
                select(WateringTask).where(
                    WateringTask.task_type == "scheduled",
                    WateringTask.scheduled_at >= start,
                    WateringTask.scheduled_at <= end,
                )
            )
        ).scalars().all()
    )
    existing_by_key = {
        (task.planting_id, aware_utc(task.scheduled_at)): task
        for task in existing
    }

    desired: set[tuple[str, datetime]] = set()
    created = 0
    updated = 0
    skipped = 0

    for planting, plant, slot in rows:
        planted_at = aware_utc(planting.planted_at)
        if planted_at is None:
            continue
        allocation = await allocation_for_planting(session, planting, slot)
        adjustment = int(allocation.watering_adjustment_percent or 0) if allocation else 0
        try:
            adjustment = clamp_adjustment(plant, adjustment)
        except ValueError:
            adjustment = 0
        for scheduled_at, base_ml in schedule_occurrences(plant, start_at=start, end_at=end):
            if scheduled_at < planted_at:
                continue
            key = (planting.id, scheduled_at)
            desired.add(key)
            planned_ml = effective_ml(base_ml, adjustment)
            task = existing_by_key.get(key)
            if task is None:
                task = WateringTask(
                    id=str(uuid4()),
                    planting_id=planting.id,
                    allocation_id=allocation.id if allocation else None,
                    device_id=slot.device_id,
                    rack_id=slot.rack_id,
                    slot_number=slot.slot_number,
                    scheduled_at=scheduled_at,
                    planned_ml=planned_ml,
                    task_type="scheduled",
                    status="pending",
                    created_at=now_utc,
                )
                session.add(task)
                existing_by_key[key] = task
                created += 1
            elif task.status == "pending" and scheduled_at > now_utc:
                changed = False
                if task.planned_ml != planned_ml:
                    task.planned_ml = planned_ml
                    changed = True
                allocation_id = allocation.id if allocation else None
                if task.allocation_id != allocation_id:
                    task.allocation_id = allocation_id
                    changed = True
                if changed:
                    updated += 1

    # If the operator changes a plant schedule, obsolete future tasks must not
    # remain in the admin queue. Completed history is never modified.
    for task in existing:
        key = (task.planting_id, aware_utc(task.scheduled_at))
        scheduled_at = aware_utc(task.scheduled_at)
        if (
            task.status == "pending"
            and scheduled_at is not None
            and scheduled_at > now_utc
            and key not in desired
        ):
            task.status = "skipped"
            task.note = "Schedule changed or planting is no longer active"
            skipped += 1

    # Also close pending scheduled tasks left behind when a planting is ready,
    # harvested or cancelled. This keeps obsolete reminders out of the queue.
    stale = list(
        (
            await session.execute(
                select(WateringTask).where(
                    WateringTask.task_type == "scheduled",
                    WateringTask.status == "pending",
                )
            )
        ).scalars().all()
    )
    for task in stale:
        if task.planting_id not in active_ids:
            task.status = "skipped"
            task.note = "Planting is ready or no longer active"
            skipped += 1

    await session.flush()
    return {
        "active_plantings": len(rows),
        "created": created,
        "updated": updated,
        "skipped": skipped,
    }


async def watering_conflict(
    session: AsyncSession,
    *,
    planting: Planting,
    plant: Plant,
    now: datetime | None = None,
) -> datetime | None:
    now_utc = aware_utc(now or datetime.now(timezone.utc))
    assert now_utc is not None
    interval = timedelta(minutes=max(30, int(plant.watering_min_interval_minutes or 240)))

    for scheduled_at, _ in schedule_occurrences(
        plant,
        start_at=now_utc - interval,
        end_at=now_utc + interval,
    ):
        if abs((scheduled_at - now_utc).total_seconds()) <= interval.total_seconds():
            return scheduled_at

    task = (
        await session.execute(
            select(WateringTask)
            .where(
                WateringTask.planting_id == planting.id,
                WateringTask.status.in_(("pending", "done")),
                WateringTask.scheduled_at >= now_utc - interval,
                WateringTask.scheduled_at <= now_utc + interval,
            )
            .order_by(WateringTask.scheduled_at)
            .limit(1)
        )
    ).scalar_one_or_none()
    return aware_utc(task.scheduled_at) if task else None
