from __future__ import annotations

from sqlalchemy import select

from ..db import SessionLocal
from ..models import Plant
from ..seed_inventory import seed_availability
from . import worker_seed_inventory as rental


async def list_rentable_plants(limit: int = 30) -> list[Plant]:
    """Return up to ``limit`` plants that are actually rentable.

    The seed check must happen before applying the result limit.  The previous
    implementation limited the SQL query first, so ``limit=1`` checked only the
    alphabetically first active plant.  If that plant was out of stock the bot
    incorrectly reported that no crops were available even when later plants
    had enough seed.
    """
    requested = max(1, min(int(limit), 100))
    async with SessionLocal() as session:
        plants = list(
            (
                await session.execute(
                    select(Plant)
                    .where(Plant.active.is_(True))
                    .order_by(Plant.code)
                )
            ).scalars().all()
        )
        result: list[Plant] = []
        for plant in plants:
            if (await seed_availability(session, plant.id)).in_stock:
                result.append(plant)
                if len(result) >= requested:
                    break
        return result


def install(core) -> None:
    # worker_seed_inventory resolves this name from its module globals at call
    # time, while worker_core uses core.list_active_plants. Patch both so every
    # Telegram rental entry point uses the corrected catalogue semantics.
    rental.list_rentable_plants = list_rentable_plants
    core.list_active_plants = list_rentable_plants
