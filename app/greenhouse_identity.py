"""Public-facing identity for a *local* KisaMore controller.

Each controller exposes its own display label so operators cannot confuse
different Raspberry Pis while controlling physical equipment.
"""
from __future__ import annotations

import os
import re
import socket


def greenhouse_identity() -> dict[str, str]:
    device_id = os.getenv("KISAMORE_DEVICE_ID", "").strip()
    hostname = socket.gethostname()
    override = os.getenv("KISAMORE_GREENHOUSE_NAME", "").strip()
    match = re.fullmatch(r"greenhouse-pi-0*(\d+)", device_id, re.IGNORECASE)
    number = int(match.group(1)) if match else None

    if override:
        name = override
    elif number is not None:
        name = f"Теплица №{number}"
    else:
        name = f"Теплица · {hostname}"

    return {
        "greenhouse_name": name,
        "greenhouse_device_id": device_id or "ID не настроен",
        "greenhouse_hostname": hostname,
    }


def template_identity_context(_request) -> dict[str, str]:
    return greenhouse_identity()
