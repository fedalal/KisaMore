"""Website Kisa wallet. Telegram is optional; linked accounts use their existing
Telegram wallet as the shared balance until the legacy bot wallet is migrated.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, JSON, String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, User
from .telegram.models import TelegramUser, WalletAccount, WalletTransaction


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SiteWallet(Base):
    __tablename__ = "site_wallets"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    balance: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class SiteWalletTransaction(Base):
    __tablename__ = "site_wallet_transactions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(40))
    reference_id: Mapped[str | None] = mapped_column(String(160))
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


async def locked_wallet(session: AsyncSession, user_id: str) -> tuple[SiteWallet | WalletAccount, TelegramUser | None]:
    """Caller MUST lock the User row first for purchases, grants and linking."""
    tg = (await session.execute(
        select(TelegramUser)
        .where(TelegramUser.marketplace_user_id == user_id)
        .with_for_update()
    )).scalar_one_or_none()
    if tg is not None:
        wallet = (await session.execute(
            select(WalletAccount).where(WalletAccount.user_id == tg.id).with_for_update()
        )).scalar_one_or_none()
        if wallet is None:
            wallet = WalletAccount(user_id=tg.id, balance=0)
            session.add(wallet)
            await session.flush()
        return wallet, tg
    wallet = await session.get(SiteWallet, user_id, with_for_update=True)
    if wallet is None:
        wallet = SiteWallet(user_id=user_id, balance=0)
        session.add(wallet)
        await session.flush()
    return wallet, None


def record_wallet_change(
    session: AsyncSession, *, user_id: str, telegram_user: TelegramUser | None,
    wallet: SiteWallet | WalletAccount, amount: int, kind: str,
    reference_type: str, reference_id: str, details: dict | None = None,
) -> None:
    if telegram_user is not None:
        session.add(WalletTransaction(
            user_id=telegram_user.id, amount=amount,
            balance_after=wallet.balance, kind=kind, reference_type=reference_type,
            reference_id=reference_id, details=details or {},
        ))
    else:
        session.add(SiteWalletTransaction(
            user_id=user_id, amount=amount,
            balance_after=wallet.balance, kind=kind, reference_type=reference_type,
            reference_id=reference_id, details=details or {},
        ))


async def combine_site_wallet_with_telegram(
    session: AsyncSession, *, website_user: User, telegram_user: TelegramUser,
) -> None:
    """Atomic balance migration when a website-only user links Telegram."""
    site = await session.get(SiteWallet, website_user.id, with_for_update=True)
    if site is None or not site.balance:
        return
    wallet = (await session.execute(
        select(WalletAccount).where(WalletAccount.user_id == telegram_user.id).with_for_update()
    )).scalar_one_or_none()
    if wallet is None:
        wallet = WalletAccount(user_id=telegram_user.id, balance=0)
        session.add(wallet)
        await session.flush()
    amount = int(site.balance)
    site.balance = 0
    site.updated_at = utcnow()
    wallet.balance += amount
    session.add(SiteWalletTransaction(
        user_id=website_user.id, amount=-amount, balance_after=0,
        kind="telegram_wallet_transfer", reference_type="telegram_user",
        reference_id=str(telegram_user.id), details={"reason": "account_link"},
    ))
    session.add(WalletTransaction(
        user_id=telegram_user.id, amount=amount, balance_after=wallet.balance,
        kind="site_wallet_transfer", reference_type="site_user",
        reference_id=website_user.id, details={"reason": "account_link"},
    ))
