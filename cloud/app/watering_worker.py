from __future__ import annotations

import asyncio
import logging
import os

from .db import SessionLocal, create_tables, engine
from .watering_service import refresh_watering_tasks


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def run_once() -> None:
    async with SessionLocal() as session:
        result = await refresh_watering_tasks(
            session,
            horizon_hours=max(24, int(os.getenv("KISAMORE_WATERING_HORIZON_HOURS", "48"))),
            lookback_hours=max(1, int(os.getenv("KISAMORE_WATERING_LOOKBACK_HOURS", "24"))),
        )
        await session.commit()
    logger.info(
        "Watering pass complete: active_plantings=%s created=%s updated=%s skipped=%s",
        result["active_plantings"],
        result["created"],
        result["updated"],
        result["skipped"],
    )


async def run() -> None:
    await create_tables()
    interval = max(60, int(os.getenv("KISAMORE_WATERING_CHECK_SECONDS", "300")))
    logger.info("KisaMore watering worker started: check=%ss", interval)
    try:
        while True:
            try:
                await run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Watering pass failed")
            await asyncio.sleep(interval)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
