from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Dict, Optional, Literal
import os
import yaml


class CameraCaptureConfig(BaseModel):
    enabled: bool = True
    interval_seconds: int = Field(default=30, ge=5, le=86400)
    google_folder_id: Optional[str] = None
    credentials_file: Optional[str] = None
    token_file: Optional[str] = None

    # Качество JPEG
    jpeg_quality: int = Field(default=90, ge=30, le=100)

    # Разрешение камеры
    frame_width: int = Field(default=1280, ge=320, le=3840)
    frame_height: int = Field(default=720, ge=240, le=2160)

    # Делать фото только если на полке включён свет
    only_when_light_on: bool = True

    # Локальная очередь фото, которые не удалось загрузить в Google Drive.
    # После успешной загрузки файл из этой папки удаляется.
    pending_dir: str = "data/camera_pending"

class CameraHW(BaseModel):
    name: str = Field(default="", max_length=100)
    device: str = Field(default="/dev/video0", min_length=1, max_length=255)
    flip_vertical: bool = False
    flip_horizontal: bool = False
    warp_enabled: bool = False
    # 4 точки перспективного выравнивания в пикселях:
    # [left_top_x, left_top_y, right_top_x, right_top_y, right_bottom_x, right_bottom_y, left_bottom_x, left_bottom_y]
    warp_points: Optional[list[float]] = Field(default=None, min_length=8, max_length=8)


class RackHW(BaseModel):
    light_relay: int = Field(ge=1, le=16)
    water_relay: int = Field(ge=1, le=16)
    sensor_slave_id: Optional[int] = Field(default=None, ge=1, le=247)

    # Новая схема: полка выбирает камеру из общего списка камер.
    camera_id: Optional[str] = Field(default=None, max_length=64)

    # Старые поля оставлены для совместимости со старым kisamore.yaml.
    # При загрузке конфига они автоматически переносятся в секцию cameras.
    camera_device: Optional[str] = Field(default=None, max_length=255)
    camera_flip_vertical: bool = False
    camera_flip_horizontal: bool = False
    camera_warp_enabled: bool = False
    camera_warp_points: Optional[list[float]] = Field(default=None, min_length=8, max_length=8)

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

    # Общий список камер. Полки ссылаются на камеру через rack.camera_id.
    cameras: Dict[str, CameraHW] = Field(default_factory=dict)

    # RS485 settings (Modbus RTU)
    rs485: Optional[RS485Settings] = None

    # NEW: датчики уровня/входы (имя -> GPIO BCM)
    level_sensors: Dict[str, int] = Field(default_factory=dict)

    # Настройки автоматической отправки фото с камер в Google Drive
    camera_capture: CameraCaptureConfig = Field(default_factory=CameraCaptureConfig)

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

    @field_validator("racks")
    @classmethod
    def normalize_camera_devices(cls, v: Dict[str, RackHW]):
        for rack in v.values():
            if rack.camera_device is not None:
                cam = rack.camera_device.strip()
                rack.camera_device = cam or None
            if rack.camera_id is not None:
                cid = rack.camera_id.strip()
                rack.camera_id = cid or None
        return v

    @field_validator("cameras")
    @classmethod
    def normalize_cameras(cls, v: Dict[str, CameraHW]):
        for cam in v.values():
            cam.device = cam.device.strip()
            cam.name = cam.name.strip()
        return v

    @field_validator("level_sensors")
    @classmethod
    def validate_level_sensors(cls, v: Dict[str, int]):
        # минимальная валидация: GPIO BCM обычно 0..27 (для Pi 3/4)
        for name, gpio in (v or {}).items():
            try:
                g = int(gpio)
            except Exception:
                raise ValueError(f"level_sensors[{name!r}] must be int, got {gpio!r}")
            if g < 0 or g > 27:
                raise ValueError(f"level_sensors[{name!r}] must be 0..27 (BCM), got {g}")
        return v


def config_path() -> str:
    return os.getenv("KISAMORE_CONFIG", "config/kisamore.yaml")


def load_config() -> HWConfig:
    path = config_path()
    if not os.path.exists(path):
        cfg = HWConfig(
            racks_count=4,
            racks={str(i): RackHW(
                light_relay=i * 2 - 1,
                water_relay=i * 2,
                sensor_slave_id=i,
                camera_id=f"camera_{i}",
            ) for i in range(1, 5)},
            cameras={str(f"camera_{i}"): CameraHW(
                name=f"Камера {i}",
                device=f"/dev/video{i - 1}",
            ) for i in range(1, 5)},
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
            level_sensors={
                "level_1": 22,
                "level_2": 27,
                "level_3": 17,
            },
            camera_capture=CameraCaptureConfig(
                enabled=True,
                interval_seconds=30,
                google_folder_id=None,
                credentials_file=None,
                jpeg_quality=85,
            ),
        )
        save_config(cfg)
        return cfg

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    need_save = False

    if "camera_capture" not in data:
        need_save = True

    cfg = HWConfig.model_validate(data)

    # Миграция старой схемы: камера была внутри каждой полки.
    # Новая схема: камеры отдельно, полка хранит только camera_id.
    if not cfg.cameras:
        for rack_id, rack in cfg.racks.items():
            device = (rack.camera_device or "").strip()
            if not device:
                continue
            camera_id = f"camera_{rack_id}"
            cfg.cameras[camera_id] = CameraHW(
                name=f"Камера {rack_id}",
                device=device,
                flip_vertical=rack.camera_flip_vertical,
                flip_horizontal=rack.camera_flip_horizontal,
                warp_enabled=rack.camera_warp_enabled,
                warp_points=rack.camera_warp_points,
            )
            rack.camera_id = camera_id
            need_save = True


    for i in range(1, cfg.racks_count + 1):
        k = str(i)
        if k not in cfg.racks:
            cfg.racks[k] = RackHW(
                light_relay=1,
                water_relay=2,
                sensor_slave_id=i,
                camera_id=f"camera_{i}",
            )
            if f"camera_{i}" not in cfg.cameras:
                cfg.cameras[f"camera_{i}"] = CameraHW(
                    name=f"Камера {i}",
                    device=f"/dev/video{i - 1}",
                )
            need_save = True

    if not cfg.level_sensors:
        cfg.level_sensors = {
            "level_1": 22,
            "level_2": 27,
            "level_3": 17,
        }
        need_save = True

    if need_save:
        save_config(cfg)

    return cfg

def save_config(cfg: HWConfig) -> None:
    path = config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = cfg.model_dump()
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
