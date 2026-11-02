"""Create another cloud greenhouse without changing existing devices.

Requires a unique KISAMORE_NEW_DEVICE_TOKEN in the environment on --apply.
"""
from __future__ import annotations
import argparse
import asyncio
import os
import re
from sqlalchemy import select
from .app.db import SessionLocal
from .app.models import Farm, Device
from .app.security import hash_device_token

async def register(args: argparse.Namespace) -> None:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,78}", args.farm_slug):
        raise ValueError("Invalid farm slug")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{1,79}", args.device_id):
        raise ValueError("Invalid device id")
    if not args.apply:
        print(f"DRY RUN: would create {args.farm_slug} / {args.device_id} ({args.farm_name})")
        print("No database changes. To register, set KISAMORE_NEW_DEVICE_TOKEN and --apply.")
        return
    token = os.environ.get("KISAMORE_NEW_DEVICE_TOKEN", "")
    if len(token) < 32:
        raise ValueError("Set unique KISAMORE_NEW_DEVICE_TOKEN (32+ chars)")
    async with SessionLocal() as session:
        existing = (await session.execute(
            select(Farm).where(Farm.slug == args.farm_slug)
        )).scalar_one_or_none()
        if existing or await session.get(Device, args.device_id):
            raise ValueError("Farm slug or device ID already in use. Nothing changed.")
        farm = Farm(slug=args.farm_slug, name=args.farm_name, is_public=True)
        session.add(farm)
        await session.flush()
        session.add(Device(
            id=args.device_id,
            farm_id=farm.id,
            name=args.device_name,
            token_hash=hash_device_token(token),
            is_active=True,
        ))
        await session.commit()
        print(f"Registered farm {farm.slug} / device {args.device_id}.")
        print("The token was not printed. Use the same secret on the new Pi.")

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--farm-slug", required=True)
    p.add_argument("--farm-name", required=True)
    p.add_argument("--device-id", required=True)
    p.add_argument("--device-name", required=True)
    p.add_argument("--apply", action="store_true")
    asyncio.run(register(p.parse_args()))

if __name__ == "__main__":
    main()
