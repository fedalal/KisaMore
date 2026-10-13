"""Automatic Battle notifications, user preferences and per-device FCM outbox."""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class BattleNotificationPreferences(Base):
    __tablename__ = "battle_notification_preferences"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    start: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    end_soon: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    finished: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    winner: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    resource_low: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    action_done: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    new_battles: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class BattleEventNotification(Base):
    __tablename__ = "battle_event_notifications"
    __table_args__ = (Index("ix_battle_event_notifications_user_created", "user_id", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_key: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    battle_id: Mapped[str] = mapped_column(ForeignKey("plant_battles.id"), index=True, nullable=False)
    entry_id: Mapped[str | None] = mapped_column(ForeignKey("plant_battle_entries.id"), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BattleEventPushDelivery(Base):
    __tablename__ = "battle_event_push_deliveries"
    __table_args__ = (UniqueConstraint("notification_id","token_hash",name="uq_battle_event_push_device"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    notification_id: Mapped[str] = mapped_column(ForeignKey("battle_event_notifications.id"),index=True,nullable=False)
    token_hash: Mapped[str] = mapped_column(ForeignKey("battle_push_devices.token_hash"),index=True,nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0,nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(80), nullable=True)
