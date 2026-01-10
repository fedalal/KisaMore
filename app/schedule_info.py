from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any, Optional

DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_RU  = {"mon":"Пн","tue":"Вт","wed":"Ср","thu":"Чт","fri":"Пт","sat":"Сб","sun":"Вс"}

def _parse_hhmm(s: str) -> time:
    hh, mm = s.split(":")
    return time(int(hh), int(mm))

def _dt_at_day(now: datetime, day_offset: int, t: time) -> datetime:
    base = (now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=day_offset))
    return base.replace(hour=t.hour, minute=t.minute)

@dataclass
class ScheduleNowNext:
    # если сейчас активный интервал
    active_start: Optional[str] = None   # "HH:MM"
    active_end: Optional[str] = None     # "HH:MM"
    # если сейчас выключено — ближайшее следующее включение
    next_day: Optional[str] = None       # "Пн", "Вт", ...
    next_time: Optional[str] = None      # "HH:MM"

    def interval_text(self) -> Optional[str]:
        if self.active_start and self.active_end:
            return f"{self.active_start}–{self.active_end}"
        return None

    def next_text(self) -> Optional[str]:
        if self.next_day and self.next_time:
            return f"{self.next_day} {self.next_time}"
        return None

def compute_now_next(schedule_channel: dict[str, list[dict[str, Any]]], now: datetime) -> ScheduleNowNext:
    """
    schedule_channel = {"mon":[{"start":"08:00","end":"21:30"}, ...], ...}
    - Определяет активный интервал (с учётом перехода через полночь).
    - Если сейчас не активен — находит ближайшее следующее включение (до 7 дней вперёд).
    """
    # 1) Проверяем активный интервал для "сегодня"
    day_key = DAY_KEYS[now.weekday()]
    intervals_today = schedule_channel.get(day_key, []) or []

    for it in intervals_today:
        s = (it.get("start") or "").strip()
        e = (it.get("end") or "").strip()
        if not s or not e:
            continue
        try:
            st = _parse_hhmm(s)
            en = _parse_hhmm(e)
        except Exception:
            continue

        start_dt = now.replace(hour=st.hour, minute=st.minute, second=0, microsecond=0)
        end_dt   = now.replace(hour=en.hour, minute=en.minute, second=0, microsecond=0)

        # через полночь
        crosses_midnight = end_dt <= start_dt
        if crosses_midnight:
            end_dt += timedelta(days=1)
            # если сейчас после полуночи, а start сегодня "позже" — значит интервал начался вчера
            if now < start_dt:
                start_dt -= timedelta(days=1)

        if start_dt <= now < end_dt:
            return ScheduleNowNext(active_start=s, active_end=e)

    # 2) Если не активен — ищем ближайшее следующее включение (0..6 дней вперёд)
    best_dt: Optional[datetime] = None
    best_day_key: Optional[str] = None
    best_time: Optional[str] = None

    for day_offset in range(0, 7):
        k = DAY_KEYS[(now.weekday() + day_offset) % 7]
        intervals = schedule_channel.get(k, []) or []

        for it in intervals:
            s = (it.get("start") or "").strip()
            if not s:
                continue
            try:
                st = _parse_hhmm(s)
            except Exception:
                continue

            cand_dt = _dt_at_day(now, day_offset, st)

            # для day_offset==0 берем только будущие старты
            if day_offset == 0 and cand_dt <= now:
                continue

            if best_dt is None or cand_dt < best_dt:
                best_dt = cand_dt
                best_day_key = k
                best_time = s

    if best_dt and best_day_key and best_time:
        return ScheduleNowNext(next_day=DAY_RU[best_day_key], next_time=best_time)

    return ScheduleNowNext()
