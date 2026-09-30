from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .battle_models import PlantBattle, PlantBattleAction, PlantBattleEntry
from .battle_service import queue_admin_text, queue_telegram_text
from .models import Farm, Plant, User
from .security import get_current_user, get_session
from .telegram.models import TelegramUser, WalletAccount, WalletTransaction


router = APIRouter(prefix="/api/v1", tags=["plant-battles"])


class JoinBattleIn(BaseModel):
    quantity: int = Field(default=1, ge=1, le=6)


class BattleActionIn(BaseModel):
    kind: str = Field(pattern="^(water|nutrient|shade)$")
    amount: int = Field(ge=1, le=5000)


def _plant_name(plant: Plant, lang: str = "en") -> str:
    names = plant.names or {}
    return str(names.get(lang) or names.get("en") or names.get("ru") or next(iter(names.values()), plant.code))


async def _battle_payload(session: AsyncSession, battle: PlantBattle, current_user_id: str | None = None) -> dict:
    plant = await session.get(Plant, battle.plant_id)
    farm_slug = (
        await session.execute(
            select(Farm.slug)
            .join_from(Farm, __import__("cloud.app.models", fromlist=["Device"]).Device, __import__("cloud.app.models", fromlist=["Device"]).Device.farm_id == Farm.id)
            .where(__import__("cloud.app.models", fromlist=["Device"]).Device.id == battle.device_id)
            .limit(1)
        )
    ).scalar_one_or_none() or "demo-farm"
    entries = list(
        (
            await session.execute(
                select(PlantBattleEntry)
                .where(PlantBattleEntry.battle_id == battle.id)
                .order_by(PlantBattleEntry.slot_number)
            )
        ).scalars().all()
    )
    entry_rows = []
    for entry in entries:
        entry_rows.append(
            {
                "id": entry.id,
                "slot_number": entry.slot_number,
                "status": entry.status,
                "is_mine": current_user_id is not None and entry.user_id == current_user_id,
                "water_used_ml": entry.water_used_ml,
                "water_budget_ml": battle.water_budget_ml,
                "nutrient_used_ml": entry.nutrient_used_ml,
                "nutrient_budget_ml": battle.nutrient_budget_ml,
                "shade_used_minutes": entry.shade_used_minutes,
                "shade_budget_minutes": battle.shade_budget_minutes,
                "is_winner": entry.is_winner,
                "badge": entry.badge,
                "planting_id": entry.planting_id,
                "timelapse_24h_url": f"/api/v1/public/farms/{farm_slug}/racks/{battle.rack_id}/slots/{entry.slot_number}/timelapse/24h",
                "timelapse_3d_url": f"/api/v1/public/farms/{farm_slug}/racks/{battle.rack_id}/slots/{entry.slot_number}/timelapse/3d",
                "timelapse_full_url": (
                    f"/api/v1/public/plantings/{entry.planting_id}/timelapse/full"
                    if entry.planting_id
                    else None
                ),
            }
        )
    return {
        "id": battle.id,
        "title": battle.title,
        "status": battle.status,
        "device_id": battle.device_id,
        "rack_id": battle.rack_id,
        "plant_id": battle.plant_id,
        "plant_name": _plant_name(plant) if plant else "Plant",
        "plant_names": plant.names if plant else {},
        "entry_price_kisa": battle.entry_price_kisa,
        "max_entries": battle.max_entries,
        "entries_count": len([item for item in entries if item.status == "active"]),
        "remaining_entries": max(0, battle.max_entries - len([item for item in entries if item.status == "active"])),
        "water_budget_ml": battle.water_budget_ml,
        "nutrient_budget_ml": battle.nutrient_budget_ml,
        "shade_budget_minutes": battle.shade_budget_minutes,
        "winner_reward_kisa": battle.winner_reward_kisa,
        "winner_entry_id": battle.winner_entry_id,
        "created_at": battle.created_at,
        "filled_at": battle.filled_at,
        "planted_at": battle.planted_at,
        "finished_at": battle.finished_at,
        "entries": entry_rows,
    }


