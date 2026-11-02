"""Persistent Lava.top orders, paid invoice deduplication, and membership entitlements."""
from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .models import Base

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

class LavaOrder(Base):
    __tablename__ = "lava_orders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    kisa_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    offer_id: Mapped[str] = mapped_column(String(36), nullable=False)
    provider_invoice_id: Mapped[str | None] = mapped_column(String(36), unique=True, index=True, nullable=True)
    checkout_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="created", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)

class LavaGrantedInvoice(Base):
    """An invoice can grant wallet funds or membership rights exactly once."""
    __tablename__ = "lava_granted_invoices"
    invoice_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_id: Mapped[str | None] = mapped_column(ForeignKey("lava_orders.id"), nullable=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(25), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)

class LavaMembership(Base):
    """Three battle entries per paid cycle, not Kisa in a wallet."""
    __tablename__ = "lava_memberships"
    parent_invoice_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    remaining_entries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    cycle_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_invoice_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)

class LavaMembershipEntry(Base):
    __tablename__ = "lava_membership_entries"
    entry_id: Mapped[str] = mapped_column(ForeignKey("plant_battle_entries.id"), primary_key=True)
    parent_invoice_id: Mapped[str] = mapped_column(ForeignKey("lava_memberships.parent_invoice_id"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
