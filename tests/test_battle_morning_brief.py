"""Battle-only morning briefing checks with no production DB or Telegram calls."""
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace as NS

from cloud.app.telegram.battle_notifications import discover_battle_daily_updates
from cloud.app.telegram.activity_notifier import TelegramActivityDelivery


class Rows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows

    def scalars(self):
        return self


class Session:
    def __init__(self, participants, linked, photos, calibrations):
        self._answers = [Rows(participants), Rows(linked), Rows(photos), Rows(calibrations)]
        self.deliveries = []
        self.keys = set()
        self.commits = 0

    async def execute(self, statement):
        return self._answers.pop(0)

    async def get(self, cls, key):
        return True if key in self.keys else None

    def add(self, delivery):
        self.deliveries.append(delivery)
        self.keys.add(delivery.event_key)

    async def commit(self):
        self.commits += 1


def context(linked):
    entry = NS(
        id="battle-entry-01",
        user_id="website-user-01",
        telegram_user_id=None,
        planting_id="planting-01",
        slot_number=2,
        water_used_ml=125,
        nutrient_used_ml=20,
        shade_used_minutes=30,
    )
    battle = NS(
        id="battle-01",
        device_id="device-01",
        rack_id=1,
        planted_at=datetime(2026, 10, 12, 10, 53, tzinfo=timezone.utc),
        water_budget_ml=1000,
        nutrient_budget_ml=100,
        shade_budget_minutes=480,
    )
    plant = NS(code="mustard", names={"ru": "Горчица", "en": "Mustard"})
    tgs = [NS(id=7, telegram_user_id=987654, language_code="ru",
              marketplace_user_id="website-user-01")] if linked else []
    photo = NS(device_id="device-01", rack_id=1,
               file_path="/srv/kisamore/data/photos/latest.jpeg",
               captured_at=datetime.now(timezone.utc))
    calibration = NS(device_id="device-01", rack_id=1, camera_id="camera_1",
                     slot_outlines={"2": [[0.1,0.1],[0.4,0.1],[0.4,0.4],[0.1,0.4]]})
    photo.camera_id = "camera_1"
    return Session([(entry,battle,plant)], tgs, [photo], [calibration])


async def main():
    on_day_one = context(True)
    count = await discover_battle_daily_updates(
        None, on_day_one, datetime(2026,10,12,12,0,tzinfo=timezone.utc)
    )
    assert count == 0 and not on_day_one.deliveries

    on_day_two = context(True)
    count = await discover_battle_daily_updates(
        None, on_day_two, datetime(2026,10,13,8,0,tzinfo=timezone.utc)
    )
    assert count == 1 and on_day_two.commits == 1
    d = on_day_two.deliveries[0]
    assert isinstance(d,TelegramActivityDelivery)
    assert d.kind == "battle_daily"
    assert "день 2" in d.payload["text"]
    assert "875" in d.payload["text"]  # water budget remainder
    assert d.payload["photo_path"].endswith("latest.jpeg")
    assert len(d.payload["slot_polygon"]) == 4
    assert d.payload["callback_data"] == "battle:open:battle-entry-01"
    assert "url" not in d.payload

    unlinked = context(False)
    count = await discover_battle_daily_updates(
        None, unlinked, datetime(2026,10,13,8,0,tzinfo=timezone.utc)
    )
    assert count == 0 and not unlinked.deliveries
    print("PASS: day-one skip, battle-only linked user morning report, correct resources, photo, no Telegram for unlinked")

if __name__ == "__main__":
    asyncio.run(main())
