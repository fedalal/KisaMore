from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Dict, Optional, Literal
import os
import yaml


class RackHW(BaseModel):
    light_relay: int = Field(ge=1, le=16)
    water_relay: int = Field(ge=1, le=16)


class RS485Settings(BaseModel):
    port: str = Field(min_length=1)                 # "/dev/ttyUSB0" или "COM3"
    baudrate: int = Field(default=9600, ge=1200, le=115200)
    parity: Literal["N", "E", "O"] = "N"
    stopbits: int = Field(default=1, ge=1, le=2)
    bytesize: int = Field(default=8, ge=5, le=8)
    slave_id: int = Field(default=1, ge=1, le=247)
    coil_base: int = Field(default=0, ge=0, le=1)   # 0 или 1
    timeout: float = Field(default=1.0, ge=0.1, le=10.0)


class HWConfig(BaseModel):
    racks_count: int = Field(ge=1, le=16)
    racks: Dict[str, RackHW] = Field(default_factory=dict)

    # RS485 settings (Modbus RTU)
    rs485: Optional[RS485Settings] = None

    @field_validator("racks")
    @classmethod
    def validate_racks(cls, v: Dict[str, RackHW]):
        for rack_str in v.keys():
            try:
                rid = int(rack_str)
            except Exception:
                raise ValueError(f"rack id must be integer string, got {rack_str!r}")
            if rid < 1 or rid > 16:
                raise ValueError(f"rack id must be 1..16, got {rack_str}")
        return v


def config_path() -> str:
    return os.getenv("KISAMORE_CONFIG", "config/kisamore.yaml")


def load_config() -> HWConfig:
    path = config_path()
    if not os.path.exists(path):
        cfg = HWConfig(
            racks_count=4,
            racks={str(i): RackHW(light_relay=i * 2 - 1, water_relay=i * 2) for i in range(1, 5)},
            rs485=RS485Settings(
                port="/dev/ttyUSB0",
                baudrate=9600,
                parity="N",
                stopbits=1,
                bytesize=8,
                slave_id=1,
                coil_base=0,
                timeout=1.0,
            ),
        )
        save_config(cfg)
        return cfg

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    cfg = HWConfig.model_validate(data)

    for i in range(1, cfg.racks_count + 1):
        k = str(i)
        if k not in cfg.racks:
            cfg.racks[k] = RackHW(light_relay=1, water_relay=2)

    return cfg


def save_config(cfg: HWConfig) -> None:
    path = config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = cfg.model_dump()
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
