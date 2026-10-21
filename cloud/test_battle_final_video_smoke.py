"""Offline regression test for admin upload and public QR final film.

Run: python -m cloud.test_battle_final_video_smoke
No production database or real telegram messages.
"""
import asyncio
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from uuid import uuid4
import subprocess

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from cloud.app import db
from cloud.app.battle_models import PlantBattle, PlantBattleEntry
from cloud.app.battle_final_video_api import (
    upload_final_video, delete_final_video, admin_final_video, public_final_video,
    final_video_exists, final_video_path,
)
from cloud.app.certificate_api import battle_certificate_page
from cloud.app.models import Base, Device, Farm, Plant, User


def uid(): return str(uuid4())


async def run():
    now = datetime.now(timezone.utc)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    with TemporaryDirectory() as temp:
        import cloud.app.battle_final_video_api as video_api
        import cloud.app.certificate_api as cert_api
        original_video_settings = video_api.get_settings
        original_cert_settings = cert_api.get_settings
        fake = SimpleNamespace(photo_dir=temp, farm_timezone="Europe/Moscow")
        video_api.get_settings = lambda: fake
        cert_api.get_settings = lambda: fake
        try:
            mp4 = Path(temp)/"example.mp4"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "color=c=green:s=160x120:r=12:d=1.2",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                "-y", str(mp4)
            ], check=True, timeout=30)
            async with factory() as session:
                farm = Farm(slug="video-smoke", name="Test")
                session.add(farm)
                await session.flush()
                device = Device(id="video-test-device", farm_id=farm.id, name="test", token_hash="test")
                plant = Plant(id=uid(), code="test-radish", names={"ru": "Редис", "en": "Radish"})
                owner = User(id=uid(), email="turntable@test.invalid", display_name="Grower",
                             password_hash="hash", preferred_language="ru", created_at=now)
                session.add_all([device, plant, owner])
                await session.flush()
                battle = PlantBattle(id=uid(), device_id=device.id, rack_id=1,
                    plant_id=plant.id, title="Battle test", status="growing",
                    created_by_user_id=owner.id, created_at=now, updated_at=now)
                entry = PlantBattleEntry(id=uid(), battle_id=battle.id, user_id=owner.id,
                    slot_number=1, price_kisa=10, status="active", created_at=now)
                session.add_all([battle, entry])
                await session.commit()

                try:
                    await public_final_video(entry.id, session)
                    raise AssertionError("Unfinished video's public route should be blocked")
                except HTTPException as err:
                    assert err.status_code == 409

                try:
                    await upload_final_video(battle.id, entry.id, UploadFile(
                        filename="fake.mp4", file=BytesIO(b"this is not a video")), owner, session)
                    raise AssertionError("Fake mp4 was accepted")
                except HTTPException as err:
                    assert err.status_code == 422
                assert not final_video_exists(entry.id)

                result = await upload_final_video(battle.id, entry.id, UploadFile(
                    filename="final.mp4", file=BytesIO(mp4.read_bytes())), owner, session)
                assert result["final_video_ready"]
                assert final_video_path(entry.id).read_bytes() == mp4.read_bytes()
                assert (await admin_final_video(battle.id, entry.id, owner, session)).status_code == 200

                try:
                    await upload_final_video(battle.id, entry.id, UploadFile(
                        filename="../broken.mp4", file=BytesIO(b"invalid replacement")), owner, session)
                    raise AssertionError("Invalid replacement accepted")
                except HTTPException as err:
                    assert err.status_code == 422
                assert final_video_path(entry.id).read_bytes() == mp4.read_bytes()

                battle.status = "finished"
                entry.status = "finished"
                battle.finished_at = now
                await session.commit()

                public = await public_final_video(entry.id, session)
                assert public.status_code == 200
                html = (await battle_certificate_page(entry.id, "ru", session)).body.decode()
                assert "ИТОГОВЫЙ ВИДЕОПОРТРЕТ" in html
                assert f"/public/battle-entries/{entry.id}/final-video" in html

                try:
                    await delete_final_video(battle.id, entry.id, owner, session)
                    raise AssertionError("Can delete final video after finish")
                except HTTPException as err:
                    assert err.status_code == 409

                try:
                    await upload_final_video(battle.id, entry.id, UploadFile(
                        filename="final.mp4", file=BytesIO(mp4.read_bytes())), owner, session)
                    raise AssertionError("Can overwrite final video after finish")
                except HTTPException as err:
                    assert err.status_code == 409

                try:
                    final_video_path("../../etc/passwd")
                    raise AssertionError("Traversal accepted")
                except HTTPException as err:
                    assert err.status_code == 404

                assert final_video_path(entry.id).exists()

                # Simulate the durable Telegram outbox delivery without using
                # any network or the actual KisaMore Telegram token.
                from cloud.app.telegram.activity_notifier import TelegramActivityDelivery
                import cloud.app.telegram.activity_notifier as notifier
                key = f"battle_final_video:{battle.id}:{entry.id}"
                session.add(TelegramActivityDelivery(
                    event_key=key, telegram_user_id=123456789,
                    kind="battle_final_video",
                    payload={"video_path": str(final_video_path(entry.id)),
                             "caption": "🎬 Итоговое видео вашего выращенного растения",
                             "url": "https://kisamore.farm/api/v1/battle-certificate/"+entry.id},
                    status="pending", attempts=0, created_at=now,
                ))
                await session.commit()
                calls = []
                class FakeBot:
                    async def send_video(self, user_id, path, caption="", reply_markup=None):
                        calls.append((user_id, path, caption, reply_markup))
                old_factory = notifier.SessionLocal
                notifier.SessionLocal = factory
                try:
                    count_sent, count_failed = await notifier.send_pending(FakeBot())
                finally:
                    notifier.SessionLocal = old_factory
                assert (count_sent, count_failed) == (1, 0)
                assert calls[0][0] == 123456789
                assert calls[0][1] == final_video_path(entry.id)
                assert "Итоговое видео" in calls[0][2]
                assert (await session.get(TelegramActivityDelivery, key)).status == "sent"
        finally:
            video_api.get_settings = original_video_settings
            cert_api.get_settings = original_cert_settings
    await engine.dispose()
    print("PASS: H.264 video, atomic upload, rejected replacement, preview, QR embed, finish gate")


if __name__ == "__main__":
    asyncio.run(run())
