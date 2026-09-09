from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select

from ..config import get_settings
from ..db import SessionLocal
from ..models import Allocation, Plant, Planting, RackCurrent, RackPhoto, RackSlot
from .models import (
    SocialComment,
    SocialFollow,
    SocialGift,
    SocialReaction,
    TelegramConversationState,
    TelegramRentalRequest,
    TelegramUser,
    WalletAccount,
    WalletTransaction,
)


ACTIVE_PLANTING_STATUSES = ("planned", "growing", "ready")
GIFT_COSTS = {"sprout": 1, "sun": 5, "support": 10, "trophy": 50}
settings = get_settings()


@dataclass
class PlantCard:
    planting: Planting
    plant: Plant
    slot: RackSlot
    photo: RackPhoto | None
    rack: RackCurrent | None
    likes: int
    dislikes: int
    comments: int
    gifts: int
    gift_kisa: int
    following: bool
    my_vote: str | None


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def language_base(value: str | None) -> str:
    raw = (value or "en").lower().replace("_", "-")
    return raw.split("-", 1)[0]


def localized_value(values: dict | None, lang: str, fallback: str = "") -> str:
    if not values:
        return fallback
    base = language_base(lang)
    for key in (lang, base, "en", "ru"):
        value = values.get(key)
        if value:
            return str(value)
    for value in values.values():
        if value:
            return str(value)
    return fallback


def day_number(planted_at: datetime | None) -> int:
    if not planted_at:
        return 1
    now = datetime.now(timezone.utc)
    dt = planted_at
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(1, (now - dt).days + 1)


def resolve_photo_path(photo: RackPhoto | None) -> Path | None:
    if photo is None or not photo.file_path:
        return None
    path = Path(photo.file_path)
    if not path.is_absolute():
        path = Path(settings.photo_dir) / path
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    return resolved if resolved.is_file() else None


async def get_or_create_user(tg: dict) -> tuple[TelegramUser, WalletAccount]:
    telegram_id = int(tg["id"])
    async with SessionLocal() as session:
        result = await session.execute(
            select(TelegramUser).where(TelegramUser.telegram_user_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            user = TelegramUser(
                telegram_user_id=telegram_id,
                username=tg.get("username"),
                first_name=tg.get("first_name"),
                last_name=tg.get("last_name"),
                language_code=tg.get("language_code"),
            )
            session.add(user)
            await session.flush()
            wallet = WalletAccount(user_id=user.id, balance=0)
            session.add(wallet)
        else:
            user.username = tg.get("username")
            user.first_name = tg.get("first_name")
            user.last_name = tg.get("last_name")
            user.language_code = tg.get("language_code")
            user.updated_at = utcnow()
            result = await session.execute(
                select(WalletAccount).where(WalletAccount.user_id == user.id)
            )
            wallet = result.scalar_one_or_none()
            if wallet is None:
                wallet = WalletAccount(user_id=user.id, balance=0)
                session.add(wallet)
        await session.commit()
        return user, wallet


async def wallet_for_update(session, user_id: int) -> WalletAccount:
    result = await session.execute(
        select(WalletAccount).where(WalletAccount.user_id == user_id).with_for_update()
    )
    return result.scalar_one()


async def list_plantings(*, limit: int = 20, offset: int = 0) -> list[tuple[Planting, Plant, RackSlot]]:
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(Planting, Plant, RackSlot)
                .join(Plant, Plant.id == Planting.plant_id)
                .join(RackSlot, RackSlot.id == Planting.slot_id)
                .where(Planting.status.in_(ACTIVE_PLANTING_STATUSES), Plant.active.is_(True))
                .order_by(Planting.planted_at.desc())
                .offset(max(0, offset))
                .limit(max(1, min(limit, 50)))
            )
        ).all()
        return list(rows)


