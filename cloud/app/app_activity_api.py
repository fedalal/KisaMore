"""Android Battle event capture and admin-only, per-user activity history.

No IP address, email, event message, FCM token, or raw installation identifier
is stored by this collector. Authentication is optional for guest events.
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Literal

from .app_activity_models import AppActivityEvent
from .config import get_settings
from .models import User, UserSession
from .security import get_admin_user, get_session, hash_session_token

router = APIRouter(tags=["Android app activity"])
Kind = Literal["launch", "screen", "heartbeat", "camera", "timelapse", "error"]
Screen = Literal["home", "battle", "history", "profile", "login", "register", "viewer", "inbox", "other"]
VERSION = "2026-10-14"


class AppEventIn(BaseModel):
    event_id: UUID
    installation_id: UUID
    kind: Kind
    screen: Screen = "other"
    label: str = Field(default="", max_length=48, pattern=r"^[A-Za-z0-9_.-]*$")
    app_version: str = Field(min_length=1, max_length=32, pattern=r"^[0-9A-Za-z_.-]+$")
    android_version: str = Field(min_length=1, max_length=24, pattern=r"^[0-9A-Za-z_.-]+$")
    seconds: int = Field(default=0, ge=0, le=60)


async def _optional_user(session_token: str | None, db: AsyncSession, now: datetime) -> User | None:
    if not session_token:
        return None
    item = (await db.execute(
        select(UserSession).where(UserSession.token_hash == hash_session_token(session_token))
    )).scalar_one_or_none()
    if item is None:
        return None
    expires = item.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= now:
        return None
    user = await db.get(User, item.user_id)
    return user if user is not None and user.is_active else None


@router.post("/api/v1/app/activity", status_code=204)
async def record_app_activity(
    event: AppEventIn,
    response: Response,
    session_token: str | None = Cookie(default=None, alias="kisamore_session"),
    db: AsyncSession = Depends(get_session),
):
    identifier = hashlib.sha256(event.installation_id.bytes).hexdigest()
    now = datetime.now(timezone.utc)
    count = (await db.execute(
        select(func.count()).select_from(AppActivityEvent).where(
            AppActivityEvent.installation_hash == identifier,
            AppActivityEvent.created_at >= now - timedelta(minutes=1),
        )
    )).scalar_one()
    if count >= 25:
        return Response(status_code=204)

    # Sanitised, finite event vocabulary; crash class names only, never stack traces.
    if event.kind == "error" and not event.label.endswith(("Exception", "Error")):
        return Response(status_code=204)
    if event.kind == "timelapse" and event.label not in ("24h", "3d", "full"):
        return Response(status_code=204)
    if event.kind == "camera" and (not event.label or not event.label.startswith("camera_")):
        return Response(status_code=204)
    if event.kind in ("launch", "screen", "heartbeat") and event.label:
        return Response(status_code=204)
    user = await _optional_user(session_token, db, now)
    db.add(AppActivityEvent(
        id=str(event.event_id), installation_hash=identifier,
        user_id=user.id if user else None,
        kind=event.kind, screen=event.screen, label=event.label,
        app_version=event.app_version, android_version=event.android_version,
        seconds=event.seconds if event.kind == "heartbeat" else 0,
        created_at=now,
    ))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()

    # Coarse opportunistic retention cleanup (90 days), no external scheduled job.
    if event.event_id.int % 500 == 0:
        await db.execute(delete(AppActivityEvent).where(
            AppActivityEvent.created_at < now - timedelta(days=90)))
        await db.commit()
    return Response(status_code=204)


def _window(days: int):
    tz = ZoneInfo(get_settings().farm_timezone)
    now = datetime.now(timezone.utc)
    local_today = now.astimezone(tz).date()
    start = datetime.combine(local_today - timedelta(days=days - 1),
                             datetime.min.time(), tzinfo=tz).astimezone(timezone.utc)
    return tz, now, start


@router.get("/api/v1/admin/app-activity")
async def app_activity_report(
    days: int = Query(default=7, ge=1, le=30),
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_session),
):
    tz, now, start = _window(days)
    rows = (await db.execute(
        select(AppActivityEvent.user_id, AppActivityEvent.installation_hash,
               AppActivityEvent.kind, AppActivityEvent.screen, AppActivityEvent.seconds,
               AppActivityEvent.created_at, AppActivityEvent.app_version,
               AppActivityEvent.android_version, User.display_name, User.email)
        .outerjoin(User, User.id == AppActivityEvent.user_id)
        .where(AppActivityEvent.created_at >= start)
        .order_by(AppActivityEvent.created_at.desc())
    )).all()

    people = {}
    for uid, install, kind, screen, seconds, stamp, app_ver, android_ver, name, email in rows:
        # Anonymous guest activities stay separate from authenticated users.
        key = "user:" + uid if uid else "guest:" + install
        if key not in people:
            people[key] = {
                "key": key, "name": name if uid else "Гость · " + install[:8],
                "email": email if uid else None, "user_id": uid,
                "installations": set(), "sessions": 0, "minutes": 0,
                "events": 0, "screens": set(), "last_seen": stamp,
                "app_version": app_ver, "android_version": android_ver,
            }
        p = people[key]
        p["installations"].add(install)
        p["events"] += 1
        if kind == "launch":
            p["sessions"] += 1
        if kind == "heartbeat":
            p["minutes"] += seconds
        if kind == "screen":
            p["screens"].add(screen)

    people_out = []
    for p in people.values():
        p["installations"] = len(p["installations"])
        p["minutes"] = round(p["minutes"] / 60, 1)
        p["screens"] = sorted(p["screens"])
        people_out.append(p)

    # Each anonymous device or authorised user can be inspected individually.
    return {
        "days": days, "timezone": str(tz), "as_of": now,
        "tracked_people": len(people_out),
        "tracked_accounts": sum(1 for p in people_out if p["user_id"]),
        "launches": sum(p["sessions"] for p in people_out),
        "minutes": round(sum(p["minutes"] for p in people_out), 1),
        "events": len(rows),
        "people": people_out,
        "notice": "Only Android versions with the new telemetry included are counted. Google Play test enrolment is not tracked.",
    }


@router.get("/api/v1/admin/app-activity/events")
async def app_activity_events(
    key: str = Query(min_length=6, max_length=72),
    days: int = Query(default=7, ge=1, le=30),
    limit: int = Query(default=250, ge=1, le=1000),
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_session),
):
    tz, now, start = _window(days)
    if key.startswith("user:"):
        selector = AppActivityEvent.user_id == key[5:]
    elif key.startswith("guest:") and len(key[6:]) == 64 and all(
            ch in "0123456789abcdef" for ch in key[6:]):
        selector = (AppActivityEvent.user_id.is_(None) &
                    (AppActivityEvent.installation_hash == key[6:]))
    else:
        raise HTTPException(422, "Invalid activity key")

    rows = (await db.execute(
        select(AppActivityEvent).where(selector, AppActivityEvent.created_at >= start)
        .order_by(AppActivityEvent.created_at.desc()).limit(limit)
    )).scalars().all()
    return {"key": key, "timezone": str(tz), "events": [
        {"time": e.created_at, "kind": e.kind, "screen": e.screen,
         "label": e.label, "seconds": e.seconds,
         "app_version": e.app_version, "android_version": e.android_version,
         "device": e.installation_hash[:8]}
        for e in rows]}
