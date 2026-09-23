from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path
import asyncio
import hashlib

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth_api import user_out
from .models import (
    Allocation,
    InventorySyncReceipt,
    Device,
    Farm,
    Notification,
    Offer,
    Order,
    Plant,
    Planting,
    RackCurrent,
    RackPhoto,
    RackSlot,
    ReservationRequest,
    User,
    WebSocialComment,
    WebSocialReaction,
)
from .marketplace_service import (
    active_inventory,
    aware_utc,
    expire_offers,
    find_available_target,
    process_waitlist,
    slot_is_blocked,
)
from .schemas import (
    AccountOut,
    AllocationOut,
    FarmMarketOut,
    NotificationOut,
    OfferOut,
    PlantPublicOut,
    PlantingPublicOut,
    PurchaseIn,
    RackMarketOut,
    ReservationIn,
    ReservationOut,
    SlotPublicOut,
)
from .security import authenticate_device, get_current_user, get_session
from .config import get_settings
from .rack_photo_storage import store_rack_photo
from .seed_inventory import SeedUnavailable, require_seed_available, seed_availability
from .telegram.admin_models import EdgeOperatorCommand
from .telegram.models import (
    SocialComment,
    SocialGift,
    SocialReaction,
    TelegramUser,
    WalletAccount,
    WalletTransaction,
)
from .telegram.service import GIFT_COSTS


router = APIRouter(prefix="/api/v1", tags=["marketplace"])


class EdgeOperatorCommandAckIn(BaseModel):
    status: str = Field(pattern="^(applied|failed)$")
    error: str = Field(default="", max_length=1000)


class WebReactionIn(BaseModel):
    reaction: str = Field(pattern="^(like|dislike)$")


class WebCommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=1000)


class WebGiftIn(BaseModel):
    gift_code: str = Field(pattern="^(sprout|sun|support|trophy)$")


