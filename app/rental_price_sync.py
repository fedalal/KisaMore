from __future__ import annotations

from sqlalchemy import select

from .db import SessionLocal
from .models import Plant


def install_rental_price_sync(service) -> None:
    """Enrich growing snapshots with cloud-facing plant configuration.

    This wrapper keeps the stable transport code untouched while adding pricing
    and individual watering recipes to catalog synchronization.
    """
    if getattr(service, "_rental_price_sync_installed", False):
        return

    original_collect_snapshot = service.collect_snapshot

    async def collect_snapshot(*, include_growing: bool = False):
        snapshot = await original_collect_snapshot(include_growing=include_growing)
        if include_growing and snapshot.get("plants"):
            async with SessionLocal() as session:
                plants = (
                    await session.execute(
                        select(
                            Plant.id,
                            Plant.rental_price_kisa,
                            Plant.watering_schedule,
                            Plant.watering_adjustment_limit_percent,
                            Plant.watering_adjustment_step_percent,
                            Plant.watering_min_interval_minutes,
                            Plant.extra_watering_options,
                        )
                    )
                ).all()
            config = {
                plant_id: {
                    "rental_price_kisa": int(price),
                    "watering_schedule": schedule or [],
                    "watering_adjustment_limit_percent": int(limit_percent),
                    "watering_adjustment_step_percent": int(step_percent),
                    "watering_min_interval_minutes": int(min_interval),
                    "extra_watering_options": extra_options or [],
                }
                for (
                    plant_id,
                    price,
                    schedule,
                    limit_percent,
                    step_percent,
                    min_interval,
                    extra_options,
                ) in plants
            }
            for item in snapshot["plants"]:
                values = config.get(item.get("plant_id"))
                if values:
                    item.update(values)
                else:
                    item.setdefault("rental_price_kisa", 20)
                    item.setdefault("watering_schedule", [])
                    item.setdefault("watering_adjustment_limit_percent", 20)
                    item.setdefault("watering_adjustment_step_percent", 10)
                    item.setdefault("watering_min_interval_minutes", 240)
                    item.setdefault("extra_watering_options", [])
        return snapshot

    service.collect_snapshot = collect_snapshot
    service._rental_price_sync_installed = True
