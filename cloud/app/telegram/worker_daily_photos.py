from __future__ import annotations

import asyncio

from . import activity_notifier
from . import worker_admin as existing
from .daily_photo_notifications import install
from .gift_feedback import install as install_gift_feedback
from .plant_card_ui import install as install_plant_card_ui
from .reaction_refresh import install as install_reaction_refresh
from .rental_picker_ui import install as install_rental_picker_ui
from .rental_progress_notifier import install as install_rental_progress
from .watering_facts import install as install_watering_facts


core = existing.core
install(core)
install_rental_progress(core)
install_rental_picker_ui()
install_plant_card_ui(core)
install_reaction_refresh(core)
install_gift_feedback(core)
install_watering_facts(activity_notifier)


if __name__ == "__main__":
    asyncio.run(core.run())
