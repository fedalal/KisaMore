from __future__ import annotations

from typing import Optional, Any
from .hw_config import HWConfig, load_config
from .rs485_driver import RS485RelayDriver, RS485Config

cfg: Optional[HWConfig] = None
driver: Optional[Any] = None

def init_runtime(active_low: bool = True) -> None:
    global cfg, driver
    cfg = load_config()

    if not cfg.rs485:
        raise RuntimeError("RS485 config missing: add rs485 section to config/kisamore.yaml")

    r = cfg.rs485
    driver = RS485RelayDriver(RS485Config(
        port=r.port,
        baudrate=r.baudrate,
        parity=r.parity,
        stopbits=r.stopbits,
        bytesize=r.bytesize,
        slave_id=r.slave_id,
        coil_base=r.coil_base,
        timeout=r.timeout,
    ))

    print(f"[KisaMore] RS485 driver enabled on {r.port}, slave_id={r.slave_id}, coil_base={r.coil_base}")
