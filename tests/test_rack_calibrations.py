"""Calibration storage and public battle propagation; isolated database."""
import asyncio
import os
from datetime import datetime, timezone
from uuid import uuid4

os.environ["KISAMORE_DATABASE_URL"] = f"sqlite+aiosqlite:///rack-calibration-{uuid4().hex}.db"
os.environ["KISAMORE_BOOTSTRAP_FARM_SLUG"] = "rack-calibration-test"
os.environ["KISAMORE_BOOTSTRAP_DEVICE_ID"] = "calibration-test-device"
os.environ["KISAMORE_BOOTSTRAP_DEVICE_TOKEN"] = "rack-calibration-test-secret-that-is-long"
os.environ["KISAMORE_COOKIE_SECURE"] = "false"
os.environ["KISAMORE_MQTT_ENABLED"] = "false"
from fastapi.testclient import TestClient
from sqlalchemy import select
from cloud.app.main import app
from cloud.app.db import SessionLocal
from cloud.app.models import Device, Plant, RackCameraPhoto, User
from cloud.app.battle_models import PlantBattle
from cloud.app.rack_calibration_api import CalibrationIn


def run(coro):
    return asyncio.run(coro)


def default_slots():
    return {str(i): [[0.04+(i-1)%2*.5,0.04+(i-1)//2*.333],
                     [0.46+(i-1)%2*.5,0.04+(i-1)//2*.333],
                     [0.46+(i-1)%2*.5,0.29+(i-1)//2*.333],
                     [0.04+(i-1)%2*.5,0.29+(i-1)//2*.333]]
            for i in range(1,7)}


async def seed():
    now = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        device=(await db.execute(select(Device))).scalars().first()
        admin=User(
            id=str(uuid4()), email="calibration-admin@example.test",
            display_name="Calibrate Admin", role="admin", is_active=True,
            password_hash="not-used", created_at=now,
        )
        plant=Plant(id=str(uuid4()),code="rocket",
                    names={"en":"Arugula","ru":"Руккола"})
        battle=PlantBattle(
            id=str(uuid4()), device_id=device.id,rack_id=2,
            plant_id=plant.id,title="Calibration sample", status="open",
            entry_price_kisa=0,max_entries=6,water_budget_ml=500,
            nutrient_budget_ml=30,shade_budget_minutes=120,
            winner_reward_kisa=20,created_by_user_id=admin.id,
            created_at=now,updated_at=now,
        )
        cams=[
            RackCameraPhoto(device_id=device.id,rack_id=2,camera_id=c,
                is_primary=(c=="cam-1"),file_path=f"/tmp/{c}.jpg",
                content_type="image/jpeg",size_bytes=200,captured_at=now,updated_at=now)
            for c in ("cam-1","cam-2")
        ]
        db.add_all([admin,plant,battle,*cams])
        await db.commit()
        return device.id,battle.id,admin.id


def main():
    # Reject shape corruption, non-convex quads and values outside the image.
    for invalid in [
        {"1": [[0,0],[1,0],[1,1],[0,1]]},
        {**default_slots(),"3":[[0,0],[1,1],[1,0],[0,1]]},
        {**default_slots(),"3":[[0,0],[1.1,0],[1,1],[0,1]]},
    ]:
        try:
            CalibrationIn(slot_outlines=invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("Malformed camera polygon was accepted")

    with TestClient(app) as client:
        device_id,battle_id,admin_id=run(seed())
        route="/api/v1/admin/rack-calibrations"
        assert client.get(route).status_code==401
        # Auth dependency override applies solely to this isolated test client.
        from cloud.app.security import get_admin_user
        from cloud.app.models import User
        async def admin_override():
            async with SessionLocal() as session:
                return await session.get(User, admin_id)
        app.dependency_overrides[get_admin_user]=admin_override
        try:
            cameras=client.get(route)
            assert cameras.status_code==200,cameras.text
            assert len(cameras.json())==2,cameras.text
            assert all(row["slot_outlines"] is None for row in cameras.json())
            url=f"{route}/{device_id}/2/cam-2"
            shapes=default_slots()
            shapes["1"]=[[.02,.03],[.52,.04],[.48,.27],[.01,.29]]
            saved=client.put(url,json={"slot_outlines":shapes})
            assert saved.status_code==200,saved.text
            assert saved.json()["slot_outlines"]["1"]==shapes["1"]
            assert client.put(f"{route}/{device_id}/2/missing",
                json={"slot_outlines":default_slots()}).status_code==404
            assert client.put(url,json={"slot_outlines":{"1":[[0,0]]}}).status_code==422
            updated=client.get(route).json()
            assert next(x for x in updated if x["camera_id"]=="cam-2")["slot_outlines"]["1"]==shapes["1"]
            assert next(x for x in updated if x["camera_id"]=="cam-1")["slot_outlines"] is None
            public=client.get("/api/v1/public/battles")
            assert public.status_code==200,public.text
            battle=next(b for b in public.json() if b["id"]==battle_id)
            assert next(c for c in battle["camera_views"] if c["camera_id"]=="cam-2")["slot_outlines"]["1"]==shapes["1"]
            assert next(c for c in battle["camera_views"] if c["camera_id"]=="cam-1")["slot_outlines"] is None
            assert client.put(url,json={"slot_outlines":default_slots()}).status_code==200
            assert len(client.get(route).json())==2
        finally:
            app.dependency_overrides.clear()
    print("PASS: authorization, camera selection, six validated 4-corner polygons, persistence, public API")


if __name__=="__main__":
    main()
