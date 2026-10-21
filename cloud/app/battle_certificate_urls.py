"""Public certificate host selection based on participant language.

ru.kisamore.farm is the Russian mirror. Keep the certificate path stable
so old QR links and printed certificates remain valid.
"""
from __future__ import annotations

from .config import get_settings


def certificate_base_url(
    participant_language: str | None,
    telegram_language: str | None = None,
) -> str:
    def code(raw: str | None) -> str:
        return (raw or "").strip().lower().replace("_", "-").split("-", 1)[0]

    if code(participant_language) == "ru" or code(telegram_language) == "ru":
        return "https://ru.kisamore.farm"
    return get_settings().public_base_url.rstrip("/")


def certificate_url(
    entry_id: str,
    participant_language: str | None,
    telegram_language: str | None = None,
) -> str:
    return (
        f"{certificate_base_url(participant_language, telegram_language)}"
        f"/api/v1/battle-certificate/{entry_id}"
    )
