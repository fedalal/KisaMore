from __future__ import annotations

import asyncio

from . import worker_admin as existing
from .daily_photo_notifications import install


core = existing.core
install(core)


if __name__ == "__main__":
    asyncio.run(core.run())
