from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import os
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select

from ..admin_models import AdminAuditLog
from ..config import get_settings
from ..db import SessionLocal
from ..models import Allocation, Plant, Planting, RackSlot, User
from .admin_models import EdgeOperatorCommand, TelegramAdmin, TelegramAdminPlantTaskAlert
from .models import TelegramRentalRequest, TelegramUser


CHECK_SECONDS = max(30, int(os.getenv("KISAMORE_ADMIN_PLANT_TASK_CHECK_SECONDS", "60")))
REMINDER_HOUR = min(23, max(0, int(os.getenv("KISAMORE_ADMIN_PLANT_TASK_HOUR", "9"))))
ACTIVE_PLANTING_STATUSES = ("planned", "growing", "ready")


def _zone() -> ZoneInfo:
    try:
        return ZoneInfo(get_settings().farm_timezone)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _local_text(value: datetime | None) -> str:
    aware = _aware(value)
    if aware is None:
        return "—"
    return aware.astimezone(_zone()).strftime("%d.%m.%Y %H:%M")


def _plant_name(plant: Plant) -> str:
    names = plant.names or {}
    for key in ("ru", "en"):
        if names.get(key):
            return str(names[key])
    return next((str(value) for value in names.values() if value), plant.code)


def _user_name(user: TelegramUser) -> str:
    full = " ".join(v for v in (user.first_name, user.last_name) if v).strip()
    if full:
        return full
    if user.username:
        return f"@{user.username}"
    return f"Telegram {user.telegram_user_id}"


def _allocation_id(request: TelegramRentalRequest) -> str | None:
    note = (request.note or "").strip()
    if not note.startswith("allocation:"):
        return None
    value = note.split(":", 1)[1].strip()
    return value or None


