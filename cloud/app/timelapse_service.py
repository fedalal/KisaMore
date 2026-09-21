from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import get_settings
from .rack_photo_storage import SLOT_COUNT, device_photo_dir


logger = logging.getLogger(__name__)
FPS = 12
MAX_FRAMES = 360
MIN_FRAMES = 12
TIMELAPSE_RENDER_VERSION = "timestamp-v1"


@dataclass(frozen=True)
class TimelapsePeriod:
    code: str
    window: timedelta | None
    refresh: timedelta


PERIODS = {
    "24h": TimelapsePeriod("24h", timedelta(hours=24), timedelta(hours=1)),
    "3d": TimelapsePeriod("3d", timedelta(days=3), timedelta(hours=3)),
    "full": TimelapsePeriod("full", None, timedelta(hours=12)),
}


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def slot_timelapse_path(
    photo_dir: str | Path,
    device_id: str,
    rack_id: int,
    slot_number: int,
    period: str,
) -> Path:
    if period not in ("24h", "3d"):
        raise ValueError("slot timelapse period must be 24h or 3d")
    slot = int(slot_number)
    if slot < 1 or slot > SLOT_COUNT:
        raise ValueError("slot_number must be 1..6")
    return (
        device_photo_dir(photo_dir, device_id)
        / "timelapse"
        / f"rack_{int(rack_id)}"
        / f"slot_{slot}"
        / f"{period}.mp4"
    )


def _safe_planting_id(planting_id: str) -> str:
    safe_id = "".join(ch for ch in str(planting_id) if ch.isalnum() or ch in ("-", "_"))
    if not safe_id:
        raise ValueError("invalid planting id")
    return safe_id


def planting_media_dir(photo_dir: str | Path, planting_id: str) -> Path:
    return Path(photo_dir) / "timelapse" / "plantings" / _safe_planting_id(planting_id)


def planting_timelapse_path(photo_dir: str | Path, planting_id: str) -> Path:
    return planting_media_dir(photo_dir, planting_id) / "full.mp4"


def planting_final_photo_path(photo_dir: str | Path, planting_id: str) -> Path:
    return planting_media_dir(photo_dir, planting_id) / "final.jpg"


def _frame_datetime(path: Path) -> datetime | None:
    # archive/rack_N/YYYY-MM-DD/HHMMSS_microseconds_hash.jpg
    try:
        date_text = path.parent.name
        parts = path.stem.split("_", 2)
        if len(parts) < 2:
            return None
        return datetime.strptime(
            f"{date_text} {parts[0]} {parts[1]}",
            "%Y-%m-%d %H%M%S %f",
        ).replace(tzinfo=timezone.utc)
    except (ValueError, OSError):
        return None


def archive_frames(
    photo_dir: str | Path,
    device_id: str,
    rack_id: int,
    start_at: datetime,
    end_at: datetime,
) -> list[Path]:
    start = _aware_utc(start_at)
    end = _aware_utc(end_at)
    if end < start:
        return []

    root = device_photo_dir(photo_dir, device_id) / "archive" / f"rack_{int(rack_id)}"
    if not root.is_dir():
        return []

    paths: list[tuple[datetime, Path]] = []
    day = start.date()
    last_day = end.date()
    while day <= last_day:
        directory = root / day.isoformat()
        if directory.is_dir():
            for path in directory.glob("*.jpg"):
                captured = _frame_datetime(path)
                if captured is not None and start <= captured <= end:
                    paths.append((captured, path))
        day += timedelta(days=1)
    paths.sort(key=lambda item: item[0])
    return [path for _, path in paths]


def select_evenly(paths: list[Path], max_frames: int = MAX_FRAMES) -> list[Path]:
    if len(paths) <= max_frames:
        return list(paths)
    if max_frames < 2:
        return [paths[-1]]
    step = (len(paths) - 1) / (max_frames - 1)
    indexes = [min(len(paths) - 1, round(index * step)) for index in range(max_frames)]
    result: list[Path] = []
    last = -1
    for index in indexes:
        if index != last:
            result.append(paths[index])
            last = index
    return result


