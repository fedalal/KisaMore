from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import io
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field
import qrcode
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .battle_models import PlantBattle, PlantBattleAction, PlantBattleEntry, PlantBattlePrediction
from .battle_service import battle_message, queue_admin_text, queue_telegram_text
from .account_preferences_api import AccountAchievement
from .models import Device, Farm, Plant, RackCameraPhoto, User
from .security import get_current_user, get_session
from .config import get_settings
from .telegram_link import create_telegram_link_token, linked_telegram_user
from .telegram.models import TelegramUser, WalletAccount, WalletTransaction


router = APIRouter(prefix="/api/v1", tags=["plant-battles"])


class JoinBattleIn(BaseModel):
    # Kept in the payload for backward compatibility with existing clients,
    # but a user may own only one plant in a battle.
    quantity: int = Field(default=1, ge=1, le=1)


class BattleActionIn(BaseModel):
    kind: str = Field(pattern="^(water|nutrient|shade)$")
    amount: int = Field(ge=1, le=5000)


class BattlePredictionIn(BaseModel):
    entry_id: str = Field(min_length=1, max_length=36)


def _plant_name(plant: Plant, lang: str = "en") -> str:
    names = plant.names or {}
    return str(names.get(lang) or names.get("en") or names.get("ru") or next(iter(names.values()), plant.code))


