from __future__ import annotations

import asyncio
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


test_dir = Path(tempfile.mkdtemp(prefix="kisamore-cloud-test-"))
device_token = "test-token-with-more-than-thirty-two-characters-123456"

os.environ["KISAMORE_DATABASE_URL"] = f"sqlite+aiosqlite:///{test_dir / 'cloud.db'}"
os.environ["KISAMORE_BOOTSTRAP_FARM_SLUG"] = "test-farm"
os.environ["KISAMORE_BOOTSTRAP_FARM_NAME"] = "Test Farm"
os.environ["KISAMORE_BOOTSTRAP_DEVICE_ID"] = "test-pi-01"
os.environ["KISAMORE_BOOTSTRAP_DEVICE_NAME"] = "Test Pi"
os.environ["KISAMORE_BOOTSTRAP_DEVICE_TOKEN"] = device_token
os.environ["KISAMORE_OFFLINE_AFTER_SECONDS"] = "120"

from fastapi.testclient import TestClient
from sqlalchemy import select

from cloud.app.db import SessionLocal
from cloud.app.main import app
from cloud.app.models import Device


def _snapshot(observed_at: datetime | None = None) -> dict:
    timestamp = observed_at or datetime.now(timezone.utc)
    return {
        "observed_at": timestamp.isoformat(),
        "software_version": "test-commit",
        "racks_count": 2,
        "levels": {"low": False, "critical": False},
        "racks": [
            {
                "rack_id": 1,
                "light_on": True,
                "water_on": False,
                "light_mode": "schedule",
                "water_mode": "manual",
                "soil_moisture": 61.4,
                "soil_temperature": 23.7,
                "sensor_observed_at": timestamp.isoformat(),
                "camera_id": "camera_1",
            },
            {
                "rack_id": 2,
                "light_on": False,
                "water_on": True,
                "light_mode": "manual",
                "water_mode": "schedule",
                "soil_moisture": None,
                "soil_temperature": None,
                "sensor_observed_at": None,
                "camera_id": "camera_2",
            },
        ],
    }


def test_authenticated_ingestion_and_public_read_only_api():
    with TestClient(app) as client:
        health = client.get("/api/v1/health")
        assert health.status_code == 200

        waiting = client.get("/api/v1/public/farms/test-farm/live")
        assert waiting.status_code == 200
        assert waiting.json()["status"] == "waiting"

        wrong_auth = client.post(
            "/api/v1/edge/snapshot",
            headers={"X-Device-ID": "test-pi-01", "Authorization": "Bearer wrong-token"},
            json=_snapshot(),
        )
        assert wrong_auth.status_code == 401

        accepted = client.post(
            "/api/v1/edge/snapshot",
            headers={
                "X-Device-ID": "test-pi-01",
                "Authorization": f"Bearer {device_token}",
            },
            json=_snapshot(),
        )
        assert accepted.status_code == 202
        assert accepted.json()["accepted"] is True

        live = client.get("/api/v1/public/farms/test-farm/live")
        assert live.status_code == 200
        data = live.json()
        assert data["status"] == "online"
        assert data["racks_count"] == 2
        assert [rack["rack_id"] for rack in data["racks"]] == [1, 2]
        assert data["racks"][0]["soil_moisture"] == 61.4
        assert data["racks"][0]["light_on"] is True

        # This stage intentionally exposes no public control route.
        no_control = client.post("/api/v1/public/farms/test-farm/racks/1/light")
        assert no_control.status_code == 404

        future = client.post(
            "/api/v1/edge/snapshot",
            headers={
                "X-Device-ID": "test-pi-01",
                "Authorization": f"Bearer {device_token}",
            },
            json=_snapshot(datetime.now(timezone.utc) + timedelta(minutes=10)),
        )
        assert future.status_code == 422

    async def read_device():
        async with SessionLocal() as session:
            return (await session.execute(select(Device))).scalar_one()

    device = asyncio.run(read_device())
    assert device.token_hash != device_token
    assert len(device.token_hash) == 64


def test_snapshot_rejects_duplicate_rack_ids():
    payload = _snapshot()
    payload["racks"][1]["rack_id"] = 1

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/edge/snapshot",
            headers={
                "X-Device-ID": "test-pi-01",
                "Authorization": f"Bearer {device_token}",
            },
            json=payload,
        )
        assert response.status_code == 422