@router.get("/public/battles")
async def list_public_battles(
    session: AsyncSession = Depends(get_session),
):
    rows = list(
        (
            await session.execute(
                select(PlantBattle)
                .where(PlantBattle.status != "cancelled")
                .order_by(PlantBattle.created_at.desc())
                .limit(30)
            )
        ).scalars().all()
    )
    return [await _battle_payload(session, battle) for battle in rows]


@router.get("/battles/me")
async def my_battles(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    battle_ids = list(
        (
            await session.execute(
                select(PlantBattleEntry.battle_id)
                .where(
                    PlantBattleEntry.user_id == user.id,
                    PlantBattleEntry.status.in_(("active", "finished")),
                )
                .distinct()
            )
        ).scalars().all()
    )
    if not battle_ids:
        return []
    rows = list(
        (
            await session.execute(
                select(PlantBattle)
                .where(PlantBattle.id.in_(battle_ids))
                .order_by(PlantBattle.created_at.desc())
            )
        ).scalars().all()
    )
    return [await _battle_payload(session, battle, user.id) for battle in rows]


@router.post("/battles/{battle_id}/join", status_code=201)
async def join_battle(
    battle_id: str,
    payload: JoinBattleIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    battle = (
        await session.execute(
            select(PlantBattle).where(PlantBattle.id == battle_id).with_for_update()
        )
    ).scalar_one_or_none()
    if battle is None or battle.status == "cancelled":
        raise HTTPException(status_code=404, detail="Battle not found")
    if battle.status != "open":
        raise HTTPException(status_code=409, detail="Battle is no longer accepting entries")

    telegram_user = (
        await session.execute(
            select(TelegramUser)
            .where(TelegramUser.marketplace_user_id == user.id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if telegram_user is None:
        raise HTTPException(
            status_code=409,
            detail="Link your Telegram account to use Kisa and join the battle",
        )
    wallet = (
        await session.execute(
            select(WalletAccount)
            .where(WalletAccount.user_id == telegram_user.id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if wallet is None:
        raise HTTPException(status_code=409, detail="Kisa wallet is not available")

    active_entries = list(
        (
            await session.execute(
                select(PlantBattleEntry)
                .where(
                    PlantBattleEntry.battle_id == battle.id,
                    PlantBattleEntry.status == "active",
                )
                .order_by(PlantBattleEntry.slot_number)
            )
        ).scalars().all()
    )
    remaining = battle.max_entries - len(active_entries)
    if payload.quantity > remaining:
        raise HTTPException(status_code=409, detail=f"Only {remaining} battle places remain")

    total = battle.entry_price_kisa * payload.quantity
    if wallet.balance < total:
        raise HTTPException(
            status_code=409,
            detail=f"Not enough Kisa. Price: {total}. Balance: {wallet.balance}",
        )

    occupied = {entry.slot_number for entry in active_entries}
    free_slots = [slot for slot in range(1, battle.max_entries + 1) if slot not in occupied]
    now = datetime.now(timezone.utc)
    created = []
    for slot_number in free_slots[: payload.quantity]:
        entry = PlantBattleEntry(
            id=str(uuid4()),
            battle_id=battle.id,
            user_id=user.id,
            telegram_user_id=telegram_user.id,
            slot_number=slot_number,
            price_kisa=battle.entry_price_kisa,
            status="active",
            created_at=now,
        )
        session.add(entry)
        created.append(entry)

    wallet.balance -= total
    session.add(
        WalletTransaction(
            user_id=telegram_user.id,
            amount=-total,
            balance_after=wallet.balance,
            kind="battle_entry",
            reference_type="plant_battle",
            reference_id=battle.id,
            details={
                "quantity": payload.quantity,
                "price_each": battle.entry_price_kisa,
                "slots": [entry.slot_number for entry in created],
            },
            created_at=now,
        )
    )

    if len(active_entries) + len(created) == battle.max_entries:
        battle.status = "ready_to_plant"
        battle.filled_at = now
        battle.updated_at = now
        all_entries = active_entries + created
        notified: set[int] = set()
        for entry in all_entries:
            if entry.telegram_user_id in notified:
                continue
            notified.add(entry.telegram_user_id)
            tg = await session.get(TelegramUser, entry.telegram_user_id)
            if tg is not None and tg.is_active:
                await queue_telegram_text(
                    session,
                    telegram_user_id=tg.telegram_user_id,
                    event_key=f"battle_full:{battle.id}:{tg.id}",
                    text=(
                        "🏁 <b>Набор в «Битву растений» завершён!</b>\n\n"
                        f"Полка {battle.rack_id}: все {battle.max_entries} мест заняты. "
                        "Администратор получил задачу посадить растения из одной партии семян. "
                        "После посадки вы получите уведомление."
                    ),
                )
        await queue_admin_text(
            session,
            event_prefix=f"battle_ready:{battle.id}",
            text=(
                "🏁 <b>Битва растений набрана полностью.</b>\n\n"
                f"Полка {battle.rack_id}, мест: {battle.max_entries}. "
                "Откройте раздел «Битвы растений» в админке и запустите посадку."
            ),
        )

    await session.commit()
    return {
        "ok": True,
        "battle_id": battle.id,
        "entry_ids": [entry.id for entry in created],
        "slots": [entry.slot_number for entry in created],
        "charged_kisa": total,
        "balance": wallet.balance,
        "status": battle.status,
    }


@router.post("/battles/{battle_id}/entries/{entry_id}/actions", status_code=201)
async def request_battle_action(
    battle_id: str,
    entry_id: str,
    payload: BattleActionIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    battle = (
        await session.execute(
            select(PlantBattle).where(PlantBattle.id == battle_id).with_for_update()
        )
    ).scalar_one_or_none()
    entry = (
        await session.execute(
            select(PlantBattleEntry).where(PlantBattleEntry.id == entry_id).with_for_update()
        )
    ).scalar_one_or_none()
    if battle is None or entry is None or entry.battle_id != battle.id:
        raise HTTPException(status_code=404, detail="Battle entry not found")
    if entry.user_id != user.id:
        raise HTTPException(status_code=403, detail="This is not your battle entry")
    if battle.status != "growing":
        raise HTTPException(status_code=409, detail="Battle controls are available only while plants are growing")

    fields = {
        "water": ("water_used_ml", battle.water_budget_ml, "ml"),
        "nutrient": ("nutrient_used_ml", battle.nutrient_budget_ml, "ml"),
        "shade": ("shade_used_minutes", battle.shade_budget_minutes, "min"),
    }
    field, budget, unit = fields[payload.kind]
    used = int(getattr(entry, field) or 0)
    if used + payload.amount > budget:
        raise HTTPException(
            status_code=409,
            detail=f"Resource limit exceeded. Remaining: {max(0, budget - used)} {unit}",
        )

    setattr(entry, field, used + payload.amount)
    now = datetime.now(timezone.utc)
    action = PlantBattleAction(
        id=str(uuid4()),
        entry_id=entry.id,
        kind=payload.kind,
        amount=payload.amount,
        status="pending",
        requested_at=now,
    )
    session.add(action)
    labels = {"water": "вода", "nutrient": "питательный раствор", "shade": "закрытие от света"}
    await queue_admin_text(
        session,
        event_prefix=f"battle_action:{action.id}",
        text=(
            "🎮 <b>Новое действие в Битве растений</b>\n\n"
            f"Полка {battle.rack_id} · контейнер {entry.slot_number}\n"
            f"Ресурс: <b>{labels[payload.kind]}</b>\n"
            f"Количество: <b>{payload.amount} {unit}</b>\n\n"
            "Выполните действие вручную и отметьте его в админке."
        ),
    )
    await session.commit()
    return {
        "ok": True,
        "action_id": action.id,
        "kind": action.kind,
        "amount": action.amount,
        "status": action.status,
        "remaining": budget - int(getattr(entry, field) or 0),
    }
