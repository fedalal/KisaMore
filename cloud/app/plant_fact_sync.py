from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from .plant_fact_models import PlantFactPool


async def sync_plant_fact_pools(session: AsyncSession, payload) -> int:
    """Upsert multilingual fact pools included in an edge inventory delta."""
    changed = 0
    now = datetime.now(timezone.utc)
    for incoming in payload.plants:
        facts = incoming.facts or {}
        record = await session.get(PlantFactPool, incoming.plant_id)
        if record is None:
            record = PlantFactPool(
                plant_id=incoming.plant_id,
                facts=facts,
                updated_at=now,
            )
            session.add(record)
            changed += 1
        elif record.facts != facts:
            record.facts = facts
            record.updated_at = now
            changed += 1
    if changed:
        await session.flush()
    return changed
