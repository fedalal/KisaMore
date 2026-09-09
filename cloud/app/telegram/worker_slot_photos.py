from __future__ import annotations

import asyncio
from html import escape
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import select

from ..config import get_settings
from ..db import SessionLocal
from ..models import Plant, Planting, RackPhoto, RackSlot
from ..rack_photo_storage import slot_latest_path
from . import worker as existing


core = existing.core
_original_get_plant_card = core.get_plant_card


async def get_plant_card(planting_id: str, user_id: int):
    """Use the automatically derived container crop for ordinary rack photos.

    The existing worker already replaces card.photo with an administrator-published
    PlantingPhoto when one exists. In that case we keep the administrator photo.
    """
    card = await _original_get_plant_card(planting_id, user_id)
    if card is None:
        return None

    if isinstance(card.photo, RackPhoto):
        path = slot_latest_path(
            get_settings().photo_dir,
            card.slot.device_id,
            card.slot.rack_id,
            card.slot.slot_number,
        )
        if Path(path).is_file():
            card.photo = SimpleNamespace(file_path=str(path))
    return card


async def show_garden(bot, chat_id: int, tg: dict) -> None:
    """Keep the localized garden view and add a photo button for active rentals."""
    lang = core.language_for(tg)
    user, _ = await core.get_or_create_user(tg)
    followed = await core.list_followed_plantings(user.id, 6)
    requests = await core.rental_requests(user.id, 6)
    allocations = await core.linked_allocations(user, 6)
    parts = [core.t(lang, "garden")]
    buttons = []

    if followed:
        parts.append("\n" + core.st(lang, "garden_following"))
        for planting, plant, slot in followed:
            name = core.plant_name(plant, lang)
            parts.append(f"• 🌱 {escape(name)} · #{slot.rack_id}/{slot.slot_number}")
            buttons.append([{"text": f"🌱 {name}"[:60], "callback_data": f"plant:show:{planting.id}:0"}])

    if requests:
        parts.append(core.st(lang, "garden_requests"))
        for req, slot, plant in requests:
            parts.append(
                core.st(
                    lang,
                    "rent_status",
                    rack=slot.rack_id,
                    slot=slot.slot_number,
                    plant=escape(core.plant_name(plant, lang)),
                    status=escape(core.st(lang, f"status_{req.status}")),
                )
            )

    if allocations:
        plant_ids = {item.plant_id for item in allocations if item.plant_id}
        device_ids = {item.device_id for item in allocations if item.device_id}
        plants_by_id = {}
        planting_by_position = {}
        async with SessionLocal() as session:
            if plant_ids:
                plant_rows = (
                    await session.execute(select(Plant).where(Plant.id.in_(plant_ids)))
                ).scalars().all()
                plants_by_id = {item.id: item for item in plant_rows}
            if device_ids:
                planting_rows = (
                    await session.execute(
                        select(Planting, RackSlot)
                        .join(RackSlot, RackSlot.id == Planting.slot_id)
                        .where(
                            RackSlot.device_id.in_(device_ids),
                            Planting.status.in_(("planned", "growing", "ready")),
                        )
                    )
                ).all()
                planting_by_position = {
                    (slot.device_id, slot.rack_id, slot.slot_number): planting
                    for planting, slot in planting_rows
                }

        parts.append("\n" + existing.rt(lang, "active"))
        for allocation in allocations:
            plant = plants_by_id.get(allocation.plant_id)
            name = core.plant_name(plant, lang) if plant else "🌱"
            parts.append(
                existing.rt(
                    lang,
                    "allocation",
                    plant=escape(name),
                    rack=allocation.rack_id,
                    slot=allocation.slot_number or "—",
                )
            )
            if allocation.slot_number:
                planting = planting_by_position.get(
                    (allocation.device_id, allocation.rack_id, allocation.slot_number)
                )
                if planting is not None:
                    buttons.append([
                        {
                            "text": f"📷 {name} · {allocation.rack_id}/{allocation.slot_number}"[:60],
                            "callback_data": f"plant:show:{planting.id}:0",
                        }
                    ])

    if not followed and not requests and not allocations:
        parts.append("\n" + core.st(lang, "garden_empty"))
    buttons.append([{"text": core.st(lang, "rent_button"), "callback_data": "rent:start"}])
    buttons.append([{"text": core.t(lang, "back_home"), "callback_data": "menu:home"}])
    await bot.send_message(chat_id, "\n".join(parts), reply_markup={"inline_keyboard": buttons})


core.get_plant_card = get_plant_card
core.show_garden = show_garden


if __name__ == "__main__":
    asyncio.run(core.run())
