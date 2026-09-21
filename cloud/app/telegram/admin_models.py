from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..models import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TelegramAdmin(Base):
    __tablename__ = "telegram_admins"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_users.id"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    welcome_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class TelegramAdminRentalAlert(Base):
    __tablename__ = "telegram_admin_rental_alerts"
    __table_args__ = (
        UniqueConstraint(
            "admin_user_id",
            "request_id",
            name="uq_telegram_admin_rental_alert",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_user_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_users.id"), index=True, nullable=False
    )
    request_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_rental_requests.id"), index=True, nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reminded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class TelegramAdminPlantTaskAlert(Base):
    """Daily Telegram reminder state for one operational greenhouse task."""

    __tablename__ = "telegram_admin_plant_task_alerts"
    __table_args__ = (
        UniqueConstraint(
            "admin_user_id",
            "task_type",
            "task_key",
            name="uq_telegram_admin_plant_task_alert",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_user_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_users.id"), index=True, nullable=False
    )
    task_type: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    task_key: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    last_reminded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class EdgeOperatorCommand(Base):
    """Durable cloud-to-Raspberry operator action requested from Telegram admin."""

    __tablename__ = "edge_operator_commands"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    device_id: Mapped[str] = mapped_column(
        ForeignKey("devices.id"), index=True, nullable=False
    )
    action: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    rack_id: Mapped[int] = mapped_column(Integer, nullable=False)
    slot_number: Mapped[int] = mapped_column(Integer, nullable=False)
    plant_id: Mapped[str | None] = mapped_column(
        ForeignKey("plants.id"), nullable=True
    )
    planting_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    allocation_id: Mapped[str | None] = mapped_column(
        ForeignKey("allocations.id"), index=True, nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending", index=True, nullable=False
    )
    requested_by_admin_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("telegram_users.id"), nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
