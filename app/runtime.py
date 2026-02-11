from __future__ import annotations

from typing import Optional, Any
from datetime import datetime

from sqlalchemy import select

from .hw_config import HWConfig, load_config
from .rs485_driver import RS485RelayDriver, RS485Config
from .inputs_driver import InputsDriver

from .db import SessionLocal
from .models import RackState, RackSchedule


DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _in_any_range(now_hm: str, ranges: list[dict]) -> bool:
    for r in ranges:
        if r["start"] <= now_hm < r["end"]:
            return True
    return False

cfg: Optional[HWConfig] = None
driver: Optional[Any] = None
inputs: Optional[InputsDriver] = None


async def init_runtime(active_low: bool = True) -> None:
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

    # NEW: входы (датчики уровня)
    inputs = InputsDriver(cfg.level_sensors, bounce_time=0.15)
    print(f"[KisaMore] Inputs enabled: {cfg.level_sensors}")

async def safety_reset_and_sync_relays() -> None:
    """
    Fail-safe при старте:
    1) выключаем ВСЕ реле (на случай, если что-то "залипло" после падения)
    2) сразу же приводим железо в соответствие с текущими режимами/расписанием из БД:
       - manual: восстанавливаем light_on/water_on
       - schedule: вычисляем состояние по текущему времени и обновляем БД

    Важно: эту функцию нужно вызывать ПОСЛЕ ensure_db_tables/ensure_db_racks.
    """

    if not cfg or not driver:
        return

    # 1) выключаем все реле
    for ch in range(1, 17):
        try:
            await driver.set_relay(ch, False)
        except Exception as e:
            print(f"[KisaMore] FAIL-SAFE: can't turn off relay {ch}: {e}")

    # 2) синхронизируем нужные состояния
    now = datetime.now()
    day_key = DAYS[now.weekday()]
    now_hm = now.strftime("%H:%M")

    async with SessionLocal() as s:
        states = (await s.execute(select(RackState))).scalars().all()
        schedules = {x.rack_id: x for x in (await s.execute(select(RackSchedule))).scalars().all()}

        for st in states:
            if st.rack_id > cfg.racks_count:
                continue
            rack_cfg = cfg.racks.get(str(st.rack_id))
            if not rack_cfg:
                continue

            sch = schedules.get(st.rack_id)
            sch_json = sch.schedule_json if sch else {}

            # Свет
            if st.light_mode == "manual":
                want_light = bool(st.light_on)
            else:
                light_ranges = (((sch_json.get("light") or {}).get(day_key)) or [])
                want_light = _in_any_range(now_hm, light_ranges)
                st.light_on = want_light

            # Полив
            if st.water_mode == "manual":
                want_water = bool(st.water_on)
            else:
                water_ranges = (((sch_json.get("water") or {}).get(day_key)) or [])
                want_water = _in_any_range(now_hm, water_ranges)
                st.water_on = want_water

            try:
                await driver.set_relay(rack_cfg.light_relay, want_light)
            except Exception as e:
                print(f"[KisaMore] sync: can't set light relay for rack {st.rack_id}: {e}")

            try:
                await driver.set_relay(rack_cfg.water_relay, want_water)
            except Exception as e:
                print(f"[KisaMore] sync: can't set water relay for rack {st.rack_id}: {e}")

        await s.commit()

    print("[KisaMore] FAIL-SAFE: all relays OFF, then synced to DB state/schedule")