async def get_plant_card(planting_id: str, user_id: int) -> PlantCard | None:
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(Planting, Plant, RackSlot)
                .join(Plant, Plant.id == Planting.plant_id)
                .join(RackSlot, RackSlot.id == Planting.slot_id)
                .where(Planting.id == planting_id)
            )
        ).first()
        if row is None:
            return None
        planting, plant, slot = row
        photo = (
            await session.execute(
                select(RackPhoto).where(
                    RackPhoto.device_id == slot.device_id,
                    RackPhoto.rack_id == slot.rack_id,
                )
            )
        ).scalar_one_or_none()
        rack = (
            await session.execute(
                select(RackCurrent).where(
                    RackCurrent.device_id == slot.device_id,
                    RackCurrent.rack_id == slot.rack_id,
                )
            )
        ).scalar_one_or_none()

        reaction_rows = (
            await session.execute(
                select(SocialReaction.reaction, func.count(SocialReaction.id))
                .where(
                    SocialReaction.target_type == "planting",
                    SocialReaction.target_id == planting_id,
                    SocialReaction.reaction.in_(("like", "dislike")),
                )
                .group_by(SocialReaction.reaction)
            )
        ).all()
        counts = {name: int(count) for name, count in reaction_rows}
        comments = int(
            (
                await session.execute(
                    select(func.count(SocialComment.id)).where(
                        SocialComment.target_type == "planting",
                        SocialComment.target_id == planting_id,
                        SocialComment.status == "published",
                    )
                )
            ).scalar_one()
            or 0
        )
        gift_row = (
            await session.execute(
                select(func.count(SocialGift.id), func.coalesce(func.sum(SocialGift.token_cost), 0)).where(
                    SocialGift.target_type == "planting",
                    SocialGift.target_id == planting_id,
                )
            )
        ).one()
        following = (
            await session.execute(
                select(SocialFollow.id).where(
                    SocialFollow.user_id == user_id,
                    SocialFollow.target_type == "planting",
                    SocialFollow.target_id == planting_id,
                )
            )
        ).scalar_one_or_none() is not None
        my_vote = (
            await session.execute(
                select(SocialReaction.reaction).where(
                    SocialReaction.user_id == user_id,
                    SocialReaction.target_type == "planting",
                    SocialReaction.target_id == planting_id,
                    SocialReaction.reaction.in_(("like", "dislike")),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        return PlantCard(
            planting=planting,
            plant=plant,
            slot=slot,
            photo=photo,
            rack=rack,
            likes=counts.get("like", 0),
            dislikes=counts.get("dislike", 0),
            comments=comments,
            gifts=int(gift_row[0] or 0),
            gift_kisa=int(gift_row[1] or 0),
            following=following,
            my_vote=my_vote,
        )


async def toggle_vote(user_id: int, planting_id: str, reaction: str) -> str | None:
    if reaction not in ("like", "dislike"):
        raise ValueError("Invalid reaction")
    async with SessionLocal() as session:
        current = (
            await session.execute(
                select(SocialReaction).where(
                    SocialReaction.user_id == user_id,
                    SocialReaction.target_type == "planting",
                    SocialReaction.target_id == planting_id,
                    SocialReaction.reaction.in_(("like", "dislike")),
                )
            )
        ).scalars().all()
        same = any(item.reaction == reaction for item in current)
        await session.execute(
            delete(SocialReaction).where(
                SocialReaction.user_id == user_id,
                SocialReaction.target_type == "planting",
                SocialReaction.target_id == planting_id,
                SocialReaction.reaction.in_(("like", "dislike")),
            )
        )
        result = None
        if not same:
            session.add(
                SocialReaction(
                    user_id=user_id,
                    target_type="planting",
                    target_id=planting_id,
                    reaction=reaction,
                    token_cost=0,
                )
            )
            result = reaction
        await session.commit()
        return result


async def toggle_follow(user_id: int, planting_id: str) -> bool:
    async with SessionLocal() as session:
        follow = (
            await session.execute(
                select(SocialFollow).where(
                    SocialFollow.user_id == user_id,
                    SocialFollow.target_type == "planting",
                    SocialFollow.target_id == planting_id,
                )
            )
        ).scalar_one_or_none()
        if follow is None:
            session.add(
                SocialFollow(
                    user_id=user_id,
                    target_type="planting",
                    target_id=planting_id,
                    last_notified_at=utcnow(),
                )
            )
            enabled = True
        else:
            await session.delete(follow)
            enabled = False
        await session.commit()
        return enabled


async def add_comment(user_id: int, planting_id: str, body: str) -> SocialComment:
    text = body.strip()
    if not text:
        raise ValueError("empty")
    if len(text) > 1000:
        raise ValueError("too_long")
    async with SessionLocal() as session:
        planting = await session.get(Planting, planting_id)
        if planting is None:
            raise ValueError("not_found")
        comment = SocialComment(
            user_id=user_id,
            target_type="planting",
            target_id=planting_id,
            body=text,
        )
        session.add(comment)
        await session.commit()
        await session.refresh(comment)
        return comment


async def list_comments(planting_id: str, *, limit: int = 10) -> list[tuple[SocialComment, TelegramUser]]:
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(SocialComment, TelegramUser)
                .join(TelegramUser, TelegramUser.id == SocialComment.user_id)
                .where(
                    SocialComment.target_type == "planting",
                    SocialComment.target_id == planting_id,
                    SocialComment.status == "published",
                )
                .order_by(SocialComment.created_at.desc())
                .limit(max(1, min(limit, 30)))
            )
        ).all()
        return list(rows)


async def set_state(
    user_id: int,
    mode: str,
    *,
    target_type: str | None = None,
    target_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    async with SessionLocal() as session:
        state = (
            await session.execute(
                select(TelegramConversationState).where(TelegramConversationState.user_id == user_id)
            )
        ).scalar_one_or_none()
        if state is None:
            state = TelegramConversationState(
                user_id=user_id,
                mode=mode,
                target_type=target_type,
                target_id=target_id,
                payload=payload or {},
            )
            session.add(state)
        else:
            state.mode = mode
            state.target_type = target_type
            state.target_id = target_id
            state.payload = payload or {}
            state.updated_at = utcnow()
        await session.commit()


async def get_state(user_id: int) -> TelegramConversationState | None:
    async with SessionLocal() as session:
        return (
            await session.execute(
                select(TelegramConversationState).where(TelegramConversationState.user_id == user_id)
            )
        ).scalar_one_or_none()


async def clear_state(user_id: int) -> None:
    async with SessionLocal() as session:
        await session.execute(
            delete(TelegramConversationState).where(TelegramConversationState.user_id == user_id)
        )
        await session.commit()


async def send_gift(user_id: int, planting_id: str, gift_code: str) -> tuple[bool, int, int]:
    cost = GIFT_COSTS.get(gift_code)
    if cost is None:
        raise ValueError("Invalid gift")
    async with SessionLocal() as session:
        wallet = await wallet_for_update(session, user_id)
        if wallet.balance < cost:
            return False, wallet.balance, cost
        planting = await session.get(Planting, planting_id)
        if planting is None:
            raise ValueError("Planting not found")
        wallet.balance -= cost
        session.add(
            SocialGift(
                user_id=user_id,
                target_type="planting",
                target_id=planting_id,
                gift_code=gift_code,
                token_cost=cost,
            )
        )
        session.add(
            WalletTransaction(
                user_id=user_id,
                amount=-cost,
                balance_after=wallet.balance,
                kind="plant_gift",
                reference_type="planting",
                reference_id=planting_id,
                details={"gift": gift_code},
            )
        )
        await session.commit()
        return True, wallet.balance, cost


async def wallet_history(user_id: int, limit: int = 8) -> list[WalletTransaction]:
    async with SessionLocal() as session:
        return list(
            (
                await session.execute(
                    select(WalletTransaction)
                    .where(WalletTransaction.user_id == user_id)
                    .order_by(WalletTransaction.created_at.desc())
                    .limit(max(1, min(limit, 20)))
                )
            ).scalars().all()
        )


async def profile_stats(user_id: int) -> dict[str, int]:
    async with SessionLocal() as session:
        likes = int((await session.execute(select(func.count(SocialReaction.id)).where(
            SocialReaction.user_id == user_id, SocialReaction.reaction == "like"
        ))).scalar_one() or 0)
        comments = int((await session.execute(select(func.count(SocialComment.id)).where(
            SocialComment.user_id == user_id, SocialComment.status == "published"
        ))).scalar_one() or 0)
        follows = int((await session.execute(select(func.count(SocialFollow.id)).where(
            SocialFollow.user_id == user_id
        ))).scalar_one() or 0)
        gifts = int((await session.execute(select(func.count(SocialGift.id)).where(
            SocialGift.user_id == user_id
        ))).scalar_one() or 0)
        kisa_spent = int((await session.execute(select(func.coalesce(func.sum(SocialGift.token_cost), 0)).where(
            SocialGift.user_id == user_id
        ))).scalar_one() or 0)
        return {"likes": likes, "comments": comments, "follows": follows, "gifts": gifts, "kisa_spent": kisa_spent}


async def community_top(limit: int = 5) -> list[tuple[Planting, Plant, RackSlot, int, int]]:
    rows = await list_plantings(limit=30)
    scored: list[tuple[Planting, Plant, RackSlot, int, int]] = []
    async with SessionLocal() as session:
        for planting, plant, slot in rows:
            likes = int((await session.execute(select(func.count(SocialReaction.id)).where(
                SocialReaction.target_type == "planting",
                SocialReaction.target_id == planting.id,
                SocialReaction.reaction == "like",
            ))).scalar_one() or 0)
            gifts = int((await session.execute(select(func.coalesce(func.sum(SocialGift.token_cost), 0)).where(
                SocialGift.target_type == "planting",
                SocialGift.target_id == planting.id,
            ))).scalar_one() or 0)
            scored.append((planting, plant, slot, likes, gifts))
    scored.sort(key=lambda item: (item[3] + item[4], item[3]), reverse=True)
    return scored[: max(1, min(limit, 10))]


async def list_followed_plantings(user_id: int, limit: int = 10) -> list[tuple[Planting, Plant, RackSlot]]:
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(Planting, Plant, RackSlot)
                .join(Plant, Plant.id == Planting.plant_id)
                .join(RackSlot, RackSlot.id == Planting.slot_id)
                .join(SocialFollow, (SocialFollow.target_type == "planting") & (SocialFollow.target_id == Planting.id))
                .where(SocialFollow.user_id == user_id)
                .order_by(SocialFollow.created_at.desc())
                .limit(max(1, min(limit, 20)))
            )
        ).all()
        return list(rows)


