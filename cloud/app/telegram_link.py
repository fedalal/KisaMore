from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import secrets

from sqlalchemy import DateTime, ForeignKey, String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, User
from .telegram.models import TelegramUser


LINK_TTL_MINUTES = 30


class WebsiteTelegramLinkToken(Base):
    __tablename__ = "website_telegram_link_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def create_telegram_link_token(
    session: AsyncSession,
    *,
    user_id: str,
) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    token = secrets.token_urlsafe(24)
    expires_at = now + timedelta(minutes=LINK_TTL_MINUTES)
    session.add(
        WebsiteTelegramLinkToken(
            token_hash=_hash(token),
            user_id=user_id,
            expires_at=expires_at,
            created_at=now,
        )
    )
    await session.flush()
    return token, expires_at


async def linked_telegram_user(
    session: AsyncSession,
    *,
    user_id: str,
) -> TelegramUser | None:
    return (
        await session.execute(
            select(TelegramUser)
            .where(
                TelegramUser.marketplace_user_id == user_id,
                TelegramUser.is_active.is_(True),
            )
            .order_by(TelegramUser.id)
            .limit(1)
        )
    ).scalar_one_or_none()


async def consume_telegram_link_token(
    session: AsyncSession,
    *,
    raw_token: str,
    telegram_user_id: int,
) -> User:
    now = datetime.now(timezone.utc)
    row = (
        await session.execute(
            select(WebsiteTelegramLinkToken)
            .where(WebsiteTelegramLinkToken.token_hash == _hash(raw_token))
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is None or row.used_at is not None or (_aware(row.expires_at) or now) <= now:
        raise ValueError("link_expired")

    website_user = await session.get(User, row.user_id)
    telegram_user = (
        await session.execute(
            select(TelegramUser)
            .where(TelegramUser.telegram_user_id == telegram_user_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if website_user is None or not website_user.is_active:
        raise ValueError("website_user_unavailable")
    if telegram_user is None or not telegram_user.is_active:
        raise ValueError("telegram_user_unavailable")
    if telegram_user.marketplace_user_id and telegram_user.marketplace_user_id != website_user.id:
        raise ValueError("telegram_already_linked")

    existing = (
        await session.execute(
            select(TelegramUser)
            .where(
                TelegramUser.marketplace_user_id == website_user.id,
                TelegramUser.id != telegram_user.id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ValueError("website_already_linked")

    telegram_user.marketplace_user_id = website_user.id
    row.used_at = now
    await session.flush()
    return website_user
