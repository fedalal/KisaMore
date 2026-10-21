"""Regression smoke for public historical battle QR pages.

Run in an isolated container: python -m cloud.test_certificate_smoke
No production database is touched.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from fastapi import HTTPException
from PIL import Image
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from cloud.app import db  # noqa: F401
from cloud.app.battle_models import PlantBattle, PlantBattleAction, PlantBattleEntry
from cloud.app.certificate_api import (
    _photo_file, battle_certificate_page, growth_photo,
)
from cloud.app.models import Base, Device, Farm, Plant, User


def uid():
    return str(uuid4())


async def run():
    now = datetime(2026, 10, 21, 14, 0, tzinfo=timezone.utc)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        farm = Farm(slug="certificate-smoke", name="Test farm")
        session.add(farm)
        await session.flush()
        device = Device(id="certificate-test-device", name="Test", farm_id=farm.id, token_hash="fake")
        plant = Plant(id=uid(), code="radish", names={"en": "Radish", "ru": "Редис"})
        owner = User(id=uid(), email="owner@example.invalid", display_name='A <Tester> & Friend',
                     password_hash="dummy", preferred_language="ru", created_at=now)
        session.add_all([device, plant, owner])
        await session.flush()
        battle = PlantBattle(
            id=uid(), device_id=device.id, rack_id=1, plant_id=plant.id,
            title='Battle <script>alert(1)</script>',
            status="finished", winner_entry_id=None, created_by_user_id=owner.id,
            created_at=now - timedelta(days=9), updated_at=now,
            planted_at=now - timedelta(days=9), finished_at=now,
        )
        entry = PlantBattleEntry(
            id=uid(), battle_id=battle.id, user_id=owner.id,
            slot_number=2, status="finished", price_kisa=20,
            created_at=now - timedelta(days=9),
            water_used_ml=360, nutrient_used_ml=15, shade_used_minutes=40,
        )
        session.add_all([battle, entry])
        session.add(PlantBattleAction(
            id=uid(), entry_id=entry.id, kind="water", amount=50,
            status="completed", requested_at=now - timedelta(days=2)
        ))
        await session.commit()

        response = await battle_certificate_page(entry.id, "ru", session)
        html = response.body.decode()
        assert response.status_code == 200
        assert "Цифровой диплом" in html and "Полив" in html
        assert "360" in html and "50" in html
        assert "A &lt;Tester&gt; &amp; Friend" in html
        assert "&lt;script&gt;" in html and "<script>alert(1)</script>" not in html
        assert html.count('class="photo-card"') == 5
        assert "/public/battle-entries/" in html and "growth-photo/4" in html
        assert "static/battle_certificate.js" in html and "static/battle_certificate.css" in html
        assert "/api/v1/public/battle-entries/" in html
        assert 'class="cert-band"' in html
        assert "kisamore-telegram-icon.png" in html
        assert "battle_certificate_premium.css" in html
        assert "https://ru.kisamore.farm/" in html
        assert "https://t.me/KisaMoreBot" in html
        assert "ПЕРВЫЙ КАДР" in html
        assert 'class="cert-qr"' in html
        assert "is-winner" not in html
        assert response.headers["Content-Security-Policy"].startswith("default-src")
        english = (await battle_certificate_page(entry.id, "en", session)).body.decode()
        assert "Digital certificate" in english and "Water" in english
        assert "A &lt;Tester&gt;" in english
        entry.is_winner = True
        await session.commit()
        winner = (await battle_certificate_page(entry.id, "ru", session)).body.decode()
        assert "ЛУЧШИЙ САДОВОД" in winner and "is-winner" in winner
        battle.status = "growing"
        await session.commit()
        try:
            await battle_certificate_page(entry.id, "ru", session)
            raise AssertionError("Certificate leaked for an unfinished battle")
        except HTTPException as exc:
            assert exc.status_code == 409
        try:
            await growth_photo(entry.id, 0, session)
            raise AssertionError("Growth photos leaked for an unfinished battle")
        except HTTPException as exc:
            assert exc.status_code == 409

    with TemporaryDirectory() as temp:
        start = datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)
        end = datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc)
        from cloud.app.rack_photo_storage import device_photo_dir
        archive = device_photo_dir(temp, "device") / "archive" / "rack_1"
        for moment, color in ((start, (50, 190, 80)), (end, (180, 90, 30))):
            parent = archive / moment.strftime("%Y-%m-%d")
            parent.mkdir(parents=True, exist_ok=True)
            dest = parent / (moment.strftime("%H%M%S_%f") + "_test.jpg")
            Image.new("RGB", (400, 300), color).save(dest)
        path = _photo_file(photo_dir=temp, device_id="device", rack_id=1, slot_number=2,
                           planting_id="planting-smoke", start=start, end=end, index=0)
        assert path and path.is_file()
        assert _photo_file(photo_dir=temp, device_id="device", rack_id=1, slot_number=2,
                           planting_id="planting-smoke", start=start, end=end, index=0) == path
        final = _photo_file(photo_dir=temp, device_id="device", rack_id=1, slot_number=2,
                            planting_id="planting-smoke", start=start, end=end, index=4)
        assert final and final.is_file() and final != path
        try:
            assert _photo_file(photo_dir=temp, device_id="device", rack_id=1, slot_number=2,
                               planting_id="planting-smoke", start=start, end=end, index=5) is None
        except Exception as exc:
            raise AssertionError("Out-of-range photo indexes should never expose paths") from exc

    await engine.dispose()
    print("PASS: localized public certificates, XSS escaping, QR stability, winner badge, unfinished gating, archived growth snapshots")


if __name__ == "__main__":
    asyncio.run(run())
