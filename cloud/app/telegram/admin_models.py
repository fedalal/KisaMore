from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, UniqueConstraint
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
