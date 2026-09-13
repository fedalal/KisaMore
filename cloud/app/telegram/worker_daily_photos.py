from __future__ import annotations

import asyncio

from . import worker_admin as existing
from .daily_photo_notifications import install
from .plant_card_ui import install as install_plant_card_ui
from .reaction_refresh import install as install_reaction_refresh
from .rental_picker_ui import install as install_rental_picker_ui
from .rental_progress_notifier import install as install_rental_progress


core = existing.core
install(core)
install_rental_progress(core)
install_rental_picker_ui()
install_plant_card_ui(core)
install_reaction_refresh(core)


if __name__ == "__main__":
    asyncio.run(core.run())