async def list_available_slots(limit: int = 20) -> list[RackSlot]:
    async with SessionLocal() as session:
        return list((await session.execute(select(RackSlot).where(
            RackSlot.enabled.is_(True), RackSlot.physical_status == "available"
        ).order_by(RackSlot.rack_id, RackSlot.slot_number).limit(max(1, min(limit, 50))))).scalars().all())


async def list_active_plants(limit: int = 30) -> list[Plant]:
    async with SessionLocal() as session:
        return list((await session.execute(select(Plant).where(Plant.active.is_(True)).order_by(Plant.code).limit(limit))).scalars().all())


async def create_rental_request(user_id: int, slot_id: int, plant_id: str) -> TelegramRentalRequest:
    async with SessionLocal() as session:
        slot = await session.get(RackSlot, slot_id)
        plant = await session.get(Plant, plant_id)
        if slot is None or not slot.enabled or slot.physical_status != "available":
            raise ValueError("slot_unavailable")
        if plant is None or not plant.active:
            raise ValueError("plant_unavailable")
        existing = (await session.execute(select(TelegramRentalRequest).where(
            TelegramRentalRequest.user_id == user_id,
            TelegramRentalRequest.slot_id == slot_id,
            TelegramRentalRequest.status.in_(("requested", "approved")),
        ))).scalar_one_or_none()
        if existing is not None:
            return existing
        req = TelegramRentalRequest(user_id=user_id, slot_id=slot_id, plant_id=plant_id, status="requested")
        session.add(req)
        await session.commit()
        await session.refresh(req)
        return req


