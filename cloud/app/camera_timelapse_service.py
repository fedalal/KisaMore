"""Per-camera whole-rack timelapses for Battle, independent of slot crop videos.

The photo upload pipeline already archives primary and secondary cameras separately.
Generated videos are stored under battle ID to prevent mixing consecutive crops.
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .rack_photo_storage import camera_photo_dir, device_photo_dir, safe_camera_id
from .timelapse_service import FPS, MAX_FRAMES, MIN_FRAMES, PERIODS, _aware_utc, _frame_datetime, _timestamp_text, select_evenly

logger = logging.getLogger(__name__)
RENDER_VERSION = "battle-camera-v1"


def _safe_battle_id(battle_id: str) -> str:
    value = str(battle_id or "")
    if not value or len(value) > 80 or any(not (c.isalnum() or c in "_-") for c in value):
        raise ValueError("Invalid battle ID")
    return value


def camera_battle_timelapse_path(
    photo_dir: str | Path, battle_id: str, camera_id: str, period: str,
) -> Path:
    if period not in PERIODS:
        raise ValueError("Unknown timelapse period")
    if not camera_id or safe_camera_id(camera_id) != camera_id:
        raise ValueError("Invalid camera ID")
    return (
        Path(photo_dir) / "timelapse" / "battles" / _safe_battle_id(battle_id)
        / camera_id / f"{period}.mp4"
    )


def camera_archive_frames(
    photo_dir: str | Path,
    device_id: str,
    rack_id: int,
    camera_id: str,
    is_primary: bool,
    start_at: datetime,
    end_at: datetime,
) -> list[Path]:
    start, end = _aware_utc(start_at), _aware_utc(end_at)
    if end < start:
        return []
    root = (
        device_photo_dir(photo_dir, device_id) if is_primary
        else camera_photo_dir(photo_dir, device_id, camera_id)
    ) / "archive" / f"rack_{int(rack_id)}"
    frames: list[tuple[datetime, Path]] = []
    day = start.date()
    while day <= end.date():
        folder = root / day.isoformat()
        if folder.is_dir():
            for item in folder.glob("*.jpg"):
                stamp = _frame_datetime(item)
                if stamp is not None and start <= stamp <= end:
                    frames.append((stamp, item))
        day += timedelta(days=1)
    frames.sort(key=lambda row: row[0])
    return [path for _, path in frames]


def _prepare_whole_rack_frame(source: Path, target: Path, stamp: datetime) -> None:
    from PIL import Image, ImageDraw, ImageFont, ImageOps

    with Image.open(source) as opened:
        opened.load()
        image = ImageOps.exif_transpose(opened).convert("RGB")
    image.thumbnail((960, 960), Image.Resampling.LANCZOS)
    # ffmpeg's yuv420p requires even dimensions.
    if image.width % 2 or image.height % 2:
        image = image.crop((0, 0, image.width - image.width % 2, image.height - image.height % 2))
    if not image.width or not image.height:
        raise ValueError("Camera frame is too small")

    caption = _timestamp_text(stamp)
    try:
        font = ImageFont.load_default(size=max(16, min(image.width, image.height) // 30))
    except TypeError:
        font = ImageFont.load_default()
    draw = ImageDraw.Draw(image, "RGBA")
    bbox = draw.textbbox((0, 0), caption, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    margin, pad = 8, 7
    x, y = max(0, image.width - tw - pad * 2 - margin), max(0, image.height - th - pad * 2 - margin)
    draw.rounded_rectangle((x, y, min(image.width, x + tw + pad * 2), min(image.height, y + th + pad * 2)),
                           radius=5, fill=(0, 0, 0, 160))
    draw.text((x + pad, y + pad), caption, font=font, fill=(255, 255, 255, 255))
    image.save(target, "JPEG", quality=85)


def generate_camera_battle_timelapse(
    *,
    photo_dir: str | Path,
    device_id: str,
    rack_id: int,
    camera_id: str,
    is_primary: bool,
    battle_id: str,
    period: str,
    start_at: datetime,
    end_at: datetime,
    final: bool = False,
) -> Path | None:
    if period not in PERIODS:
        raise ValueError("Invalid timelapse period")
    frames = camera_archive_frames(
        photo_dir, device_id, rack_id, camera_id, is_primary, start_at, end_at,
    )
    if len(frames) < MIN_FRAMES:
        return None
    selected = select_evenly(frames, 240 if period == "full" else min(MAX_FRAMES, 180))
    target = camera_battle_timelapse_path(photo_dir, battle_id, camera_id, period)
    marker = target.with_suffix(".version")
    if target.is_file() and marker.is_file() and marker.read_text().strip() == RENDER_VERSION:
        newest = max((p.stat().st_mtime for p in frames), default=0)
        age = datetime.now(timezone.utc).timestamp() - target.stat().st_mtime
        if newest <= target.stat().st_mtime or (not final and age < PERIODS[period].refresh.total_seconds()):
            return target

    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kisamore-rackcam-") as directory:
        folder = Path(directory)
        for i, frame in enumerate(selected, 1):
            stamp = _frame_datetime(frame)
            if stamp:
                _prepare_whole_rack_frame(frame, folder / f"frame_{i:06d}.jpg", stamp)
        temporary = folder / "render.mp4"
        command = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-framerate", str(FPS), "-start_number", "1",
            "-i", str(folder / "frame_%06d.jpg"),
            "-vf", "format=yuv420p",
            "-c:v", "libx264",
            "-preset", os.getenv("KISAMORE_TIMELAPSE_PRESET", "veryfast"),
            "-crf", os.getenv("KISAMORE_TIMELAPSE_CRF", "23"),
            "-movflags", "+faststart",
            str(temporary),
        ]
        try:
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                           timeout=max(60, int(os.getenv("KISAMORE_TIMELAPSE_FFMPEG_TIMEOUT", "180"))))
        except subprocess.CalledProcessError as exc:
            raise RuntimeError("Rack camera timelapse failed: " +
                               (exc.stderr or b"").decode("utf-8", errors="replace")[-1000:]) from exc
        temporary.replace(target)
        marker.write_text(RENDER_VERSION, encoding="utf-8")
    logger.info("Rendered camera timelapse battle=%s camera=%s period=%s frames=%s", battle_id, camera_id, period, len(selected))
    return target
