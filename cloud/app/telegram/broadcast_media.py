from __future__ import annotations

import logging
import subprocess
from pathlib import Path


logger = logging.getLogger(__name__)

# Telegram's public Bot API accepts multipart uploads of up to 50 MB for
# animations and videos. Keep a little headroom for the prepared file.
TELEGRAM_FILE_LIMIT_BYTES = 50 * 1024 * 1024
TELEGRAM_TARGET_BYTES = 46 * 1024 * 1024

PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".m4v", ".mov", ".webm"}


def media_kind(path: str | Path, original_name: str | None = None) -> str:
    source = Path(path)
    original_suffix = Path(str(original_name or "")).suffix.lower()
    suffix = original_suffix or source.suffix.lower()
    if suffix == ".gif":
        return "animation"
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    if suffix in PHOTO_EXTENSIONS:
        return "photo"
    # Stored legacy broadcasts only contained images.
    if source.suffix.lower() in PHOTO_EXTENSIONS:
        return "photo"
    raise ValueError(f"Unsupported broadcast media type: {suffix or source.name}")


def media_mime(path: str | Path, original_name: str | None = None) -> str:
    kind = media_kind(path, original_name)
    suffix = Path(path).suffix.lower()
    if kind == "animation":
        return "image/gif" if suffix == ".gif" else "video/mp4"
    if kind == "video":
        if suffix == ".webm":
            return "video/webm"
        if suffix == ".mov":
            return "video/quicktime"
        return "video/mp4"
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(suffix, "application/octet-stream")


def _duration_seconds(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        text=True,
    )
    duration = float((result.stdout or "").strip())
    if duration <= 0:
        raise ValueError("Media duration is not available")
    return duration


def _transcode(
    source: Path,
    target: Path,
    *,
    animation: bool,
) -> Path:
    duration = _duration_seconds(source)
    target.parent.mkdir(parents=True, exist_ok=True)

    # Aim below Telegram's 50 MB upload ceiling. Retry with a lower bitrate if
    # container overhead or source complexity still makes the result too large.
    target_bytes = TELEGRAM_TARGET_BYTES
    for attempt in range(3):
        total_bps = max(48_000, int(target_bytes * 8 / duration * 0.92))
        audio_bps = 0 if animation else min(64_000, max(24_000, total_bps // 5))
        video_bps = max(24_000, total_bps - audio_bps)
        video_kbps = max(24, video_bps // 1000)
        audio_kbps = max(24, audio_bps // 1000) if audio_bps else 0

        temporary = target.with_suffix(".tmp.mp4")
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-vf",
            "scale=w='if(gt(iw,1280),1280,iw)':h='if(gt(ih,1280),1280,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-b:v",
            f"{video_kbps}k",
            "-maxrate",
            f"{video_kbps}k",
            "-bufsize",
            f"{max(video_kbps * 2, 48)}k",
        ]
        if animation:
            command.extend(["-an"])
        else:
            command.extend(["-c:a", "aac", "-b:a", f"{audio_kbps}k"])
        command.extend(["-movflags", "+faststart", str(temporary)])

        try:
            subprocess.run(
                command,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=900,
            )
        except subprocess.CalledProcessError as exc:
            message = (exc.stderr or b"").decode("utf-8", errors="replace")[-1500:]
            raise RuntimeError(f"ffmpeg broadcast media conversion failed: {message}") from exc

        size = temporary.stat().st_size
        if size < TELEGRAM_FILE_LIMIT_BYTES:
            temporary.replace(target)
            logger.info(
                "Prepared broadcast %s: source=%s target=%s size=%.1f MB attempt=%s",
                "animation" if animation else "video",
                source,
                target,
                size / 1024 / 1024,
                attempt + 1,
            )
            return target

        temporary.unlink(missing_ok=True)
        target_bytes = int(target_bytes * 0.72)

    raise RuntimeError(
        "Could not reduce broadcast media below Telegram's 50 MB upload limit"
    )


def prepare_media_for_telegram(
    path: str | Path,
    original_name: str | None = None,
) -> tuple[str, Path]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)

    kind = media_kind(source, original_name)
    if kind == "photo":
        return kind, source

    if kind == "animation":
        # GIFs are converted once to a silent H.264 MP4 and still sent through
        # sendAnimation. This greatly reduces large GIFs while preserving
        # Telegram's looping animation UI.
        target = source.with_name(f"{source.stem}_telegram_animation.mp4")
        if target.is_file() and target.stat().st_mtime >= source.stat().st_mtime:
            return kind, target
        return kind, _transcode(source, target, animation=True)

    # Telegram's public Bot API only accepts 50 MB uploads. Keep an existing
    # MP4 if it already fits; otherwise convert it once to a sendable MP4.
    if source.suffix.lower() == ".mp4" and source.stat().st_size < TELEGRAM_FILE_LIMIT_BYTES:
        return kind, source

    target = source.with_name(f"{source.stem}_telegram_video.mp4")
    if target.is_file() and target.stat().st_mtime >= source.stat().st_mtime:
        return kind, target
    return kind, _transcode(source, target, animation=False)