async def _battle_payload(session: AsyncSession, battle: PlantBattle, current_user_id: str | None = None) -> dict:
    plant = await session.get(Plant, battle.plant_id)
    farm_slug = (
        await session.execute(
            select(Farm.slug)
            .join(Device, Device.farm_id == Farm.id)
            .where(Device.id == battle.device_id)
            .limit(1)
        )
    ).scalar_one_or_none() or "demo-farm"
    camera_rows = list(
        (
            await session.execute(
                select(RackCameraPhoto)
                .where(
                    RackCameraPhoto.device_id == battle.device_id,
                    RackCameraPhoto.rack_id == battle.rack_id,
                )
                .order_by(
                    RackCameraPhoto.is_primary.desc(),
                    RackCameraPhoto.camera_id,
                )
            )
        ).scalars().all()
    )
    camera_views = [
        {
            "camera_id": item.camera_id,
            "primary": bool(item.is_primary),
            "captured_at": item.captured_at,
            "photo_url": (
                f"/api/v1/public/farms/{farm_slug}/racks/{battle.rack_id}/"
                f"cameras/{item.camera_id}/photo"
            ),
            "timelapse_urls": {
                period: (
                    f"/api/v1/public/battles/{battle.id}/cameras/"
                    f"{item.camera_id}/timelapse/{period}"
                )
                for period in ("24h", "3d", "full")
            },
        }
        for item in camera_rows
    ]

    entries = list(
        (
            await session.execute(
                select(PlantBattleEntry)
                .where(PlantBattleEntry.battle_id == battle.id)
                .order_by(PlantBattleEntry.slot_number)
            )
        ).scalars().all()
    )
    prediction_rows = list(
        (
            await session.execute(
                select(PlantBattlePrediction)
                .where(PlantBattlePrediction.battle_id == battle.id)
            )
        ).scalars().all()
    )
    prediction_counts: dict[str, int] = {}
    my_prediction_entry_id = None
    for prediction in prediction_rows:
        prediction_counts[prediction.entry_id] = prediction_counts.get(prediction.entry_id, 0) + 1
        if current_user_id is not None and prediction.user_id == current_user_id:
            my_prediction_entry_id = prediction.entry_id

    entry_rows = []
    for entry in entries:
        is_mine = current_user_id is not None and entry.user_id == current_user_id
        resources_visible = is_mine or battle.status == "finished"
        actions_visible = is_mine or battle.status == "finished"
        actions = []
        if actions_visible:
            action_rows = list(
                (
                    await session.execute(
                        select(PlantBattleAction)
                        .where(PlantBattleAction.entry_id == entry.id)
                        .order_by(PlantBattleAction.requested_at.desc())
                        .limit(100)
                    )
                ).scalars().all()
            )
            actions = [
                {
                    "id": action.id,
                    "kind": action.kind,
                    "amount": action.amount,
                    "status": action.status,
                    "note": action.note,
                    "requested_at": action.requested_at,
                    "completed_at": action.completed_at,
                }
                for action in action_rows
            ]
        entry_rows.append(
            {
                "id": entry.id,
                "slot_number": entry.slot_number,
                "status": entry.status,
                "is_mine": is_mine,
                "resources_visible": resources_visible,
                "water_used_ml": entry.water_used_ml if resources_visible else None,
                "water_budget_ml": battle.water_budget_ml if resources_visible else None,
                "nutrient_used_ml": entry.nutrient_used_ml if resources_visible else None,
                "nutrient_budget_ml": battle.nutrient_budget_ml if resources_visible else None,
                "shade_used_minutes": entry.shade_used_minutes if resources_visible else None,
                "shade_budget_minutes": battle.shade_budget_minutes if resources_visible else None,
                "actions": actions,
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
                "certificate_url": (
                    f"/api/v1/battle-certificate/{entry.id}"
                    if battle.status == "finished"
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
        "grow_days": plant.grow_days if plant else None,
        "farm_slug": farm_slug,
        "rack_photo_url": f"/api/v1/public/farms/{farm_slug}/racks/{battle.rack_id}/photo",
        "camera_views": camera_views,
        "entry_price_kisa": battle.entry_price_kisa,
        "max_entries": battle.max_entries,
        "entries_count": len([item for item in entries if item.status in ("active", "finished")]),
        "remaining_entries": (
            max(0, battle.max_entries - len([item for item in entries if item.status == "active"]))
            if battle.status == "open"
            else 0
        ),
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
        "entries": entry_rows,
        "prediction_total": len(prediction_rows),
        "prediction_counts": prediction_counts,
        "my_prediction_entry_id": my_prediction_entry_id,
    }


async def _certificate_context(session: AsyncSession, entry_id: str):
    row = (
        await session.execute(
            select(PlantBattleEntry, PlantBattle, Plant, User)
            .join(PlantBattle, PlantBattle.id == PlantBattleEntry.battle_id)
            .join(Plant, Plant.id == PlantBattle.plant_id)
            .join(User, User.id == PlantBattleEntry.user_id)
            .where(PlantBattleEntry.id == entry_id)
            .limit(1)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Battle entry not found")
    entry, battle, plant, user = row
    if battle.status != "finished":
        raise HTTPException(status_code=409, detail="Diploma is available after the battle is finished")
    return entry, battle, plant, user


@router.get("/public/battle-entries/{entry_id}")
async def public_battle_entry(
    entry_id: str,
    session: AsyncSession = Depends(get_session),
):
    entry, battle, plant, user = await _certificate_context(session, entry_id)
    names = plant.names or {}
    return {
        "entry_id": entry.id,
        "battle_id": battle.id,
        "battle_title": battle.title,
        "participant": user.display_name,
        "plant_names": names,
        "rack_id": battle.rack_id,
        "slot_number": entry.slot_number,
        "planted_at": battle.planted_at,
        "finished_at": battle.finished_at,
        "water_used_ml": entry.water_used_ml,
        "nutrient_used_ml": entry.nutrient_used_ml,
        "shade_used_minutes": entry.shade_used_minutes,
        "is_winner": entry.is_winner,
        "badge": entry.badge,
        "certificate_url": f"/api/v1/battle-certificate/{entry.id}",
        "timelapse_full_url": (
            f"/api/v1/public/plantings/{entry.planting_id}/timelapse/full"
            if entry.planting_id
            else None
        ),
    }


@router.get("/public/battle-entries/{entry_id}/qr")
async def battle_entry_qr(
    entry_id: str,
    session: AsyncSession = Depends(get_session),
):
    entry, _battle, _plant, _user = await _certificate_context(session, entry_id)
    base = get_settings().public_base_url.rstrip("/")
    url = f"{base}/api/v1/battle-certificate/{entry.id}"
    image = qrcode.make(url)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/battle-certificate/{entry_id}", response_class=HTMLResponse, include_in_schema=False)
async def battle_certificate(
    entry_id: str,
    session: AsyncSession = Depends(get_session),
):
    entry, battle, plant, user = await _certificate_context(session, entry_id)
    lang = (user.preferred_language or "en").lower().split("-", 1)[0]
    ru = lang == "ru"
    names = plant.names or {}
    plant_name = names.get(lang) or names.get("en") or names.get("ru") or plant.code
    title = "Цифровой диплом" if ru else "Digital diploma"
    subtitle = "Битва растений KisaMore" if ru else "KisaMore Plant Battle"
    participant_label = "Участник" if ru else "Participant"
    plant_label = "Растение" if ru else "Plant"
    place_label = "Место" if ru else "Position"
    result_label = "Результат" if ru else "Result"
    result = (
        "🏆 Лучший садовод" if ru and entry.is_winner
        else "🏆 Best Gardener" if entry.is_winner
        else "Участник соревнования" if ru
        else "Battle participant"
    )
    info = (
        "QR-код открывает полную историю растения и таймлапс."
        if ru
        else "The QR code opens this plant's permanent result page and timelapse."
    )
    full_video = (
        f'<a class="button" href="/api/v1/public/plantings/{escape(entry.planting_id)}/timelapse/full">'
        + ("Смотреть таймлапс" if ru else "Watch full timelapse")
        + "</a>"
        if entry.planting_id
        else ""
    )
    return HTMLResponse(
        f"""<!doctype html>
<html lang="{escape(lang)}">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)} — KisaMore</title>
<style>
body{{margin:0;background:#edf5f0;color:#183c31;font-family:Arial,sans-serif}}
.page{{max-width:900px;margin:40px auto;padding:20px}}
.certificate{{background:#fff;border:2px solid #b9d5c8;border-radius:28px;padding:48px;box-shadow:0 22px 60px rgba(20,60,45,.12)}}
.brand{{font-weight:900;letter-spacing:.08em;color:#287455}}h1{{font-size:48px;margin:18px 0 8px}}h2{{font-weight:500;color:#668078;margin:0 0 34px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:28px 0}}.item{{padding:16px;border-radius:14px;background:#f5faf7}}
.label{{display:block;color:#72877f;font-size:12px;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px}}.value{{font-size:20px;font-weight:800}}
.result{{font-size:28px;font-weight:900;margin:30px 0;color:#a67400}}.qr{{display:flex;gap:24px;align-items:center;margin-top:34px;padding-top:26px;border-top:1px solid #dfeae5}}.qr img{{width:170px;height:170px}}
.button{{display:inline-block;margin-top:14px;padding:11px 16px;border-radius:10px;background:#287455;color:white;text-decoration:none;font-weight:700}}
@media(max-width:650px){{.certificate{{padding:26px}}h1{{font-size:36px}}.grid{{grid-template-columns:1fr}}.qr{{align-items:flex-start;flex-direction:column}}}}
@media print{{body{{background:#fff}}.page{{margin:0;max-width:none}}.certificate{{box-shadow:none}}}}
</style>
</head>
<body><main class="page"><section class="certificate">
<div class="brand">KISAMORE</div>
<h1>{escape(title)}</h1><h2>{escape(subtitle)} · {escape(battle.title)}</h2>
<div class="grid">
<div class="item"><span class="label">{escape(participant_label)}</span><span class="value">{escape(user.display_name)}</span></div>
<div class="item"><span class="label">{escape(plant_label)}</span><span class="value">{escape(str(plant_name))}</span></div>
<div class="item"><span class="label">{escape(place_label)}</span><span class="value">#{battle.rack_id}/{entry.slot_number}</span></div>
<div class="item"><span class="label">{escape(result_label)}</span><span class="value">{escape(result)}</span></div>
</div>
<div class="result">{escape(result)}</div>
<div class="qr"><img src="/api/v1/public/battle-entries/{escape(entry.id)}/qr" alt="QR"><div><p>{escape(info)}</p>{full_video}</div></div>
</section></main></body></html>"""
    )


@router.get("/account/telegram-link/status")
async def telegram_link_status(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    linked = await linked_telegram_user(session, user_id=user.id)
    return {
        "linked": linked is not None,
        "telegram_username": linked.username if linked else None,
    }


@router.post("/account/telegram-link", status_code=201)
async def create_telegram_link(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    linked = await linked_telegram_user(session, user_id=user.id)
    if linked is not None:
        return {
            "linked": True,
            "telegram_username": linked.username,
            "bot_url": None,
            "expires_at": None,
        }

    token, expires_at = await create_telegram_link_token(session, user_id=user.id)
    await session.commit()
    username = get_settings().telegram_bot_username.lstrip("@")
    return {
        "linked": False,
        "telegram_username": None,
        "bot_url": f"https://t.me/{username}?start=link_{token}",
        "expires_at": expires_at,
    }


@router.get("/battles/profile")
async def my_battle_profile(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Authenticated battle stats, earned rewards and finished battle history."""
    entries = list((
        await session.execute(
            select(PlantBattleEntry, PlantBattle)
            .join(PlantBattle, PlantBattle.id == PlantBattleEntry.battle_id)
            .where(
                PlantBattleEntry.user_id == user.id,
                PlantBattleEntry.status.in_(("active", "finished")),
            )
            .order_by(PlantBattleEntry.created_at.desc())
        )
    ).all())
    finished = [(entry, battle) for entry, battle in entries if battle.status == "finished"]
    wins = sum(1 for entry, _ in finished if entry.is_winner)
    # First authenticated profile visit earns one permanent starter award.
    milestone = await session.get(AccountAchievement, (user.id, "first_step"))
    if milestone is None:
        milestone = AccountAchievement(
            user_id=user.id, code="first_step", earned_at=datetime.now(timezone.utc)
        )
        session.add(milestone)
        await session.commit()
    rewards = [{
        "id": f"first_step:{user.id}", "code": "first_step",
        "title": "Первый шаг", "icon": "sprout",
        "earned_at": milestone.earned_at.isoformat(),
    }]
    history = []
    for entry, battle in finished:
        earned = (battle.finished_at or entry.created_at).isoformat()
        plant = await session.get(Plant, battle.plant_id)
        history.append({
            "battle_id": battle.id, "entry_id": entry.id, "title": battle.title,
            "plant_name": _plant_name(plant) if plant else "Plant",
            "finished_at": battle.finished_at.isoformat() if battle.finished_at else None,
            "is_winner": bool(entry.is_winner),
            "certificate_url": f"/api/v1/battle-certificate/{entry.id}",
        })
        if entry.is_winner:
            rewards.extend([
                {"id": f"winner:{entry.id}", "code": "best_gardener",
                 "title": "Лучший садовод", "icon": "award", "earned_at": earned},
                {"id": f"kisa:{entry.id}", "code": "winner_kisa",
                 "title": f"{battle.winner_reward_kisa} Kisa",
                 "icon": "coins", "earned_at": earned},
            ])
        rewards.append({
            "id": f"certificate:{entry.id}", "code": "certificate",
            "title": "QR-диплом", "icon": "qr-code", "earned_at": earned,
            "url": f"/api/v1/battle-certificate/{entry.id}",
        })
    rewards.sort(key=lambda item: item["earned_at"], reverse=True)
    return {
        "battle_count": len({battle.id for _, battle in entries}),
        "win_count": wins,
        "rating_points": len(finished) * 10 + wins * 100,
        "rating_rule": "10 points per finished entry + 100 per victory",
        "rewards": rewards,
        "history": history,
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


@router.get("/battles/{battle_id}")
async def authenticated_battle(
    battle_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    battle = await session.get(PlantBattle, battle_id)
    if battle is None or battle.status == "cancelled":
        raise HTTPException(status_code=404, detail="Battle not found")
    return await _battle_payload(session, battle, user.id)


@router.post("/battles/{battle_id}/prediction")
async def set_battle_prediction(
    battle_id: str,
    payload: BattlePredictionIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    battle = await session.get(PlantBattle, battle_id)
    if battle is None or battle.status == "cancelled":
        raise HTTPException(status_code=404, detail="Battle not found")
    if battle.status == "finished":
        raise HTTPException(status_code=409, detail="Predictions are closed for finished battles")

    entry = await session.get(PlantBattleEntry, payload.entry_id)
    if entry is None or entry.battle_id != battle.id or entry.status not in ("active", "finished"):
        raise HTTPException(status_code=404, detail="Battle entry not found")

    now = datetime.now(timezone.utc)
    prediction = (
        await session.execute(
            select(PlantBattlePrediction)
            .where(
                PlantBattlePrediction.battle_id == battle.id,
                PlantBattlePrediction.user_id == user.id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()

    if prediction is None:
        prediction = PlantBattlePrediction(
            id=str(uuid4()),
            battle_id=battle.id,
            user_id=user.id,
            entry_id=entry.id,
            created_at=now,
            updated_at=now,
        )
        session.add(prediction)
    else:
        prediction.entry_id = entry.id
        prediction.updated_at = now

    await session.commit()
    return await _battle_payload(session, battle, user.id)


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

    existing_entry = (
        await session.execute(
            select(PlantBattleEntry)
            .where(
                PlantBattleEntry.battle_id == battle.id,
                PlantBattleEntry.user_id == user.id,
                PlantBattleEntry.status.in_(("active", "finished")),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing_entry is not None:
        raise HTTPException(
            status_code=409,
            detail="You already own a plant in this battle",
        )

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
                    text=battle_message(
                        tg,
                        "full",
                        rack=battle.rack_id,
                        count=battle.max_entries,
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
