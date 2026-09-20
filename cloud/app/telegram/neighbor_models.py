from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..models import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TelegramNeighborNotifierState(Base):
    __tablename__ = "telegram_neighbor_notifier_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TelegramNeighborDelivery(Base):
    __tablename__ = "telegram_neighbor_deliveries"
    __table_args__ = (UniqueConstraint("planting_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    planting_id: Mapped[str] = mapped_column(
        ForeignKey("plantings.id"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_users.id"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending", index=True, nullable=False
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    annotated_photo_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    card_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class TelegramNeighborReadyDelivery(Base):
    __tablename__ = "telegram_neighbor_ready_deliveries"
    __table_args__ = (UniqueConstraint("planting_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    planting_id: Mapped[str] = mapped_column(
        ForeignKey("plantings.id"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_users.id"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending", index=True, nullable=False
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    annotated_photo_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    card_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
