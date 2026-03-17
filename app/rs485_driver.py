from __future__ import annotations

from dataclasses import dataclass
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
    Драйвер для 16-канального RS485-реле и чтения Modbus-датчиков
    на том же RS485-порту.
    """

    def __init__(self, cfg: RS485Config):
        self.cfg = cfg
        self._io_lock = asyncio.Lock()
        self._instr = self._make_instrument(cfg.slave_id)

    def _make_instrument(self, slave_id: int) -> minimalmodbus.Instrument:
        instr = minimalmodbus.Instrument(self.cfg.port, int(slave_id))
        instr.mode = minimalmodbus.MODE_RTU

        instr.serial.baudrate = int(self.cfg.baudrate)
        instr.serial.bytesize = int(self.cfg.bytesize)
        instr.serial.stopbits = int(self.cfg.stopbits)
        instr.serial.timeout = float(self.cfg.timeout)

        parity = (self.cfg.parity or "N").upper()
        if parity == "N":
            instr.serial.parity = minimalmodbus.serial.PARITY_NONE
        elif parity == "E":
            instr.serial.parity = minimalmodbus.serial.PARITY_EVEN
        elif parity == "O":
            instr.serial.parity = minimalmodbus.serial.PARITY_ODD
        else:
            raise ValueError(f"Unsupported parity: {self.cfg.parity!r}. Use N/E/O.")

        instr.clear_buffers_before_each_transaction = True
        return instr

    def _reg_for_channel(self, channel: int) -> int:
        if not 1 <= channel <= 16:
            raise ValueError("channel must be in 1..16")
        return int(self.cfg.coil_base) + int(channel)

    def _set_relay_sync(self, channel: int, on: bool) -> None:
        reg = self._reg_for_channel(channel)
        value = RELAY_ON if on else RELAY_OFF
        self._instr.write_register(reg, value, functioncode=6)
        time.sleep(0.03)

    async def set_relay(self, channel: int, on: bool) -> None:
        async with self._io_lock:
            await asyncio.to_thread(self._set_relay_sync, channel, on)

    async def relay_on(self, channel: int) -> None:
        await self.set_relay(channel, True)

    async def relay_off(self, channel: int) -> None:
        await self.set_relay(channel, False)

    async def all_off(self):
        for ch in range(1, 17):
            try:
                await self.set_relay(ch, False)
            except Exception as e:
                print(f"[RS485] failed to turn off relay {ch}: {e}")

    @staticmethod
    def _to_signed_16(v: int) -> int:
        return v - 65536 if v > 32767 else v

    def _read_soil_sensor_sync(self, slave_id: int) -> tuple[float, float]:
        """
        Читает датчик почвы по Modbus RTU:
        регистры 0x0000..0x0002, используем:
          reg0 = влажность / 10
          reg1 = температура (signed int16) / 10
        """
        instr = self._make_instrument(slave_id)

        regs = instr.read_registers(
            registeraddress=0,
            number_of_registers=3,
            functioncode=3,
        )

        if not regs or len(regs) < 2:
            raise RuntimeError("Sensor returned not enough registers")

        moisture_raw = int(regs[0])
        temp_raw = int(regs[1])

        soil_moisture = moisture_raw / 10.0
        soil_temperature = self._to_signed_16(temp_raw) / 10.0

        return soil_moisture, soil_temperature

    async def read_soil_sensor(self, slave_id: int) -> tuple[float, float]:
        async with self._io_lock:
            return await asyncio.to_thread(self._read_soil_sensor_sync, slave_id)