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

class ManualSetIn(BaseModel):
    on: bool

class ModeSetIn(BaseModel):
    mode: Mode

class RackHWOut(BaseModel):
    light_relay: int
    water_relay: int

class HWConfigOut(BaseModel):
    racks_count: int 
    racks: Dict[str, RackHWOut] = Field(default_factory=dict)
