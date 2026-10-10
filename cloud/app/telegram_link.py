from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import secrets

from sqlalchemy import DateTime, ForeignKey, String, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from .models import Allocation, Base, Notification, Offer, Order, ReservationRequest, User
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

    # All wallet mutations lock the website user first.
    website_user = await session.get(User, row.user_id, with_for_update=True)
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
    old_marketplace_user_id = telegram_user.marketplace_user_id
    if old_marketplace_user_id and old_marketplace_user_id != website_user.id:
        old_user = await session.get(User, old_marketplace_user_id)
        is_internal = bool(
            old_user
            and not old_user.is_active
            and old_user.email.endswith("@internal.kisamore.local")
        )
        if not is_internal:
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

    if old_marketplace_user_id and old_marketplace_user_id != website_user.id:
        # Telegram-first rentals historically used an inactive technical User.
        # Move their marketplace ownership to the real website account so
        # current plants and rental history remain visible after linking.
        for model in (Allocation, ReservationRequest, Offer, Order, Notification):
            await session.execute(
                update(model)
                .where(model.user_id == old_marketplace_user_id)
                .values(user_id=website_user.id)
            )

    # Transfer the website-only Kisa balance into the existing Telegram wallet.
    # The debit and credit ledgers are written in the same transaction.
    from .site_wallet import combine_site_wallet_with_telegram
    from .battle_models import PlantBattleEntry
    await combine_site_wallet_with_telegram(
        session, website_user=website_user, telegram_user=telegram_user
    )
    # New website-only entries get Telegram notifications after the link.
    await session.execute(
        update(PlantBattleEntry)
        .where(
            PlantBattleEntry.user_id == website_user.id,
            PlantBattleEntry.telegram_user_id.is_(None),
        )
        .values(telegram_user_id=telegram_user.id)
    )
    telegram_user.marketplace_user_id = website_user.id
    row.used_at = now
    await session.flush()
    return website_user
