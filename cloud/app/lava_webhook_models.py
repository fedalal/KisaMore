"""Durable inbox for Lava.top notifications; never grants credits until verified."""
from datetime import datetime, timezone
from sqlalchemy import DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from .models import Base

class LavaWebhookEvent(Base):
    __tablename__ = "lava_webhook_events"
    event_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    invoice_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="received_unprocessed", nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
