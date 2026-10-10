from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

from PIL import Image

from app.hw_config import RackHW
from cloud.app.rack_photo_storage import (
    rack_camera_latest_path,
    rack_latest_path,
    slot_camera_latest_path,
    store_rack_camera_photo,
)


def _jpeg(width: int = 600, height: int = 900) -> bytes:
    image = Image.new("RGB", (width, height), (36, 124, 72))
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def test_rack_camera_assignments_keep_primary_first_and_unique():
    rack = RackHW(
        light_relay=1,
        water_relay=2,
        camera_id="camera_1",
        camera_ids=["camera_2", "camera_1", "camera_2", "camera_3"],
    )

    assert rack.camera_id == "camera_1"
    assert rack.camera_ids == ["camera_1", "camera_2", "camera_3"]


def test_first_camera_becomes_primary_when_only_camera_ids_are_supplied():
    rack = RackHW(
        light_relay=1,
        water_relay=2,
        camera_ids=["camera_top", "camera_side"],
    )

    assert rack.camera_id == "camera_top"
    assert rack.camera_ids == ["camera_top", "camera_side"]


def test_primary_photo_keeps_legacy_paths_and_secondary_is_isolated(tmp_path):
    captured_at = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    content = _jpeg()

    primary = store_rack_camera_photo(
        photo_dir=tmp_path,
        device_id="greenhouse-pi-01",
        rack_id=1,
        camera_id="camera_1",
        is_primary=True,
        captured_at=captured_at,
        content=content,
    )
    secondary = store_rack_camera_photo(
        photo_dir=tmp_path,
        device_id="greenhouse-pi-01",
        rack_id=1,
        camera_id="camera_top",
        is_primary=False,
        captured_at=captured_at,
        content=content,
    )

    assert primary.latest_path == rack_latest_path(
        tmp_path,
        "greenhouse-pi-01",
        1,
    )
    assert secondary.latest_path == rack_camera_latest_path(
        tmp_path,
        "greenhouse-pi-01",
        1,
        "camera_top",
        primary=False,
    )
    assert primary.latest_path != secondary.latest_path
    assert primary.latest_path.is_file()
    assert secondary.latest_path.is_file()

    for slot_number in range(1, 7):
        assert primary.slot_paths[slot_number].is_file()
        assert secondary.slot_paths[slot_number] == slot_camera_latest_path(
            tmp_path,
            "greenhouse-pi-01",
            1,
            "camera_top",
            slot_number,
            primary=False,
        )
        assert secondary.slot_paths[slot_number].is_file()



def test_battle_camera_archives_and_video_paths_are_isolated(tmp_path):
    from datetime import timedelta
    from cloud.app.camera_timelapse_service import (
        camera_archive_frames,
        camera_battle_timelapse_path,
        generate_camera_battle_timelapse,
    )
    import pytest

    captured = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
    for camera_id, is_primary in (("camera_1", True), ("camera_2", False)):
        store_rack_camera_photo(
            photo_dir=tmp_path,
            device_id="test-pi",
            rack_id=1,
            camera_id=camera_id,
            is_primary=is_primary,
            captured_at=captured,
            content=_jpeg(),
        )
    start, end = captured - timedelta(minutes=1), captured + timedelta(minutes=1)
    p1 = camera_archive_frames(tmp_path, "test-pi", 1, "camera_1", True, start, end)
    p2 = camera_archive_frames(tmp_path, "test-pi", 1, "camera_2", False, start, end)
    assert len(p1) == len(p2) == 1
    assert p1[0] != p2[0]
    assert "cameras" not in str(p1[0])
    assert "camera_2" in str(p2[0])
    assert camera_battle_timelapse_path(tmp_path, "battle_a", "camera_1", "24h") != (
        camera_battle_timelapse_path(tmp_path, "battle_a", "camera_2", "24h")
    )
    assert camera_battle_timelapse_path(tmp_path, "battle_a", "camera_1", "full") != (
        camera_battle_timelapse_path(tmp_path, "battle_b", "camera_1", "full")
    )
    with pytest.raises(ValueError):
        camera_battle_timelapse_path(tmp_path, "battle_a", "../invalid", "24h")
    with pytest.raises(ValueError):
        camera_battle_timelapse_path(tmp_path, "battle_a", "camera_1", "wrong")
    assert generate_camera_battle_timelapse(
        photo_dir=tmp_path,
        device_id="test-pi",
        rack_id=1,
        camera_id="camera_2",
        is_primary=False,
        battle_id="battle_a",
        period="24h",
        start_at=start,
        end_at=end,
    ) is None  # Not enough source images: no fake video



def test_battle_camera_video_generation_creates_playable_mp4(tmp_path):
    """Exercise the real image-to-video pipeline when ffmpeg is installed."""
    import shutil
    from datetime import timedelta

    import pytest
    from cloud.app.camera_timelapse_service import generate_camera_battle_timelapse

    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg is not present")
    captured = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
    for i in range(12):
        store_rack_camera_photo(
            photo_dir=tmp_path,
            device_id="test-pi",
            rack_id=2,
            camera_id="camera_secondary",
            is_primary=False,
            captured_at=captured + timedelta(minutes=i),
            content=_jpeg(320, 480),
        )
    result = generate_camera_battle_timelapse(
        photo_dir=tmp_path,
        device_id="test-pi",
        rack_id=2,
        camera_id="camera_secondary",
        is_primary=False,
        battle_id="test-battle",
        period="24h",
        start_at=captured,
        end_at=captured + timedelta(hours=1),
    )
    assert result is not None
    assert result.is_file() and result.stat().st_size > 1000
    assert result.read_bytes()[4:8] == b"ftyp"
