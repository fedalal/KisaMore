from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..models import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TelegramUser(Base):
    __tablename__ = "telegram_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    marketplace_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), unique=True, index=True, nullable=True
    )
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    language_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    wallet: Mapped["WalletAccount"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class WalletAccount(Base):
    __tablename__ = "wallet_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_users.id"), unique=True, index=True, nullable=False
    )
    balance: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    user: Mapped[TelegramUser] = relationship(back_populates="wallet")


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("telegram_users.id"), index=True, nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_after: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    kind: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reference_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, nullable=False)


class StarPayment(Base):
    __tablename__ = "star_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("telegram_users.id"), index=True, nullable=False)
    telegram_payment_charge_id: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    provider_payment_charge_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    invoice_payload: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    stars_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    kisa_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="paid", index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class SocialReaction(Base):
    __tablename__ = "social_reactions"
    __table_args__ = (
        UniqueConstraint("user_id", "target_type", "target_id", "reaction"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("telegram_users.id"), index=True, nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    reaction: Mapped[str] = mapped_column(String(32), nullable=False)
    token_cost: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class SocialGift(Base):
    __tablename__ = "social_gifts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("telegram_users.id"), index=True, nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    gift_code: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    token_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, nullable=False)


class SocialComment(Base):
    __tablename__ = "social_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("telegram_users.id"), index=True, nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("social_comments.id"), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="published", index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SocialFollow(Base):
    __tablename__ = "social_follows"
    __table_args__ = (UniqueConstraint("user_id", "target_type", "target_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("telegram_users.id"), index=True, nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class TelegramConversationState(Base):
    __tablename__ = "telegram_conversation_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_users.id"), unique=True, index=True, nullable=False
    )
    mode: Mapped[str] = mapped_column(String(40), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class TelegramRentalRequest(Base):
    __tablename__ = "telegram_rental_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("telegram_users.id"), index=True, nullable=False)
    slot_id: Mapped[int] = mapped_column(ForeignKey("rack_slots.id"), index=True, nullable=False)
    plant_id: Mapped[str] = mapped_column(ForeignKey("plants.id"), index=True, nullable=False)
    price_kisa: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="requested", index=True, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class SocialReport(Base):
    __tablename__ = "social_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("telegram_users.id"), index=True, nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    reason: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="new", index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
