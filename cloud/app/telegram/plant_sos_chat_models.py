from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..models import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TelegramPlantSosMessage(Base):
    """One message inside an SOS conversation.

    sender_type is either "user" or "admin". User messages already exist in the
    Telegram chat, while admin messages are queued here and delivered by the bot
    worker so the web API never needs the Telegram bot token.
    """

    __tablename__ = "telegram_plant_sos_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_plant_sos_reports.id"), index=True, nullable=False
    )
    sender_type: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    telegram_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("telegram_users.id"), index=True, nullable=True
    )
    admin_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    delivery_status: Mapped[str] = mapped_column(
        String(20), default="not_required", index=True, nullable=False
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, nullable=False
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class TelegramPlantSosMessageAlert(Base):
    """Telegram-admin alert fan-out for each user message."""

    __tablename__ = "telegram_plant_sos_message_alerts"
    __table_args__ = (
        UniqueConstraint(
            "message_id",
            "admin_user_id",
            name="uq_telegram_plant_sos_message_alert",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_plant_sos_messages.id"), index=True, nullable=False
    )
    admin_user_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_users.id"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending", index=True, nullable=False
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
