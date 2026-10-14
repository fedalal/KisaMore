"""Server-side activity records, linked to a user only when authenticated."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class AppActivityEvent(Base):
    __tablename__ = "app_activity_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    installation_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    screen: Mapped[str] = mapped_column(String(20), nullable=False)
    label: Mapped[str] = mapped_column(String(48), nullable=False, default="")
    app_version: Mapped[str] = mapped_column(String(32), nullable=False)
    android_version: Mapped[str] = mapped_column(String(24), nullable=False)
    seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
