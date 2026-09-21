from __future__ import annotations

import asyncio

from . import activity_notifier
from . import worker_admin as existing
from .broadcast_poll_selection import install as install_broadcast_poll_selection
from .broadcast_service import install as install_broadcasts
from .daily_photo_notifications import install
from .find_plant_game import install as install_find_plant_game
from .gamification import install as install_gamification
from .gamification_profile import install as install_gamification_profile
from .gamification_resilience import install as install_gamification_resilience
from .gift_feedback import install as install_gift_feedback
from .language_preferences import install as install_language_preferences
from .neighbor_notifier import install as install_neighbor_notifications
from .plant_card_ui import install as install_plant_card_ui
from .plant_sos import install as install_plant_sos
from .promotion_service import install as install_promotions
from .reaction_refresh import install as install_reaction_refresh
from .rentable_catalog import install as install_rentable_catalog
from .rental_picker_ui import install as install_rental_picker_ui
from .rental_progress_notifier import install as install_rental_progress
from .rental_engagement import install as install_rental_engagement
from .stars_monitor import telegram_stars_sync_loop
from .wallet_gift_notifier import install as install_wallet_gift_notifications
from .watering_facts import install as install_watering_facts


core = existing.core
install_rentable_catalog(core)
install(core)
install_rental_progress(core)
install_rental_engagement(core)
install_rental_picker_ui()
install_plant_card_ui(core)
install_reaction_refresh(core)
install_gift_feedback(core)
install_watering_facts(activity_notifier)
install_broadcasts(core)
install_neighbor_notifications(core)
install_wallet_gift_notifications(core)
install_language_preferences(core)
install_gamification(core)
install_gamification_profile(core)
install_find_plant_game(core)
install_gamification_resilience(core)
install_plant_sos(core)
install_promotions(core)
install_broadcast_poll_selection(core)


async def run() -> None:
    stars_task = asyncio.create_task(
        telegram_stars_sync_loop(),
        name="telegram-stars-monitor",
    )
    try:
        await core.run()
    finally:
        stars_task.cancel()
        try:
            await stars_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    asyncio.run(run())
