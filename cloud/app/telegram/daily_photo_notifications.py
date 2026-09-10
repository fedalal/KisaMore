from __future__ import annotations

from datetime import datetime, time, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import or_, select

from ..config import get_settings
from ..db import SessionLocal
from ..models import Plant, Planting, RackPhoto, RackSlot
from .models import SocialFollow, TelegramUser


DAILY_PHOTO_HOUR = 10
ACTIVE_PLANTING_STATUSES = ("planned", "growing", "ready")


def _zone() -> ZoneInfo:
    try:
        return ZoneInfo(get_settings().farm_timezone)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def pending_follow_notifications(limit: int = 50):
    """Return at most one fresh-photo notification per followed planting per day.

    The daily window opens at 10:00 in the greenhouse timezone. If the bot is
    temporarily down at 10:00, the notification is sent on the first pass after
    it comes back up rather than being lost for the whole day.
    """
    now_utc = datetime.now(timezone.utc)
    zone = _zone()
    now_local = now_utc.astimezone(zone)
    cutoff_local = datetime.combine(
        now_local.date(),
        time(hour=DAILY_PHOTO_HOUR),
        tzinfo=zone,
    )
    if now_local < cutoff_local:
        return []
    cutoff_utc = cutoff_local.astimezone(timezone.utc)

    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(SocialFollow, TelegramUser, Planting, Plant, RackSlot, RackPhoto)
                .join(TelegramUser, TelegramUser.id == SocialFollow.user_id)
                .join(
                    Planting,
                    (SocialFollow.target_type == "planting")
                    & (SocialFollow.target_id == Planting.id),
                )
                .join(Plant, Plant.id == Planting.plant_id)
                .join(RackSlot, RackSlot.id == Planting.slot_id)
                .join(
                    RackPhoto,
                    (RackPhoto.device_id == RackSlot.device_id)
                    & (RackPhoto.rack_id == RackSlot.rack_id),
                )
                .where(
                    SocialFollow.notifications_enabled.is_(True),
                    TelegramUser.is_active.is_(True),
                    Planting.status.in_(ACTIVE_PLANTING_STATUSES),
                    or_(
                        SocialFollow.last_notified_at.is_(None),
                        SocialFollow.last_notified_at < cutoff_utc,
                    ),
                )
                .order_by(SocialFollow.id)
                .limit(max(1, min(limit, 100)))
            )
        ).all()

        result = []
        for follow, user, planting, plant, slot, photo in rows:
            last_notified = _aware_utc(follow.last_notified_at)
            photo_updated = _aware_utc(photo.updated_at)
            if photo_updated is None:
                continue
            if last_notified is not None and photo_updated <= last_notified:
                continue
            result.append(
                SimpleNamespace(
                    follow_id=follow.id,
                    telegram_user_id=user.telegram_user_id,
                    language_code=user.language_code,
                    planting_id=planting.id,
                    plant_name_values=plant.names,
                    rack_id=slot.rack_id,
                    slot_number=slot.slot_number,
                    photo=photo,
                )
            )
        return result


async def mark_follow_notified(follow_id: int, _observed_at: datetime) -> None:
    """Record delivery time, not camera time, so another photo cannot resend today."""
    async with SessionLocal() as session:
        follow = await session.get(SocialFollow, follow_id)
        if follow is not None:
            follow.last_notified_at = datetime.now(timezone.utc)
            await session.commit()


def install(core) -> None:
    # worker_core resolves these names from its module globals at runtime, so
    # replacing the module attributes changes the existing follow loop without
    # duplicating or replacing the rest of the Telegram worker stack.
    core.pending_follow_notifications = pending_follow_notifications
    core.mark_follow_notified = mark_follow_notified
