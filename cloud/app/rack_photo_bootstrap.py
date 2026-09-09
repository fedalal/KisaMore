from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy import select

from .config import get_settings
from .db import SessionLocal
from .models import RackPhoto
from .rack_photo_storage import SLOT_COUNT, slot_latest_path, store_rack_photo


async def backfill_rack_photo_derivatives() -> None:
    """Create the new archive/latest layout for rack photos saved before this feature."""
    settings = get_settings()
    migrated = 0

    async with SessionLocal() as session:
        photos = (await session.execute(select(RackPhoto))).scalars().all()
        for photo in photos:
            source = Path(photo.file_path)
            if not source.is_file():
                continue

            missing_crop = any(
                not slot_latest_path(
                    settings.photo_dir,
                    photo.device_id,
                    photo.rack_id,
                    slot_number,
                ).is_file()
                for slot_number in range(1, SLOT_COUNT + 1)
            )
            if not missing_crop and "latest" in source.parts:
                continue

            try:
                content = await asyncio.to_thread(source.read_bytes)
                stored = await asyncio.to_thread(
                    store_rack_photo,
                    photo_dir=settings.photo_dir,
                    device_id=photo.device_id,
                    rack_id=photo.rack_id,
                    captured_at=photo.captured_at,
                    content=content,
                )
            except Exception as exc:
                print(
                    f"[rack-photo] backfill failed: device={photo.device_id}, "
                    f"rack={photo.rack_id}, error={type(exc).__name__}: {exc!r}"
                )
                continue

            photo.file_path = str(stored.latest_path)
            photo.size_bytes = len(content)
            migrated += 1

        if migrated:
            await session.commit()

    if migrated:
        print(f"[rack-photo] backfilled rack photos: {migrated}")
