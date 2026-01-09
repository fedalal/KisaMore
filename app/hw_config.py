from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Dict
import os
import yaml

ALLOWED_GPIO_BCM = [4,5,6,12,13,16,17,18,19,20,21,22,23,24,25,26,27]

class RackHW(BaseModel):
    light_relay: int = Field(ge=1, le=16)
    water_relay: int = Field(ge=1, le=16)

class HWConfig(BaseModel):
    racks_count: int = Field(ge=1, le=16)
    relay_to_gpio: Dict[str, int] = Field(default_factory=dict)
    racks: Dict[str, RackHW] = Field(default_factory=dict)

    @field_validator("relay_to_gpio")
    @classmethod
    def validate_gpio(cls, v: Dict[str, int]):
        for relay_str, gpio in v.items():
            try:
                r = int(relay_str)
            except Exception:
                raise ValueError(f"relay_to_gpio key must be integer string, got {relay_str!r}")
            if r < 1 or r > 16:
                raise ValueError(f"relay_to_gpio key must be 1..16, got {relay_str}")
            if gpio not in ALLOWED_GPIO_BCM:
                raise ValueError(f"GPIO {gpio} is not allowed. Allowed: {ALLOWED_GPIO_BCM}")
        return v

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
            relay_to_gpio={},
            racks={str(i): RackHW(light_relay=i*2-1, water_relay=i*2) for i in range(1, 5)},
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
