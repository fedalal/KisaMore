from __future__ import annotations

from sqlalchemy import select

from .db import SessionLocal
from .models import Plant


def install_fact_sync(service) -> None:
    """Attach multilingual plant fact pools to growing snapshots.

    The core transport stays unchanged; this wrapper only enriches catalog
    records when growing data is included.
    """
    if getattr(service, "_fact_sync_installed", False):
        return

    original_collect_snapshot = service.collect_snapshot

    async def collect_snapshot(*, include_growing: bool = False):
        snapshot = await original_collect_snapshot(include_growing=include_growing)
        if include_growing and snapshot.get("plants"):
            async with SessionLocal() as session:
                rows = (
                    await session.execute(select(Plant.id, Plant.facts))
                ).all()
            facts_by_id = {plant_id: facts or {} for plant_id, facts in rows}
            for item in snapshot["plants"]:
                item["facts"] = facts_by_id.get(item.get("plant_id"), {})
        return snapshot

    service.collect_snapshot = collect_snapshot
    service._fact_sync_installed = True
