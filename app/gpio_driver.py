from __future__ import annotations

from gpiozero import OutputDevice


class GPIODriver:
    """Relay channel -> BCM GPIO, fail-safe OFF when pins are opened.

    Waveshare RPi Relay Board (B) is active LOW: HIGH=OFF, LOW=ON.
    Relay contacts must use COM/NO for OFF on power loss.
    """

    def __init__(self, relay_to_gpio: dict[int, int], active_low: bool = True):
        self._relays: dict[int, OutputDevice] = {}
        try:
            for relay_id, gpio in sorted(relay_to_gpio.items()):
                self._relays[int(relay_id)] = OutputDevice(
                    int(gpio),
                    active_high=not active_low,
                    initial_value=False,
                )
        except Exception:
            self.close()
            raise

    @property
    def channels(self) -> tuple[int, ...]:
        return tuple(sorted(self._relays))

    async def set_relay(self, relay_id: int, on: bool) -> None:
        # A misconfigured relay must fail loudly: silent no-ops can break watering.
        channel = int(relay_id)
        if channel not in self._relays:
            raise ValueError(f"GPIO relay channel {channel} is not configured")
        if on:
            self._relays[channel].on()
        else:
            self._relays[channel].off()

    def close(self) -> None:
        for dev in self._relays.values():
            try:
                dev.off()
                dev.close()
            except Exception:
                pass
        self._relays.clear()
