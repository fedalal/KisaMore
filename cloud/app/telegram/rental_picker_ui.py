from __future__ import annotations

from . import worker_seed_inventory as rental


async def show_rental_plants(bot, chat_id: int, tg: dict, slot_id: int) -> None:
    """Show a compact rental list without growth days.

    Growth time remains available in the detailed plant card after the user
    opens a plant. Keeping it out of the first list avoids implying that the
    displayed number is an exact delivery/waiting time.
    """
    lang = rental.core.language_for(tg)
    slot = await rental._rental_slot(slot_id)
    if slot is None:
        await rental.show_rental_slots(bot, chat_id, tg)
        return

    plants = await rental.list_rentable_plants(50)
    plants.sort(
        key=lambda plant: (
            rental.core.plant_name(plant, lang).casefold(),
            (getattr(plant, "code", "") or "").casefold(),
        )
    )
    if not plants:
        await bot.send_message(
            chat_id,
            rental.seed_text(lang),
            reply_markup={
                "inline_keyboard": [[
                    {
                        "text": rental.core.st(lang, "back_garden"),
                        "callback_data": "menu:garden",
                    }
                ]]
            },
        )
        return

    rows = []
    for plant in plants:
        name = rental.core.plant_name(plant, lang)
        price = int(plant.rental_price_kisa or 0)
        rows.append([
            {
                "text": f"🌱 {name} · Ⓚ{price} · ℹ️"[:60],
                "callback_data": f"rent:info:{slot_id}:{plant.id}",
            }
        ])

    rows.append([
        {
            "text": rental.core.st(lang, "cancel"),
            "callback_data": "menu:garden",
        }
    ])
    await bot.send_message(
        chat_id,
        rental.core.st(
            lang,
            "rent_choose_plant",
            rack=slot.rack_id,
            slot=slot.slot_number,
        ),
        reply_markup={"inline_keyboard": rows},
    )


def install() -> None:
    # worker_seed_inventory's callbacks resolve show_rental_plants through the
    # module global at runtime, so replacing it here updates both the initial
    # rental flow and the "back to plants" action.
    rental.show_rental_plants = show_rental_plants
    rental.core.show_rental_plants = show_rental_plants
