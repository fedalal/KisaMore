from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path
import asyncio
import hashlib

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth_api import user_out
from .models import (
    Allocation,
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


router = APIRouter(prefix="/api/v1", tags=["marketplace"])


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

    plants = (
        await session.execute(select(Plant).where(Plant.active.is_(True)).order_by(Plant.code))
    ).scalars().all()
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
                            planted_at=aware_utc(planting.planted_at),
                            expected_harvest_at=aware_utc(planting.expected_harvest_at),
                            status=planting.status,
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
            )
            for plant in plants
        ],
        racks=racks,
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

    device_dir = hashlib.sha256(device.id.encode("utf-8")).hexdigest()[:20]
    target_dir = Path(settings.photo_dir) / device_dir
    await asyncio.to_thread(target_dir.mkdir, parents=True, exist_ok=True)
    target = target_dir / f"rack_{rack_id}.jpg"
    temporary = target.with_suffix(".jpg.tmp")
    await asyncio.to_thread(temporary.write_bytes, content)
    await asyncio.to_thread(temporary.replace, target)

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
            file_path=str(target),
            size_bytes=len(content),
            captured_at=captured_at,
            updated_at=now,
        )
        session.add(record)
    else:
        record.file_path = str(target)
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
    if payload.plant_id and await session.get(Plant, payload.plant_id) is None:
        raise HTTPException(status_code=404, detail="Plant not found")
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
    if payload.plant_id:
        plant = await session.get(Plant, payload.plant_id)
        if plant is None or not plant.active:
            raise HTTPException(status_code=404, detail="Active plant not found")

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
        plant_id=payload.plant_id or (offer.plant_id if offer else None),
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
    return {
        "assignments": [
            {
                "allocation_id": item.id,
                "resource_type": item.resource_type,
                "rack_id": item.rack_id,
                "slot_number": item.slot_number,
                "plant_id": item.plant_id,
            }
            for item in allocations
        ]
    }
