from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime, timezone
from typing import List, Literal, Dict, Optional

Mode = Literal["manual", "schedule"]


class TimeRange(BaseModel):
    start: str
    end: str


class ChannelSchedule(BaseModel):
    mon: List[TimeRange] = Field(default_factory=list)
    tue: List[TimeRange] = Field(default_factory=list)
    wed: List[TimeRange] = Field(default_factory=list)
    thu: List[TimeRange] = Field(default_factory=list)
    fri: List[TimeRange] = Field(default_factory=list)
    sat: List[TimeRange] = Field(default_factory=list)
    sun: List[TimeRange] = Field(default_factory=list)


class RackSchedulePayload(BaseModel):
    light: ChannelSchedule = Field(default_factory=ChannelSchedule)
    water: ChannelSchedule = Field(default_factory=ChannelSchedule)


class RackStateOut(BaseModel):
    rack_id: int
    light_on: bool
    water_on: bool
    light_mode: Mode
    water_mode: Mode

    light_until: Optional[str] = None
    light_next: Optional[str] = None
    water_until: Optional[str] = None
    water_next: Optional[str] = None

    soil_moisture: Optional[float] = None
    soil_temperature: Optional[float] = None

    camera_id: Optional[str] = None
    camera_device: Optional[str] = None
    camera_flip_vertical: bool = False
    camera_flip_horizontal: bool = False
    camera_warp_enabled: bool = False
    camera_warp_points: Optional[List[float]] = None


class ManualSetIn(BaseModel):
    on: bool


class ModeSetIn(BaseModel):
    mode: Mode


class RackHWOut(BaseModel):
    light_relay: int
    water_relay: int
    sensor_slave_id: Optional[int] = None
    camera_id: Optional[str] = None

    camera_device: Optional[str] = None
    camera_flip_vertical: bool = False
    camera_flip_horizontal: bool = False
    camera_warp_enabled: bool = False
    camera_warp_points: Optional[List[float]] = None


class CameraHWOut(BaseModel):
    name: str = ""
    device: str
    flip_vertical: bool = False
    flip_horizontal: bool = False
    warp_enabled: bool = False
    warp_points: Optional[List[float]] = None
    autofocus_enabled: bool = True
    focus_absolute: Optional[int] = None
    white_balance_auto: bool = True
    white_balance_temperature: Optional[int] = None


class HWConfigOut(BaseModel):
    racks_count: int
    racks: Dict[str, RackHWOut] = Field(default_factory=dict)
    cameras: Dict[str, CameraHWOut] = Field(default_factory=dict)


PlantingStatus = Literal["planned", "growing", "ready", "harvested", "cancelled"]
SlotStatus = Literal["available", "reserved", "growing", "ready", "maintenance", "disabled"]


class WateringScheduleItem(BaseModel):
    time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    ml: int = Field(ge=1, le=2000)


class ExtraWateringOption(BaseModel):
    ml: int = Field(ge=1, le=2000)
    price_kisa: int = Field(ge=0, le=1_000_000)


class PlantIn(BaseModel):
    code: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    names: Dict[str, str] = Field(min_length=1)
    descriptions: Dict[str, str] = Field(default_factory=dict)
    seed_image_name: str = Field(default="", max_length=255, pattern=r"^[^/\\]*$")
    microgreen_image_name: str = Field(default="", max_length=255, pattern=r"^[^/\\]*$")
    grow_days: int = Field(default=14, ge=1, le=365)
    rental_price_kisa: Optional[int] = Field(default=None, ge=0, le=1_000_000)
    watering_schedule: List[WateringScheduleItem] = Field(default_factory=list, max_length=12)
    watering_adjustment_limit_percent: int = Field(default=20, ge=0, le=50)
    watering_adjustment_step_percent: int = Field(default=10, ge=1, le=25)
    watering_min_interval_minutes: int = Field(default=240, ge=30, le=1440)
    extra_watering_options: List[ExtraWateringOption] = Field(default_factory=list, max_length=10)
    active: bool = True

    @field_validator("watering_schedule")
    @classmethod
    def watering_times_must_be_unique(cls, value):
        times = [item.time for item in value]
        if len(times) != len(set(times)):
            raise ValueError("watering times must be unique")
        return sorted(value, key=lambda item: item.time)

    @field_validator("extra_watering_options")
    @classmethod
    def extra_watering_volumes_must_be_unique(cls, value):
        volumes = [item.ml for item in value]
        if len(volumes) != len(set(volumes)):
            raise ValueError("extra watering volumes must be unique")
        return sorted(value, key=lambda item: item.ml)

    @model_validator(mode="after")
    def watering_adjustment_is_consistent(self):
        if self.watering_adjustment_limit_percent and self.watering_adjustment_step_percent > self.watering_adjustment_limit_percent:
            raise ValueError("watering adjustment step cannot exceed the limit")
        return self


class PlantOut(PlantIn):
    id: str
    rental_price_kisa: int
    created_at: datetime
    updated_at: datetime


class PlantingCreateIn(BaseModel):
    rack_id: int = Field(ge=1, le=16)
    slot_number: int = Field(ge=1, le=6)
    plant_id: str = Field(min_length=1, max_length=36)
    planted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    expected_harvest_at: Optional[datetime] = None
    notes: str = Field(default="", max_length=2000)


class PlantingUpdateIn(BaseModel):
    status: Optional[PlantingStatus] = None
    expected_harvest_at: Optional[datetime] = None
    actual_harvest_at: Optional[datetime] = None
    notes: Optional[str] = Field(default=None, max_length=2000)


class SlotUpdateIn(BaseModel):
    status: SlotStatus
    enabled: Optional[bool] = None


class PlantingOut(BaseModel):
    id: str
    plant_id: str
    plant_code: str
    plant_names: Dict[str, str]
    planted_at: datetime
    expected_harvest_at: datetime
    actual_harvest_at: Optional[datetime]
    status: PlantingStatus
    cloud_allocation_id: Optional[str]
    notes: str


class RackSlotOut(BaseModel):
    id: int
    rack_id: int
    slot_number: int
    status: SlotStatus
    enabled: bool
    cloud_allocation_id: Optional[str]
    requested_plant_id: Optional[str]
    current_planting: Optional[PlantingOut]
