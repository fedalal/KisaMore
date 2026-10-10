from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from .account_preferences_api import AccountPreferences
from .admin_models import AdminAuditLog
from .battle_models import BATTLE_BLOCKING_STATUSES, PlantBattle, PlantBattleAction, PlantBattleEntry
from .battle_service import battle_message, queue_telegram_text, rack_has_blocking_battle
from .marketplace_service import process_waitlist
from .models import Allocation, Device, Offer, Plant, RackSlot, User
from .security import get_admin_user, get_session
from .seed_inventory import SeedUnavailable, require_seed_available
from .config import get_settings
from .telegram.admin_models import EdgeOperatorCommand
from .telegram.models import TelegramRentalRequest, TelegramUser, WalletAccount, WalletTransaction
from .site_wallet import SiteWallet, locked_wallet, record_wallet_change


router = APIRouter(prefix="/api/v1/admin/battles", tags=["admin-battles"])


class CreateBattleIn(BaseModel):
    device_id: str = Field(min_length=1, max_length=80)
    rack_id: int = Field(ge=1, le=16)
    plant_id: str = Field(min_length=1, max_length=36)
    title: str = Field(default="Битва растений", min_length=2, max_length=180)
    start_date: date | None = None
    end_date: date | None = None
    entry_price_kisa: int = Field(default=20, ge=0, le=1_000_000)
    water_budget_ml: int = Field(default=1000, ge=0, le=100_000)
    nutrient_budget_ml: int = Field(default=100, ge=0, le=100_000)
    shade_budget_minutes: int = Field(default=480, ge=0, le=100_000)
    winner_reward_kisa: int = Field(default=20, ge=0, le=1_000_000)


class RejectActionIn(BaseModel):
    note: str = Field(default="", max_length=500)


class WinnerIn(BaseModel):
    entry_id: str = Field(min_length=1, max_length=36)