def _farm_zone() -> ZoneInfo:
    try:
        return ZoneInfo(get_settings().farm_timezone)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _slot_box(width: int, height: int, slot_number: int) -> tuple[int, int, int, int]:
    slot = int(slot_number)
    if slot < 1 or slot > SLOT_COUNT:
        raise ValueError("slot_number must be 1..6")

    index = slot - 1
    row = index // 2
    column = index % 2

    left = round(width * column / 2)
    right = round(width * (column + 1) / 2)
    top = round(height * row / 3)
    bottom = round(height * (row + 1) / 3)
    return left, top, right, bottom


def _timestamp_text(captured_at: datetime) -> str:
    local = _aware_utc(captured_at).astimezone(_farm_zone())
    return local.strftime("%Y-%m-%d %H:%M:%S")


def _prepare_timelapse_frame(
    source: Path,
    target: Path,
    *,
    slot_number: int,
    captured_at: datetime,
) -> None:
    """Crop the requested container and draw an international timestamp."""
    from PIL import Image, ImageDraw, ImageFont, ImageOps

    with Image.open(source) as raw:
        raw.load()
        image = ImageOps.exif_transpose(raw).convert("RGB")
        crop = image.crop(_slot_box(image.width, image.height, slot_number))

    text = _timestamp_text(captured_at)
    font_size = max(18, min(48, round(min(crop.width, crop.height) * 0.05)))
    try:
        font = ImageFont.load_default(size=font_size)
    except TypeError:
        font = ImageFont.load_default()

    overlay = Image.new("RGBA", crop.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    padding_x = max(8, round(font_size * 0.35))
    padding_y = max(5, round(font_size * 0.20))
    margin = max(10, round(font_size * 0.45))

    right = crop.width - margin
    bottom = crop.height - margin
    left = max(0, right - text_width - 2 * padding_x)
    top = max(0, bottom - text_height - 2 * padding_y)

    draw.rounded_rectangle(
        (left, top, right, bottom),
        radius=max(4, round(font_size * 0.18)),
        fill=(0, 0, 0, 150),
    )
    draw.text(
        (right - text_width - padding_x, bottom - text_height - padding_y),
        text,
        font=font,
        fill=(255, 255, 255, 255),
    )

    prepared = Image.alpha_composite(crop.convert("RGBA"), overlay).convert("RGB")
    target.parent.mkdir(parents=True, exist_ok=True)
    prepared.save(target, format="JPEG", quality=92, optimize=True)


def ensure_planting_final_photo(
    *,
    photo_dir: str | Path,
    device_id: str,
    rack_id: int,
    slot_number: int,
    planting_id: str,
    start_at: datetime,
    end_at: datetime,
) -> Path | None:
    """Persist the last frame of one planting as immutable historical media.

    A rack/slot is reused by future crops, so historical Telegram cards must
    never point at the mutable slot_latest image. The final image is generated
    from the archived rack frame that belongs to this planting and stored under
    planting_id.
    """
    target = planting_final_photo_path(photo_dir, planting_id)
    if target.is_file():
        return target

    frames = archive_frames(photo_dir, device_id, rack_id, start_at, end_at)
    if not frames:
        return None

    source = frames[-1]
    captured_at = _frame_datetime(source)
    if captured_at is None:
        return None

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp.jpg")
    _prepare_timelapse_frame(
        source,
        temporary,
        slot_number=slot_number,
        captured_at=captured_at,
    )
    temporary.replace(target)
    logger.info(
        "Saved final planting photo: planting=%s device=%s rack=%s slot=%s source=%s target=%s",
        planting_id,
        device_id,
        rack_id,
        slot_number,
        source,
        target,
    )
    return target


def _render_marker_path(target: Path) -> Path:
    return target.with_name(target.name + f".{TIMELAPSE_RENDER_VERSION}")


def _crop_filter(slot_number: int) -> str:
    slot = int(slot_number)
    if slot < 1 or slot > SLOT_COUNT:
        raise ValueError("slot_number must be 1..6")
    index = slot - 1
    row = index // 2
    column = index % 2
    width = "trunc(iw/4)*2"
    height = "trunc(ih/6)*2"
    x = "0" if column == 0 else "iw/2"
    y = "0" if row == 0 else ("ih/3" if row == 1 else "2*ih/3")
    return f"crop={width}:{height}:{x}:{y}"


def _needs_refresh(target: Path, frames: list[Path], refresh: timedelta, *, final: bool) -> bool:
    if not target.is_file():
        return True
    if not _render_marker_path(target).is_file():
        # One-time rebuild of timelapses created before timestamps were added.
        return True
    try:
        target_mtime = target.stat().st_mtime
    except OSError:
        return True
    newest_source = max((path.stat().st_mtime for path in frames), default=0.0)
    if newest_source > target_mtime:
        if final:
            return True
        age = datetime.now(timezone.utc).timestamp() - target_mtime
        return age >= refresh.total_seconds()
    return False


def generate_slot_timelapse(
    *,
    photo_dir: str | Path,
    device_id: str,
    rack_id: int,
    slot_number: int,
    period: str,
    start_at: datetime,
    end_at: datetime,
    target: Path | None = None,
    final: bool = False,
) -> Path | None:
    spec = PERIODS[period]
    frames = archive_frames(photo_dir, device_id, rack_id, start_at, end_at)
    if len(frames) < MIN_FRAMES:
        return None
    frames = select_evenly(frames)
    output = target or slot_timelapse_path(photo_dir, device_id, rack_id, slot_number, period)
    if not _needs_refresh(output, frames, spec.refresh, final=final):
        return output

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kisamore-timelapse-") as temp_name:
        temp_dir = Path(temp_name)
        for index, source in enumerate(frames, start=1):
            captured_at = _frame_datetime(source)
            if captured_at is None:
                continue
            prepared = temp_dir / f"frame_{index:06d}.jpg"
            _prepare_timelapse_frame(
                source,
                prepared,
                slot_number=slot_number,
                captured_at=captured_at,
            )

        temporary = output.with_suffix(".tmp.mp4")
        vf = "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p"
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-framerate",
            str(FPS),
            "-start_number",
            "1",
            "-i",
            str(temp_dir / "frame_%06d.jpg"),
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-preset",
            os.getenv("KISAMORE_TIMELAPSE_PRESET", "veryfast"),
            "-crf",
            os.getenv("KISAMORE_TIMELAPSE_CRF", "23"),
            "-movflags",
            "+faststart",
            str(temporary),
        ]
        try:
            subprocess.run(
                command,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=max(60, int(os.getenv("KISAMORE_TIMELAPSE_FFMPEG_TIMEOUT", "180"))),
            )
        except subprocess.CalledProcessError as exc:
            message = (exc.stderr or b"").decode("utf-8", errors="replace")[-1200:]
            raise RuntimeError(f"ffmpeg timelapse failed: {message}") from exc
        temporary.replace(output)
        _render_marker_path(output).write_text(
            TIMELAPSE_RENDER_VERSION,
            encoding="utf-8",
        )

    logger.info(
        "Generated timelapse: period=%s device=%s rack=%s slot=%s frames=%s duration=%.1fs target=%s",
        period,
        device_id,
        rack_id,
        slot_number,
        len(frames),
        len(frames) / FPS,
        output,
    )
    return output


def period_window(period: str, now: datetime | None = None) -> tuple[datetime, datetime]:
    spec = PERIODS[period]
    if spec.window is None:
        raise ValueError("full period needs an explicit planting start")
    end = _aware_utc(now or datetime.now(timezone.utc))
    return end - spec.window, end
