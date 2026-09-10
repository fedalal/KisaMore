from __future__ import annotations

import asyncio

from ..seed_inventory import list_rentable_plants
from . import worker_watering as existing


core = existing.core

SEED_TEXT = {
    "en": "🌾 There are currently no plants with enough seeds for a new container.",
    "ru": "🌾 Сейчас нет растений с достаточным остатком семян для нового контейнера.",
    "de": "🌾 Zurzeit gibt es keine Pflanzen mit genügend Saatgut für einen neuen Behälter.",
    "fr": "🌾 Il n’y a actuellement aucune plante avec assez de graines pour un nouveau bac.",
    "es": "🌾 Ahora no hay plantas con suficientes semillas para un contenedor nuevo.",
    "it": "🌾 Al momento non ci sono piante con semi sufficienti per un nuovo contenitore.",
    "pt": "🌾 No momento não há plantas com sementes suficientes para um novo recipiente.",
    "pl": "🌾 Obecnie nie ma roślin z wystarczającą ilością nasion na nowy pojemnik.",
    "zh": "🌾 目前没有种子库存足够用于新容器的植物。",
}


def seed_text(lang: str) -> str:
    return SEED_TEXT.get(lang) or SEED_TEXT["en"]


async def show_rental_plants(bot, chat_id: int, tg: dict, slot_id: int) -> None:
    """Only offer plants for which at least one unreserved seed portion exists."""
    lang = core.language_for(tg)
    slots = await core.list_available_slots(50)
    slot = next((item for item in slots if item.id == slot_id), None)
    if slot is None:
        await show_rental_slots(bot, chat_id, tg)
        return

    plants = await list_rentable_plants(50)
    plants.sort(
        key=lambda plant: (
            core.plant_name(plant, lang).casefold(),
            (getattr(plant, "code", "") or "").casefold(),
        )
    )
    if not plants:
        await bot.send_message(
            chat_id,
            seed_text(lang),
            reply_markup={
                "inline_keyboard": [[
                    {"text": core.st(lang, "back_garden"), "callback_data": "menu:garden"}
                ]]
            },
        )
        return

    rows = [
        [{
            "text": f"🌱 {core.plant_name(plant, lang)} · Ⓚ {int(plant.rental_price_kisa or 0)}"[:60],
            "callback_data": f"rent:plant:{slot_id}:{plant.id}",
        }]
        for plant in plants
    ]
    rows.append([{"text": core.st(lang, "cancel"), "callback_data": "menu:garden"}])
    await bot.send_message(
        chat_id,
        core.st(lang, "rent_choose_plant", rack=slot.rack_id, slot=slot.slot_number),
        reply_markup={"inline_keyboard": rows},
    )


async def show_rental_slots(bot, chat_id: int, tg: dict) -> None:
    """Use the existing first-free-container flow, but stop early if seeds are unavailable."""
    lang = core.language_for(tg)
    plants = await list_rentable_plants(1)
    if not plants:
        await bot.send_message(
            chat_id,
            seed_text(lang),
            reply_markup={
                "inline_keyboard": [[
                    {"text": core.st(lang, "back_garden"), "callback_data": "menu:garden"}
                ]]
            },
        )
        return

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
    await show_rental_plants(bot, chat_id, tg, slots[0].id)


# worker.py and worker_core resolve these functions through core globals at
# runtime. Keep all photo, watering and lifecycle wrappers, replacing only the
# rental inventory source and rental picker.
core.list_active_plants = list_rentable_plants
core.show_rental_plants = show_rental_plants
core.show_rental_slots = show_rental_slots


if __name__ == "__main__":
    asyncio.run(core.run())
