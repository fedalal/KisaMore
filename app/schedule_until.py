from __future__ import annotations
from datetime import datetime, time, timedelta
from typing import Any, Optional

DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

def _parse_hhmm(s: str) -> time:
    hh, mm = s.split(":")
    return time(int(hh), int(mm))

def active_until(schedule_channel: dict[str, list[dict[str, Any]]], now: datetime) -> Optional[str]:
    """
    Возвращает "HH:MM", если сейчас внутри интервала расписания.
    Поддерживает интервалы через полночь (22:00–02:00).
    """
    day_key = DAY_KEYS[now.weekday()]
    intervals = schedule_channel.get(day_key, []) or []

    for it in intervals:
        start_s = (it.get("start") or "").strip()
        end_s = (it.get("end") or "").strip()
        if not start_s or not end_s:
            continue

        try:
            st = _parse_hhmm(start_s)
            en = _parse_hhmm(end_s)
        except Exception:
            continue

        start_dt = now.replace(hour=st.hour, minute=st.minute, second=0, microsecond=0)
        end_dt = now.replace(hour=en.hour, minute=en.minute, second=0, microsecond=0)

        # интервал через полночь
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)

        # если интервал начался вчера (пример: 22:00–02:00, сейчас 01:00)
        if end_dt.date() != start_dt.date() and now < start_dt:
            start_dt -= timedelta(days=1)

        if start_dt <= now < end_dt:
            return end_dt.strftime("%H:%M")

    return None
