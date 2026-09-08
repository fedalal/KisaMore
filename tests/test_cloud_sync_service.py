from __future__ import annotations

import asyncio
import sys
import json
import types
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
from app.models import Base, Plant, RackSensorHistory, RackSlot, RackState


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
    assert settings.growing_sync_timeout_seconds == 120

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


def test_mqtt_snapshot_is_published_in_small_chunks(monkeypatch):
    published = []
    clients = []

    class FakePublishInfo:
        rc = 0

        def wait_for_publish(self, timeout=None):
            assert timeout is None or timeout > 0

        def is_published(self):
            return True

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.username = None
            clients.append(self)

        def username_pw_set(self, username, password=None):
            self.username = (username, password)

        def tls_set(self):
            raise AssertionError("TLS must not be enabled by default")

        def connect(self, host, port, keepalive=60):
            assert (host, port) == ("mqtt.example.test", 1883)
            assert keepalive >= 15

        def loop_start(self):
            pass

        def publish(self, topic, payload, qos=0, retain=False):
            published.append((topic, payload, qos, retain))
            return FakePublishInfo()

        def loop_stop(self):
            pass

        def disconnect(self):
            pass

    fake_mqtt = types.ModuleType("paho.mqtt.client")
    fake_mqtt.CallbackAPIVersion = types.SimpleNamespace(VERSION2=object())
    fake_mqtt.MQTTv311 = object()
    fake_mqtt.MQTT_ERR_SUCCESS = 0
    fake_mqtt.Client = FakeClient
    monkeypatch.setitem(sys.modules, "paho", types.ModuleType("paho"))
    monkeypatch.setitem(sys.modules, "paho.mqtt", types.ModuleType("paho.mqtt"))
    monkeypatch.setitem(sys.modules, "paho.mqtt.client", fake_mqtt)

    service = CloudSyncService()
    service._settings = CloudSyncSettings(
        api_url="https://api.example.test",
        device_id="pi-01",
        device_token="test-token-with-at-least-32-characters",
        mqtt_host="mqtt.example.test",
        mqtt_username="edge",
        mqtt_password="secret",
        mqtt_chunk_bytes=512,
    )
    snapshot = {
        "observed_at": "2026-08-05T12:00:00+00:00",
        "software_version": "test",
        "racks_count": 1,
        "levels": {},
        "plants": [{"plant_id": "x", "name": "y" * 3000}],
        "racks": [{"rack_id": 1, "slots": []}],
    }

    service._send_snapshot_blocking(snapshot, timeout_seconds=10)

    assert clients[0].username == ("edge", "secret")
    chunk_messages = [item for item in published if "/chunk/" in item[0]]
    done_messages = [item for item in published if item[0].endswith("/done")]
    assert len(chunk_messages) > 1
    assert len(done_messages) == 1
    assert all(len(payload) <= 512 for _, payload, _, _ in chunk_messages)
    assert all(qos == 1 and retain is False for _, _, qos, retain in published)
    done = json.loads(done_messages[0][1])
    rebuilt = b"".join(payload for _, payload, _, _ in chunk_messages)
    assert done["bytes"] == len(rebuilt)
    assert done["chunks"] == len(chunk_messages)


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
            session.add(
                Plant(
                    id="plant-radish",
                    code="radish",
                    names={"en": "Radish", "ru": "Редис"},
                    descriptions={},
                    seed_image_name="radish_seeds.jpg",
                    microgreen_image_name="radish_microgreens.jpg",
                    grow_days=12,
                )
            )
            session.add(RackSlot(rack_id=1, slot_number=1, status="available"))
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
        automatic_snapshot = await service.collect_snapshot()
        manual_snapshot = await service.collect_snapshot(include_growing=True)
        await engine.dispose()
        return automatic_snapshot, manual_snapshot

    snapshot, manual_snapshot = asyncio.run(collect())
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
                "slots": [],
            }
        ]
    assert snapshot["plants"] == []
    assert snapshot["racks"][0]["slots"] == []
    assert manual_snapshot["plants"][0]["seed_image_name"] == "radish_seeds.jpg"
    assert manual_snapshot["plants"][0]["microgreen_image_name"] == "radish_microgreens.jpg"
    assert manual_snapshot["racks"][0]["slots"][0]["slot_number"] == 1


def test_manual_growing_sync_includes_catalog_and_placement(monkeypatch):
    service = CloudSyncService()
    service._settings = CloudSyncSettings(
        api_url="https://api.example.test",
        device_id="pi-01",
        device_token="test-token-with-at-least-32-characters",
    )
    sent = []

    async def fake_collect_snapshot(*, include_growing=False):
        assert include_growing is True
        return {
            "plants": [{"plant_id": "plant-radish"}],
            "racks": [{"slots": [{"slot_number": 1}]}],
        }

    async def fake_send_snapshot(snapshot, timeout_seconds=None):
        assert timeout_seconds == 120
        sent.append(snapshot)

    monkeypatch.setattr(service, "collect_snapshot", fake_collect_snapshot)
    monkeypatch.setattr(service, "_send_snapshot", fake_send_snapshot)
    monkeypatch.setattr(service, "_sync_assignments", lambda: asyncio.sleep(0, result=2))

    result = asyncio.run(service.sync_growing_now())
    assert result == {"plants_count": 1, "slots_count": 1, "assignments_count": 2}
    assert sent[0]["plants"][0]["plant_id"] == "plant-radish"


