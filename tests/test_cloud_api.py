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
os.environ["KISAMORE_COOKIE_SECURE"] = "false"
os.environ["KISAMORE_OFFER_HOURS"] = "24"
os.environ["KISAMORE_PHOTO_DIR"] = str(test_dir / "photos")

from fastapi.testclient import TestClient
from sqlalchemy import select

from cloud.app.db import SessionLocal
from cloud.app.main import app
from cloud.app.models import Device, RackCurrent, TelemetrySample


def _snapshot(observed_at: datetime | None = None) -> dict:
    timestamp = observed_at or datetime.now(timezone.utc)
    return {
        "observed_at": timestamp.isoformat(),
        "software_version": "test-commit",
        "racks_count": 2,
        "levels": {"low": False, "critical": False},
        "plants": [
            {
                "plant_id": "plant-radish",
                "code": "radish",
                "names": {"en": "Radish", "ru": "Редис", "zh": "萝卜"},
                "descriptions": {},
                "seed_image_name": "radish_seeds.jpg",
                "microgreen_image_name": "radish_microgreens.jpg",
                "grow_days": 12,
                "active": True,
                "updated_at": timestamp.isoformat(),
            }
        ],
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
                "slots": [
                    {
                        "slot_number": number,
                        "status": "available",
                        "enabled": True,
                        "planting": None,
                    }
                    for number in range(1, 7)
                ],
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
                "slots": [
                    {
                        "slot_number": number,
                        "status": "available",
                        "enabled": True,
                        "planting": None,
                    }
                    for number in range(1, 7)
                ],
            },
        ],
    }


