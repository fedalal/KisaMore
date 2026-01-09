import os
import sys

def is_raspberry_pi() -> bool:
    force = os.getenv("KISAMORE_FORCE_GPIO", "").strip().lower()
    if force in ("1", "true", "yes"):
        return True
    if force in ("0", "false", "no"):
        return False

    if sys.platform.startswith("win"):
        return False

    try:
        with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
            cpuinfo = f.read().lower()
        return ("raspberry pi" in cpuinfo) or ("bcm" in cpuinfo)
    except Exception:
        return False
