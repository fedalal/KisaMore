"""Smoke tests for anonymous vs authenticated Android telemetry and admin access."""
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from cloud.app.main import app
from cloud.app.models import Base, User, UserSession
from cloud.app.security import get_session, hash_session_token


async def run():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as con:
        await con.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    admin_id = str(uuid4())
    player_id = str(uuid4())
    async with factory() as db:
        db.add_all([
            User(id=admin_id,email="activity-admin@example.com",display_name="Admin",role="admin",
                 password_hash="x",created_at=now),
            User(id=player_id,email="activity-player@example.com",display_name="Tester",role="customer",
                 password_hash="x",created_at=now),
        ])
        await db.flush()
        db.add_all([
            UserSession(id=str(uuid4()),user_id=admin_id,token_hash=hash_session_token("admin-activity"),
                        expires_at=now+timedelta(days=1),created_at=now),
            UserSession(id=str(uuid4()),user_id=player_id,token_hash=hash_session_token("player-activity"),
                        expires_at=now+timedelta(days=1),created_at=now),
        ])
        await db.commit()

    async def isolated_session():
        async with factory() as db:
            yield db

    app.dependency_overrides[get_session] = isolated_session
    try:
        transport = httpx.ASGITransport(app=app)
        install = str(uuid4())
        async with httpx.AsyncClient(transport=transport,base_url="http://test") as client:
            assert (await client.get("/api/v1/admin/app-activity")).status_code == 401
            payload=dict(event_id=str(uuid4()),installation_id=install,kind="launch",
                         screen="home",app_version="0.6.30",android_version="16")
            assert (await client.post("/api/v1/app/activity",json=payload)).status_code==204
            assert (await client.post("/api/v1/app/activity",json=payload)).status_code==204
            async with factory() as db:
                from cloud.app.app_activity_models import AppActivityEvent
                from sqlalchemy import select
                rows=(await db.execute(select(AppActivityEvent))).scalars().all()
                assert len(rows)==1 and rows[0].user_id is None,rows
            client.cookies.set("kisamore_session","player-activity")
            assert (await client.get("/api/v1/admin/app-activity")).status_code == 403
            payload.update(event_id=str(uuid4()),kind="camera",screen="battle",label="camera_5")
            assert (await client.post("/api/v1/app/activity",json=payload)).status_code==204
            payload.update(event_id=str(uuid4()),kind="heartbeat",label="",seconds=30)
            assert (await client.post("/api/v1/app/activity",json=payload)).status_code==204
            client.cookies.set("kisamore_session","admin-activity")
            res=await client.get("/api/v1/admin/app-activity?days=7")
            assert res.status_code==200,res.text
            data=res.json()
            assert data["tracked_people"]==2,data
            assert data["tracked_accounts"]==1,data
            assert data["launches"]==1,data
            player=next(p for p in data["people"] if p["user_id"]==player_id)
            guest=next(p for p in data["people"] if p["user_id"] is None)
            assert player["email"]=="activity-player@example.com"
            assert guest["name"].startswith("Гость")
            assert player["minutes"]==0.5,player
            events=await client.get("/api/v1/admin/app-activity/events",params={"key":player["key"],"days":7})
            assert events.status_code==200,events.text
            assert {e["kind"] for e in events.json()["events"]}=={"camera","heartbeat"}
            assert (await client.get("/api/v1/admin/app-activity/events",
                                     params={"key":guest["key"]})).json()["events"][0]["kind"]=="launch"
        print("PASS: anonymous/user separation, auth, duplicate idempotency, per-user timeline")
    finally:
        app.dependency_overrides.pop(get_session,None)
        await engine.dispose()

if __name__=="__main__":
    asyncio.run(run())
