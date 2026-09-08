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
    session_days: int
    cookie_secure: bool
    offer_hours: int
    photo_dir: str
    photo_max_bytes: int
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str
    mqtt_password: str
    mqtt_tls: bool
    mqtt_topic_prefix: str
    mqtt_message_ttl_seconds: int


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
        session_days=max(1, int(os.getenv("KISAMORE_SESSION_DAYS", "30"))),
        cookie_secure=os.getenv("KISAMORE_COOKIE_SECURE", "true").strip().lower()
        not in ("0", "false", "no"),
        offer_hours=max(1, int(os.getenv("KISAMORE_OFFER_HOURS", "24"))),
        photo_dir=os.getenv("KISAMORE_PHOTO_DIR", "/srv/kisamore/data/photos").strip(),
        photo_max_bytes=max(
            100_000, int(os.getenv("KISAMORE_PHOTO_MAX_BYTES", "2097152"))
        ),
        mqtt_host=os.getenv("KISAMORE_MQTT_HOST", "").strip(),
        mqtt_port=int(os.getenv("KISAMORE_MQTT_PORT", "1883")),
        mqtt_username=os.getenv("KISAMORE_MQTT_USERNAME", "").strip(),
        mqtt_password=os.getenv("KISAMORE_MQTT_PASSWORD", "").strip(),
        mqtt_tls=os.getenv("KISAMORE_MQTT_TLS", "false").strip().lower()
        in ("1", "true", "yes", "on"),
        mqtt_topic_prefix=(
            os.getenv("KISAMORE_MQTT_TOPIC_PREFIX", "kisamore").strip().strip("/")
            or "kisamore"
        ),
        mqtt_message_ttl_seconds=max(
            30, int(os.getenv("KISAMORE_MQTT_MESSAGE_TTL_SECONDS", "300"))
        ),
    )
