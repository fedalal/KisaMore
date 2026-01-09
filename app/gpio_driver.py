from typing import Any

class GPIODriver:
    """
    Управление релейной платой: relay_id (1..16) -> GPIO BCM pin.
    На НЕ-Raspberry Pi работает в режиме заглушки.
    """

    def __init__(self, relay_to_gpio: dict[int, int], active_low: bool = True, enabled: bool = True):
        self.enabled = enabled
        self._relays: dict[int, Any] = {}

        if not self.enabled:
            return

        from gpiozero import OutputDevice

        for relay_id, gpio in relay_to_gpio.items():
            self._relays[int(relay_id)] = OutputDevice(
                int(gpio),
                active_high=not active_low,
                initial_value=False,
            )

    async def set_relay(self, relay_id: int, on: bool) -> None:
        if not self.enabled:
            return
        dev = self._relays.get(int(relay_id))
        if not dev:
            return
        dev.on() if on else dev.off()
