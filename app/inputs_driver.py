from __future__ import annotations

from typing import Dict
from gpiozero import Button

class InputsDriver:
    """
    Драйвер цифровых входов (сухой контакт -> GPIO + GND).
    Используем pull_up=True, поэтому замкнут на GND => активен.
    """

    def __init__(self, name_to_gpio: Dict[str, int], bounce_time: float = 0.1):
        self._btn: Dict[str, Button] = {}
        for name, gpio in (name_to_gpio or {}).items():
            self._btn[str(name)] = Button(
                pin=int(gpio),
                pull_up=True,
                bounce_time=bounce_time,   # антидребезг/антинаводки
            )

    def snapshot(self) -> Dict[str, bool]:
        """
        Возвращает состояние:
        True  = контакт замкнут (датчик сработал)
        False = разомкнут
        """
        return {name: bool(btn.is_pressed) for name, btn in self._btn.items()}
