from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .rack_photo_storage import SLOT_COUNT, device_photo_dir


FPS = 12
MAX_FRAMES = 360
MIN_FRAMES = 12


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


def planting_timelapse_path(photo_dir: str | Path, planting_id: str) -> Path:
    safe_id = "".join(ch for ch in str(planting_id) if ch.isalnum() or ch in ("-", "_"))
    if not safe_id:
        raise ValueError("invalid planting id")
    return Path(photo_dir) / "timelapse" / "plantings" / safe_id / "full.mp4"


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
            link = temp_dir / f"frame_{index:06d}.jpg"
            try:
                link.symlink_to(source.resolve())
            except OSError:
                link.write_bytes(source.read_bytes())

        temporary = output.with_suffix(".tmp.mp4")
        vf = f"{_crop_filter(slot_number)},scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p"
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

    return output


def period_window(period: str, now: datetime | None = None) -> tuple[datetime, datetime]:
    spec = PERIODS[period]
    if spec.window is None:
        raise ValueError("full period needs an explicit planting start")
    end = _aware_utc(now or datetime.now(timezone.utc))
    return end - spec.window, end
