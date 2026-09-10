from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .admin_models import AdminAuditLog
from .models import User
from .security import get_admin_user, get_session
from .telegram.admin_models import TelegramAdmin
from .telegram.models import TelegramUser


router = APIRouter(prefix="/api/v1/admin/telegram-admins", tags=["admin-telegram"])


class TelegramAdminIn(BaseModel):
    enabled: bool


@router.get("")
async def list_telegram_admins(
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(
            select(TelegramAdmin, TelegramUser)
            .join(TelegramUser, TelegramUser.id == TelegramAdmin.user_id)
            .where(TelegramAdmin.enabled.is_(True))
            .order_by(TelegramUser.created_at)
        )
    ).all()
    return [
        {
            "user_id": user.id,
            "telegram_user_id": user.telegram_user_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "enabled": bool(item.enabled),
            "welcome_sent_at": item.welcome_sent_at,
        }
        for item, user in rows
    ]


@router.put("/{telegram_user_pk}")
async def set_telegram_admin(
    telegram_user_pk: int,
    payload: TelegramAdminIn,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    telegram_user = await session.get(TelegramUser, telegram_user_pk)
    if telegram_user is None:
        raise HTTPException(status_code=404, detail="Telegram user not found")

    row = await session.get(TelegramAdmin, telegram_user_pk)
    now = datetime.now(timezone.utc)
    if row is None:
        row = TelegramAdmin(
            user_id=telegram_user_pk,
            enabled=payload.enabled,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
    else:
        row.enabled = payload.enabled
        row.updated_at = now
        if payload.enabled:
            # Send the welcome message again after a deliberate re-enable so the
            # operator can immediately verify that this Telegram account works.
            row.welcome_sent_at = None

    session.add(
        AdminAuditLog(
            admin_user_id=admin.id,
            action="telegram_admin_status",
            target_type="telegram_user",
            target_id=str(telegram_user_pk),
            details={
                "enabled": payload.enabled,
                "telegram_user_id": telegram_user.telegram_user_id,
                "username": telegram_user.username,
            },
        )
    )
    await session.commit()
    return {
        "ok": True,
        "user_id": telegram_user.id,
        "telegram_user_id": telegram_user.telegram_user_id,
        "enabled": bool(row.enabled),
    }
