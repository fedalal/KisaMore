from pydantic import BaseModel, Field
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

    # Подсказки для UI по расписанию:
    # - *_until: если устройство сейчас включено (и мы внутри интервала расписания) — до какого времени будет работать ("HH:MM")
    # - *_next: если сейчас выключено — когда включится в следующий раз (например "Пн 08:00")
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

    # Старые поля оставлены в ответе API для совместимости.
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

class HWConfigOut(BaseModel):
    racks_count: int 
    racks: Dict[str, RackHWOut] = Field(default_factory=dict)
    cameras: Dict[str, CameraHWOut] = Field(default_factory=dict)
