from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..models import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TelegramBroadcast(Base):
    __tablename__ = "telegram_broadcasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    language_code: Mapped[str] = mapped_column(String(16), default="all", index=True, nullable=False)
    text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    question: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_mode: Mapped[str] = mapped_column(String(16), default="none", nullable=False)
    show_results_to_users: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    photo_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True, nullable=False)
    total_recipients: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sent_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TelegramBroadcastOption(Base):
    __tablename__ = "telegram_broadcast_options"
    __table_args__ = (UniqueConstraint("broadcast_id", "position"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    broadcast_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_broadcasts.id"), index=True, nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(String(120), nullable=False)


class TelegramBroadcastDelivery(Base):
    __tablename__ = "telegram_broadcast_deliveries"
    __table_args__ = (UniqueConstraint("broadcast_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    broadcast_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_broadcasts.id"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("telegram_users.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    telegram_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TelegramBroadcastAnswer(Base):
    __tablename__ = "telegram_broadcast_answers"
    __table_args__ = (UniqueConstraint("broadcast_id", "user_id", "option_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    broadcast_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_broadcasts.id"), index=True, nullable=False
    )
    option_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_broadcast_options.id"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("telegram_users.id"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
