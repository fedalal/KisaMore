"""Public battle profiles expose display name and avatar only, never contacts."""
import asyncio
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

folder = Path(tempfile.mkdtemp(prefix="battle-public-participants-"))
os.environ["KISAMORE_DATABASE_URL"] = f"sqlite+aiosqlite:///battle-profiles-{uuid4().hex}.db"
os.environ["KISAMORE_BOOTSTRAP_FARM_SLUG"] = "battle-public-profiles"
os.environ["KISAMORE_BOOTSTRAP_DEVICE_ID"] = "profiles-test-device"
os.environ["KISAMORE_BOOTSTRAP_DEVICE_TOKEN"] = "profiles-test-token-12345678901234567890"
os.environ["KISAMORE_COOKIE_SECURE"] = "false"
os.environ["KISAMORE_PHOTO_DIR"] = str(folder)
os.environ["KISAMORE_MQTT_ENABLED"] = "false"

from fastapi.testclient import TestClient
from sqlalchemy import select
from cloud.app.main import app
from cloud.app.db import SessionLocal
from cloud.app.models import Device, Plant, User
from cloud.app.battle_models import PlantBattle, PlantBattleEntry
from cloud.app.account_preferences_api import AccountPreferences
from cloud.app.security import hash_password


async def seed():
    now = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        device = (await db.execute(select(Device))).scalars().first()
        user = User(
            id=str(uuid4()), email="private-customer@example.test",
            display_name="Greenhouse Player", role="customer",
            is_active=True, password_hash=hash_password("strong-password"),
            created_at=now,
        )
        plant = Plant(
            id=str(uuid4()), code="test-rocket",
            names={"en": "Arugula", "ru": "Рукола"},
        )
        battle = PlantBattle(
            id=str(uuid4()), device_id=device.id, rack_id=1, plant_id=plant.id,
            title="A public battle", status="open", entry_price_kisa=10, max_entries=6,
            water_budget_ml=500, nutrient_budget_ml=100, shade_budget_minutes=240,
            winner_reward_kisa=20, created_by_user_id=user.id,
            created_at=now, updated_at=now,
        )
        entry = PlantBattleEntry(
            id=str(uuid4()), battle_id=battle.id, user_id=user.id, slot_number=1,
            telegram_user_id=None, price_kisa=10, status="active",
            water_used_ml=0, nutrient_used_ml=0, shade_used_minutes=0,
            is_winner=False, created_at=now,
        )
        db.add_all([user,plant,battle,entry])
        await db.commit()
        return battle.id, entry.id, user.id


async def attach_avatar(user_id):
    avatar_folder=folder/"avatars"
    avatar_folder.mkdir(parents=True, exist_ok=True)
    data=b"\xff\xd8\xff\xe0fake avatar test data"
    (avatar_folder/"test.jpg").write_bytes(data)
    async with SessionLocal() as db:
        db.add(AccountPreferences(user_id=user_id, avatar_key="test.jpg"))
        await db.commit()
    return data


async def refund_entry(entry_id):
    async with SessionLocal() as db:
        entry=await db.get(PlantBattleEntry,entry_id)
        entry.status="refunded"
        await db.commit()


def main():
    with TestClient(app) as client:
        battle_id,entry_id,user_id = asyncio.run(seed())
        resp=client.get("/api/v1/public/battles")
        assert resp.status_code==200,resp.text
        battle=next(b for b in resp.json() if b["id"]==battle_id)
        assert battle["plant_names"]["ru"]=="Рукола"
        person=battle["entries"][0]
        assert person["participant_name"]=="Greenhouse Player"
        assert person["participant_avatar_url"] is None
        assert "private-customer@example.test" not in resp.text
        assert "telegram_user_id" not in resp.text
        route=f"/api/v1/public/battles/entries/{entry_id}/avatar"
        assert client.get(route).status_code==404

        expected=asyncio.run(attach_avatar(user_id))
        resp=client.get("/api/v1/public/battles")
        person=next(b for b in resp.json() if b["id"]==battle_id)["entries"][0]
        assert person["participant_avatar_url"]==route
        photo=client.get(route)
        assert photo.status_code==200 and photo.content==expected
        assert photo.headers["content-type"]=="image/jpeg"

        asyncio.run(refund_entry(entry_id))
        assert client.get(route).status_code==404
        updated=client.get("/api/v1/public/battles").json()
        assert next(b for b in updated if b["id"]==battle_id)["entries"]==[]
        print("PASS: public participant names, translations, entry-scoped avatars and private contacts")


if __name__=="__main__":
    main()
