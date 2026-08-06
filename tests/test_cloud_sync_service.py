from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from urllib import error as urllib_error

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import cloud_sync_service as sync_module
from app.cloud_sync_service import (
    CloudSyncService,
    CloudSyncSettings,
    _remaining_delay,
    _retry_delays,
)
from app.models import Base, RackSensorHistory, RackState


def test_cloud_settings_are_disabled_without_all_credentials(monkeypatch):
    monkeypatch.delenv("KISAMORE_CLOUD_URL", raising=False)
    monkeypatch.delenv("KISAMORE_DEVICE_ID", raising=False)
    monkeypatch.delenv("KISAMORE_DEVICE_TOKEN", raising=False)

    assert CloudSyncSettings.from_env() is None


def test_invalid_cloud_settings_do_not_start_background_task(monkeypatch):
    monkeypatch.setenv("KISAMORE_CLOUD_URL", "http://public-api.example.test")
    monkeypatch.setenv("KISAMORE_DEVICE_ID", "pi-01")
    monkeypatch.setenv(
        "KISAMORE_DEVICE_TOKEN",
        "test-token-with-at-least-32-characters",
    )

    service = CloudSyncService()
    asyncio.run(service.start())

    assert service._settings is None
    assert service._task is None


def test_snapshot_is_sent_with_device_authentication(monkeypatch):
    monkeypatch.setenv("KISAMORE_CLOUD_URL", "https://api.example.test/")
    monkeypatch.setenv("KISAMORE_DEVICE_ID", "pi-01")
    monkeypatch.setenv(
        "KISAMORE_DEVICE_TOKEN",
        "secret-device-token-with-at-least-32-characters",
    )
    monkeypatch.setenv("KISAMORE_CLOUD_INTERVAL_SECONDS", "30")

    settings = CloudSyncSettings.from_env()
    assert settings is not None
    assert settings.api_url == "https://api.example.test"

    snapshot = {
        "observed_at": "2026-08-05T12:00:00+00:00",
        "software_version": "test",
        "racks_count": 1,
        "levels": {},
        "racks": [],
    }

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b'{"accepted":true}'

    def fake_urlopen(request, timeout):
        assert request.full_url == "https://api.example.test/api/v1/edge/snapshot"
        assert request.get_method() == "POST"
        assert request.get_header("X-device-id") == "pi-01"
        assert request.get_header("Authorization") == (
            "Bearer secret-device-token-with-at-least-32-characters"
        )
        assert request.get_header("Content-type") == "application/json"
        assert request.get_header("Connection") == "close"
        assert json.loads(request.data) == snapshot
        assert timeout == settings.request_timeout_seconds
        return FakeResponse()

    monkeypatch.setattr(sync_module.urllib_request, "urlopen", fake_urlopen)
    service = CloudSyncService()
    service._settings = settings

    asyncio.run(service._send_snapshot(snapshot))


def test_read_timeout_does_not_trigger_exponential_backoff():
    delay, next_failure_delay = _retry_delays(
        TimeoutError("response was not received in time"),
        interval_seconds=30,
        failure_delay=240,
    )

    assert delay == 30
    assert next_failure_delay == 30


def test_wrapped_read_timeout_does_not_trigger_exponential_backoff():
    delay, next_failure_delay = _retry_delays(
        urllib_error.URLError(TimeoutError("response was not received in time")),
        interval_seconds=30,
        failure_delay=240,
    )

    assert delay == 30
    assert next_failure_delay == 30


def test_other_failures_keep_exponential_backoff():
    delay, next_failure_delay = _retry_delays(
        RuntimeError("temporary failure"),
        interval_seconds=30,
        failure_delay=240,
    )

    assert delay == 240
    assert next_failure_delay == 300


def test_request_time_is_included_in_sync_interval():
    assert _remaining_delay(30, 10) == 20
    assert _remaining_delay(30, 30) == 0
    assert _remaining_delay(30, 45) == 0


def test_snapshot_uses_saved_sensor_history_without_polling_hardware(monkeypatch, tmp_path):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'edge.db'}"
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    sensor_time = datetime(2026, 8, 5, 9, 30, tzinfo=timezone.utc)

    class FakeInputs:
        def snapshot(self):
            return {"low": True, "critical": False}

    async def collect():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            session.add(
                RackState(
                    rack_id=1,
                    light_on=True,
                    water_on=False,
                    light_mode="schedule",
                    water_mode="manual",
                )
            )
            session.add(
                RackSensorHistory(
                    rack_id=1,
                    sensor_slave_id=12,
                    soil_moisture=58.2,
                    soil_temperature=22.4,
                    created_at=sensor_time,
                )
            )
            await session.commit()

        monkeypatch.setattr(sync_module, "SessionLocal", session_factory)
        monkeypatch.setattr(
            sync_module.runtime,
            "cfg",
            SimpleNamespace(
                racks_count=1,
                racks={"1": SimpleNamespace(camera_id="camera_1")},
            ),
        )
        monkeypatch.setattr(sync_module.runtime, "inputs", FakeInputs())

        service = CloudSyncService()
        service._settings = CloudSyncSettings(
            api_url="https://api.example.test",
            device_id="pi-01",
            device_token="test-token-with-at-least-32-characters",
            software_version="test-version",
        )
        snapshot = await service.collect_snapshot()
        await engine.dispose()
        return snapshot

    snapshot = asyncio.run(collect())
    assert snapshot["racks_count"] == 1
    assert snapshot["levels"] == {"low": True, "critical": False}
    assert snapshot["racks"] == [
        {
            "rack_id": 1,
            "light_on": True,
            "water_on": False,
            "light_mode": "schedule",
            "water_mode": "manual",
            "soil_moisture": 58.2,
            "soil_temperature": 22.4,
            "sensor_observed_at": sensor_time.isoformat(),
            "camera_id": "camera_1",
        }
    ]
