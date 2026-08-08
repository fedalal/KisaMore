from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


Mode = Literal["manual", "schedule"]


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
    stream_url: str | None
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
