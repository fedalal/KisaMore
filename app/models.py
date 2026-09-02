from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Boolean, JSON
from sqlalchemy import Float, DateTime, ForeignKey, Text, UniqueConstraint
from datetime import datetime, timezone


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

class Base(DeclarativeBase):
    pass

class RackSensorHistory(Base):
    __tablename__ = "rack_sensor_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rack_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    sensor_slave_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    soil_moisture: Mapped[float | None] = mapped_column(Float, nullable=True)
    soil_temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True, nullable=False)

class RackState(Base):
    __tablename__ = "rack_state"
    rack_id: Mapped[int] = mapped_column(Integer, primary_key=True)

    light_on: Mapped[bool] = mapped_column(Boolean, default=False)
    water_on: Mapped[bool] = mapped_column(Boolean, default=False)

    light_mode: Mapped[str] = mapped_column(String, default="schedule")
    water_mode: Mapped[str] = mapped_column(String, default="schedule")

class RackSchedule(Base):
    __tablename__ = "rack_schedule"
    rack_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    schedule_json: Mapped[dict] = mapped_column(JSON, default=dict)


class Plant(Base):
    """Plant catalog managed by the greenhouse operator.

    Translated names and descriptions are kept as JSON maps (``{"en": ...}``)
    so the edge controller stays independent from the set of website locales.
    """

    __tablename__ = "plants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    names: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    descriptions: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    seed_image_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    microgreen_image_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    grow_days: Mapped[int] = mapped_column(Integer, default=14, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow_naive, onupdate=_utcnow_naive, nullable=False
    )


class RackSlot(Base):
    """One of the six physical container positions on a rack."""

    __tablename__ = "rack_slots"
    __table_args__ = (UniqueConstraint("rack_id", "slot_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rack_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    slot_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="available", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    cloud_allocation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    requested_plant_id: Mapped[str | None] = mapped_column(
        ForeignKey("plants.id"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow_naive, onupdate=_utcnow_naive, nullable=False
    )


class Planting(Base):
    """Historical planting record; completed records are never overwritten."""

    __tablename__ = "plantings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("rack_slots.id"), index=True, nullable=False)
    plant_id: Mapped[str] = mapped_column(ForeignKey("plants.id"), index=True, nullable=False)
    planted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expected_harvest_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    actual_harvest_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="growing", index=True, nullable=False)
    cloud_allocation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow_naive, onupdate=_utcnow_naive, nullable=False
    )
