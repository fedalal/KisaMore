from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from ..config import get_settings
from ..models import RackPhoto
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


core.get_plant_card = get_plant_card


if __name__ == "__main__":
    asyncio.run(core.run())
