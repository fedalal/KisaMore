from gpiozero import OutputDevice

class GPIODriver:
    """Управление релейной платой: relay_id (1..16) -> GPIO BCM pin."""

    def __init__(self, relay_to_gpio: dict[int, int], active_low: bool = True):
        self._relays: dict[int, OutputDevice] = {}
        for relay_id, gpio in relay_to_gpio.items():
            self._relays[int(relay_id)] = OutputDevice(
                int(gpio),
                active_high=not active_low,
                initial_value=False,
            )

    async def set_relay(self, relay_id: int, on: bool) -> None:
        dev = self._relays.get(int(relay_id))
        if not dev:
            return
        dev.on() if on else dev.off()
