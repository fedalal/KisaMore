from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

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

    captured_payload_path = None

    def fake_run(command, *, input, capture_output, check, timeout):
        nonlocal captured_payload_path
        assert command[0] == "curl"
        assert "--http1.1" in command
        assert command[command.index("--noproxy") + 1] == "*"
        assert command[command.index("--connect-timeout") + 1] == "5"
        assert command[command.index("--max-time") + 1] == "10"
        assert command[command.index("--header") + 1] == "@-"
        assert command[-1] == "https://api.example.test/api/v1/edge/snapshot"
        assert not any(settings.device_token in argument for argument in command)
        assert not any(settings.device_id in argument for argument in command)

        captured_payload_path = Path(command[command.index("--data-binary") + 1][1:])
        assert json.loads(captured_payload_path.read_text(encoding="utf-8")) == snapshot
        assert input == (
            b"Authorization: Bearer secret-device-token-with-at-least-32-characters\n"
            b"X-Device-ID: pi-01\n"
            b"Content-Type: application/json\n"
            b"Accept: application/json\n"
            b"Connection: close\n"
        )
        assert capture_output is True
        assert check is False
        assert timeout == settings.request_timeout_seconds + 1.0
        return SimpleNamespace(returncode=0, stdout=b"202", stderr=b"")

    monkeypatch.setattr(sync_module.subprocess, "run", fake_run)
    service = CloudSyncService()
    service._settings = settings

    asyncio.run(service._send_snapshot(snapshot))
    assert captured_payload_path is not None
    assert not captured_payload_path.exists()


def test_read_timeout_does_not_trigger_exponential_backoff():
    delay, next_failure_delay = _retry_delays(
        TimeoutError("response was not received in time"),
        interval_seconds=30,
        failure_delay=240,
    )

    assert delay == 30
    assert next_failure_delay == 30


def test_curl_timeout_is_reported_as_timeout_error(monkeypatch):
    settings = CloudSyncSettings(
        api_url="https://api.example.test",
        device_id="pi-01",
        device_token="test-token-with-at-least-32-characters",
    )

    def fake_run(*args, **kwargs):
        return SimpleNamespace(
            returncode=28,
            stdout=b"000",
            stderr=b"curl: (28) Operation timed out",
        )

    monkeypatch.setattr(sync_module.subprocess, "run", fake_run)
    service = CloudSyncService()
    service._settings = settings

    try:
        service._send_snapshot_blocking({"racks": []})
    except TimeoutError as exc:
        assert "Operation timed out" in str(exc)
    else:
        raise AssertionError("curl exit code 28 must be treated as a timeout")


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
