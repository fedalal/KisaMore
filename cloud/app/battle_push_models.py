"""FCM targets and durable push outbox; never store tokens in logs."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .models import Base

class BattlePushDevice(Base):
    __tablename__ = "battle_push_devices"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    token: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

class BattlePushDelivery(Base):
    __tablename__ = "battle_push_deliveries"
    __table_args__ = (UniqueConstraint("receipt_id","token_hash",name="uq_battle_push_receipt_device"),)
    id: Mapped[str] = mapped_column(String(36),primary_key=True)
    receipt_id: Mapped[str] = mapped_column(ForeignKey("battle_message_receipts.id"),index=True,nullable=False)
    token_hash: Mapped[str] = mapped_column(ForeignKey("battle_push_devices.token_hash"),index=True,nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer,nullable=False,default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(80))
