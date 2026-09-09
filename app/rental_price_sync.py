from __future__ import annotations

from sqlalchemy import select

from .db import SessionLocal
from .models import Plant


def install_rental_price_sync(service) -> None:
    """Enrich growing snapshots with the plant rental price.

    Kept separate from CloudSyncService so the pricing feature does not disturb
    the already stable MQTT/delta transport code.
    """
    if getattr(service, "_rental_price_sync_installed", False):
        return

    original_collect_snapshot = service.collect_snapshot

    async def collect_snapshot(*, include_growing: bool = False):
        snapshot = await original_collect_snapshot(include_growing=include_growing)
        if include_growing and snapshot.get("plants"):
            async with SessionLocal() as session:
                plants = (
                    await session.execute(select(Plant.id, Plant.rental_price_kisa))
                ).all()
            prices = {plant_id: int(price) for plant_id, price in plants}
            for item in snapshot["plants"]:
                item["rental_price_kisa"] = prices.get(item.get("plant_id"), 20)
        return snapshot

    service.collect_snapshot = collect_snapshot
    service._rental_price_sync_installed = True
