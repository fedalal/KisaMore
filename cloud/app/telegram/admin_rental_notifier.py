from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape

from sqlalchemy import select

from ..db import SessionLocal
from ..models import Plant, RackSlot
from .admin_models import TelegramAdmin, TelegramAdminRentalAlert
from .models import TelegramRentalRequest, TelegramUser


CHECK_SECONDS = 10
REMINDER_MINUTES = 30


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _plant_name(plant: Plant) -> str:
    names = plant.names or {}
    for key in ("ru", "en"):
        if names.get(key):
            return str(names[key])
    return next((str(value) for value in names.values() if value), plant.code)


def _user_name(user: TelegramUser) -> str:
    full_name = " ".join(
        value for value in (user.first_name, user.last_name) if value
    ).strip()
    if full_name:
        return full_name
    if user.username:
        return f"@{user.username}"
    return f"Telegram {user.telegram_user_id}"


def _request_text(
    request: TelegramRentalRequest,
    user: TelegramUser,
    slot: RackSlot,
    plant: Plant,
    *,
    reminder: bool,
) -> str:
    heading = "⏰ <b>Напоминание: заявка ждёт решения</b>" if reminder else "🆕 <b>Новая заявка на аренду</b>"
    username = f"@{escape(user.username)}" if user.username else "—"
    created = _aware(request.created_at)
    created_text = created.astimezone().strftime("%d.%m.%Y %H:%M") if created else "—"
    return (
        f"{heading}\n\n"
        f"Заявка: <b>#{request.id}</b>\n"
        f"Пользователь: <b>{escape(_user_name(user))}</b>\n"
        f"Username: {username}\n"
        f"Растение: <b>{escape(_plant_name(plant))}</b>\n"
        f"Полка {slot.rack_id} · контейнер {slot.slot_number}\n"
        f"Стоимость: <b>Ⓚ {int(request.price_kisa or 0)}</b>\n"
        f"Подана: {escape(created_text)}\n\n"
        f"Пока заявка не обработана, бот будет напоминать о ней каждые {REMINDER_MINUTES} минут."
    )


def request_keyboard(request_id: int) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Одобрить", "callback_data": f"adminrent:approve:{request_id}"},
                {"text": "❌ Отклонить", "callback_data": f"adminrent:reject:{request_id}"},
            ],
            [
                {"text": "📋 Все заявки", "callback_data": "adminrent:list"},
            ],
        ]
    }


async def is_telegram_admin(user_id: int) -> bool:
    async with SessionLocal() as session:
        row = await session.get(TelegramAdmin, user_id)
        return bool(row and row.enabled)


async def send_welcome_messages(bot) -> int:
    sent = 0
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(TelegramAdmin, TelegramUser)
                .join(TelegramUser, TelegramUser.id == TelegramAdmin.user_id)
                .where(
                    TelegramAdmin.enabled.is_(True),
                    TelegramAdmin.welcome_sent_at.is_(None),
                )
            )
        ).all()
        for admin, user in rows:
            try:
                await bot.send_message(
                    user.telegram_user_id,
                    "🛡 <b>Режим администратора KisaMore включён</b>\n\n"
                    "Теперь сюда будут приходить новые заявки на аренду. "
                    "Необработанные заявки будут напоминаться каждые 30 минут.\n\n"
                    "Команда /admin покажет все заявки, которые сейчас ждут решения.",
                )
            except Exception:
                continue
            admin.welcome_sent_at = datetime.now(timezone.utc)
            sent += 1
        if sent:
            await session.commit()
    return sent


async def send_pending_alerts(bot) -> tuple[int, int]:
    """Send or remind every enabled Telegram admin about pending rental requests.

    Delivery state is stored in PostgreSQL, so a bot restart does not lose an
    unhandled request. A failed Telegram API call leaves the alert due and it is
    retried on the next pass.
    """
    now = datetime.now(timezone.utc)
    reminder_before = now - timedelta(minutes=REMINDER_MINUTES)
    sent = 0
    failed = 0

    async with SessionLocal() as session:
        admins = list(
            (
                await session.execute(
                    select(TelegramAdmin, TelegramUser)
                    .join(TelegramUser, TelegramUser.id == TelegramAdmin.user_id)
                    .where(TelegramAdmin.enabled.is_(True), TelegramUser.is_active.is_(True))
                )
            ).all()
        )
        if not admins:
            return 0, 0

        requests = list(
            (
                await session.execute(
                    select(TelegramRentalRequest, TelegramUser, RackSlot, Plant)
                    .join(TelegramUser, TelegramUser.id == TelegramRentalRequest.user_id)
                    .join(RackSlot, RackSlot.id == TelegramRentalRequest.slot_id)
                    .join(Plant, Plant.id == TelegramRentalRequest.plant_id)
                    .where(TelegramRentalRequest.status == "requested")
                    .order_by(TelegramRentalRequest.created_at)
                    .limit(100)
                )
            ).all()
        )
        if not requests:
            return 0, 0

        for admin, admin_user in admins:
            for request, renter, slot, plant in requests:
                alert = (
                    await session.execute(
                        select(TelegramAdminRentalAlert).where(
                            TelegramAdminRentalAlert.admin_user_id == admin.user_id,
                            TelegramAdminRentalAlert.request_id == request.id,
                        )
                    )
                ).scalar_one_or_none()
                if alert is None:
                    alert = TelegramAdminRentalAlert(
                        admin_user_id=admin.user_id,
                        request_id=request.id,
                        created_at=now,
                    )
                    session.add(alert)
                    await session.flush()

                previous = _aware(alert.last_reminded_at or alert.sent_at)
                due = alert.sent_at is None or previous is None or previous <= reminder_before
                if not due:
                    continue
                reminder = alert.sent_at is not None
                try:
                    await bot.send_message(
                        admin_user.telegram_user_id,
                        _request_text(request, renter, slot, plant, reminder=reminder),
                        reply_markup=request_keyboard(request.id),
                    )
                except Exception:
                    failed += 1
                    continue

                if alert.sent_at is None:
                    alert.sent_at = now
                alert.last_reminded_at = now
                sent += 1

        if sent:
            await session.commit()
    return sent, failed


async def pending_requests(limit: int = 10):
    async with SessionLocal() as session:
        return list(
            (
                await session.execute(
                    select(TelegramRentalRequest, TelegramUser, RackSlot, Plant)
                    .join(TelegramUser, TelegramUser.id == TelegramRentalRequest.user_id)
                    .join(RackSlot, RackSlot.id == TelegramRentalRequest.slot_id)
                    .join(Plant, Plant.id == TelegramRentalRequest.plant_id)
                    .where(TelegramRentalRequest.status == "requested")
                    .order_by(TelegramRentalRequest.created_at)
                    .limit(max(1, min(limit, 30)))
                )
            ).all()
        )


def format_pending_request(row) -> tuple[str, dict]:
    request, renter, slot, plant = row
    return (
        _request_text(request, renter, slot, plant, reminder=False),
        request_keyboard(request.id),
    )
