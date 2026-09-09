from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PlantingPhoto(Base):
    __tablename__ = "planting_photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    planting_id: Mapped[str] = mapped_column(ForeignKey("plantings.id"), index=True, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(40), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, nullable=False)
    uploaded_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    target_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(160), index=True, nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, nullable=False)
