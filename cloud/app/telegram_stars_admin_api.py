from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .models import User
from .security import get_admin_user, get_session
from .telegram.models import (
    StarPayment,
    TelegramStarAccount,
    TelegramStarTransaction,
    TelegramUser,
)


router = APIRouter(prefix="/api/v1/admin/telegram-stars", tags=["admin-telegram-stars"])


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _period_boundaries() -> tuple[datetime, datetime, str]:
    timezone_name = get_settings().farm_timezone
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        zone = timezone.utc
        timezone_name = "UTC"
    now = datetime.now(zone)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = day_start.replace(day=1)
    return day_start.astimezone(timezone.utc), month_start.astimezone(timezone.utc), timezone_name


async def _sum_paid(
    session: AsyncSession,
    column,
    *,
    since: datetime | None = None,
) -> int:
    stmt = select(func.coalesce(func.sum(column), 0)).where(StarPayment.status == "paid")
    if since is not None:
        stmt = stmt.where(StarPayment.paid_at >= since)
    return int((await session.execute(stmt)).scalar_one() or 0)


@router.get("")
async def telegram_stars_report(
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    day_start, month_start, timezone_name = _period_boundaries()

    account = await session.get(TelegramStarAccount, 1)
    total_stars = await _sum_paid(session, StarPayment.stars_amount)
    today_stars = await _sum_paid(session, StarPayment.stars_amount, since=day_start)
    month_stars = await _sum_paid(session, StarPayment.stars_amount, since=month_start)
    total_kisa = await _sum_paid(session, StarPayment.kisa_amount)
    payment_count = int(
        (
            await session.execute(
                select(func.count(StarPayment.id)).where(StarPayment.status == "paid")
            )
        ).scalar_one()
        or 0
    )

    official_rows = list(
        (
            await session.execute(
                select(TelegramStarTransaction)
                .order_by(TelegramStarTransaction.occurred_at.desc())
                .limit(200)
            )
        ).scalars().all()
    )
    official_incoming = {
        item.transaction_id
        for item in official_rows
        if item.direction == "incoming"
    }
    official_outgoing = {
        item.transaction_id
        for item in official_rows
        if item.direction == "outgoing"
    }

    payment_rows = (
        await session.execute(
            select(StarPayment, TelegramUser)
            .join(TelegramUser, TelegramUser.id == StarPayment.user_id)
            .order_by(StarPayment.paid_at.desc())
            .limit(200)
        )
    ).all()

    telegram_ids = {
        item.telegram_user_id
        for item in official_rows
        if item.telegram_user_id is not None
    }
    users_by_telegram_id: dict[int, TelegramUser] = {}
    if telegram_ids:
        users = (
            await session.execute(
                select(TelegramUser).where(TelegramUser.telegram_user_id.in_(telegram_ids))
            )
        ).scalars().all()
        users_by_telegram_id = {int(item.telegram_user_id): item for item in users}

    purchases = []
    for payment, user in payment_rows:
        charge_id = payment.telegram_payment_charge_id
        if charge_id in official_outgoing:
            official_state = "refunded"
        elif charge_id in official_incoming:
            official_state = "confirmed"
        else:
            official_state = "not_in_recent_history"
        purchases.append(
            {
                "id": payment.id,
                "telegram_payment_charge_id": charge_id,
                "telegram_user_id": user.telegram_user_id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "stars": int(payment.stars_amount),
                "kisa": int(payment.kisa_amount),
                "status": payment.status,
                "official_state": official_state,
                "paid_at": _aware(payment.paid_at),
            }
        )

    official_transactions = []
    for item in official_rows:
        tg_user = users_by_telegram_id.get(int(item.telegram_user_id)) if item.telegram_user_id is not None else None
        official_transactions.append(
            {
                "transaction_id": item.transaction_id,
                "direction": item.direction,
                "stars": int(item.amount_stars),
                "nanostars": int(item.nanostar_amount),
                "partner_type": item.partner_type,
                "transaction_type": item.transaction_type,
                "telegram_user_id": item.telegram_user_id,
                "username": tg_user.username if tg_user else None,
                "first_name": tg_user.first_name if tg_user else None,
                "last_name": tg_user.last_name if tg_user else None,
                "invoice_payload": item.invoice_payload,
                "occurred_at": _aware(item.occurred_at),
            }
        )

    return {
        "summary": {
            "official_balance": int(account.balance_stars) if account else None,
            "official_balance_nanostars": int(account.balance_nanostars) if account else 0,
            "official_synced_at": _aware(account.synced_at) if account else None,
            "official_sync_error": account.last_error if account else None,
            "stars_received_all_time": total_stars,
            "stars_received_today": today_stars,
            "stars_received_month": month_stars,
            "kisa_issued_for_stars": total_kisa,
            "payments_count": payment_count,
            "timezone": timezone_name,
        },
        "purchases": purchases,
        "official_transactions": official_transactions,
    }
