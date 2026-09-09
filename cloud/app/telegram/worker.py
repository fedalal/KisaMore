from __future__ import annotations

import asyncio

from . import worker_core as core


async def show_rental_slots(bot, chat_id: int, tg: dict) -> None:
    """Start rental with the first available container instead of asking for a slot."""
    lang = core.language_for(tg)
    slots = await core.list_available_slots(1)
    if not slots:
        await bot.send_message(
            chat_id,
            core.st(lang, "rent_no_slots"),
            reply_markup={
                "inline_keyboard": [[
                    {"text": core.st(lang, "back_garden"), "callback_data": "menu:garden"}
                ]]
            },
        )
        return

    await core.show_rental_plants(bot, chat_id, tg, slots[0].id)


# Functions defined in worker_core resolve globals in that module at runtime,
# so replacing this function changes the existing rent:start flow without
# duplicating the rest of the bot worker.
core.show_rental_slots = show_rental_slots


if __name__ == "__main__":
    asyncio.run(core.run())
