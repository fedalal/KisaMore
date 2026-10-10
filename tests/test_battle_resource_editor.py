"""Integration checks for changing battle resource limits through /admin.

Uses temporary, standalone SQLite; it never writes to production PostgreSQL.
Run: python tests/test_battle_resource_editor.py
"""
import asyncio
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

tmp = Path(tempfile.mkdtemp(prefix="battle-resource-editor-"))
os.environ["KISAMORE_DATABASE_URL"] = f"sqlite+aiosqlite:///battle-resource-{uuid4().hex}.db"
os.environ["KISAMORE_BOOTSTRAP_FARM_SLUG"] = "battle-resources-test"
os.environ["KISAMORE_BOOTSTRAP_DEVICE_ID"] = "battle-editor-device"
os.environ["KISAMORE_BOOTSTRAP_DEVICE_TOKEN"] = "test-token-must-have-more-than-32-bytes"
os.environ["KISAMORE_COOKIE_SECURE"] = "false"
os.environ["KISAMORE_PHOTO_DIR"] = str(tmp / "photos")
os.environ["KISAMORE_MQTT_ENABLED"] = "false"

from cloud.app.main import app
from cloud.app.db import SessionLocal
from cloud.app.models import Device, Plant, User
from cloud.app.battle_models import PlantBattle, PlantBattleEntry
from cloud.app.admin_models import AdminAuditLog
from cloud.app.security import hash_password


async def seed():
    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        device = (await session.execute(select(Device))).scalars().first()
        assert device is not None
        admin = User(
            id=str(uuid4()), email="admin-battle-editor@example.org",
            display_name="Editor admin", role="admin", is_active=True,
            password_hash=hash_password("strong-admin-pass"), created_at=now,
        )
        customer = User(
            id=str(uuid4()), email="customer-battle-editor@example.org",
            display_name="Editor participant", role="customer", is_active=True,
            password_hash=hash_password("strong-customer-pass"), created_at=now,
        )
        plant = Plant(id=str(uuid4()), code="editor-test-plant", names={"en": "Rucola"})
        battle = PlantBattle(
            id=str(uuid4()), device_id=device.id, rack_id=1, plant_id=plant.id,
            title="Original name", status="growing", entry_price_kisa=10,
            max_entries=6, water_budget_ml=1000, nutrient_budget_ml=200,
            shade_budget_minutes=480, winner_reward_kisa=20,
            created_by_user_id=admin.id, created_at=now, updated_at=now,
        )
        entry = PlantBattleEntry(
            id=str(uuid4()), battle_id=battle.id, user_id=customer.id,
            telegram_user_id=None, slot_number=1, price_kisa=10,
            status="active", water_used_ml=300, nutrient_used_ml=40,
            shade_used_minutes=90, is_winner=False, created_at=now,
        )
        session.add_all([admin, customer, plant, battle, entry])
        await session.commit()
        return battle.id


async def get_battle(battle_id):
    async with SessionLocal() as session:
        battle = await session.get(PlantBattle, battle_id)
        logs = (await session.execute(
            select(AdminAuditLog).where(
                AdminAuditLog.target_id == battle_id,
                AdminAuditLog.action == "update_plant_battle",
            ).order_by(AdminAuditLog.id)
        )).scalars().all()
        return battle, logs


def main():
    with TestClient(app) as client:
        battle_id = asyncio.run(seed())
        route = f"/api/v1/admin/battles/{battle_id}"
        good = {
            "title": "Updated resources",
            "start_date": "2026-10-12",
            "end_date": "2026-10-18",
            "water_budget_ml": 700,
            "nutrient_budget_ml": 100,
            "shade_budget_minutes": 200,
        }

        unauth = client.patch(route, json=good)
        assert unauth.status_code == 401, unauth.text

        customer_login = client.post("/api/v1/auth/login", json={
            "email": "customer-battle-editor@example.org",
            "password": "strong-customer-pass",
        })
        customer_login.raise_for_status()
        regular_user = client.patch(route, json=good)
        assert regular_user.status_code == 403, regular_user.text

        admin_login = client.post("/api/v1/auth/login", json={
            "email": "admin-battle-editor@example.org", "password": "strong-admin-pass",
        })
        admin_login.raise_for_status()
        result = client.patch(route, json=good)
        assert result.status_code == 200, result.text
        data = result.json()
        assert data["title"] == "Updated resources"
        assert data["water_budget_ml"] == 700
        assert data["nutrient_budget_ml"] == 100
        assert data["shade_budget_minutes"] == 200

        battle, logs = asyncio.run(get_battle(battle_id))
        assert len(logs) == 1
        assert logs[0].details["before"]["water_budget_ml"] == 1000
        assert logs[0].details["after"]["water_budget_ml"] == 700
        assert logs[0].details["before"]["nutrient_budget_ml"] == 200
        assert logs[0].details["after"]["shade_budget_minutes"] == 200

        # Every active player's already-reserved resources remain protected,
        # including pending actions (their cost is counted on request).
        for name, minimum in [
            ("water_budget_ml", 300),
            ("nutrient_budget_ml", 40),
            ("shade_budget_minutes", 90),
        ]:
            bad = dict(good)
            bad[name] = minimum - 1
            failed = client.patch(route, json=bad)
            assert failed.status_code == 409, (name, failed.text)
            battle, updated_logs = asyncio.run(get_battle(battle_id))
            assert getattr(battle, name) == good[name]
            assert len(updated_logs) == 1

        # Schema rejects negative or abnormally large values.
        for amount in (-1, 100001):
            for name in ("water_budget_ml", "nutrient_budget_ml", "shade_budget_minutes"):
                invalid = client.patch(route, json={**good, name: amount})
                assert invalid.status_code == 422, (name, amount, invalid.text)

        invalid_dates = client.patch(route, json={**good, "end_date": "2026-10-01"})
        assert invalid_dates.status_code == 422

        # Legacy clients that only update title/date still work.
        legacy = client.patch(route, json={
            "title": "Renamed only", "start_date": None, "end_date": None,
        })
        assert legacy.status_code == 200, legacy.text
        assert legacy.json()["water_budget_ml"] == 700
        assert legacy.json()["nutrient_budget_ml"] == 100
        assert legacy.json()["shade_budget_minutes"] == 200

        # Lower to precisely the reserved usage; higher values also allowed.
        exact = client.patch(route, json={
            **good, "water_budget_ml": 300,
            "nutrient_budget_ml": 40, "shade_budget_minutes": 90,
        })
        assert exact.status_code == 200, exact.text
        assert exact.json()["water_budget_ml"] == 300
        assert exact.json()["nutrient_budget_ml"] == 40
        assert exact.json()["shade_budget_minutes"] == 90
        print("PASS: admin editing, resource usage floor, audit, input validation and old clients")


if __name__ == "__main__":
    main()
