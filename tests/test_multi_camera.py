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
