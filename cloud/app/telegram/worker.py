from __future__ import annotations

import asyncio

from sqlalchemy import select

from ..admin_models import PlantingPhoto
from ..db import SessionLocal
from . import worker_core as core
from .rental_service import create_rental_request, list_available_slots


_original_get_plant_card = core.get_plant_card


async def get_plant_card(planting_id: str, user_id: int):
    """Prefer an admin-published photo for this planting over the generic rack photo."""
    card = await _original_get_plant_card(planting_id, user_id)
    if card is None:
        return None
    async with SessionLocal() as session:
        photo = (
            await session.execute(
                select(PlantingPhoto)
                .where(
                    PlantingPhoto.planting_id == planting_id,
                    PlantingPhoto.is_public.is_(True),
                )
                .order_by(PlantingPhoto.published_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    if photo is not None:
        card.photo = photo
    return card


async def show_rental_plants(bot, chat_id: int, tg: dict, slot_id: int) -> None:
    """Show plants sorted by the localized name visible to the current user."""
    lang = core.language_for(tg)
    slots = await list_available_slots(50)
    slot = next((item for item in slots if item.id == slot_id), None)
    if slot is None:
        await show_rental_slots(bot, chat_id, tg)
        return

    plants = await core.list_active_plants(50)
    plants.sort(
        key=lambda plant: (
            core.plant_name(plant, lang).casefold(),
            (getattr(plant, "code", "") or "").casefold(),
        )
    )

    rows = [
        [
            {
                "text": f"🌱 {core.plant_name(plant, lang)}"[:60],
                "callback_data": f"rent:plant:{slot_id}:{plant.id}",
            }
        ]
        for plant in plants
    ]
    rows.append(
        [{"text": core.st(lang, "cancel"), "callback_data": "menu:garden"}]
    )
    await bot.send_message(
        chat_id,
        core.st(
            lang,
            "rent_choose_plant",
            rack=slot.rack_id,
            slot=slot.slot_number,
        ),
        reply_markup={"inline_keyboard": rows},
    )


async def show_rental_slots(bot, chat_id: int, tg: dict) -> None:
    """Start rental with the first truly available container."""
    lang = core.language_for(tg)
    slots = await list_available_slots(1)
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

    await show_rental_plants(bot, chat_id, tg, slots[0].id)


# Functions defined in worker_core resolve globals in that module at runtime.
# Replace only the small integration helpers without duplicating the whole worker.
core.get_plant_card = get_plant_card
core.list_available_slots = list_available_slots
core.create_rental_request = create_rental_request
core.show_rental_plants = show_rental_plants
core.show_rental_slots = show_rental_slots


if __name__ == "__main__":
    asyncio.run(core.run())