async def _social_counts(session: AsyncSession, planting_id: str) -> dict[str, int]:
    telegram_reactions = (
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
    web_reactions = (
        await session.execute(
            select(WebSocialReaction.reaction, func.count(WebSocialReaction.id))
            .where(
                WebSocialReaction.target_type == "planting",
                WebSocialReaction.target_id == planting_id,
                WebSocialReaction.reaction.in_(("like", "dislike")),
            )
            .group_by(WebSocialReaction.reaction)
        )
    ).all()

    result = {"likes": 0, "dislikes": 0, "comments": 0, "gifts": 0, "gift_kisa": 0}
    for reaction, count in [*telegram_reactions, *web_reactions]:
        key = "likes" if reaction == "like" else "dislikes"
        result[key] += int(count or 0)

    telegram_comments = int(
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
    web_comments = int(
        (
            await session.execute(
                select(func.count(WebSocialComment.id)).where(
                    WebSocialComment.target_type == "planting",
                    WebSocialComment.target_id == planting_id,
                    WebSocialComment.status == "published",
                )
            )
        ).scalar_one()
        or 0
    )
    result["comments"] = telegram_comments + web_comments

    gift_row = (
        await session.execute(
            select(
                func.count(SocialGift.id),
                func.coalesce(func.sum(SocialGift.token_cost), 0),
            ).where(
                SocialGift.target_type == "planting",
                SocialGift.target_id == planting_id,
            )
        )
    ).one()
    result["gifts"] = int(gift_row[0] or 0)
    result["gift_kisa"] = int(gift_row[1] or 0)
    return result


async def _require_planting(session: AsyncSession, planting_id: str) -> Planting:
    planting = await session.get(Planting, planting_id)
    if planting is None:
        raise HTTPException(status_code=404, detail="Planting not found")
    return planting


def allocation_out(item: Allocation) -> AllocationOut:
    return AllocationOut(
        id=item.id,
        resource_type=item.resource_type,
        device_id=item.device_id,
        rack_id=item.rack_id,
        slot_number=item.slot_number,
        plant_id=item.plant_id,
        status=item.status,
        starts_at=aware_utc(item.starts_at),
        ends_at=aware_utc(item.ends_at),
    )


def reservation_out(item: ReservationRequest) -> ReservationOut:
    return ReservationOut(
        id=item.id,
        resource_type=item.resource_type,
        device_id=item.device_id,
        rack_id=item.rack_id,
        slot_number=item.slot_number,
        plant_id=item.plant_id,
        status=item.status,
        created_at=aware_utc(item.created_at),
    )


def _public_plant_image_path(plant: Plant) -> tuple[Path, str] | None:
    """Resolve the same catalogue image directory used by the Telegram bot."""
    raw_name = (
        str(plant.microgreen_image_name or "").strip()
        or str(plant.seed_image_name or "").strip()
    )
    if not raw_name:
        return None

    name = Path(raw_name).name
    if name != raw_name:
        return None

    media_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    media_type = media_types.get(Path(name).suffix.lower())
    if media_type is None:
        return None

    path = Path(get_settings().plant_image_dir) / name
    return (path, media_type) if path.is_file() else None


def offer_out(item: Offer) -> OfferOut:
    return OfferOut(
        id=item.id,
        reservation_id=item.reservation_id,
        resource_type=item.resource_type,
        device_id=item.device_id,
        rack_id=item.rack_id,
        slot_number=item.slot_number,
        plant_id=item.plant_id,
        status=item.status,
        expires_at=aware_utc(item.expires_at),
    )


@router.get("/public/farms/{farm_slug}/market", response_model=FarmMarketOut)
async def public_market(
    farm_slug: str,
    session: AsyncSession = Depends(get_session),
):
    farm = (
        await session.execute(
            select(Farm).where(Farm.slug == farm_slug, Farm.is_public.is_(True))
        )
    ).scalar_one_or_none()
    if farm is None:
        raise HTTPException(status_code=404, detail="Public farm not found")
    device = (
        await session.execute(
            select(Device)
            .where(Device.farm_id == farm.id, Device.is_active.is_(True))
            .order_by(Device.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=404, detail="Farm device not found")

    all_plants = list(
        (
            await session.execute(select(Plant).where(Plant.active.is_(True)).order_by(Plant.code))
        ).scalars().all()
    )
    plant_by_id = {plant.id: plant for plant in all_plants}
    plants = [
        plant
        for plant in all_plants
        if (await seed_availability(session, plant.id)).in_stock
    ]
    slots, allocations, offers = await active_inventory(session, device.id)
    rack_states = (
        await session.execute(
            select(RackCurrent).where(
                RackCurrent.device_id == device.id,
                RackCurrent.rack_id <= device.racks_count,
            )
        )
    ).scalars().all()
    rack_state_by_id = {rack.rack_id: rack for rack in rack_states}
    photos = (
        await session.execute(select(RackPhoto).where(RackPhoto.device_id == device.id))
    ).scalars().all()
    photo_by_rack_id = {photo.rack_id: photo for photo in photos}
    slot_ids = [slot.id for slot in slots]
    plantings = []
    if slot_ids:
        plantings = (
            await session.execute(
                select(Planting).where(
                    Planting.slot_id.in_(slot_ids),
                    Planting.status.in_(("planned", "growing", "ready")),
                )
            )
        ).scalars().all()
    planting_by_slot = {item.slot_id: item for item in plantings}

    social_by_planting: dict[str, dict[str, int]] = {
        item.id: {"likes": 0, "dislikes": 0, "comments": 0, "gifts": 0, "gift_kisa": 0}
        for item in plantings
    }
    planting_ids = list(social_by_planting)
    if planting_ids:
        reaction_rows = (
            await session.execute(
                select(
                    SocialReaction.target_id,
                    SocialReaction.reaction,
                    func.count(SocialReaction.id),
                )
                .where(
                    SocialReaction.target_type == "planting",
                    SocialReaction.target_id.in_(planting_ids),
                    SocialReaction.reaction.in_(("like", "dislike")),
                )
                .group_by(SocialReaction.target_id, SocialReaction.reaction)
            )
        ).all()
        for target_id, reaction, count in reaction_rows:
            key = "likes" if reaction == "like" else "dislikes"
            social_by_planting[target_id][key] = int(count or 0)

        web_reaction_rows = (
            await session.execute(
                select(
                    WebSocialReaction.target_id,
                    WebSocialReaction.reaction,
                    func.count(WebSocialReaction.id),
                )
                .where(
                    WebSocialReaction.target_type == "planting",
                    WebSocialReaction.target_id.in_(planting_ids),
                    WebSocialReaction.reaction.in_(("like", "dislike")),
                )
                .group_by(WebSocialReaction.target_id, WebSocialReaction.reaction)
            )
        ).all()
        for target_id, reaction, count in web_reaction_rows:
            key = "likes" if reaction == "like" else "dislikes"
            social_by_planting[target_id][key] += int(count or 0)

        comment_rows = (
            await session.execute(
                select(SocialComment.target_id, func.count(SocialComment.id))
                .where(
                    SocialComment.target_type == "planting",
                    SocialComment.target_id.in_(planting_ids),
                    SocialComment.status == "published",
                )
                .group_by(SocialComment.target_id)
            )
        ).all()
        for target_id, count in comment_rows:
            social_by_planting[target_id]["comments"] = int(count or 0)

        web_comment_rows = (
            await session.execute(
                select(WebSocialComment.target_id, func.count(WebSocialComment.id))
                .where(
                    WebSocialComment.target_type == "planting",
                    WebSocialComment.target_id.in_(planting_ids),
                    WebSocialComment.status == "published",
                )
                .group_by(WebSocialComment.target_id)
            )
        ).all()
        for target_id, count in web_comment_rows:
            social_by_planting[target_id]["comments"] += int(count or 0)

        gift_rows = (
            await session.execute(
                select(
                    SocialGift.target_id,
                    func.count(SocialGift.id),
                    func.coalesce(func.sum(SocialGift.token_cost), 0),
                )
                .where(
                    SocialGift.target_type == "planting",
                    SocialGift.target_id.in_(planting_ids),
                )
                .group_by(SocialGift.target_id)
            )
        ).all()
        for target_id, count, gift_kisa in gift_rows:
            social_by_planting[target_id]["gifts"] = int(count or 0)
            social_by_planting[target_id]["gift_kisa"] = int(gift_kisa or 0)

    racks: list[RackMarketOut] = []
    for rack_id in range(1, device.racks_count + 1):
        rack_slots = [slot for slot in slots if slot.rack_id == rack_id]
        public_slots = []
        for slot in rack_slots:
            blocked = slot_is_blocked(rack_id, slot.slot_number, allocations, offers)
            available = slot.enabled and slot.physical_status == "available" and not blocked
            if not slot.enabled:
                status = "disabled"
            elif blocked:
                status = "occupied"
            else:
                status = slot.physical_status
            planting = planting_by_slot.get(slot.id)
            public_slots.append(
                SlotPublicOut(
                    rack_id=rack_id,
                    slot_number=slot.slot_number,
                    status=status,
                    physical_status=slot.physical_status,
                    available=available,
                    expected_available_at=aware_utc(slot.expected_available_at),
                    planting=(
                        PlantingPublicOut(
                            id=planting.id,
                            plant_id=planting.plant_id,
                            plant_names=(
                                plant_by_id[planting.plant_id].names
                                if planting.plant_id in plant_by_id
                                else {}
                            ),
                            planted_at=aware_utc(planting.planted_at),
                            expected_harvest_at=aware_utc(planting.expected_harvest_at),
                            status=planting.status,
                            likes=social_by_planting[planting.id]["likes"],
                            dislikes=social_by_planting[planting.id]["dislikes"],
                            comments=social_by_planting[planting.id]["comments"],
                            gifts=social_by_planting[planting.id]["gifts"],
                            gift_kisa=social_by_planting[planting.id]["gift_kisa"],
                        )
                        if planting
                        else None
                    ),
                )
            )
        rack_state = rack_state_by_id.get(rack_id)
        photo = photo_by_rack_id.get(rack_id)
        whole_available = find_available_target(
            "rack", rack_id, None, slots, allocations, offers
        ) is not None
        racks.append(
            RackMarketOut(
                rack_id=rack_id,
                available_slots=sum(item.available for item in public_slots),
                whole_rack_available=whole_available,
                light_on=rack_state.light_on if rack_state else None,
                water_on=rack_state.water_on if rack_state else None,
                soil_moisture=rack_state.soil_moisture if rack_state else None,
                soil_temperature=rack_state.soil_temperature if rack_state else None,
                photo_url=(
                    f"/api/v1/public/farms/{farm.slug}/racks/{rack_id}/photo"
                    if photo
                    else None
                ),
                photo_captured_at=aware_utc(photo.captured_at) if photo else None,
                slots=public_slots,
            )
        )

    return FarmMarketOut(
        farm_slug=farm.slug,
        farm_name=farm.name,
        device_id=device.id,
        plants=[
            PlantPublicOut(
                id=plant.id,
                code=plant.code,
                names=plant.names,
                descriptions=plant.descriptions,
                seed_image_name=plant.seed_image_name,
                microgreen_image_name=plant.microgreen_image_name,
                grow_days=plant.grow_days,
                rental_price_kisa=plant.rental_price_kisa,
                watering_schedule=plant.watering_schedule or [],
                watering_adjustment_limit_percent=plant.watering_adjustment_limit_percent,
                watering_adjustment_step_percent=plant.watering_adjustment_step_percent,
                watering_min_interval_minutes=plant.watering_min_interval_minutes,
                extra_watering_options=plant.extra_watering_options or [],
            )
            for plant in plants
        ],
        racks=racks,
    )


@router.post("/public/plantings/{planting_id}/reaction")
async def web_planting_reaction(
    planting_id: str,
    payload: WebReactionIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _require_planting(session, planting_id)

    current = (
        await session.execute(
            select(WebSocialReaction).where(
                WebSocialReaction.user_id == user.id,
                WebSocialReaction.target_type == "planting",
                WebSocialReaction.target_id == planting_id,
            )
        )
    ).scalar_one_or_none()

    active_reaction: str | None = payload.reaction
    if current is not None and current.reaction == payload.reaction:
        await session.delete(current)
        active_reaction = None
    else:
        if current is not None:
            await session.delete(current)
            await session.flush()
        session.add(
            WebSocialReaction(
                user_id=user.id,
                target_type="planting",
                target_id=planting_id,
                reaction=payload.reaction,
                created_at=datetime.now(timezone.utc),
            )
        )

    await session.commit()
    counts = await _social_counts(session, planting_id)
    return {**counts, "my_reaction": active_reaction}


@router.get("/public/plantings/{planting_id}/comments")
async def web_planting_comments(
    planting_id: str,
    session: AsyncSession = Depends(get_session),
):
    await _require_planting(session, planting_id)

    web_rows = (
        await session.execute(
            select(WebSocialComment, User)
            .join(User, User.id == WebSocialComment.user_id)
            .where(
                WebSocialComment.target_type == "planting",
                WebSocialComment.target_id == planting_id,
                WebSocialComment.status == "published",
            )
            .order_by(WebSocialComment.created_at.desc())
            .limit(50)
        )
    ).all()
    telegram_rows = (
        await session.execute(
            select(SocialComment, TelegramUser)
            .join(TelegramUser, TelegramUser.id == SocialComment.user_id)
            .where(
                SocialComment.target_type == "planting",
                SocialComment.target_id == planting_id,
                SocialComment.status == "published",
            )
            .order_by(SocialComment.created_at.desc())
            .limit(50)
        )
    ).all()

    items = [
        {
            "id": f"web:{comment.id}",
            "author": author.display_name,
            "body": comment.body,
            "created_at": aware_utc(comment.created_at),
            "source": "web",
        }
        for comment, author in web_rows
    ]
    items.extend(
        {
            "id": f"telegram:{comment.id}",
            "author": author.first_name or author.username or "KisaMore user",
            "body": comment.body,
            "created_at": aware_utc(comment.created_at),
            "source": "telegram",
        }
        for comment, author in telegram_rows
    )
    items.sort(key=lambda item: item["created_at"], reverse=True)
    return {"items": items[:50]}


@router.post("/public/plantings/{planting_id}/comments", status_code=201)
async def web_add_planting_comment(
    planting_id: str,
    payload: WebCommentIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _require_planting(session, planting_id)
    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=422, detail="Comment cannot be empty")

    comment = WebSocialComment(
        user_id=user.id,
        target_type="planting",
        target_id=planting_id,
        body=body,
        status="published",
        created_at=datetime.now(timezone.utc),
    )
    session.add(comment)
    await session.commit()
    await session.refresh(comment)
    counts = await _social_counts(session, planting_id)
    return {
        "comment": {
            "id": f"web:{comment.id}",
            "author": user.display_name,
            "body": comment.body,
            "created_at": aware_utc(comment.created_at),
            "source": "web",
        },
        **counts,
    }


@router.post("/public/plantings/{planting_id}/gift")
async def web_planting_gift(
    planting_id: str,
    payload: WebGiftIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _require_planting(session, planting_id)
    cost = GIFT_COSTS[payload.gift_code]

    telegram_user = (
        await session.execute(
            select(TelegramUser).where(TelegramUser.marketplace_user_id == user.id)
        )
    ).scalar_one_or_none()
    if telegram_user is None:
        raise HTTPException(
            status_code=409,
            detail="KISA wallet is not linked to this website account",
        )

    wallet = (
        await session.execute(
            select(WalletAccount)
            .where(WalletAccount.user_id == telegram_user.id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if wallet is None:
        raise HTTPException(status_code=409, detail="KISA wallet is not available")
    if wallet.balance < cost:
        raise HTTPException(
            status_code=409,
            detail=f"Not enough KISA. Balance: {wallet.balance}",
        )

    wallet.balance -= cost
    session.add(
        SocialGift(
            user_id=telegram_user.id,
            target_type="planting",
            target_id=planting_id,
            gift_code=payload.gift_code,
            token_cost=cost,
            created_at=datetime.now(timezone.utc),
        )
    )
    session.add(
        WalletTransaction(
            user_id=telegram_user.id,
            amount=-cost,
            balance_after=wallet.balance,
            kind="plant_gift",
            reference_type="planting",
            reference_id=planting_id,
            details={"gift": payload.gift_code, "source": "web"},
            created_at=datetime.now(timezone.utc),
        )
    )
    await session.commit()
    counts = await _social_counts(session, planting_id)
    return {**counts, "balance": wallet.balance, "cost": cost}


@router.get("/public/plants/{plant_id}/image", response_class=FileResponse)
async def public_plant_image(
    plant_id: str,
    session: AsyncSession = Depends(get_session),
):
    plant = await session.get(Plant, plant_id)
    if plant is None or not plant.active:
        raise HTTPException(status_code=404, detail="Plant image not found")

    resolved = _public_plant_image_path(plant)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Plant image not found")

    path, media_type = resolved
    return FileResponse(
        path,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.post("/edge/racks/{rack_id}/photo", status_code=201)
async def upload_rack_photo(
    rack_id: int,
    captured_at: datetime = Form(),
    photo: UploadFile = File(),
    device: Device = Depends(authenticate_device),
    session: AsyncSession = Depends(get_session),
):
    if rack_id < 1 or rack_id > max(device.racks_count, 1):
        raise HTTPException(status_code=404, detail="Rack not found")
    if photo.content_type not in ("image/jpeg", "image/jpg"):
        raise HTTPException(status_code=415, detail="Only JPEG photos are accepted")
    settings = get_settings()
    content = await photo.read(settings.photo_max_bytes + 1)
    await photo.close()
    if len(content) > settings.photo_max_bytes:
        raise HTTPException(status_code=413, detail="Photo is too large")
    if len(content) < 4 or not content.startswith(b"\xff\xd8\xff"):
        raise HTTPException(status_code=422, detail="Invalid JPEG photo")
    captured_at = aware_utc(captured_at)
    if captured_at is None:
        raise HTTPException(status_code=422, detail="captured_at is required")

    stored = await asyncio.to_thread(
        store_rack_photo,
        photo_dir=settings.photo_dir,
        device_id=device.id,
        rack_id=rack_id,
        captured_at=captured_at,
        content=content,
    )

    now = datetime.now(timezone.utc)
    record = (
        await session.execute(
            select(RackPhoto).where(
                RackPhoto.device_id == device.id,
                RackPhoto.rack_id == rack_id,
            )
        )
    ).scalar_one_or_none()
    if record is None:
        record = RackPhoto(
            device_id=device.id,
            rack_id=rack_id,
            file_path=str(stored.latest_path),
            size_bytes=len(content),
            captured_at=captured_at,
            updated_at=now,
        )
        session.add(record)
    else:
        record.file_path = str(stored.latest_path)
        record.content_type = "image/jpeg"
        record.size_bytes = len(content)
        record.captured_at = captured_at
        record.updated_at = now
    await session.commit()
    return {"accepted": True, "rack_id": rack_id, "captured_at": captured_at}


@router.get("/public/farms/{farm_slug}/racks/{rack_id}/photo", response_class=FileResponse)
async def public_rack_photo(
    farm_slug: str,
    rack_id: int,
    session: AsyncSession = Depends(get_session),
):
    row = (
        await session.execute(
            select(RackPhoto)
            .join(Device, Device.id == RackPhoto.device_id)
            .join(Farm, Farm.id == Device.farm_id)
            .where(
                Farm.slug == farm_slug,
                Farm.is_public.is_(True),
                Device.is_active.is_(True),
                RackPhoto.rack_id == rack_id,
            )
            .order_by(Device.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None or not Path(row.file_path).is_file():
        raise HTTPException(status_code=404, detail="Rack photo not found")
    return FileResponse(
        row.file_path,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-store",
            "X-Captured-At": aware_utc(row.captured_at).isoformat(),
        },
    )


async def account_out(session: AsyncSession, user: User) -> AccountOut:
    await process_waitlist(session)
    await session.commit()
    allocations = (
        await session.execute(
            select(Allocation).where(Allocation.user_id == user.id).order_by(Allocation.created_at.desc())
        )
    ).scalars().all()
    reservations = (
        await session.execute(
            select(ReservationRequest)
            .where(ReservationRequest.user_id == user.id)
            .order_by(ReservationRequest.created_at.desc())
        )
    ).scalars().all()
    offers = (
        await session.execute(
            select(Offer).where(Offer.user_id == user.id).order_by(Offer.created_at.desc())
        )
    ).scalars().all()
    notifications = (
        await session.execute(
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc())
            .limit(100)
        )
    ).scalars().all()
    return AccountOut(
        user=user_out(user),
        allocations=[allocation_out(item) for item in allocations],
        reservations=[reservation_out(item) for item in reservations],
        offers=[offer_out(item) for item in offers],
        notifications=[
            NotificationOut(
                id=item.id,
                kind=item.kind,
                payload=item.payload,
                read_at=aware_utc(item.read_at),
                created_at=aware_utc(item.created_at),
            )
            for item in notifications
        ],
    )


@router.get("/account", response_model=AccountOut)
async def get_account(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await account_out(session, user)


@router.post("/shop/reservations", response_model=ReservationOut, status_code=201)
async def create_reservation(
    payload: ReservationIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    device = await session.get(Device, payload.device_id)
    if device is None or not device.is_active:
        raise HTTPException(status_code=404, detail="Device not found")

    plant = None
    if payload.plant_id:
        plant = (
            await session.execute(
                select(Plant).where(Plant.id == payload.plant_id).with_for_update()
            )
        ).scalar_one_or_none()
        if plant is None or not plant.active:
            raise HTTPException(status_code=404, detail="Active plant not found")

    duplicate = (
        await session.execute(
            select(ReservationRequest).where(
                ReservationRequest.user_id == user.id,
                ReservationRequest.device_id == payload.device_id,
                ReservationRequest.resource_type == payload.resource_type,
                ReservationRequest.rack_id == payload.rack_id,
                ReservationRequest.slot_number == payload.slot_number,
                ReservationRequest.status.in_(("waiting", "offered")),
            )
        )
    ).scalar_one_or_none()
    if duplicate:
        raise HTTPException(status_code=409, detail="Matching reservation already exists")

    if plant is not None:
        required = 6 if payload.resource_type == "rack" else 1
        try:
            await require_seed_available(
                session,
                plant.id,
                required_plantings=required,
            )
        except SeedUnavailable as exc:
            raise HTTPException(status_code=409, detail="Seeds are not available for this plant") from exc

    now = datetime.now(timezone.utc)
    reservation = ReservationRequest(
        id=str(uuid4()),
        user_id=user.id,
        device_id=payload.device_id,
        resource_type=payload.resource_type,
        rack_id=payload.rack_id,
        slot_number=payload.slot_number,
        plant_id=payload.plant_id,
        status="waiting",
        created_at=now,
        updated_at=now,
    )
    session.add(reservation)
    await session.flush()
    await process_waitlist(session, payload.device_id)
    await session.commit()
    await session.refresh(reservation)
    return reservation_out(reservation)


@router.delete("/shop/reservations/{reservation_id}", status_code=204)
async def cancel_reservation(
    reservation_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    reservation = await session.get(ReservationRequest, reservation_id)
    if reservation is None or reservation.user_id != user.id:
        raise HTTPException(status_code=404, detail="Reservation not found")
    if reservation.status not in ("waiting", "offered"):
        raise HTTPException(status_code=409, detail="Reservation cannot be cancelled")
    reservation.status = "cancelled"
    reservation.updated_at = datetime.now(timezone.utc)
    offer = (
        await session.execute(select(Offer).where(Offer.reservation_id == reservation.id))
    ).scalar_one_or_none()
    if offer and offer.status == "pending":
        offer.status = "cancelled"
    await process_waitlist(session, reservation.device_id)
    await session.commit()


@router.post("/shop/purchases", response_model=AllocationOut, status_code=201)
async def purchase(
    payload: PurchaseIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    device = await session.get(Device, payload.device_id)
    if device is None or not device.is_active:
        raise HTTPException(status_code=404, detail="Device not found")

    offer = None
    if payload.offer_id:
        await expire_offers(session)
        offer = await session.get(Offer, payload.offer_id)
        if offer is None or offer.user_id != user.id or offer.status != "pending":
            raise HTTPException(status_code=409, detail="Offer is not available")
        if aware_utc(offer.expires_at) <= datetime.now(timezone.utc):
            raise HTTPException(status_code=409, detail="Offer has expired")
        if (
            offer.device_id != payload.device_id
            or offer.resource_type != payload.resource_type
            or offer.rack_id != payload.rack_id
            or offer.slot_number != payload.slot_number
        ):
            raise HTTPException(status_code=422, detail="Purchase does not match the offer")
        if payload.plant_id and offer.plant_id and payload.plant_id != offer.plant_id:
            raise HTTPException(status_code=422, detail="Purchase plant does not match the offer")

    selected_plant_id = payload.plant_id or (offer.plant_id if offer else None)
    plant = None
    if selected_plant_id:
        plant = (
            await session.execute(
                select(Plant).where(Plant.id == selected_plant_id).with_for_update()
            )
        ).scalar_one_or_none()
        if plant is None or not plant.active:
            raise HTTPException(status_code=404, detail="Active plant not found")

        seed_reserved_by_offer = bool(offer and offer.plant_id == selected_plant_id)
        if not seed_reserved_by_offer:
            required = 6 if payload.resource_type == "rack" else 1
            try:
                await require_seed_available(
                    session,
                    plant.id,
                    required_plantings=required,
                )
            except SeedUnavailable as exc:
                raise HTTPException(status_code=409, detail="Seeds are not available for this plant") from exc

    target_query = select(RackSlot).where(
        RackSlot.device_id == payload.device_id,
        RackSlot.rack_id == payload.rack_id,
    )
    if payload.resource_type == "slot":
        target_query = target_query.where(RackSlot.slot_number == payload.slot_number)
    locked_slots = (await session.execute(target_query.with_for_update())).scalars().all()
    if payload.resource_type == "slot" and len(locked_slots) != 1:
        raise HTTPException(status_code=404, detail="Rack slot not found")
    if payload.resource_type == "rack" and {slot.slot_number for slot in locked_slots} != set(range(1, 7)):
        raise HTTPException(status_code=409, detail="Rack does not have six available container positions")

    slots, allocations, offers = await active_inventory(session, payload.device_id)
    if offer:
        offers = [item for item in offers if item.id != offer.id]
    target = find_available_target(
        payload.resource_type,
        payload.rack_id,
        payload.slot_number,
        slots,
        allocations,
        offers,
    )
    if target != (payload.rack_id, payload.slot_number):
        raise HTTPException(status_code=409, detail="Requested resource is no longer available")

    now = datetime.now(timezone.utc)
    allocation = Allocation(
        id=str(uuid4()),
        user_id=user.id,
        device_id=payload.device_id,
        resource_type=payload.resource_type,
        rack_id=payload.rack_id,
        slot_number=payload.slot_number,
        plant_id=selected_plant_id,
        status="active",
        starts_at=now,
        created_at=now,
    )
    session.add(allocation)
    await session.flush()
    session.add(
        Order(
            id=str(uuid4()),
            user_id=user.id,
            allocation_id=allocation.id,
            status="test_paid",
            amount_minor=0,
            currency="EUR",
            created_at=now,
        )
    )
    if offer:
        offer.status = "accepted"
        reservation = await session.get(ReservationRequest, offer.reservation_id)
        if reservation:
            reservation.status = "accepted"
            reservation.updated_at = now
    session.add(
        Notification(
            id=str(uuid4()),
            user_id=user.id,
            kind="purchase_confirmed",
            payload={
                "allocation_id": allocation.id,
                "resource_type": allocation.resource_type,
                "rack_id": allocation.rack_id,
                "slot_number": allocation.slot_number,
            },
            created_at=now,
        )
    )
    await session.commit()
    return allocation_out(allocation)


@router.post("/shop/allocations/{allocation_id}/release", response_model=AllocationOut)
async def release_allocation(
    allocation_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    allocation = await session.get(Allocation, allocation_id)
    if allocation is None or allocation.user_id != user.id:
        raise HTTPException(status_code=404, detail="Allocation not found")
    if allocation.status != "active":
        raise HTTPException(status_code=409, detail="Allocation is not active")
    allocation.status = "completed"
    allocation.ends_at = datetime.now(timezone.utc)
    await process_waitlist(session, allocation.device_id)
    await session.commit()
    return allocation_out(allocation)


@router.post("/account/notifications/{notification_id}/read", status_code=204)
async def read_notification(
    notification_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    notification = await session.get(Notification, notification_id)
    if notification is None or notification.user_id != user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.read_at = datetime.now(timezone.utc)
    await session.commit()


@router.get("/edge/assignments")
async def edge_assignments(
    device: Device = Depends(authenticate_device),
    session: AsyncSession = Depends(get_session),
):
    allocations = (
        await session.execute(
            select(Allocation)
            .where(Allocation.device_id == device.id, Allocation.status == "active")
            .order_by(Allocation.rack_id, Allocation.slot_number)
        )
    ).scalars().all()
    commands = list(
        (
            await session.execute(
                select(EdgeOperatorCommand)
                .where(
                    EdgeOperatorCommand.device_id == device.id,
                    EdgeOperatorCommand.status == "pending",
                )
                .order_by(EdgeOperatorCommand.created_at, EdgeOperatorCommand.id)
                .limit(50)
            )
        ).scalars().all()
    )
    receipt = await session.get(InventorySyncReceipt, device.id)
    return {
        "inventory_sync_id": receipt.sync_id if receipt else None,
        "assignments": [
            {
                "allocation_id": item.id,
                "resource_type": item.resource_type,
                "rack_id": item.rack_id,
                "slot_number": item.slot_number,
                "plant_id": item.plant_id,
            }
            for item in allocations
        ],
        "operator_commands": [
            {
                "id": item.id,
                "action": item.action,
                "rack_id": item.rack_id,
                "slot_number": item.slot_number,
                "plant_id": item.plant_id,
                "planting_id": item.planting_id,
                "allocation_id": item.allocation_id,
            }
            for item in commands
        ],
    }


@router.post("/edge/operator-commands/{command_id}/ack")
async def acknowledge_edge_operator_command(
    command_id: str,
    payload: EdgeOperatorCommandAckIn,
    device: Device = Depends(authenticate_device),
    session: AsyncSession = Depends(get_session),
):
    command = (
        await session.execute(
            select(EdgeOperatorCommand)
            .where(
                EdgeOperatorCommand.id == command_id,
                EdgeOperatorCommand.device_id == device.id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if command is None:
        raise HTTPException(status_code=404, detail="Operator command not found")

    if command.status == "applied" and payload.status == "applied":
        return {"ok": True, "status": command.status}
    if command.status == "failed" and payload.status == "failed":
        return {"ok": True, "status": command.status}

    command.status = payload.status
    command.error = payload.error.strip()[:1000] or None
    command.applied_at = datetime.now(timezone.utc) if payload.status == "applied" else None
    await session.commit()
    return {"ok": True, "status": command.status}
