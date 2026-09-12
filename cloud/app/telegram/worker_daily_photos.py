from __future__ import annotations

import asyncio

from . import worker_admin as existing
from .daily_photo_notifications import install
from .rental_progress_notifier import install as install_rental_progress


core = existing.core
install(core)
install_rental_progress(core)


if __name__ == "__main__":
    asyncio.run(core.run())
