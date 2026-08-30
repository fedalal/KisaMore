from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Farm(Base):
    __tablename__ = "farms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    devices: Mapped[list["Device"]] = relationship(back_populates="farm")


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    software_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    racks_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    levels: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    farm: Mapped[Farm] = relationship(back_populates="devices")
    racks: Mapped[list["RackCurrent"]] = relationship(
        back_populates="device", cascade="all, delete-orphan"
    )


class RackCurrent(Base):
    __tablename__ = "rack_current"
    __table_args__ = (UniqueConstraint("device_id", "rack_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), index=True, nullable=False)
    rack_id: Mapped[int] = mapped_column(Integer, nullable=False)
    light_on: Mapped[bool] = mapped_column(Boolean, nullable=False)
    water_on: Mapped[bool] = mapped_column(Boolean, nullable=False)
    light_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    water_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    soil_moisture: Mapped[float | None] = mapped_column(Float, nullable=True)
    soil_temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    sensor_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    camera_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    device: Mapped[Device] = relationship(back_populates="racks")


class TelemetrySample(Base):
    __tablename__ = "telemetry_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), index=True, nullable=False)
    rack_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    light_on: Mapped[bool] = mapped_column(Boolean, nullable=False)
    water_on: Mapped[bool] = mapped_column(Boolean, nullable=False)
    soil_moisture: Mapped[float | None] = mapped_column(Float, nullable=True)
    soil_temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)


class Plant(Base):
    __tablename__ = "plants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    names: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    descriptions: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    grow_days: Mapped[int] = mapped_column(Integer, default=14, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    edge_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RackSlot(Base):
    __tablename__ = "rack_slots"
    __table_args__ = (UniqueConstraint("device_id", "rack_id", "slot_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), index=True, nullable=False)
    rack_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    slot_number: Mapped[int] = mapped_column(Integer, nullable=False)
    physical_status: Mapped[str] = mapped_column(String(24), default="available", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    edge_allocation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    requested_plant_id: Mapped[str | None] = mapped_column(ForeignKey("plants.id"), nullable=True)
    expected_available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RackPhoto(Base):
    __tablename__ = "rack_photos"
    __table_args__ = (UniqueConstraint("device_id", "rack_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), index=True, nullable=False)
    rack_id: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(40), default="image/jpeg", nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Planting(Base):
    __tablename__ = "plantings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("rack_slots.id"), index=True, nullable=False)
    plant_id: Mapped[str] = mapped_column(ForeignKey("plants.id"), index=True, nullable=False)
    planted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expected_harvest_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actual_harvest_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    cloud_allocation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    preferred_language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="customer", nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReservationRequest(Base):
    __tablename__ = "reservation_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), index=True, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(16), nullable=False)
    rack_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    slot_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    plant_id: Mapped[str | None] = mapped_column(ForeignKey("plants.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="waiting", index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Offer(Base):
    __tablename__ = "offers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    reservation_id: Mapped[str] = mapped_column(
        ForeignKey("reservation_requests.id"), unique=True, index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(16), nullable=False)
    rack_id: Mapped[int] = mapped_column(Integer, nullable=False)
    slot_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    plant_id: Mapped[str | None] = mapped_column(ForeignKey("plants.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Allocation(Base):
    __tablename__ = "allocations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), index=True, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(16), nullable=False)
    rack_id: Mapped[int] = mapped_column(Integer, nullable=False)
    slot_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    plant_id: Mapped[str | None] = mapped_column(ForeignKey("plants.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    allocation_id: Mapped[str] = mapped_column(ForeignKey("allocations.id"), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="test_paid", nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
