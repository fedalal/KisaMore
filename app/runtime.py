from __future__ import annotations
from typing import Optional
from .hw_config import HWConfig, load_config
from .gpio_driver import GPIODriver

cfg: Optional[HWConfig] = None
driver: Optional[GPIODriver] = None

def init_runtime(active_low: bool = True) -> None:
    global cfg, driver
    cfg = load_config()
    relay_to_gpio = {int(k): int(v) for k, v in (cfg.relay_to_gpio or {}).items()}
    driver = GPIODriver(relay_to_gpio=relay_to_gpio, active_low=active_low)
