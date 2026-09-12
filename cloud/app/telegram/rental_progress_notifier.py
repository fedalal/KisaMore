from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from ..db import SessionLocal
from .activity_notifier import MAX_ATTEMPTS, TelegramActivityDelivery


CHECK_SECONDS = 10


async def send_pending(bot) -> tuple[int, int]:
    sent = 0
    failed = 0

    async with SessionLocal() as session:
        deliveries = list(
            (
                await session.execute(
                    select(TelegramActivityDelivery)
                    .where(
                        TelegramActivityDelivery.status == "photo_pending",
                        TelegramActivityDelivery.kind == "rental_progress",
                        TelegramActivityDelivery.attempts < MAX_ATTEMPTS,
                    )
                    .order_by(TelegramActivityDelivery.created_at)
                    .limit(30)
                )
            ).scalars().all()
        )

        for delivery in deliveries:
            payload = delivery.payload or {}
            photo_path = Path(str(payload.get("photo_path") or ""))
            try:
                if not photo_path.is_file():
                    raise FileNotFoundError(photo_path)

                await bot.send_photo(
                    delivery.telegram_user_id,
                    photo_path,
                    caption=str(payload.get("text") or "KisaMore")[:1024],
                )
                delivery.status = "sent"
                delivery.sent_at = datetime.now(timezone.utc)
                delivery.last_error = None
                sent += 1
            except Exception as exc:
                delivery.attempts += 1
                delivery.last_error = f"{type(exc).__name__}: {exc}"[:2000]
                if delivery.attempts >= MAX_ATTEMPTS:
                    delivery.status = "failed"
                failed += 1
            await session.commit()

    return sent, failed


def install(core) -> None:
    previous_loop = core.follow_notification_loop

    async def rental_progress_loop(bot) -> None:
        while True:
            try:
                sent, failed = await send_pending(bot)
                if sent or failed:
                    core.logger.info(
                        "Telegram rental progress pass: sent=%s failed=%s",
                        sent,
                        failed,
                    )
            except asyncio.CancelledError:
                raise
            except Exception:
                core.logger.exception("Telegram rental progress notification pass failed")
            await asyncio.sleep(CHECK_SECONDS)

    async def combined_loop(bot) -> None:
        await asyncio.gather(
            previous_loop(bot),
            rental_progress_loop(bot),
        )

    core.follow_notification_loop = combined_loop
