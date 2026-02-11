from __future__ import annotations

from typing import Dict
import time
import RPi.GPIO as GPIO


class InputsDriver:
    """
    Датчики уровня = сухой контакт между GPIO и GND.
    Используем PUD_UP, поэтому:
      - разомкнут => 1
      - замкнут   => 0
    snapshot() возвращает True, когда датчик СРАБОТАЛ (контакт замкнут).
    """

    def __init__(self, name_to_gpio: Dict[str, int], debounce_s: float = 0.05):
        self._pins: Dict[str, int] = {str(k): int(v) for k, v in (name_to_gpio or {}).items()}
        self._debounce_s = float(debounce_s)

        GPIO.setmode(GPIO.BCM)
        for _, pin in self._pins.items():
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    def _read_stable(self, pin: int) -> int:
        """Простая антидребезг/антинаводка: 3 чтения подряд должны совпасть."""
        a = GPIO.input(pin)
        time.sleep(self._debounce_s)
        b = GPIO.input(pin)
        time.sleep(self._debounce_s)
        c = GPIO.input(pin)
        return a if (a == b == c) else c

    def snapshot(self) -> Dict[str, bool]:
        out: Dict[str, bool] = {}
        for name, pin in self._pins.items():
            v = self._read_stable(pin)
            out[name] = (v == 0)  # замкнут на GND => сработал
        return out

    def close(self) -> None:
        # аккуратно освободить только наши пины
        for _, pin in self._pins.items():
            try:
                GPIO.cleanup(pin)
            except Exception:
                pass