async def _plant_tasks(session):
    rows = (
        await session.execute(
            select(TelegramRentalRequest, TelegramUser, RackSlot, Plant)
            .join(TelegramUser, TelegramUser.id == TelegramRentalRequest.user_id)
            .join(RackSlot, RackSlot.id == TelegramRentalRequest.slot_id)
            .join(Plant, Plant.id == TelegramRentalRequest.plant_id)
            .where(TelegramRentalRequest.status == "approved")
            .order_by(TelegramRentalRequest.updated_at)
            .limit(200)
        )
    ).all()

    result = []
    for request, renter, slot, plant in rows:
        allocation_id = _allocation_id(request)
        if not allocation_id:
            continue
        allocation = await session.get(Allocation, allocation_id)
        if allocation is None or allocation.status != "active":
            continue
        planting = (
            await session.execute(
                select(Planting.id)
                .where(
                    Planting.cloud_allocation_id == allocation.id,
                    Planting.status.in_(ACTIVE_PLANTING_STATUSES),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if planting is not None:
            continue
        result.append((request, renter, slot, plant, allocation))
    return result


async def _ready_tasks(session):
    now = datetime.now(timezone.utc)
    rows = (
        await session.execute(
            select(Planting, Plant, RackSlot)
            .join(Plant, Plant.id == Planting.plant_id)
            .join(RackSlot, RackSlot.id == Planting.slot_id)
            .where(
                Planting.status == "growing",
                Planting.expected_harvest_at <= now,
            )
            .order_by(Planting.expected_harvest_at)
            .limit(200)
        )
    ).all()
    return list(rows)


async def _due_for_admin(
    session,
    *,
    admin_user_id: int,
    task_type: str,
    task_key: str,
    now: datetime,
) -> TelegramAdminPlantTaskAlert | None:
    row = (
        await session.execute(
            select(TelegramAdminPlantTaskAlert).where(
                TelegramAdminPlantTaskAlert.admin_user_id == admin_user_id,
                TelegramAdminPlantTaskAlert.task_type == task_type,
                TelegramAdminPlantTaskAlert.task_key == task_key,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = TelegramAdminPlantTaskAlert(
            admin_user_id=admin_user_id,
            task_type=task_type,
            task_key=task_key,
            created_at=now,
        )
        session.add(row)
        await session.flush()
        return row

    last = _aware(row.last_reminded_at)
    if last is None:
        return row
    if last.astimezone(_zone()).date() < now.astimezone(_zone()).date():
        return row
    return None


def _plant_text(request, renter, slot, plant) -> str:
    return (
        "🌱 <b>Нужно посадить растение</b>\n\n"
        f"Заявка: <b>#{request.id}</b>\n"
        f"Пользователь: <b>{escape(_user_name(renter))}</b>\n"
        f"Растение: <b>{escape(_plant_name(plant))}</b>\n"
        f"Полка {slot.rack_id} · контейнер {slot.slot_number}\n"
        f"Заявка одобрена: {_local_text(request.updated_at)}\n\n"
        "После фактической посадки нажмите кнопку ниже. "
        "Raspberry Pi создаст посадку и рассчитает срок выращивания."
    )


def _ready_text(planting, plant, slot) -> str:
    expected = _aware(planting.expected_harvest_at)
    now = datetime.now(timezone.utc)
    overdue_days = 0
    if expected is not None and now > expected:
        overdue_days = max(0, (now - expected).days)
    overdue = f"\nПросрочено: <b>{overdue_days} дн.</b>" if overdue_days else ""
    return (
        "✂️ <b>Пора проверить растение для сбора</b>\n\n"
        f"Растение: <b>{escape(_plant_name(plant))}</b>\n"
        f"Полка {slot.rack_id} · контейнер {slot.slot_number}\n"
        f"Посажено: {_local_text(planting.planted_at)}\n"
        f"Плановый срок: <b>{_local_text(planting.expected_harvest_at)}</b>"
        f"{overdue}\n\n"
        "Если растение действительно достигло нужной стадии, отметьте его готовым."
    )


async def send_daily_alerts(bot) -> tuple[int, int]:
    now = datetime.now(timezone.utc)
    local_now = now.astimezone(_zone())
    if local_now.hour < REMINDER_HOUR:
        return 0, 0

    sent = 0
    failed = 0
    async with SessionLocal() as session:
        admins = list(
            (
                await session.execute(
                    select(TelegramAdmin, TelegramUser)
                    .join(TelegramUser, TelegramUser.id == TelegramAdmin.user_id)
                    .where(
                        TelegramAdmin.enabled.is_(True),
                        TelegramUser.is_active.is_(True),
                    )
                )
            ).all()
        )
        if not admins:
            return 0, 0

        plant_tasks = await _plant_tasks(session)
        ready_tasks = await _ready_tasks(session)

        for admin, admin_user in admins:
            for request, renter, slot, plant, _allocation in plant_tasks:
                alert = await _due_for_admin(
                    session,
                    admin_user_id=admin.user_id,
                    task_type="plant",
                    task_key=str(request.id),
                    now=now,
                )
                if alert is None:
                    continue
                try:
                    await bot.send_message(
                        int(admin_user.telegram_user_id),
                        _plant_text(request, renter, slot, plant),
                        reply_markup={
                            "inline_keyboard": [[
                                {
                                    "text": "🌱 Отметить посаженным",
                                    "callback_data": f"adminplant:plant:{request.id}",
                                }
                            ]]
                        },
                    )
                    alert.last_reminded_at = now
                    sent += 1
                except Exception:
                    failed += 1

            for planting, plant, slot in ready_tasks:
                alert = await _due_for_admin(
                    session,
                    admin_user_id=admin.user_id,
                    task_type="ready",
                    task_key=str(planting.id),
                    now=now,
                )
                if alert is None:
                    continue
                try:
                    await bot.send_message(
                        int(admin_user.telegram_user_id),
                        _ready_text(planting, plant, slot),
                        reply_markup={
                            "inline_keyboard": [[
                                {
                                    "text": "✅ Отметить готовым",
                                    "callback_data": f"adminplant:ready:{planting.id}",
                                }
                            ]]
                        },
                    )
                    alert.last_reminded_at = now
                    sent += 1
                except Exception:
                    failed += 1

        if sent:
            await session.commit()
        elif session.new:
            # Do not leave unsent alert rows in an open transaction.
            await session.rollback()

    return sent, failed


async def send_command_results(bot) -> tuple[int, int]:
    """Tell the requesting Telegram admin when Raspberry applied the action."""
    sent = 0
    failed = 0
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(EdgeOperatorCommand, TelegramUser)
                .join(
                    TelegramUser,
                    TelegramUser.id == EdgeOperatorCommand.requested_by_admin_user_id,
                )
                .where(
                    EdgeOperatorCommand.status.in_(("applied", "failed")),
                    EdgeOperatorCommand.result_notified_at.is_(None),
                    TelegramUser.is_active.is_(True),
                )
                .order_by(EdgeOperatorCommand.created_at)
                .limit(50)
            )
        ).all()

        for command, admin_user in rows:
            try:
                if command.status == "applied":
                    if command.action == "plant":
                        text = (
                            "✅ <b>Raspberry Pi подтвердил посадку.</b>\n\n"
                            f"Полка {command.rack_id} · контейнер {command.slot_number}\n"
                            "Посадка создана, срок выращивания рассчитан автоматически."
                        )
                    else:
                        text = (
                            "✅ <b>Raspberry Pi обновил растение.</b>\n\n"
                            f"Полка {command.rack_id} · контейнер {command.slot_number}\n"
                            "Статус: <b>готово к сбору</b>."
                        )
                else:
                    reason = escape(command.error or "неизвестная ошибка")
                    text = (
                        "⚠️ <b>Raspberry Pi не смог выполнить команду.</b>\n\n"
                        f"Полка {command.rack_id} · контейнер {command.slot_number}\n"
                        f"Причина: <code>{reason}</code>\n\n"
                        "Задача останется актуальной, и бот напомнит о ней снова."
                    )
                await bot.send_message(int(admin_user.telegram_user_id), text)
                command.result_notified_at = datetime.now(timezone.utc)
                sent += 1
            except Exception:
                failed += 1
            await session.commit()

    return sent, failed


async def queue_plant_command(
    *,
    request_id: int,
    telegram_admin_user_id: int,
    web_admin: User,
) -> EdgeOperatorCommand:
    async with SessionLocal() as session:
        request = await session.get(TelegramRentalRequest, request_id)
        if request is None or request.status != "approved":
            raise ValueError("request_not_approved")

        allocation_id = _allocation_id(request)
        if not allocation_id:
            raise ValueError("allocation_missing")
        allocation = await session.get(Allocation, allocation_id)
        slot = await session.get(RackSlot, request.slot_id)
        plant = await session.get(Plant, request.plant_id)
        if allocation is None or allocation.status != "active" or slot is None or plant is None:
            raise ValueError("allocation_missing")

        existing_planting = (
            await session.execute(
                select(Planting.id)
                .where(
                    Planting.cloud_allocation_id == allocation.id,
                    Planting.status.in_(ACTIVE_PLANTING_STATUSES),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing_planting is not None:
            raise ValueError("already_planted")

        existing_command = (
            await session.execute(
                select(EdgeOperatorCommand)
                .where(
                    EdgeOperatorCommand.action == "plant",
                    EdgeOperatorCommand.allocation_id == allocation.id,
                    EdgeOperatorCommand.status.in_(("pending", "applied")),
                )
                .order_by(EdgeOperatorCommand.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing_command is not None:
            return existing_command

        now = datetime.now(timezone.utc)
        command = EdgeOperatorCommand(
            id=str(uuid4()),
            device_id=allocation.device_id,
            action="plant",
            rack_id=slot.rack_id,
            slot_number=slot.slot_number,
            plant_id=plant.id,
            planting_id=str(uuid4()),
            allocation_id=allocation.id,
            status="pending",
            requested_by_admin_user_id=telegram_admin_user_id,
            created_at=now,
        )
        session.add(command)
        session.add(
            AdminAuditLog(
                admin_user_id=web_admin.id,
                action="telegram_mark_planted",
                target_type="telegram_rental_request",
                target_id=str(request.id),
                details={
                    "command_id": command.id,
                    "allocation_id": allocation.id,
                    "device_id": allocation.device_id,
                    "rack_id": slot.rack_id,
                    "slot_number": slot.slot_number,
                    "plant_id": plant.id,
                },
            )
        )
        await session.commit()
        await session.refresh(command)
        return command


async def queue_ready_command(
    *,
    planting_id: str,
    telegram_admin_user_id: int,
    web_admin: User,
) -> EdgeOperatorCommand:
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(Planting, RackSlot)
                .join(RackSlot, RackSlot.id == Planting.slot_id)
                .where(Planting.id == planting_id)
            )
        ).first()
        if row is None:
            raise ValueError("planting_missing")
        planting, slot = row
        if planting.status == "ready":
            raise ValueError("already_ready")
        if planting.status != "growing":
            raise ValueError("not_growing")

        existing_command = (
            await session.execute(
                select(EdgeOperatorCommand)
                .where(
                    EdgeOperatorCommand.action == "ready",
                    EdgeOperatorCommand.planting_id == planting.id,
                    EdgeOperatorCommand.status.in_(("pending", "applied")),
                )
                .order_by(EdgeOperatorCommand.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing_command is not None:
            return existing_command

        command = EdgeOperatorCommand(
            id=str(uuid4()),
            device_id=slot.device_id,
            action="ready",
            rack_id=slot.rack_id,
            slot_number=slot.slot_number,
            plant_id=planting.plant_id,
            planting_id=planting.id,
            allocation_id=planting.cloud_allocation_id,
            status="pending",
            requested_by_admin_user_id=telegram_admin_user_id,
            created_at=datetime.now(timezone.utc),
        )
        session.add(command)
        session.add(
            AdminAuditLog(
                admin_user_id=web_admin.id,
                action="telegram_mark_ready",
                target_type="planting",
                target_id=str(planting.id),
                details={
                    "command_id": command.id,
                    "device_id": slot.device_id,
                    "rack_id": slot.rack_id,
                    "slot_number": slot.slot_number,
                },
            )
        )
        await session.commit()
        await session.refresh(command)
        return command