def test_authenticated_ingestion_and_public_read_only_api():
    with TestClient(app) as client:
        dashboard = client.get("/")
        assert dashboard.status_code == 200
        assert "KisaMore Farm" in dashboard.text
        assert 'content="test-farm"' in dashboard.text

        dashboard_css = client.get("/static/dashboard.css")
        assert dashboard_css.status_code == 200
        assert "text/css" in dashboard_css.headers["content-type"]

        dashboard_js = client.get("/static/dashboard.js")
        assert dashboard_js.status_code == 200
        assert 'const translations = {' in dashboard_js.text
        assert 'window.setInterval(loadData, 30_000);' in dashboard_js.text
        assert "Українська" not in dashboard.text

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

        photo_bytes = b"\xff\xd8\xff\xe0test-jpeg"
        photo_upload = client.post(
            "/api/v1/edge/racks/1/photo",
            headers={
                "X-Device-ID": "test-pi-01",
                "Authorization": f"Bearer {device_token}",
            },
            data={"captured_at": datetime.now(timezone.utc).isoformat()},
            files={"photo": ("rack-1.jpg", photo_bytes, "image/jpeg")},
        )
        assert photo_upload.status_code == 201

        public_photo = client.get("/api/v1/public/farms/test-farm/racks/1/photo")
        assert public_photo.status_code == 200
        assert public_photo.content == photo_bytes
        assert public_photo.headers["content-type"] == "image/jpeg"

        live = client.get("/api/v1/public/farms/test-farm/live")
        assert live.status_code == 200
        data = live.json()
        assert data["status"] == "online"
        assert data["racks_count"] == 2
        assert [rack["rack_id"] for rack in data["racks"]] == [1, 2]
        assert data["racks"][0]["soil_moisture"] == 61.4
        assert data["racks"][0]["light_on"] is True

        market = client.get("/api/v1/public/farms/test-farm/market")
        assert market.status_code == 200
        market_data = market.json()
        assert market_data["plants"][0]["names"]["ru"] == "Редис"
        assert market_data["plants"][0]["seed_image_name"] == "radish_seeds.jpg"
        assert market_data["plants"][0]["microgreen_image_name"] == "radish_microgreens.jpg"
        assert len(market_data["racks"][0]["slots"]) == 6
        assert market_data["racks"][0]["whole_rack_available"] is True
        assert market_data["racks"][0]["photo_url"].endswith("/racks/1/photo")

        registered = client.post(
            "/api/v1/auth/register",
            json={
                "email": "grower@example.com",
                "display_name": "Test Grower",
                "password": "long-test-password",
                "language": "ru",
            },
        )
        assert registered.status_code == 201
        assert registered.json()["preferred_language"] == "ru"
        assert "kisamore_session" in client.cookies

        purchased = client.post(
            "/api/v1/shop/purchases",
            json={
                "device_id": "test-pi-01",
                "resource_type": "slot",
                "rack_id": 1,
                "slot_number": 1,
                "plant_id": "plant-radish",
            },
        )
        assert purchased.status_code == 201
        allocation_id = purchased.json()["id"]

        duplicate_purchase = client.post(
            "/api/v1/shop/purchases",
            json={
                "device_id": "test-pi-01",
                "resource_type": "slot",
                "rack_id": 1,
                "slot_number": 1,
                "plant_id": "plant-radish",
            },
        )
        assert duplicate_purchase.status_code == 409

        reservation = client.post(
            "/api/v1/shop/reservations",
            json={
                "device_id": "test-pi-01",
                "resource_type": "slot",
                "rack_id": 1,
                "slot_number": 1,
                "plant_id": "plant-radish",
            },
        )
        assert reservation.status_code == 201
        assert reservation.json()["status"] == "waiting"

        released = client.post(f"/api/v1/shop/allocations/{allocation_id}/release")
        assert released.status_code == 200
        account = client.get("/api/v1/account")
        assert account.status_code == 200
        pending_offers = [item for item in account.json()["offers"] if item["status"] == "pending"]
        assert len(pending_offers) == 1

        whole_rack = client.post(
            "/api/v1/shop/purchases",
            json={
                "device_id": "test-pi-01",
                "resource_type": "rack",
                "rack_id": 2,
                "slot_number": None,
                "plant_id": None,
            },
        )
        assert whole_rack.status_code == 201
        blocked_rack_slot = client.post(
            "/api/v1/shop/purchases",
            json={
                "device_id": "test-pi-01",
                "resource_type": "slot",
                "rack_id": 2,
                "slot_number": 3,
                "plant_id": None,
            },
        )
        assert blocked_rack_slot.status_code == 409

        reduced_snapshot = _snapshot()
        reduced_snapshot["racks_count"] = 1
        reduced_snapshot["racks"] = reduced_snapshot["racks"][:1]
        reduced = client.post(
            "/api/v1/edge/snapshot",
            headers={
                "X-Device-ID": "test-pi-01",
                "Authorization": f"Bearer {device_token}",
            },
            json=reduced_snapshot,
        )
        assert reduced.status_code == 202

        reduced_live = client.get("/api/v1/public/farms/test-farm/live")
        assert reduced_live.status_code == 200
        reduced_data = reduced_live.json()
        assert reduced_data["racks_count"] == 1
        assert [rack["rack_id"] for rack in reduced_data["racks"]] == [1]

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

    async def read_persisted_state():
        async with SessionLocal() as session:
            device = (await session.execute(select(Device))).scalar_one()
            current_rack_ids = (
                await session.execute(
                    select(RackCurrent.rack_id).order_by(RackCurrent.rack_id)
                )
            ).scalars().all()
            telemetry_rack_ids = (
                await session.execute(
                    select(TelemetrySample.rack_id).order_by(TelemetrySample.rack_id)
                )
            ).scalars().all()
            return device, current_rack_ids, telemetry_rack_ids

    device, current_rack_ids, telemetry_rack_ids = asyncio.run(read_persisted_state())
    assert device.token_hash != device_token
    assert len(device.token_hash) == 64
    assert current_rack_ids == [1, 2]
    assert 2 in telemetry_rack_ids


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
