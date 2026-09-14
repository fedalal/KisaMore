from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from ..config import get_settings
from ..db import SessionLocal
from ..models import Planting, RackPhoto, RackSlot
from ..rack_photo_storage import slot_latest_path
from .activity_notifier import TelegramActivityDelivery


WAIT_STATUS = "planting_photo_wait"
READY_STATUS = "planting_photo_pending"


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _markup(payload: dict) -> dict | None:
    callback_data = payload.get("callback_data")
    if not callback_data:
        return None
    return {
        "inline_keyboard": [[
            {
                "text": str(payload.get("button") or "🌱 KisaMore")[:60],
                "callback_data": str(callback_data)[:64],
            }
        ]]
    }


async def _fresh_photo_for_planting(session, planting_id: str):
    row = (
        await session.execute(
            select(Planting, RackSlot, RackPhoto)
            .join(RackSlot, RackSlot.id == Planting.slot_id)
            .join(
                RackPhoto,
                (RackPhoto.device_id == RackSlot.device_id)
                & (RackPhoto.rack_id == RackSlot.rack_id),
            )
            .where(Planting.id == planting_id)
            .limit(1)
        )
    ).one_or_none()
    if row is None:
        return None

    planting, slot, rack_photo = row
    planted_at = _aware(planting.planted_at)
    captured_at = _aware(rack_photo.captured_at)
    if planted_at is None or captured_at is None or captured_at <= planted_at:
        return None

    path = slot_latest_path(
        get_settings().photo_dir,
        slot.device_id,
        slot.rack_id,
        slot.slot_number,
    )
    if not Path(path).is_file():
        return None

    return path, captured_at


async def _attach_fresh_photo(session, delivery: TelegramActivityDelivery) -> bool:
    payload = dict(delivery.payload or {})
    planting_id = str(payload.get("planting_id") or "").strip()
    if not planting_id:
        delivery.status = WAIT_STATUS
        return False

    fresh = await _fresh_photo_for_planting(session, planting_id)
    if fresh is None:
        delivery.status = WAIT_STATUS
        return False

    path, captured_at = fresh
    payload["photo_path"] = str(path)
    payload["photo_captured_at"] = captured_at.isoformat()
    payload["photo_required"] = True
    delivery.payload = payload
    delivery.status = READY_STATUS
    return True


def install(activity_notifier) -> None:
    """Delay planting-start messages until a post-planting camera frame exists.

    The ordinary lifecycle notifier discovers a planting immediately. We keep that
    durable outbox row, move only `planting_started` into a waiting state and send
    it as a photo message once RackPhoto.captured_at is newer than planted_at.
    This avoids both stale empty-container photos and lost notifications during a
    long camera/MQTT outage.
    """

    original_queue = activity_notifier._queue_planting_event
    original_send_pending = activity_notifier.send_pending

    async def queue_planting_event(session, **kwargs):
        created = await original_queue(session, **kwargs)
        if not created or kwargs.get("delivery_kind") != "planting_started":
            return created

        planting = kwargs.get("planting")
        if planting is None:
            return created

        await session.flush()
        key = f"planting_started:{planting.id}"
        delivery = await session.get(TelegramActivityDelivery, key)
        if delivery is not None:
            delivery.status = WAIT_STATUS
            await _attach_fresh_photo(session, delivery)
        return created

    async def send_planting_photos(bot) -> tuple[int, int]:
        sent = 0
        failed = 0
        async with SessionLocal() as session:
            deliveries = list(
                (
                    await session.execute(
                        select(TelegramActivityDelivery)
                        .where(
                            TelegramActivityDelivery.kind == "planting_started",
                            TelegramActivityDelivery.status.in_(
                                ("pending", WAIT_STATUS, READY_STATUS)
                            ),
                            TelegramActivityDelivery.attempts
                            < activity_notifier.MAX_ATTEMPTS,
                        )
                        .order_by(TelegramActivityDelivery.created_at)
                        .limit(50)
                    )
                ).scalars().all()
            )

            for delivery in deliveries:
                payload = dict(delivery.payload or {})
                photo_path = str(payload.get("photo_path") or "").strip()

                # Existing rows from older deployments may still be plain
                # `pending`. Migrate them safely instead of allowing the old
                # text-only sender to deliver them with a stale photo behind the
                # Open button.
                if (
                    delivery.status != READY_STATUS
                    or not photo_path
                    or not Path(photo_path).is_file()
                ):
                    if not await _attach_fresh_photo(session, delivery):
                        await session.commit()
                        continue
                    payload = dict(delivery.payload or {})
                    photo_path = str(payload.get("photo_path") or "").strip()

                try:
                    await bot.send_photo(
                        delivery.telegram_user_id,
                        photo_path,
                        caption=str(payload.get("text") or "KisaMore"),
                        reply_markup=_markup(payload),
                    )
                    delivery.status = "sent"
                    delivery.sent_at = datetime.now(timezone.utc)
                    delivery.last_error = None
                    sent += 1
                except Exception as exc:
                    delivery.attempts += 1
                    delivery.last_error = f"{type(exc).__name__}: {exc}"[:2000]
                    if delivery.attempts >= activity_notifier.MAX_ATTEMPTS:
                        delivery.status = "failed"
                    else:
                        delivery.status = READY_STATUS
                    failed += 1
                    activity_notifier.logger.exception(
                        "Could not send fresh planting photo to Telegram user %s",
                        delivery.telegram_user_id,
                    )
                await session.commit()

        return sent, failed

    async def send_pending(bot) -> tuple[int, int]:
        photo_sent, photo_failed = await send_planting_photos(bot)
        normal_sent, normal_failed = await original_send_pending(bot)
        return photo_sent + normal_sent, photo_failed + normal_failed

    activity_notifier._queue_planting_event = queue_planting_event
    activity_notifier.send_pending = send_pending
