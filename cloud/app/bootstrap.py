from __future__ import annotations

from sqlalchemy import select

from .config import get_settings
from .db import SessionLocal
from .models import Device, Farm
from .security import hash_device_token


async def bootstrap_first_device() -> None:
    settings = get_settings()
    if not settings.bootstrap_device_id or not settings.bootstrap_device_token:
        return

    if len(settings.bootstrap_device_token) < 32:
        raise RuntimeError("KISAMORE_BOOTSTRAP_DEVICE_TOKEN must contain at least 32 characters")

    async with SessionLocal() as session:
        farm = (
            await session.execute(select(Farm).where(Farm.slug == settings.bootstrap_farm_slug))
        ).scalar_one_or_none()
        if farm is None:
            farm = Farm(slug=settings.bootstrap_farm_slug, name=settings.bootstrap_farm_name)
            session.add(farm)
            await session.flush()

        device = await session.get(Device, settings.bootstrap_device_id)
        if device is None:
            session.add(
                Device(
                    id=settings.bootstrap_device_id,
                    farm_id=farm.id,
                    name=settings.bootstrap_device_name,
                    token_hash=hash_device_token(settings.bootstrap_device_token),
                )
            )
            await session.commit()
            print(f"[cloud] bootstrapped device {settings.bootstrap_device_id!r}")
