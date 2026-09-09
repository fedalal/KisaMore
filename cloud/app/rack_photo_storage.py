from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path


SLOT_COLUMNS = 2
SLOT_ROWS = 3
SLOT_COUNT = SLOT_COLUMNS * SLOT_ROWS


@dataclass(frozen=True)
class StoredRackPhoto:
    latest_path: Path
    archive_path: Path
    slot_paths: dict[int, Path]
    width: int
    height: int


def device_photo_key(device_id: str) -> str:
    return hashlib.sha256(device_id.encode("utf-8")).hexdigest()[:20]


def device_photo_dir(photo_dir: str | Path, device_id: str) -> Path:
    return Path(photo_dir) / device_photo_key(device_id)


def rack_latest_path(photo_dir: str | Path, device_id: str, rack_id: int) -> Path:
    return device_photo_dir(photo_dir, device_id) / "latest" / f"rack_{int(rack_id)}.jpg"


def slot_latest_path(
    photo_dir: str | Path,
    device_id: str,
    rack_id: int,
    slot_number: int,
) -> Path:
    slot = int(slot_number)
    if slot < 1 or slot > SLOT_COUNT:
        raise ValueError("slot_number must be 1..6")
    return (
        device_photo_dir(photo_dir, device_id)
        / "latest"
        / f"rack_{int(rack_id)}_slot_{slot}.jpg"
    )


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def _atomic_save_jpeg(image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    image.save(temporary, format="JPEG", quality=92, optimize=True)
    temporary.replace(path)


def _slot_box(width: int, height: int, slot_number: int) -> tuple[int, int, int, int]:
    """Return an automatic 2x3 crop for slots numbered 1 2 / 3 4 / 5 6."""
    slot = int(slot_number)
    if slot < 1 or slot > SLOT_COUNT:
        raise ValueError("slot_number must be 1..6")

    index = slot - 1
    row = index // SLOT_COLUMNS
    column = index % SLOT_COLUMNS

    left = round(width * column / SLOT_COLUMNS)
    right = round(width * (column + 1) / SLOT_COLUMNS)
    top = round(height * row / SLOT_ROWS)
    bottom = round(height * (row + 1) / SLOT_ROWS)
    return left, top, right, bottom


def store_rack_photo(
    *,
    photo_dir: str | Path,
    device_id: str,
    rack_id: int,
    captured_at: datetime,
    content: bytes,
) -> StoredRackPhoto:
    """Store the master rack JPEG, archive it and refresh six derived slot JPEGs.

    Historical storage contains only the original rack image. The six slot images
    are derived latest views and are overwritten for every new rack frame.
    """
    from PIL import Image, ImageOps

    captured = _aware_utc(captured_at)
    digest = hashlib.sha256(content).hexdigest()
    root = device_photo_dir(photo_dir, device_id)

    # Decode first so a corrupt JPEG can never replace a previously valid latest image.
    with Image.open(BytesIO(content)) as source:
        source.load()
        image = ImageOps.exif_transpose(source).convert("RGB")
        width, height = image.size
        if width < 2 or height < 3:
            raise ValueError("rack photo is too small to split into six slots")

        latest = rack_latest_path(photo_dir, device_id, rack_id)
        _atomic_write(latest, content)

        archive_dir = root / "archive" / f"rack_{int(rack_id)}" / captured.strftime("%Y-%m-%d")
        archive_name = f"{captured.strftime('%H%M%S_%f')}_{digest[:10]}.jpg"
        archive = archive_dir / archive_name
        if not archive.exists():
            _atomic_write(archive, content)

        slot_paths: dict[int, Path] = {}
        for slot_number in range(1, SLOT_COUNT + 1):
            crop = image.crop(_slot_box(width, height, slot_number))
            target = slot_latest_path(photo_dir, device_id, rack_id, slot_number)
            _atomic_save_jpeg(crop, target)
            slot_paths[slot_number] = target

    return StoredRackPhoto(
        latest_path=latest,
        archive_path=archive,
        slot_paths=slot_paths,
        width=width,
        height=height,
    )
