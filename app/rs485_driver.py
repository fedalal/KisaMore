# rs485_driver.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import asyncio
import time
import minimalmodbus


RELAY_ON = 0x0100
RELAY_OFF = 0x0200


@dataclass(frozen=True)
class RS485Config:
    port: str
    baudrate: int = 9600
    parity: str = "N"      # "N", "E", "O"
    stopbits: int = 1
    bytesize: int = 8
    slave_id: int = 1
    coil_base: int = 0     # смещение регистра (если вдруг нужно)
    timeout: float = 1.0


class RS485RelayDriver:
    """
    Драйвер для 16-канального RS485-реле, которое управляется через Modbus RTU
    командой FC06 (Write Single Register), как в твоей документации.
    """

    def __init__(self, cfg: RS485Config):
        self.cfg = cfg

        instr = minimalmodbus.Instrument(cfg.port, cfg.slave_id)  # COM8, slave=1
        instr.mode = minimalmodbus.MODE_RTU

        # serial params
        instr.serial.baudrate = int(cfg.baudrate)
        instr.serial.bytesize = int(cfg.bytesize)
        instr.serial.stopbits = int(cfg.stopbits)
        instr.serial.timeout = float(cfg.timeout)

        parity = (cfg.parity or "N").upper()
        if parity == "N":
            instr.serial.parity = minimalmodbus.serial.PARITY_NONE
        elif parity == "E":
            instr.serial.parity = minimalmodbus.serial.PARITY_EVEN
        elif parity == "O":
            instr.serial.parity = minimalmodbus.serial.PARITY_ODD
        else:
            raise ValueError(f"Unsupported parity: {cfg.parity!r}. Use N/E/O.")

        # полезно для USB-RS485
        instr.clear_buffers_before_each_transaction = True

        self._instr = instr

    def _reg_for_channel(self, channel: int) -> int:
        # По твоим примерам: ch=1 -> reg=0x0001, ch=2 -> reg=0x0002
        if not 1 <= channel <= 16:
            raise ValueError("channel must be in 1..16")
        return int(self.cfg.coil_base) + int(channel)

    def _set_relay_sync(self, channel: int, on: bool) -> None:
        """Синхронная запись (используется внутри to_thread, чтобы не блокировать event loop)."""
        reg = self._reg_for_channel(channel)
        value = RELAY_ON if on else RELAY_OFF

        # FC06: Write Single Register
        self._instr.write_register(reg, value, functioncode=6)

        # небольшая пауза, чтобы модуль успевал (часто помогает)
        time.sleep(0.03)

    async def set_relay(self, channel: int, on: bool) -> None:
        """Асинхронный API проекта: safe для FastAPI/scheduler."""
        await asyncio.to_thread(self._set_relay_sync, channel, on)

    async def relay_on(self, channel: int) -> None:
        await self.set_relay(channel, True)

    async def relay_off(self, channel: int) -> None:
        await self.set_relay(channel, False)

    async def all_off(self):
        """
        Гарантированно выключает все 16 реле.
        Используется при старте приложения (fail-safe).
        """
        for ch in range(1, 17):
            try:
                await self.set_relay(ch, False)
            except Exception as e:
                # не падаем при старте из-за одного реле
                print(f"[RS485] failed to turn off relay {ch}: {e}")
