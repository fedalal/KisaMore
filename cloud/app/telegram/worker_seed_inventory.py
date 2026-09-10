from __future__ import annotations

import asyncio

from ..seed_inventory import list_rentable_plants
from . import worker_watering as existing


# worker.py renders the plant picker through core.list_active_plants at runtime.
# Replace that source with the stock-aware list while keeping all existing
# watering, lifecycle, photo and rental-notification wrappers intact.
core = existing.core
core.list_active_plants = list_rentable_plants


if __name__ == "__main__":
    asyncio.run(core.run())
