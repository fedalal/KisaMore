"""Calendar-day progress for Plant Battles.

Battle start/end dates are inclusive, in the greenhouse's configured timezone.
Plant.grow_days is a *plant property*, not the competition duration.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import get_settings


def battle_progress(
    start_date: date | None,
    end_date: date | None,
    *,
    today: date | None = None,
) -> tuple[int | None, int | None]:
    """Return (current competition day, total calendar days).

    No current day is reported before start; after end, the day is capped at
    the competition's length so finished/late-closing battles never exceed it.
    A missing/invalid date range deliberately does not fall back to grow_days.
    """
    if start_date is None or end_date is None or end_date < start_date:
        return None, None
    total = (end_date - start_date).days + 1
    if today is None:
        try:
            zone = ZoneInfo(get_settings().farm_timezone)
        except (ZoneInfoNotFoundError, AttributeError):
            zone = timezone.utc
        today = datetime.now(zone).date()
    if today < start_date:
        return None, total
    return min((today - start_date).days + 1, total), total
