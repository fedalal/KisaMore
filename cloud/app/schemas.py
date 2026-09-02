from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


Mode = Literal["manual", "schedule"]
ResourceType = Literal["slot", "rack"]
SUPPORTED_LANGUAGES = ("en", "ru", "zh", "de", "fr", "es", "it", "pt", "pl")


class PlantSnapshotIn(BaseModel):
    plant_id: str = Field(min_length=1, max_length=36)
    code: str = Field(min_length=1, max_length=80)
    names: dict[str, str] = Field(min_length=1)
    descriptions: dict[str, str] = Field(default_factory=dict)
    seed_image_name: str = Field(default="", max_length=255, pattern=r"^[^/\\]*$")
    microgreen_image_name: str = Field(default="", max_length=255, pattern=r"^[^/\\]*$")
    grow_days: int = Field(ge=1, le=365)
    active: bool = True
    updated_at: datetime | None = None


class PlantingSnapshotIn(BaseModel):
    planting_id: str = Field(min_length=1, max_length=36)
    plant_id: str = Field(min_length=1, max_length=36)
    planted_at: datetime
    expected_harvest_at: datetime
    actual_harvest_at: datetime | None = None
    status: Literal["planned", "growing", "ready", "harvested", "cancelled"]
    cloud_allocation_id: str | None = Field(default=None, max_length=36)


class RackSlotSnapshotIn(BaseModel):
    slot_number: int = Field(ge=1, le=6)
    status: Literal["available", "reserved", "growing", "ready", "maintenance", "disabled"]
    enabled: bool = True
    cloud_allocation_id: str | None = Field(default=None, max_length=36)
    requested_plant_id: str | None = Field(default=None, max_length=36)
    planting: PlantingSnapshotIn | None = None


class RackSnapshotIn(BaseModel):
    rack_id: int = Field(ge=1, le=16)
    light_on: bool
    water_on: bool
    light_mode: Mode
    water_mode: Mode
    soil_moisture: float | None = Field(default=None, ge=0, le=100)
    soil_temperature: float | None = Field(default=None, ge=-50, le=100)
    sensor_observed_at: datetime | None = None
    camera_id: str | None = Field(default=None, max_length=80)
    slots: list[RackSlotSnapshotIn] = Field(default_factory=list, max_length=6)

    @field_validator("sensor_observed_at")
    @classmethod
    def sensor_time_must_include_timezone(cls, value: datetime | None):
        if value is not None and value.tzinfo is None:
            raise ValueError("sensor_observed_at must include a timezone")
        return value


class EdgeSnapshotIn(BaseModel):
    observed_at: datetime
    software_version: str = Field(default="unknown", min_length=1, max_length=100)
    racks_count: int = Field(ge=1, le=16)
    levels: dict[str, bool] = Field(default_factory=dict)
    plants: list[PlantSnapshotIn] = Field(default_factory=list, max_length=500)
    racks: list[RackSnapshotIn] = Field(min_length=1, max_length=16)

    @field_validator("observed_at")
    @classmethod
    def observed_time_must_include_timezone(cls, value: datetime):
        if value.tzinfo is None:
            raise ValueError("observed_at must include a timezone")
        return value

    @model_validator(mode="after")
    def rack_ids_must_be_unique_and_in_range(self):
        rack_ids = [rack.rack_id for rack in self.racks]
        if len(rack_ids) != len(set(rack_ids)):
            raise ValueError("rack IDs must be unique")
        if any(rack_id > self.racks_count for rack_id in rack_ids):
            raise ValueError("rack ID exceeds racks_count")
        return self


class RackLiveOut(BaseModel):
    rack_id: int
    light_on: bool
    water_on: bool
    light_mode: str
    water_mode: str
    soil_moisture: float | None
    soil_temperature: float | None
    sensor_observed_at: datetime | None
    camera_id: str | None
    observed_at: datetime


class FarmLiveOut(BaseModel):
    farm_slug: str
    farm_name: str
    device_id: str
    device_name: str
    status: Literal["online", "offline", "waiting"]
    last_seen_at: datetime | None
    software_version: str | None
    racks_count: int
    racks: list[RackLiveOut]


