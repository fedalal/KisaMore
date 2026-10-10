"""Shared Kisa promotion awards for website and Android registrations.

The Telegram promotion table is still the single source of campaign rules.
Both registration paths share /api/v1/auth/register; the periodic Telegram
worker catches missed awards and handles campaigns for existing users.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from .db import SessionLocal
from .models import User
from .site_wallet import locked_wallet, SiteWalletTransaction
from .telegram.models import TelegramUser, WalletTransaction
from .telegram.promotion_models import (
    SitePromotionGrant, TelegramPromotion, TelegramPromotionGrant,
)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _eligible(promotion: TelegramPromotion, created_at: datetime) -> bool:
    created = _aware(created_at)
    start = _aware(promotion.start_at)
    end = _aware(promotion.end_at)
    if promotion.audience == "new":
        return start <= created < end
    if promotion.audience == "existing":
        return created < start
    return promotion.audience == "all" and created < end


async def grant_for_website_user(
    session: AsyncSession, user: User, now: datetime | None = None
) -> int:
    """Credit any eligible campaigns in the caller's transaction.

    Caller must serialize on the website User row (registration owns the new
    row; periodic worker acquires FOR UPDATE). Linking uses this same lock.
    """
    if not user.is_active:
        return 0
    now = now or datetime.now(timezone.utc)
    campaigns = (await session.execute(
        select(TelegramPromotion)
        .where(
            TelegramPromotion.enabled.is_(True),
            TelegramPromotion.start_at <= now,
            TelegramPromotion.created_at < TelegramPromotion.end_at,
        )
        .order_by(TelegramPromotion.id)
    )).scalars().all()
    if not campaigns:
        return 0

    # A website user can link a Telegram account with pre-existing bonuses.
    # Never issue the same promotion again after linking.
    linked_tg = (await session.execute(
        select(TelegramUser).where(TelegramUser.marketplace_user_id == user.id)
    )).scalar_one_or_none()

    eligible = []
    for promo in campaigns:
        if not _eligible(promo, user.created_at):
            continue
        if await session.get(SitePromotionGrant, (promo.id, user.id)) is not None:
            continue
        if linked_tg and await session.get(
            TelegramPromotionGrant, (promo.id, linked_tg.id)
        ) is not None:
            continue
        eligible.append(promo)
    if not eligible:
        return 0

    wallet, linked_tg = await locked_wallet(session, user.id)
    amount_total = 0
    for promo in eligible:
        wallet.balance += int(promo.amount_kisa)
        metadata = {"promotion_name": promo.name, "message": promo.message}
        site_tx = None
        telegram_tx = None
        if linked_tg:
            telegram_tx = WalletTransaction(
                user_id=linked_tg.id, amount=int(promo.amount_kisa),
                balance_after=int(wallet.balance), kind="promotion_bonus",
                reference_type="promotion", reference_id=str(promo.id),
                details=metadata,
            )
            session.add(telegram_tx)
        else:
            site_tx = SiteWalletTransaction(
                user_id=user.id, amount=int(promo.amount_kisa),
                balance_after=int(wallet.balance), kind="promotion_bonus",
                reference_type="promotion", reference_id=str(promo.id),
                details=metadata,
            )
            session.add(site_tx)
        await session.flush()
        session.add(SitePromotionGrant(
            promotion_id=promo.id,
            user_id=user.id,
            site_transaction_id=site_tx.id if site_tx else None,
            telegram_transaction_id=telegram_tx.id if telegram_tx else None,
            balance_after=int(wallet.balance),
            granted_at=now,
        ))
        amount_total += int(promo.amount_kisa)
    await session.flush()
    return amount_total


async def _candidate_ids(
    session: AsyncSession, promotion: TelegramPromotion, batch_size: int
) -> list[str]:
    # Skip campaigns already awarded to a Telegram identity linked to the
    # website. This also prevents rescanning backfilled / linked records.
    stmt = (
        select(User.id)
        .outerjoin(
            SitePromotionGrant,
            and_(
                SitePromotionGrant.promotion_id == promotion.id,
                SitePromotionGrant.user_id == User.id,
            ),
        )
        .outerjoin(TelegramUser, TelegramUser.marketplace_user_id == User.id)
        .outerjoin(
            TelegramPromotionGrant,
            and_(
                TelegramPromotionGrant.promotion_id == promotion.id,
                TelegramPromotionGrant.user_id == TelegramUser.id,
            ),
        )
        .where(
            User.is_active.is_(True),
            SitePromotionGrant.user_id.is_(None),
            TelegramPromotionGrant.user_id.is_(None),
        )
        .order_by(User.created_at, User.id)
        .limit(batch_size)
    )
    if promotion.audience == "new":
        stmt = stmt.where(
            User.created_at >= promotion.start_at,
            User.created_at < promotion.end_at,
        )
    elif promotion.audience == "existing":
        stmt = stmt.where(User.created_at < promotion.start_at)
    else:
        stmt = stmt.where(User.created_at < promotion.end_at)
    return list((await session.execute(stmt)).scalars().all())


async def _grant_one_website(user_id: str) -> bool:
    async with SessionLocal() as session:
        try:
            user = (await session.execute(
                select(User).where(User.id == user_id).with_for_update()
            )).scalar_one_or_none()
            if not user:
                return False
            awarded = await grant_for_website_user(session, user)
            if awarded:
                await session.commit()
                return True
            await session.rollback()
            return False
        except IntegrityError:
            # Database uniqueness protects against retries / multiple workers.
            await session.rollback()
            return False


async def discover_and_grant_website(batch_size: int = 100) -> int:
    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        promotions = (await session.execute(
            select(TelegramPromotion)
            .where(
                TelegramPromotion.enabled.is_(True),
                TelegramPromotion.start_at <= now,
                TelegramPromotion.created_at < TelegramPromotion.end_at,
            )
            .order_by(TelegramPromotion.id)
        )).scalars().all()
        candidates = set()
        for promo in promotions:
            candidates.update(await _candidate_ids(session, promo, batch_size))
    granted_users = 0
    for user_id in sorted(candidates):
        if await _grant_one_website(user_id):
            granted_users += 1
        await asyncio.sleep(0)
    return granted_users
