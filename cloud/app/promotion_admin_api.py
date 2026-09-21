from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .admin_models import AdminAuditLog
from .config import get_settings
from .models import User
from .security import get_admin_user, get_session
from .telegram.models import TelegramUser
from .telegram.promotion_models import TelegramPromotion, TelegramPromotionGrant


router = APIRouter(prefix="/api/v1/admin/promotions", tags=["admin-promotions"])
AUDIENCES = ("new", "existing", "all")


class PromotionCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    audience: str
    start_date: date
    end_date: date
    amount_kisa: int = Field(ge=1, le=1_000_000)
    message: str = Field(min_length=1, max_length=1200)
    enabled: bool = True


class PromotionStateIn(BaseModel):
    enabled: bool


def _zone() -> ZoneInfo:
    try:
        return ZoneInfo(get_settings().farm_timezone)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _utc_day_bounds(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    if end_date < start_date:
        raise HTTPException(status_code=422, detail="End date must not be before start date")
    zone = _zone()
    start_local = datetime.combine(start_date, time.min, tzinfo=zone)
    end_local_exclusive = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=zone)
    return start_local.astimezone(timezone.utc), end_local_exclusive.astimezone(timezone.utc)


def _local_date(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(_zone()).date().isoformat()


def _end_local_date(exclusive_end: datetime) -> str:
    if exclusive_end.tzinfo is None:
        exclusive_end = exclusive_end.replace(tzinfo=timezone.utc)
    local = exclusive_end.astimezone(_zone()) - timedelta(microseconds=1)
    return local.date().isoformat()


def _status(row: TelegramPromotion) -> str:
    if not row.enabled:
        return "paused"
    now = datetime.now(timezone.utc)
    start = row.start_at if row.start_at.tzinfo else row.start_at.replace(tzinfo=timezone.utc)
    end = row.end_at if row.end_at.tzinfo else row.end_at.replace(tzinfo=timezone.utc)
    if now < start:
        return "scheduled"
    if now >= end:
        return "ended"
    return "active"


async def _eligible_count(session: AsyncSession, row: TelegramPromotion) -> int:
    stmt = select(func.count(TelegramUser.id)).where(TelegramUser.is_active.is_(True))
    if row.audience == "new":
        stmt = stmt.where(
            TelegramUser.created_at >= row.start_at,
            TelegramUser.created_at < row.end_at,
        )
    elif row.audience == "existing":
        stmt = stmt.where(TelegramUser.created_at < row.start_at)
    elif row.audience == "all":
        stmt = stmt.where(TelegramUser.created_at < row.end_at)
    return int((await session.execute(stmt)).scalar_one() or 0)


async def _payload(session: AsyncSession, row: TelegramPromotion) -> dict:
    grant_count = int(
        (
            await session.execute(
                select(func.count(TelegramPromotionGrant.user_id)).where(
                    TelegramPromotionGrant.promotion_id == row.id
                )
            )
        ).scalar_one()
        or 0
    )
    notified_count = int(
        (
            await session.execute(
                select(func.count(TelegramPromotionGrant.user_id)).where(
                    TelegramPromotionGrant.promotion_id == row.id,
                    TelegramPromotionGrant.notification_status == "sent",
                )
            )
        ).scalar_one()
        or 0
    )
    failed_count = int(
        (
            await session.execute(
                select(func.count(TelegramPromotionGrant.user_id)).where(
                    TelegramPromotionGrant.promotion_id == row.id,
                    TelegramPromotionGrant.notification_status == "failed",
                )
            )
        ).scalar_one()
        or 0
    )
    return {
        "id": row.id,
        "name": row.name,
        "audience": row.audience,
        "start_date": _local_date(row.start_at),
        "end_date": _end_local_date(row.end_at),
        "start_at": row.start_at,
        "end_at": row.end_at,
        "amount_kisa": row.amount_kisa,
        "message": row.message,
        "enabled": bool(row.enabled),
        "status": _status(row),
        "eligible_count": await _eligible_count(session, row),
        "grant_count": grant_count,
        "notified_count": notified_count,
        "failed_count": failed_count,
        "created_at": row.created_at,
        "timezone": str(_zone()),
    }


@router.get("")
async def list_promotions(
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    rows = list(
        (
            await session.execute(
                select(TelegramPromotion)
                .order_by(TelegramPromotion.created_at.desc(), TelegramPromotion.id.desc())
                .limit(200)
            )
        ).scalars().all()
    )
    return {
        "timezone": str(_zone()),
        "items": [await _payload(session, row) for row in rows],
    }


@router.post("", status_code=201)
async def create_promotion(
    payload: PromotionCreateIn,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    audience = payload.audience.strip().lower()
    if audience not in AUDIENCES:
        raise HTTPException(status_code=422, detail="Audience must be new, existing or all")

    name = payload.name.strip()
    message = payload.message.strip()
    if not name or not message:
        raise HTTPException(status_code=422, detail="Name and message are required")

    start_at, end_at = _utc_day_bounds(payload.start_date, payload.end_date)
    row = TelegramPromotion(
        name=name,
        audience=audience,
        start_at=start_at,
        end_at=end_at,
        amount_kisa=int(payload.amount_kisa),
        message=message,
        enabled=bool(payload.enabled),
        created_by_admin_id=admin.id,
    )
    session.add(row)
    await session.flush()

    session.add(
        AdminAuditLog(
            admin_user_id=admin.id,
            action="create_promotion",
            target_type="telegram_promotion",
            target_id=str(row.id),
            details={
                "name": row.name,
                "audience": row.audience,
                "start_date": payload.start_date.isoformat(),
                "end_date": payload.end_date.isoformat(),
                "amount_kisa": row.amount_kisa,
                "enabled": row.enabled,
            },
        )
    )
    await session.commit()
    await session.refresh(row)
    return await _payload(session, row)


@router.patch("/{promotion_id}")
async def set_promotion_state(
    promotion_id: int,
    payload: PromotionStateIn,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    row = await session.get(TelegramPromotion, promotion_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Promotion not found")

    row.enabled = bool(payload.enabled)
    session.add(
        AdminAuditLog(
            admin_user_id=admin.id,
            action="promotion_state",
            target_type="telegram_promotion",
            target_id=str(row.id),
            details={"enabled": row.enabled, "name": row.name},
        )
    )
    await session.commit()
    await session.refresh(row)
    return await _payload(session, row)