def test_background_sync_includes_growing_data_and_fetches_assignments(monkeypatch):
    service = CloudSyncService()
    service._settings = CloudSyncSettings(
        api_url="https://api.example.test",
        device_id="pi-01",
        device_token="test-token-with-at-least-32-characters",
    )
    calls = []

    async def fake_collect_snapshot(*, include_growing=False):
        calls.append(("collect", include_growing))
        return {
            "plants": [{"plant_id": "plant-radish"}],
            "racks": [{"slots": [{"slot_number": 1}]}],
        }

    async def fake_send_snapshot(snapshot, timeout_seconds=None):
        calls.append(("send", timeout_seconds, snapshot))

    async def fake_sync_assignments():
        calls.append(("assignments",))
        return 2

    async def fake_send_changed_photos():
        calls.append(("photos",))
        service._stop_event.set()
        return 0

    monkeypatch.setattr(service, "collect_snapshot", fake_collect_snapshot)
    monkeypatch.setattr(service, "_send_snapshot", fake_send_snapshot)
    monkeypatch.setattr(service, "_sync_assignments", fake_sync_assignments)
    monkeypatch.setattr(service, "_send_changed_photos", fake_send_changed_photos)

    asyncio.run(service._run())

    assert calls[0] == ("collect", True)
    assert calls[1][0:2] == ("send", None)
    assert calls[1][2]["plants"][0]["plant_id"] == "plant-radish"
    assert calls[2] == ("assignments",)
    assert calls[3] == ("photos",)


def test_failed_inventory_falls_back_to_telemetry_and_assignment_failure_is_separate(monkeypatch, capsys):
    service = CloudSyncService()
    service._settings = CloudSyncSettings(
        api_url="https://api.example.test", device_id="pi-01",
        device_token="test-token-with-at-least-32-characters",
    )
    original = {
        "plants": [{"plant_id": "radish"}],
        "racks": [{"rack_id": 1, "soil_temperature": 23, "slots": [{"slot_number": 1}]}],
    }
    sent = []

    async def collect(**kwargs):
        return original

    async def send(snapshot, timeout_seconds=None):
        assert timeout_seconds is None
        sent.append(snapshot)
        if snapshot["plants"]:
            raise TimeoutError("full payload timed out")

    async def assignments():
        raise TimeoutError("assignments timed out")

    async def photos():
        service._stop_event.set()
        return 0

    monkeypatch.setattr(service, "collect_snapshot", collect)
    monkeypatch.setattr(service, "_send_snapshot", send)
    monkeypatch.setattr(service, "_sync_assignments", assignments)
    monkeypatch.setattr(service, "_send_changed_photos", photos)
    asyncio.run(service._run())
    assert len(sent) == 2
    assert sent[1]["plants"] == []
    assert sent[1]["racks"][0]["slots"] == []
    assert sent[1]["racks"][0]["soil_temperature"] == 23
    assert original["plants"] and original["racks"][0]["slots"]
    log = capsys.readouterr().out
    assert "snapshot sent" in log
    assert "assignments failed (snapshot already accepted)" in log


def test_only_changed_latest_photos_are_uploaded(monkeypatch, tmp_path):
    latest_dir = tmp_path / "latest"
    latest_dir.mkdir()
    photo = latest_dir / "rack_1.jpg"
    photo.write_bytes(b"\xff\xd8\xff\xe0photo")
    monkeypatch.setattr(
        sync_module.runtime,
        "cfg",
        SimpleNamespace(
            racks_count=2,
            camera_capture=SimpleNamespace(enabled=True, latest_dir=str(latest_dir)),
        ),
    )
    service = CloudSyncService()
    service._settings = CloudSyncSettings(
        api_url="https://api.example.test",
        device_id="pi-01",
        device_token="test-token-with-at-least-32-characters",
    )
    uploads = []

    def fake_upload(rack_id, path, captured_at):
        uploads.append((rack_id, path.name, captured_at))

    monkeypatch.setattr(service, "_send_photo_blocking", fake_upload)
    assert asyncio.run(service._send_changed_photos()) == 1
    assert asyncio.run(service._send_changed_photos()) == 0
    photo.write_bytes(b"\xff\xd8\xff\xe0new-photo")
    assert asyncio.run(service._send_changed_photos()) == 1
    assert [item[0] for item in uploads] == [1, 1]


def test_photos_are_not_uploaded_when_camera_capture_is_disabled(monkeypatch, tmp_path):
    latest_dir = tmp_path / "latest"
    latest_dir.mkdir()
    (latest_dir / "rack_1.jpg").write_bytes(b"\xff\xd8\xff\xe0photo")
    monkeypatch.setattr(
        sync_module.runtime,
        "cfg",
        SimpleNamespace(
            racks_count=1,
            camera_capture=SimpleNamespace(enabled=False, latest_dir=str(latest_dir)),
        ),
    )
    service = CloudSyncService()
    service._settings = CloudSyncSettings(
        api_url="https://api.example.test",
        device_id="pi-01",
        device_token="test-token-with-at-least-32-characters",
    )

    def unexpected_upload(*args, **kwargs):
        raise AssertionError("disabled camera capture must not upload photos")

    monkeypatch.setattr(service, "_send_photo_blocking", unexpected_upload)

    assert asyncio.run(service._send_changed_photos()) == 0
