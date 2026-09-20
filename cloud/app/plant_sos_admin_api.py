from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .admin_models import AdminAuditLog
from .models import Plant, Planting, RackSlot, User
from .security import get_admin_user, get_session
from .telegram.models import TelegramUser
from .telegram.plant_sos import TelegramPlantSosReport
from .telegram.plant_sos_chat_models import TelegramPlantSosMessage


router = APIRouter(prefix="/api/v1/admin/sos", tags=["admin-sos"])


class SosReplyIn(BaseModel):
    message: str = Field(min_length=1, max_length=1500)


class SosStatusIn(BaseModel):
    status: str = Field(pattern="^(open|resolved)$")


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _plant_name(plant: Plant) -> str:
    names = plant.names or {}
    return str(names.get("ru") or names.get("en") or next(
        (value for value in names.values() if value),
        plant.code,
    ))


def _user_name(user: TelegramUser) -> str:
    value = " ".join(x for x in (user.first_name, user.last_name) if x).strip()
    return value or (f"@{user.username}" if user.username else f"Telegram {user.telegram_user_id}")


async def _report_context(session: AsyncSession, report_id: int):
    return (
        await session.execute(
            select(TelegramPlantSosReport, TelegramUser, Planting, Plant, RackSlot)
            .join(TelegramUser, TelegramUser.id == TelegramPlantSosReport.user_id)
            .join(Planting, Planting.id == TelegramPlantSosReport.planting_id)
            .join(Plant, Plant.id == Planting.plant_id)
            .join(RackSlot, RackSlot.id == Planting.slot_id)
            .where(TelegramPlantSosReport.id == report_id)
            .limit(1)
        )
    ).first()


@router.get("")
async def list_sos_threads(
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(
            select(TelegramPlantSosReport, TelegramUser, Planting, Plant, RackSlot)
            .join(TelegramUser, TelegramUser.id == TelegramPlantSosReport.user_id)
            .join(Planting, Planting.id == TelegramPlantSosReport.planting_id)
            .join(Plant, Plant.id == Planting.plant_id)
            .join(RackSlot, RackSlot.id == Planting.slot_id)
            .order_by(TelegramPlantSosReport.created_at.desc())
            .limit(200)
        )
    ).all()

    result = []
    for report, user, planting, plant, slot in rows:
        last_message = (
            await session.execute(
                select(TelegramPlantSosMessage)
                .where(TelegramPlantSosMessage.report_id == report.id)
                .order_by(
                    TelegramPlantSosMessage.created_at.desc(),
                    TelegramPlantSosMessage.id.desc(),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        unread = int(
            (
                await session.execute(
                    select(func.count(TelegramPlantSosMessage.id)).where(
                        TelegramPlantSosMessage.report_id == report.id,
                        TelegramPlantSosMessage.sender_type == "user",
                        TelegramPlantSosMessage.admin_read_at.is_(None),
                    )
                )
            ).scalar_one()
            or 0
        )
        if last_message is None and report.status == "new":
            unread = max(unread, 1)

        result.append(
            {
                "id": report.id,
                "status": report.status,
                "created_at": _aware(report.created_at),
                "last_at": _aware(last_message.created_at if last_message else report.created_at),
                "last_message": last_message.body if last_message else report.message,
                "last_sender": last_message.sender_type if last_message else "user",
                "unread": unread,
                "user": {
                    "id": user.id,
                    "name": _user_name(user),
                    "username": user.username,
                    "telegram_user_id": user.telegram_user_id,
                },
                "plant": {
                    "planting_id": planting.id,
                    "name": _plant_name(plant),
                    "rack_id": slot.rack_id,
                    "slot_number": slot.slot_number,
                },
            }
        )
    return result


@router.get("/{report_id}")
async def sos_thread(
    report_id: int,
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    row = await _report_context(session, report_id)
    if row is None:
        raise HTTPException(status_code=404, detail="SOS thread not found")
    report, user, planting, plant, slot = row

    messages = list(
        (
            await session.execute(
                select(TelegramPlantSosMessage)
                .where(TelegramPlantSosMessage.report_id == report.id)
                .order_by(TelegramPlantSosMessage.created_at, TelegramPlantSosMessage.id)
            )
        ).scalars().all()
    )

    now = datetime.now(timezone.utc)
    changed = False
    for message in messages:
        if message.sender_type == "user" and message.admin_read_at is None:
            message.admin_read_at = now
            changed = True
    if report.status == "new":
        report.status = "open"
        changed = True
    if changed:
        await session.commit()

    items = [
        {
            "id": item.id,
            "sender": item.sender_type,
            "body": item.body,
            "created_at": _aware(item.created_at),
            "delivery_status": item.delivery_status,
            "delivered_at": _aware(item.delivered_at),
        }
        for item in messages
    ]
    if not items and report.message:
        items.append(
            {
                "id": f"legacy:{report.id}",
                "sender": "user",
                "body": report.message,
                "created_at": _aware(report.created_at),
                "delivery_status": "not_required",
                "delivered_at": None,
            }
        )

    return {
        "id": report.id,
        "status": report.status,
        "created_at": _aware(report.created_at),
        "user": {
            "id": user.id,
            "name": _user_name(user),
            "username": user.username,
            "telegram_user_id": user.telegram_user_id,
        },
        "plant": {
            "planting_id": planting.id,
            "name": _plant_name(plant),
            "rack_id": slot.rack_id,
            "slot_number": slot.slot_number,
        },
        "messages": items,
    }


@router.post("/{report_id}/messages")
async def reply_sos(
    report_id: int,
    payload: SosReplyIn,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    report = await session.get(TelegramPlantSosReport, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="SOS thread not found")

    body = payload.message.strip()
    if not body:
        raise HTTPException(status_code=422, detail="Message is empty")

    now = datetime.now(timezone.utc)
    message = TelegramPlantSosMessage(
        report_id=report.id,
        sender_type="admin",
        admin_user_id=admin.id,
        body=body,
        delivery_status="pending",
        attempts=0,
        created_at=now,
    )
    session.add(message)
    report.status = "open"
    session.add(
        AdminAuditLog(
            admin_user_id=admin.id,
            action="sos_reply",
            target_type="telegram_plant_sos_report",
            target_id=str(report.id),
            details={"message": body},
        )
    )
    await session.commit()
    await session.refresh(message)
    return {"ok": True, "message_id": message.id, "delivery_status": message.delivery_status}


@router.patch("/{report_id}")
async def update_sos_status(
    report_id: int,
    payload: SosStatusIn,
    admin: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    report = await session.get(TelegramPlantSosReport, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="SOS thread not found")

    report.status = payload.status
    session.add(
        AdminAuditLog(
            admin_user_id=admin.id,
            action="sos_status",
            target_type="telegram_plant_sos_report",
            target_id=str(report.id),
            details={"status": payload.status},
        )
    )
    await session.commit()
    return {"ok": True, "status": report.status}
