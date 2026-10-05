from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


BATTLE_BLOCKING_STATUSES = ("open", "ready_to_plant", "planting", "growing", "judging")
BATTLE_JOINABLE_STATUSES = ("open",)


class PlantBattle(Base):
    __tablename__ = "plant_battles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), index=True, nullable=False)
    rack_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    plant_id: Mapped[str] = mapped_column(ForeignKey("plants.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(180), default="Plant Battle", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="open", index=True, nullable=False)
    entry_price_kisa: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    max_entries: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    water_budget_ml: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    nutrient_budget_ml: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    shade_budget_minutes: Mapped[int] = mapped_column(Integer, default=480, nullable=False)
    winner_reward_kisa: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    winner_entry_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    planted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def resource_type(self) -> str:
        return "rack"

    @property
    def slot_number(self):
        return None


class PlantBattleEntry(Base):
    __tablename__ = "plant_battle_entries"
    __table_args__ = (
        UniqueConstraint("battle_id", "slot_number", name="uq_plant_battle_slot"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    battle_id: Mapped[str] = mapped_column(ForeignKey("plant_battles.id"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    telegram_user_id: Mapped[int] = mapped_column(ForeignKey("telegram_users.id"), index=True, nullable=False)
    slot_number: Mapped[int] = mapped_column(Integer, nullable=False)
    price_kisa: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True, nullable=False)
    allocation_id: Mapped[str | None] = mapped_column(ForeignKey("allocations.id"), index=True, nullable=True)
    planting_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    water_used_ml: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    nutrient_used_ml: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    shade_used_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_winner: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    badge: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PlantBattleAction(Base):
    __tablename__ = "plant_battle_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    entry_id: Mapped[str] = mapped_column(ForeignKey("plant_battle_entries.id"), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class PlantBattlePrediction(Base):
    __tablename__ = "plant_battle_predictions"
    __table_args__ = (
        UniqueConstraint("battle_id", "user_id", name="uq_plant_battle_prediction_user"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    battle_id: Mapped[str] = mapped_column(ForeignKey("plant_battles.id"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    entry_id: Mapped[str] = mapped_column(ForeignKey("plant_battle_entries.id"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
