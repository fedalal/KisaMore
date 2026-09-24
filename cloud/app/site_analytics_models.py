"""First-party analytics and durable website registration notifications."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .models import Base


class PageView(Base):
    __tablename__ = 'site_pageviews'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    visitor_id: Mapped[str] = mapped_column(String(36), index=True)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    path: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(100))
    medium: Mapped[str] = mapped_column(String(100))
    campaign: Mapped[str] = mapped_column(String(100))
    utm_content: Mapped[str] = mapped_column(String(100), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SiteRegistration(Base):
    __tablename__ = 'site_registrations'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), primary_key=True)
    visitor_id: Mapped[str | None] = mapped_column(String(36), index=True)
    source: Mapped[str] = mapped_column(String(100))
    medium: Mapped[str] = mapped_column(String(100))
    campaign: Mapped[str] = mapped_column(String(100))
    utm_content: Mapped[str] = mapped_column(String(100), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SiteRegistrationDelivery(Base):
    __tablename__ = 'site_registration_deliveries'
    __table_args__ = (UniqueConstraint('user_id', 'admin_user_id'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('site_registrations.user_id'))
    admin_user_id: Mapped[int] = mapped_column(ForeignKey('telegram_users.id'))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