class UpdateBattleIn(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    start_date: date | None = None
    end_date: date | None = None


def _plant_name(plant: Plant) -> str:
    names = plant.names or {}
    return str(names.get("ru") or names.get("en") or next(iter(names.values()), plant.code))


async def _serialize(session: AsyncSession, battle: PlantBattle) -> dict:
    plant = await session.get(Plant, battle.plant_id)
    entries = list(
        (
            await session.execute(
                select(PlantBattleEntry)
                .where(PlantBattleEntry.battle_id == battle.id)
                .order_by(PlantBattleEntry.slot_number)
            )
        ).scalars().all()
    )
    entry_ids = [entry.id for entry in entries]
    # Only the admin endpoint fetches identifiable participant data.
    user_ids = {entry.user_id for entry in entries}
    telegram_ids = {entry.telegram_user_id for entry in entries if entry.telegram_user_id is not None}
    users = {}
    telegram = {}
    avatars = {}
    if user_ids:
        users = {
            user.id: user for user in (
                await session.execute(select(User).where(User.id.in_(user_ids)))
            ).scalars().all()
        }
        avatars = {
            pref.user_id: pref for pref in (
                await session.execute(
                    select(AccountPreferences).where(AccountPreferences.user_id.in_(user_ids))
                )
            ).scalars().all()
        }
    if telegram_ids or user_ids:
        telegram_rows = (
            await session.execute(
                select(TelegramUser).where(or_(
                    TelegramUser.id.in_(telegram_ids) if telegram_ids else False,
                    TelegramUser.marketplace_user_id.in_(user_ids) if user_ids else False,
                ))
            )
        ).scalars().all()
        telegram_by_id = {item.id: item for item in telegram_rows}
        telegram_by_user = {
            item.marketplace_user_id: item
            for item in telegram_rows if item.marketplace_user_id
        }
        telegram = {
            entry.id: telegram_by_id.get(entry.telegram_user_id) or telegram_by_user.get(entry.user_id)
            for entry in entries
        }
    actions = []
    if entry_ids:
        actions = list(
            (
                await session.execute(
                    select(PlantBattleAction)
                    .where(PlantBattleAction.entry_id.in_(entry_ids))
                    .order_by(PlantBattleAction.requested_at.desc())
                )
            ).scalars().all()
        )
    action_by_entry: dict[str, list[dict]] = {}
    for item in actions:
        action_by_entry.setdefault(item.entry_id, []).append(
            {
                "id": item.id,
                "kind": item.kind,
                "amount": item.amount,
                "status": item.status,
                "note": item.note,
                "requested_at": item.requested_at,
                "completed_at": item.completed_at,
            }
        )
    return {
        "id": battle.id,
        "title": battle.title,
        "status": battle.status,
        "device_id": battle.device_id,
        "rack_id": battle.rack_id,
        "plant_id": battle.plant_id,
        "plant_name": _plant_name(plant) if plant else battle.plant_id,
        "entry_price_kisa": battle.entry_price_kisa,
        "max_entries": battle.max_entries,
        "entries_count": len([entry for entry in entries if entry.status in ("active", "finished")]),
        "water_budget_ml": battle.water_budget_ml,
        "nutrient_budget_ml": battle.nutrient_budget_ml,
        "shade_budget_minutes": battle.shade_budget_minutes,
        "winner_reward_kisa": battle.winner_reward_kisa,
        "winner_entry_id": battle.winner_entry_id,
        "start_date": battle.start_date,
        "end_date": battle.end_date,
        "created_at": battle.created_at,
        "filled_at": battle.filled_at,
        "planted_at": battle.planted_at,
        "finished_at": battle.finished_at,
        "entries": [
            {
                "id": entry.id,
                "user_id": entry.user_id,
                "telegram_user_id": entry.telegram_user_id,
                "user_name": users[entry.user_id].display_name if entry.user_id in users else None,
                "user_email": users[entry.user_id].email if entry.user_id in users else None,
                "user_avatar_url": (
                    f"/api/v1/admin/battles/participant-avatar/{entry.user_id}"
                    if entry.user_id in avatars and avatars[entry.user_id].avatar_key else None
                ),
                "telegram_username": (
                    telegram[entry.id].username if telegram.get(entry.id) else None
                ),
                "telegram_chat_id": (
                    telegram[entry.id].telegram_user_id if telegram.get(entry.id) else None
                ),
                "slot_number": entry.slot_number,
                "price_kisa": entry.price_kisa,
                "status": entry.status,
                "allocation_id": entry.allocation_id,
                "planting_id": entry.planting_id,
                "water_used_ml": entry.water_used_ml,
                "nutrient_used_ml": entry.nutrient_used_ml,
                "shade_used_minutes": entry.shade_used_minutes,
                "is_winner": entry.is_winner,
                "badge": entry.badge,
                "created_at": entry.created_at,
                "actions": action_by_entry.get(entry.id, []),
            }
            for entry in entries
        ],
    }


@router.get("")
async def list_battles(
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    battles = list(
        (
            await session.execute(
                select(PlantBattle).order_by(PlantBattle.created_at.desc()).limit(100)
            )
        ).scalars().all()
    )
    return [await _serialize(session, battle) for battle in battles]


@router.get("/participant-avatar/{user_id}", response_class=FileResponse)
async def admin_participant_avatar(
    user_id: str,
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    """Serve stored account avatars only to authenticated site admins."""
    row = await session.get(AccountPreferences, user_id)
    if row is None or not row.avatar_key:
        raise HTTPException(status_code=404, detail="Avatar not found")
    # Avatar names are generated by the upload endpoint, never trust a DB path.
    key = row.avatar_key
    filename = Path(key)
    if filename.name != key or filename.suffix.lower() not in (".jpg", ".png", ".webp"):
        raise HTTPException(status_code=404, detail="Avatar not found")
    image = Path(get_settings().photo_dir) / "avatars" / filename.name
    if not image.is_file():
        raise HTTPException(status_code=404, detail="Avatar not found")
    mime = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}[filename.suffix.lower()]
    return FileResponse(image, media_type=mime, headers={
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
    })


@router.get("/options")
async def battle_options(
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    devices = list(
        (
            await session.execute(
                select(Device).where(Device.is_active.is_(True)).order_by(Device.id)
            )
        ).scalars().all()
    )
    plants = list(
        (
            await session.execute(
                select(Plant).where(Plant.active.is_(True)).order_by(Plant.code)
            )
        ).scalars().all()
    )
    rack_options = []
    now = datetime.now(timezone.utc)
    for device in devices:
        slots = list(
            (
                await session.execute(
                    select(RackSlot)
                    .where(RackSlot.device_id == device.id)
                    .order_by(RackSlot.rack_id, RackSlot.slot_number)
                )
            ).scalars().all()
        )
        for rack_id in sorted({slot.rack_id for slot in slots}):
            rack_slots = [slot for slot in slots if slot.rack_id == rack_id]
            slot_ids = [slot.id for slot in rack_slots]
            physical_ok = (
                {slot.slot_number for slot in rack_slots} == set(range(1, 7))
                and all(slot.enabled and slot.physical_status == "available" for slot in rack_slots)
            )
            allocation_exists = (
                await session.execute(
                    select(Allocation.id).where(
                        Allocation.device_id == device.id,
                        Allocation.rack_id == rack_id,
                        Allocation.status == "active",
                    ).limit(1)
                )
            ).scalar_one_or_none() is not None
            offer_exists = (
                await session.execute(
                    select(Offer.id).where(
                        Offer.device_id == device.id,
                        Offer.rack_id == rack_id,
                        Offer.status == "pending",
                        Offer.expires_at > now,
                    ).limit(1)
                )
            ).scalar_one_or_none() is not None
            telegram_request_exists = False
            if slot_ids:
                telegram_request_exists = (
                    await session.execute(
                        select(TelegramRentalRequest.id).where(
                            TelegramRentalRequest.slot_id.in_(slot_ids),
                            TelegramRentalRequest.status.in_(("requested", "approved")),
                        ).limit(1)
                    )
                ).scalar_one_or_none() is not None
            battle_exists = await rack_has_blocking_battle(
                session,
                device_id=device.id,
                rack_id=rack_id,
            )
            rack_options.append(
                {
                    "device_id": device.id,
                    "device_name": device.name,
                    "rack_id": rack_id,
                    "available": physical_ok and not allocation_exists and not offer_exists and not telegram_request_exists and not battle_exists,
                }
            )
    return {
        "racks": rack_options,
        "plants": [
            {"id": plant.id, "code": plant.code, "name": _plant_name(plant)}
            for plant in plants
        ],
    }


@router.post("", status_code=201)
async def create_battle(
    payload: CreateBattleIn,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    device = await session.get(Device, payload.device_id)
    plant = (
        await session.execute(
            select(Plant).where(Plant.id == payload.plant_id).with_for_update()
        )
    ).scalar_one_or_none()
    if device is None or not device.is_active:
        raise HTTPException(status_code=404, detail="Device not found")
    if plant is None or not plant.active:
        raise HTTPException(status_code=404, detail="Active plant not found")

    rack_slots = list(
        (
            await session.execute(
                select(RackSlot)
                .where(
                    RackSlot.device_id == payload.device_id,
                    RackSlot.rack_id == payload.rack_id,
                )
                .with_for_update()
            )
        ).scalars().all()
    )
    if {slot.slot_number for slot in rack_slots} != set(range(1, 7)):
        raise HTTPException(status_code=409, detail="Rack must contain six containers")
    if not all(slot.enabled and slot.physical_status == "available" for slot in rack_slots):
        raise HTTPException(status_code=409, detail="All six containers must be physically available")
    if await rack_has_blocking_battle(session, device_id=payload.device_id, rack_id=payload.rack_id):
        raise HTTPException(status_code=409, detail="This rack is already reserved for another battle")

    now = datetime.now(timezone.utc)
    allocation_exists = (
        await session.execute(
            select(Allocation.id).where(
                Allocation.device_id == payload.device_id,
                Allocation.rack_id == payload.rack_id,
                Allocation.status == "active",
            ).limit(1)
        )
    ).scalar_one_or_none()
    offer_exists = (
        await session.execute(
            select(Offer.id).where(
                Offer.device_id == payload.device_id,
                Offer.rack_id == payload.rack_id,
                Offer.status == "pending",
                Offer.expires_at > now,
            ).limit(1)
        )
    ).scalar_one_or_none()
    slot_ids = [slot.id for slot in rack_slots]
    request_exists = (
        await session.execute(
            select(TelegramRentalRequest.id).where(
                TelegramRentalRequest.slot_id.in_(slot_ids),
                TelegramRentalRequest.status.in_(("requested", "approved")),
            ).limit(1)
        )
    ).scalar_one_or_none()
    if allocation_exists or offer_exists or request_exists:
        raise HTTPException(status_code=409, detail="Rack is already reserved or rented")

    try:
        await require_seed_available(session, plant.id, required_plantings=6)
    except SeedUnavailable as exc:
        raise HTTPException(status_code=409, detail="Not enough seeds for six battle containers") from exc

    if payload.start_date and payload.end_date and payload.end_date < payload.start_date:
        raise HTTPException(status_code=422, detail="End date cannot be earlier than start date")

    battle = PlantBattle(
        id=str(uuid4()),
        device_id=payload.device_id,
        rack_id=payload.rack_id,
        plant_id=payload.plant_id,
        title=payload.title.strip(),
        start_date=payload.start_date,
        end_date=payload.end_date,
        status="open",
        entry_price_kisa=payload.entry_price_kisa,
        max_entries=6,
        water_budget_ml=payload.water_budget_ml,
        nutrient_budget_ml=payload.nutrient_budget_ml,
        shade_budget_minutes=payload.shade_budget_minutes,
        winner_reward_kisa=payload.winner_reward_kisa,
        created_by_user_id=admin.id,
        created_at=now,
        updated_at=now,
    )
    session.add(battle)
    session.add(
        AdminAuditLog(
            admin_user_id=admin.id,
            action="create_plant_battle",
            target_type="plant_battle",
            target_id=battle.id,
            details={
                "device_id": battle.device_id,
                "rack_id": battle.rack_id,
                "plant_id": battle.plant_id,
                "entry_price_kisa": battle.entry_price_kisa,
                "title": battle.title,
                "start_date": battle.start_date.isoformat() if battle.start_date else None,
                "end_date": battle.end_date.isoformat() if battle.end_date else None,
            },
        )
    )
    await session.commit()
    return await _serialize(session, battle)


@router.patch("/{battle_id}")
async def update_battle(
    battle_id: str,
    payload: UpdateBattleIn,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    battle = (
        await session.execute(
            select(PlantBattle).where(PlantBattle.id == battle_id).with_for_update()
        )
    ).scalar_one_or_none()
    if battle is None:
        raise HTTPException(status_code=404, detail="Battle not found")
    if payload.start_date and payload.end_date and payload.end_date < payload.start_date:
        raise HTTPException(status_code=422, detail="End date cannot be earlier than start date")

    old = {
        "title": battle.title,
        "start_date": battle.start_date.isoformat() if battle.start_date else None,
        "end_date": battle.end_date.isoformat() if battle.end_date else None,
    }
    battle.title = payload.title.strip()
    battle.start_date = payload.start_date
    battle.end_date = payload.end_date
    battle.updated_at = datetime.now(timezone.utc)

    session.add(
        AdminAuditLog(
            admin_user_id=admin.id,
            action="update_plant_battle",
            target_type="plant_battle",
            target_id=battle.id,
            details={
                "before": old,
                "after": {
                    "title": battle.title,
                    "start_date": battle.start_date.isoformat() if battle.start_date else None,
                    "end_date": battle.end_date.isoformat() if battle.end_date else None,
                },
            },
        )
    )
    await session.commit()
    return await _serialize(session, battle)


@router.post("/{battle_id}/start")
async def start_battle(
    battle_id: str,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    battle = (
        await session.execute(
            select(PlantBattle).where(PlantBattle.id == battle_id).with_for_update()
        )
    ).scalar_one_or_none()
    if battle is None:
        raise HTTPException(status_code=404, detail="Battle not found")
    if battle.status == "planting":
        return await _serialize(session, battle)
    if battle.status != "ready_to_plant":
        raise HTTPException(status_code=409, detail="Battle needs all six participants before planting")

    entries = list(
        (
            await session.execute(
                select(PlantBattleEntry)
                .where(
                    PlantBattleEntry.battle_id == battle.id,
                    PlantBattleEntry.status == "active",
                )
                .order_by(PlantBattleEntry.slot_number)
                .with_for_update()
            )
        ).scalars().all()
    )
    if len(entries) != battle.max_entries:
        raise HTTPException(status_code=409, detail="Battle does not contain six active entries")

    now = datetime.now(timezone.utc)
    for entry in entries:
        allocation = Allocation(
            id=str(uuid4()),
            user_id=entry.user_id,
            device_id=battle.device_id,
            resource_type="slot",
            rack_id=battle.rack_id,
            slot_number=entry.slot_number,
            plant_id=battle.plant_id,
            status="active",
            starts_at=now,
            created_at=now,
        )
        session.add(allocation)
        await session.flush()
        entry.allocation_id = allocation.id
        planting_id = str(uuid4())
        entry.planting_id = planting_id
        session.add(
            EdgeOperatorCommand(
                id=str(uuid4()),
                device_id=battle.device_id,
                action="plant",
                rack_id=battle.rack_id,
                slot_number=entry.slot_number,
                plant_id=battle.plant_id,
                planting_id=planting_id,
                allocation_id=allocation.id,
                status="pending",
                created_at=now,
            )
        )

    battle.status = "planting"
    battle.updated_at = now
    session.add(
        AdminAuditLog(
            admin_user_id=admin.id,
            action="start_plant_battle",
            target_type="plant_battle",
            target_id=battle.id,
            details={"rack_id": battle.rack_id, "entries": len(entries)},
        )
    )
    await session.commit()
    return await _serialize(session, battle)


@router.post("/{battle_id}/cancel")
async def cancel_battle(
    battle_id: str,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    battle = (
        await session.execute(
            select(PlantBattle).where(PlantBattle.id == battle_id).with_for_update()
        )
    ).scalar_one_or_none()
    if battle is None:
        raise HTTPException(status_code=404, detail="Battle not found")
    if battle.status == "cancelled":
        return await _serialize(session, battle)
    if battle.status not in ("open", "ready_to_plant"):
        raise HTTPException(status_code=409, detail="A planted battle cannot be cancelled here")

    entries = list(
        (
            await session.execute(
                select(PlantBattleEntry)
                .where(
                    PlantBattleEntry.battle_id == battle.id,
                    PlantBattleEntry.status == "active",
                )
                .with_for_update()
            )
        ).scalars().all()
    )
    now = datetime.now(timezone.utc)
    for entry in entries:
        await session.execute(select(User).where(User.id == entry.user_id).with_for_update())
        wallet, tg_for_wallet = await locked_wallet(session, entry.user_id)
        wallet.balance += entry.price_kisa
        record_wallet_change(
            session, user_id=entry.user_id, telegram_user=tg_for_wallet,
            wallet=wallet, amount=entry.price_kisa, kind="battle_refund",
            reference_type="plant_battle_entry", reference_id=entry.id,
            details={"battle_id": battle.id, "reason": "battle_cancelled"},
        )
        entry.status = "refunded"
        tg = await session.get(TelegramUser, entry.telegram_user_id) if entry.telegram_user_id else None
        if tg is not None and tg.is_active:
            await queue_telegram_text(
                session,
                telegram_user_id=tg.telegram_user_id,
                event_key=f"battle_cancelled:{battle.id}:{entry.id}",
                text=battle_message(
                    tg,
                    "cancelled",
                    slot=entry.slot_number,
                    refund=entry.price_kisa,
                ),
            )

    battle.status = "cancelled"
    battle.updated_at = now
    await process_waitlist(session, battle.device_id)
    session.add(
        AdminAuditLog(
            admin_user_id=admin.id,
            action="cancel_plant_battle",
            target_type="plant_battle",
            target_id=battle.id,
            details={"refunded_entries": len(entries)},
        )
    )
    await session.commit()
    return await _serialize(session, battle)


@router.post("/actions/{action_id}/complete")
async def complete_action(
    action_id: str,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    action = (
        await session.execute(
            select(PlantBattleAction)
            .where(PlantBattleAction.id == action_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if action is None:
        raise HTTPException(status_code=404, detail="Battle action not found")
    if action.status == "completed":
        return {"ok": True, "status": "completed"}
    if action.status != "pending":
        raise HTTPException(status_code=409, detail="Only pending actions can be completed")
    entry = await session.get(PlantBattleEntry, action.entry_id)
    battle = await session.get(PlantBattle, entry.battle_id) if entry else None
    if entry is None or battle is None:
        raise HTTPException(status_code=409, detail="Battle action data is incomplete")

    now = datetime.now(timezone.utc)
    action.status = "completed"
    action.completed_at = now
    action.completed_by_user_id = admin.id
    tg = await session.get(TelegramUser, entry.telegram_user_id) if entry.telegram_user_id else None
    if tg is not None and tg.is_active:
        lang_ru = (tg.language_code or "").lower().startswith("ru")
        labels = (
            {"water": "полив", "nutrient": "питательный раствор", "shade": "закрытие от света"}
            if lang_ru
            else {"water": "watering", "nutrient": "nutrient solution", "shade": "shade"}
        )
        unit = "мин" if lang_ru and action.kind == "shade" else "ml" if not lang_ru and action.kind != "shade" else "min" if action.kind == "shade" else "мл"
        await queue_telegram_text(
            session,
            telegram_user_id=tg.telegram_user_id,
            event_key=f"battle_action_done:{action.id}",
            text=battle_message(
                tg,
                "action_done",
                rack=battle.rack_id,
                slot=entry.slot_number,
                action=labels.get(action.kind, action.kind),
                amount=action.amount,
                unit=unit,
            ),
        )
    await session.commit()
    return {"ok": True, "status": action.status}


@router.post("/actions/{action_id}/reject")
async def reject_action(
    action_id: str,
    payload: RejectActionIn,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    action = (
        await session.execute(
            select(PlantBattleAction)
            .where(PlantBattleAction.id == action_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if action is None:
        raise HTTPException(status_code=404, detail="Battle action not found")
    if action.status == "rejected":
        return {"ok": True, "status": "rejected"}
    if action.status != "pending":
        raise HTTPException(status_code=409, detail="Only pending actions can be rejected")

    entry = (
        await session.execute(
            select(PlantBattleEntry)
            .where(PlantBattleEntry.id == action.entry_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=409, detail="Battle entry not found")
    field = {
        "water": "water_used_ml",
        "nutrient": "nutrient_used_ml",
        "shade": "shade_used_minutes",
    }[action.kind]
    setattr(entry, field, max(0, int(getattr(entry, field) or 0) - action.amount))
    action.status = "rejected"
    action.note = payload.note.strip() or "Rejected by administrator"
    action.completed_at = datetime.now(timezone.utc)
    action.completed_by_user_id = admin.id
    await session.commit()
    return {"ok": True, "status": action.status}


@router.post("/{battle_id}/winner")
async def choose_winner(
    battle_id: str,
    payload: WinnerIn,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    battle = (
        await session.execute(
            select(PlantBattle).where(PlantBattle.id == battle_id).with_for_update()
        )
    ).scalar_one_or_none()
    if battle is None:
        raise HTTPException(status_code=404, detail="Battle not found")
    if battle.status == "finished":
        return await _serialize(session, battle)
    if battle.status != "judging":
        raise HTTPException(status_code=409, detail="Winner can be selected after all six plants are harvested")

    entry = (
        await session.execute(
            select(PlantBattleEntry)
            .where(
                PlantBattleEntry.id == payload.entry_id,
                PlantBattleEntry.battle_id == battle.id,
                PlantBattleEntry.status == "active",
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=404, detail="Battle entry not found")

    await session.execute(select(User).where(User.id == entry.user_id).with_for_update())
    wallet, tg_for_wallet = await locked_wallet(session, entry.user_id)
    reward = max(0, battle.winner_reward_kisa)
    if reward:
        wallet.balance += reward
        record_wallet_change(
            session, user_id=entry.user_id, telegram_user=tg_for_wallet,
            wallet=wallet, amount=reward, kind="battle_prize",
            reference_type="plant_battle", reference_id=battle.id,
            details={"entry_id": entry.id, "badge": "Лучший садовод"},
        )

    now = datetime.now(timezone.utc)
    entry.is_winner = True
    entry.badge = "Лучший садовод"
    battle.winner_entry_id = entry.id
    battle.status = "finished"
    battle.finished_at = now
    battle.updated_at = now

    entries = list(
        (
            await session.execute(
                select(PlantBattleEntry).where(PlantBattleEntry.battle_id == battle.id)
            )
        ).scalars().all()
    )
    notified: set[int] = set()
    for participant in entries:
        if participant.status == "active":
            participant.status = "finished"
        if participant.telegram_user_id in notified:
            continue
        notified.add(participant.telegram_user_id)
        tg = await session.get(TelegramUser, participant.telegram_user_id) if participant.telegram_user_id else None
        if tg is None or not tg.is_active:
            continue
        certificate = (
            f"{get_settings().public_base_url.rstrip('/')}/api/v1/battle-certificate/{participant.id}"
        )
        if participant.telegram_user_id == entry.telegram_user_id:
            text = battle_message(
                tg,
                "winner",
                reward=reward,
                certificate=certificate,
            )
        else:
            text = battle_message(
                tg,
                "finished",
                winner_slot=entry.slot_number,
                certificate=certificate,
            )
        await queue_telegram_text(
            session,
            telegram_user_id=tg.telegram_user_id,
            event_key=f"battle_finished:{battle.id}:{tg.id}",
            text=text,
        )

    await process_waitlist(session, battle.device_id)
    session.add(
        AdminAuditLog(
            admin_user_id=admin.id,
            action="finish_plant_battle",
            target_type="plant_battle",
            target_id=battle.id,
            details={
                "winner_entry_id": entry.id,
                "winner_slot": entry.slot_number,
                "reward_kisa": reward,
            },
        )
    )
    await session.commit()
    return await _serialize(session, battle)
