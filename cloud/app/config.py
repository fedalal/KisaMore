from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip().rstrip("/") for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    database_url: str
    cors_origins: tuple[str, ...]
    offline_after_seconds: int
    bootstrap_farm_slug: str
    bootstrap_farm_name: str
    bootstrap_device_id: str
    bootstrap_device_name: str
    bootstrap_device_token: str
    public_hls_base_url: str


@lru_cache
def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv(
            "KISAMORE_DATABASE_URL",
            "sqlite+aiosqlite:///./cloud-data/kisamore-cloud.db",
        ).strip(),
        cors_origins=_csv(
            os.getenv(
                "KISAMORE_CORS_ORIGINS",
                "https://kisamore-platform.fedalal.chatgpt.site",
            )
        ),
        offline_after_seconds=max(
            30, int(os.getenv("KISAMORE_OFFLINE_AFTER_SECONDS", "120"))
        ),
        bootstrap_farm_slug=os.getenv("KISAMORE_BOOTSTRAP_FARM_SLUG", "demo-farm").strip(),
        bootstrap_farm_name=os.getenv("KISAMORE_BOOTSTRAP_FARM_NAME", "KisaMore Farm").strip(),
        bootstrap_device_id=os.getenv("KISAMORE_BOOTSTRAP_DEVICE_ID", "").strip(),
        bootstrap_device_name=os.getenv("KISAMORE_BOOTSTRAP_DEVICE_NAME", "Greenhouse Pi").strip(),
        bootstrap_device_token=os.getenv("KISAMORE_BOOTSTRAP_DEVICE_TOKEN", "").strip(),
        public_hls_base_url=(
            os.getenv("KISAMORE_PUBLIC_HLS_BASE_URL", "/hls").strip().rstrip("/")
            or "/hls"
        ),
    )
