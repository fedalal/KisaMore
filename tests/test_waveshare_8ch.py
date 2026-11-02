"""Tests run without actual Raspberry Pi GPIO pins or an RS485 adapter."""
import asyncio
import importlib
import sys
import types
import unittest
from unittest.mock import patch

from app.hw_config import HWConfig, RackHW, GPIORelaySettings, WAVESHARE_8CH_BCM
from pydantic import ValidationError


def four_racks():
    return {str(i): RackHW(light_relay=2*i-1, water_relay=2*i)
            for i in range(1, 5)}


class ConfigurationTests(unittest.TestCase):
    def test_existing_greenhouse_stays_rs485(self):
        cfg = HWConfig(racks_count=1, racks={"1": RackHW(light_relay=1, water_relay=2)})
        self.assertEqual(cfg.relay_backend, "rs485")

    def test_waveshare_pins_and_four_racks(self):
        cfg = HWConfig(racks_count=4, racks=four_racks(), relay_backend="gpio",
                       level_sensors={"level_1": 22, "level_2": 27, "level_3": 17})
        self.assertEqual(cfg.gpio_relays.channels, WAVESHARE_8CH_BCM)
        self.assertEqual(tuple(cfg.gpio_relays.channels.values()), (5, 6, 13, 16, 19, 20, 21, 26))
        self.assertTrue(cfg.gpio_relays.active_low)

    def test_input_pin_conflict_rejected(self):
        with self.assertRaises(ValidationError):
            HWConfig(racks_count=4, racks=four_racks(), relay_backend="gpio",
                     level_sensors={"level_1": 5})

    def test_gpio_duplicate_pin_rejected(self):
        with self.assertRaises(ValidationError):
            HWConfig(racks_count=4, racks=four_racks(), relay_backend="gpio",
                     gpio_relays=GPIORelaySettings(channels={1: 5, 2: 5}))

    def test_gpio_missing_required_channel_rejected(self):
        with self.assertRaises(ValidationError):
            HWConfig(racks_count=4, racks=four_racks(), relay_backend="gpio",
                     gpio_relays=GPIORelaySettings(channels={1: 5, 2: 6}))


class LightOnlyTests(unittest.TestCase):
    def test_four_lights_with_no_water(self):
        from pathlib import Path
        import yaml
        config = yaml.safe_load(
            (Path(__file__).resolve().parents[1] /
             "docs/new-greenhouse-waveshare-B.yaml").read_text()
        )
        cfg = HWConfig.model_validate(config)
        self.assertEqual(cfg.relay_backend, "gpio")
        self.assertIsNone(cfg.rs485)
        self.assertEqual(
            [(r.light_relay, r.water_relay) for r in cfg.racks.values()],
            [(1, None), (2, None), (3, None), (4, None)],
        )

    def test_water_manual_is_rejected_before_db_write(self):
        from fastapi import HTTPException
        from app.schemas import ManualSetIn, ModeSetIn
        # Cloud CI image lacks physical Pi packages; stub imports, not I/O.
        with patch.dict(sys.modules, {
            "minimalmodbus": types.ModuleType("minimalmodbus"),
            "gpiozero": types.SimpleNamespace(OutputDevice=object),
        }):
            from app import runtime, routes_manual
        cfg = HWConfig(
            racks_count=1, relay_backend="gpio",
            racks={"1": RackHW(light_relay=1, water_relay=None)},
        )
        saved_cfg, saved_driver = runtime.cfg, runtime.driver
        try:
            runtime.cfg = cfg
            runtime.driver = object()
            with self.assertRaises(HTTPException) as e:
                asyncio.run(routes_manual.manual_water(1, ManualSetIn(on=True)))
            self.assertEqual(e.exception.status_code, 409)
            with self.assertRaises(HTTPException) as e:
                asyncio.run(routes_manual.set_water_mode(1, ModeSetIn(mode="manual")))
            self.assertEqual(e.exception.status_code, 409)
        finally:
            runtime.cfg, runtime.driver = saved_cfg, saved_driver

    def test_different_lights_must_use_different_relays(self):
        with self.assertRaises(ValidationError):
            HWConfig(racks_count=2, relay_backend="gpio",
                     racks={"1": RackHW(light_relay=1),
                            "2": RackHW(light_relay=1)})


class RelayDriverTests(unittest.TestCase):
    def test_active_low_and_unknown_channel(self):
        class FakeOutputDevice:
            instances = []
            def __init__(self, pin, *, active_high, initial_value):
                self.pin = pin
                self.active_high = active_high
                self.value = initial_value
                self.closed = False
                self.instances.append(self)
            def on(self): self.value = True
            def off(self): self.value = False
            def close(self): self.closed = True

        module = types.ModuleType("gpiozero")
        module.OutputDevice = FakeOutputDevice
        # Mock the driver output without ever accessing physical Pi GPIO.
        with patch.dict(sys.modules, {"gpiozero": module}):
            from app import gpio_driver
            with patch.object(gpio_driver, "OutputDevice", FakeOutputDevice):
                driver = gpio_driver.GPIODriver({1: 5, 2: 6}, active_low=True)
            self.assertEqual(driver.channels, (1, 2))
            first = FakeOutputDevice.instances[0]
            self.assertFalse(first.active_high)
            self.assertFalse(first.value)
            asyncio.run(driver.set_relay(1, True))
            self.assertTrue(first.value)
            asyncio.run(driver.set_relay(1, False))
            self.assertFalse(first.value)
            with self.assertRaises(ValueError):
                asyncio.run(driver.set_relay(9, True))
            driver.close()
            self.assertTrue(first.closed)
            self.assertFalse(first.value)


if __name__ == "__main__":
    unittest.main()