class PlantPublicOut(BaseModel):
    id: str
    code: str
    names: dict[str, str]
    descriptions: dict[str, str]
    seed_image_name: str
    microgreen_image_name: str
    grow_days: int


class PlantingPublicOut(BaseModel):
    id: str
    plant_id: str
    planted_at: datetime
    expected_harvest_at: datetime
    status: str


class SlotPublicOut(BaseModel):
    rack_id: int
    slot_number: int
    status: str
    physical_status: str
    available: bool
    expected_available_at: datetime | None
    planting: PlantingPublicOut | None


class RackMarketOut(BaseModel):
    rack_id: int
    available_slots: int
    whole_rack_available: bool
    light_on: bool | None
    water_on: bool | None
    soil_moisture: float | None
    soil_temperature: float | None
    photo_url: str | None
    photo_captured_at: datetime | None
    slots: list[SlotPublicOut]


class FarmMarketOut(BaseModel):
    farm_slug: str
    farm_name: str
    device_id: str
    plants: list[PlantPublicOut]
    racks: list[RackMarketOut]


class RegisterIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=10, max_length=256)
    language: str = Field(default="en", max_length=10)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str):
        value = value.strip().lower()
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("invalid email address")
        return value

    @field_validator("language")
    @classmethod
    def supported_language(cls, value: str):
        if value not in SUPPORTED_LANGUAGES:
            raise ValueError("unsupported language")
        return value


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class LanguageIn(BaseModel):
    language: str = Field(max_length=10)

    @field_validator("language")
    @classmethod
    def supported_language(cls, value: str):
        if value not in SUPPORTED_LANGUAGES:
            raise ValueError("unsupported language")
        return value


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    preferred_language: str
    role: str
    email_verified: bool


class PurchaseIn(BaseModel):
    device_id: str = Field(min_length=1, max_length=80)
    resource_type: ResourceType
    rack_id: int = Field(ge=1, le=16)
    slot_number: int | None = Field(default=None, ge=1, le=6)
    plant_id: str | None = Field(default=None, max_length=36)
    offer_id: str | None = Field(default=None, max_length=36)

    @model_validator(mode="after")
    def target_matches_resource_type(self):
        if self.resource_type == "slot" and self.slot_number is None:
            raise ValueError("slot_number is required for a slot purchase")
        if self.resource_type == "rack" and self.slot_number is not None:
            raise ValueError("slot_number must be empty for a rack purchase")
        return self


class ReservationIn(BaseModel):
    device_id: str = Field(min_length=1, max_length=80)
    resource_type: ResourceType
    rack_id: int | None = Field(default=None, ge=1, le=16)
    slot_number: int | None = Field(default=None, ge=1, le=6)
    plant_id: str | None = Field(default=None, max_length=36)

    @model_validator(mode="after")
    def reservation_target_is_valid(self):
        if self.slot_number is not None and self.rack_id is None:
            raise ValueError("rack_id is required when slot_number is set")
        if self.resource_type == "rack" and self.slot_number is not None:
            raise ValueError("slot_number must be empty for a rack reservation")
        return self


class AllocationOut(BaseModel):
    id: str
    resource_type: str
    device_id: str
    rack_id: int
    slot_number: int | None
    plant_id: str | None
    status: str
    starts_at: datetime
    ends_at: datetime | None


class ReservationOut(BaseModel):
    id: str
    resource_type: str
    device_id: str
    rack_id: int | None
    slot_number: int | None
    plant_id: str | None
    status: str
    created_at: datetime


class OfferOut(BaseModel):
    id: str
    reservation_id: str
    resource_type: str
    device_id: str
    rack_id: int
    slot_number: int | None
    plant_id: str | None
    status: str
    expires_at: datetime


class NotificationOut(BaseModel):
    id: str
    kind: str
    payload: dict
    read_at: datetime | None
    created_at: datetime


class AccountOut(BaseModel):
    user: UserOut
    allocations: list[AllocationOut]
    reservations: list[ReservationOut]
    offers: list[OfferOut]
    notifications: list[NotificationOut]
