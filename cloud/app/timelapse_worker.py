from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select

from .config import get_settings
from .db import SessionLocal, create_tables, engine
from .models import Planting, RackSlot
from .timelapse_service import (
    PERIODS,
    generate_slot_timelapse,
    period_window,
    planting_timelapse_path,
)


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)
settings = get_settings()
ACTIVE_STATUSES = ("planned", "growing", "ready")
ENDED_SLOT_STATUSES = ("available", "maintenance", "disabled", "empty")


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def _load_relevant_plantings() -> list[tuple[Planting, RackSlot]]:
    now = datetime.now(timezone.utc)
    recent = now - timedelta(days=2)
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(Planting, RackSlot)
                .join(RackSlot, RackSlot.id == Planting.slot_id)
                .where(
                    or_(
                        Planting.status.in_(ACTIVE_STATUSES),
                        Planting.actual_harvest_at >= recent,
                        Planting.observed_at >= recent,
                    )
                )
                .order_by(RackSlot.device_id, RackSlot.rack_id, RackSlot.slot_number, Planting.planted_at)
            )
        ).all()
    return list(rows)


def _position(slot: RackSlot) -> tuple[str, int, int]:
    return slot.device_id, slot.rack_id, slot.slot_number


async def run_once() -> None:
    now = datetime.now(timezone.utc)
    rows = await _load_relevant_plantings()
    by_position: dict[tuple[str, int, int], list[tuple[Planting, RackSlot]]] = {}
    for planting, slot in rows:
        by_position.setdefault(_position(slot), []).append((planting, slot))

    active_positions: dict[tuple[str, int, int], tuple[Planting, RackSlot]] = {}
    for key, items in by_position.items():
        items.sort(key=lambda item: _aware(item[0].planted_at) or datetime.min.replace(tzinfo=timezone.utc))
        planting, slot = items[-1]
        slot_status = str(slot.physical_status or "").lower()
        if planting.status in ACTIVE_STATUSES and slot_status not in ENDED_SLOT_STATUSES:
            active_positions[key] = (planting, slot)

    generated = 0
    skipped = 0
    failed = 0

    # Operational timelapses belong to the current physical container. Clamp
    # the rolling window to the current planting start so a new crop never shows
    # frames from the previous occupant of the same container.
    for (_device_id, _rack_id, _slot_number), (planting, slot) in active_positions.items():
        planted_at = _aware(planting.planted_at)
        if planted_at is None:
            continue
        for period in ("24h", "3d"):
            start_at, end_at = period_window(period, now)
            start_at = max(start_at, planted_at)
            try:
                path = await asyncio.to_thread(
                    generate_slot_timelapse,
                    photo_dir=settings.photo_dir,
                    device_id=slot.device_id,
                    rack_id=slot.rack_id,
                    slot_number=slot.slot_number,
                    period=period,
                    start_at=start_at,
                    end_at=end_at,
                )
                if path is None:
                    skipped += 1
                else:
                    generated += 1
            except Exception:
                failed += 1
                logger.exception(
                    "Could not generate %s timelapse for %s rack=%s slot=%s",
                    period,
                    slot.device_id,
                    slot.rack_id,
                    slot.slot_number,
                )

    # Full-cycle timelapses are tied to planting_id. A stale active status cannot
    # leak frames from the next crop: the next planting start (or an available
    # slot observation) becomes the previous cycle's effective end.
    for key, items in by_position.items():
        items.sort(key=lambda item: _aware(item[0].planted_at) or datetime.min.replace(tzinfo=timezone.utc))
        for index, (planting, slot) in enumerate(items):
            planted_at = _aware(planting.planted_at)
            if planted_at is None:
                continue
            next_start = None
            if index + 1 < len(items):
                next_start = _aware(items[index + 1][0].planted_at)

            is_current = active_positions.get(key, (None, None))[0] is planting
            if is_current:
                end_at = now
                final = False
            else:
                end_at = _aware(planting.actual_harvest_at)
                if end_at is None and next_start is not None:
                    end_at = next_start
                if end_at is None:
                    end_at = _aware(slot.observed_at) or _aware(planting.observed_at) or now
                final = True

            if end_at < planted_at:
                continue
            try:
                path = await asyncio.to_thread(
                    generate_slot_timelapse,
                    photo_dir=settings.photo_dir,
                    device_id=slot.device_id,
                    rack_id=slot.rack_id,
                    slot_number=slot.slot_number,
                    period="full",
                    start_at=planted_at,
                    end_at=end_at,
                    target=planting_timelapse_path(settings.photo_dir, planting.id),
                    final=final,
                )
                if path is None:
                    skipped += 1
                else:
                    generated += 1
            except Exception:
                failed += 1
                logger.exception("Could not generate full timelapse for planting %s", planting.id)

    logger.info(
        "Timelapse pass complete: plantings=%s active_positions=%s generated_or_current=%s skipped=%s failed=%s",
        len(rows),
        len(active_positions),
        generated,
        skipped,
        failed,
    )


async def run() -> None:
    await create_tables()
    interval = max(60, int(__import__("os").getenv("KISAMORE_TIMELAPSE_CHECK_SECONDS", "300")))
    logger.info(
        "KisaMore timelapse worker started: check=%ss, 24h refresh=%s, 3d refresh=%s, full refresh=%s",
        interval,
        PERIODS["24h"].refresh,
        PERIODS["3d"].refresh,
        PERIODS["full"].refresh,
    )
    try:
        while True:
            try:
                await run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Timelapse pass failed")
            await asyncio.sleep(interval)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
