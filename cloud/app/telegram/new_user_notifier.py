from __future__ import annotations

from datetime import datetime, timezone
from html import escape

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, mapped_column

from ..db import SessionLocal
from ..models import Base
from .admin_models import TelegramAdmin
from .models import TelegramUser


MAX_ATTEMPTS = 5


class TelegramAdminNewUserState(Base):
    """Cursor used to avoid replaying users that existed before this feature."""

    __tablename__ = "telegram_admin_new_user_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    last_seen_user_id: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    initialized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TelegramAdminNewUserAlert(Base):
    __tablename__ = "telegram_admin_new_user_alerts"
    __table_args__ = (
        UniqueConstraint(
            "admin_user_id",
            "new_user_id",
            name="uq_telegram_admin_new_user_alert",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_user_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_users.id"), index=True, nullable=False
    )
    new_user_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_users.id"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


def _user_name(user: TelegramUser) -> str:
    full_name = " ".join(
        value for value in (user.first_name, user.last_name) if value
    ).strip()
    if full_name:
        return full_name
    if user.username:
        return f"@{user.username}"
    return f"Telegram {user.telegram_user_id}"


def _user_text(user: TelegramUser) -> str:
    username = f"@{escape(user.username)}" if user.username else "—"
    created = user.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    created_text = created.astimezone().strftime("%d.%m.%Y %H:%M")
    language = escape(user.language_code or "—")
    return (
        "👤 <b>Новый пользователь KisaMore</b>\n\n"
        f"Имя: <b>{escape(_user_name(user))}</b>\n"
        f"Username: {username}\n"
        f"Telegram ID: <code>{int(user.telegram_user_id)}</code>\n"
        f"Язык: <b>{language}</b>\n"
        f"Зарегистрирован: {escape(created_text)}"
    )


def user_keyboard(user_id: int) -> dict:
    return {
        "inline_keyboard": [[
            {"text": "🎁 Подарить", "callback_data": f"adminuser:gift:{user_id}"}
        ]]
    }


async def discover_new_users() -> int:
    """Create one delivery per enabled admin for users created after activation."""
    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        state = await session.get(TelegramAdminNewUserState, 1)
        if state is None:
            latest = int(
                (
                    await session.execute(
                        select(func.coalesce(func.max(TelegramUser.id), 0))
                    )
                ).scalar_one()
                or 0
            )
            session.add(
                TelegramAdminNewUserState(
                    id=1,
                    last_seen_user_id=latest,
                    initialized_at=now,
                    updated_at=now,
                )
            )
            await session.commit()
            return 0

        users = list(
            (
                await session.execute(
                    select(TelegramUser)
                    .where(TelegramUser.id > state.last_seen_user_id)
                    .order_by(TelegramUser.id)
                    .limit(100)
                )
            ).scalars().all()
        )
        if not users:
            return 0

        admins = list(
            (
                await session.execute(
                    select(TelegramAdmin.user_id).where(TelegramAdmin.enabled.is_(True))
                )
            ).scalars().all()
        )
        created = 0
        for user in users:
            for admin_user_id in admins:
                if int(admin_user_id) == int(user.id):
                    continue
                exists = (
                    await session.execute(
                        select(TelegramAdminNewUserAlert.id).where(
                            TelegramAdminNewUserAlert.admin_user_id == int(admin_user_id),
                            TelegramAdminNewUserAlert.new_user_id == int(user.id),
                        )
                    )
                ).scalar_one_or_none()
                if exists is None:
                    session.add(
                        TelegramAdminNewUserAlert(
                            admin_user_id=int(admin_user_id),
                            new_user_id=int(user.id),
                            status="pending",
                            attempts=0,
                            created_at=now,
                        )
                    )
                    created += 1

        state.last_seen_user_id = int(users[-1].id)
        state.updated_at = now
        await session.commit()
        return created


async def send_pending_alerts(bot) -> tuple[int, int]:
    sent = 0
    failed = 0
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(TelegramAdminNewUserAlert, TelegramUser)
                .join(TelegramUser, TelegramUser.id == TelegramAdminNewUserAlert.new_user_id)
                .where(
                    TelegramAdminNewUserAlert.status == "pending",
                    TelegramAdminNewUserAlert.attempts < MAX_ATTEMPTS,
                )
                .order_by(TelegramAdminNewUserAlert.id)
                .limit(50)
            )
        ).all()

        for alert, new_user in rows:
            admin_user = await session.get(TelegramUser, alert.admin_user_id)
            admin = await session.get(TelegramAdmin, alert.admin_user_id)
            if admin_user is None or admin is None or not admin.enabled or not admin_user.is_active:
                alert.status = "skipped"
                continue
            try:
                await bot.send_message(
                    int(admin_user.telegram_user_id),
                    _user_text(new_user),
                    reply_markup=user_keyboard(new_user.id),
                )
                alert.status = "sent"
                alert.sent_at = datetime.now(timezone.utc)
                alert.last_error = None
                sent += 1
            except Exception as exc:
                alert.attempts += 1
                alert.last_error = f"{type(exc).__name__}: {exc}"[:2000]
                if alert.attempts >= MAX_ATTEMPTS:
                    alert.status = "failed"
                failed += 1

        if rows:
            await session.commit()
    return sent, failed