async def rental_requests(user_id: int, limit: int = 10) -> list[tuple[TelegramRentalRequest, RackSlot, Plant]]:
    async with SessionLocal() as session:
        rows = (await session.execute(
            select(TelegramRentalRequest, RackSlot, Plant)
            .join(RackSlot, RackSlot.id == TelegramRentalRequest.slot_id)
            .join(Plant, Plant.id == TelegramRentalRequest.plant_id)
            .where(TelegramRentalRequest.user_id == user_id)
            .order_by(TelegramRentalRequest.created_at.desc())
            .limit(max(1, min(limit, 20)))
        )).all()
        return list(rows)


async def linked_allocations(user: TelegramUser, limit: int = 10) -> list[Allocation]:
    if not user.marketplace_user_id:
        return []
    async with SessionLocal() as session:
        return list((await session.execute(
            select(Allocation).where(Allocation.user_id == user.marketplace_user_id, Allocation.status == "active")
            .order_by(Allocation.starts_at.desc()).limit(max(1, min(limit, 20)))
        )).scalars().all())


@dataclass
class FollowNotification:
    follow_id: int
    telegram_user_id: int
    language_code: str | None
    planting_id: str
    plant_name_values: dict
    rack_id: int
    slot_number: int
    photo: RackPhoto


async def pending_follow_notifications(limit: int = 50) -> list[FollowNotification]:
    async with SessionLocal() as session:
        rows = (await session.execute(
            select(SocialFollow, TelegramUser, Planting, Plant, RackSlot, RackPhoto)
            .join(TelegramUser, TelegramUser.id == SocialFollow.user_id)
            .join(Planting, (SocialFollow.target_type == "planting") & (SocialFollow.target_id == Planting.id))
            .join(Plant, Plant.id == Planting.plant_id)
            .join(RackSlot, RackSlot.id == Planting.slot_id)
            .join(RackPhoto, (RackPhoto.device_id == RackSlot.device_id) & (RackPhoto.rack_id == RackSlot.rack_id))
            .where(
                SocialFollow.notifications_enabled.is_(True),
                SocialFollow.last_notified_at.is_not(None),
                RackPhoto.updated_at > SocialFollow.last_notified_at,
            )
            .order_by(RackPhoto.updated_at.asc())
            .limit(max(1, min(limit, 100)))
        )).all()
        return [FollowNotification(
            follow_id=follow.id,
            telegram_user_id=user.telegram_user_id,
            language_code=user.language_code,
            planting_id=planting.id,
            plant_name_values=plant.names,
            rack_id=slot.rack_id,
            slot_number=slot.slot_number,
            photo=photo,
        ) for follow, user, planting, plant, slot, photo in rows]


async def mark_follow_notified(follow_id: int, observed_at: datetime) -> None:
    async with SessionLocal() as session:
        follow = await session.get(SocialFollow, follow_id)
        if follow is not None:
            value = observed_at
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            follow.last_notified_at = value
            await session.commit()
