from __future__ import annotations

import os
import re
from dataclasses import dataclass
from urllib.parse import quote, urlsplit, urlunsplit


_FARM_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _is_enabled(value: str) -> bool:
    return value.strip().lower() not in {"0", "false", "no", "off"}


@dataclass(frozen=True)
class CameraLiveStreamSettings:
    publish_url: str
    publish_user: str
    publish_password: str
    farm_slug: str
    ffmpeg_path: str = "ffmpeg"
    video_codec: str = "auto"
    reconnect_seconds: float = 5.0

    @classmethod
    def from_env(cls) -> CameraLiveStreamSettings | None:
        publish_url = os.getenv("KISAMORE_MEDIA_PUBLISH_URL", "").strip().rstrip("/")
        if not publish_url:
            return None
        if not _is_enabled(os.getenv("KISAMORE_MEDIA_ENABLED", "true")):
            return None

        parsed = urlsplit(publish_url)
        if parsed.scheme not in {"rtsp", "rtsps"} or not parsed.hostname:
            raise ValueError(
                "KISAMORE_MEDIA_PUBLISH_URL must be an rtsp:// or rtsps:// URL"
            )

        publish_user = os.getenv("KISAMORE_MEDIA_PUBLISH_USER", "").strip()
        publish_password = os.getenv("KISAMORE_MEDIA_PUBLISH_PASSWORD", "").strip()
        if not publish_user or not publish_password:
            raise ValueError(
                "KISAMORE_MEDIA_PUBLISH_USER and KISAMORE_MEDIA_PUBLISH_PASSWORD "
                "are required when live streaming is enabled"
            )

        farm_slug = os.getenv("KISAMORE_MEDIA_FARM_SLUG", "demo-farm").strip().lower()
        if not _FARM_SLUG_RE.fullmatch(farm_slug):
            raise ValueError(
                "KISAMORE_MEDIA_FARM_SLUG must contain lowercase letters, digits and hyphens"
            )

        video_codec = os.getenv("KISAMORE_MEDIA_VIDEO_CODEC", "auto").strip()
        if video_codec not in {"auto", "h264_v4l2m2m", "libx264"}:
            raise ValueError(
                "KISAMORE_MEDIA_VIDEO_CODEC must be auto, h264_v4l2m2m or libx264"
            )

        return cls(
            publish_url=publish_url,
            publish_user=publish_user,
            publish_password=publish_password,
            farm_slug=farm_slug,
            ffmpeg_path=os.getenv("KISAMORE_FFMPEG_PATH", "ffmpeg").strip() or "ffmpeg",
            video_codec=video_codec,
            reconnect_seconds=max(
                1.0,
                float(os.getenv("KISAMORE_MEDIA_RECONNECT_SECONDS", "5")),
            ),
        )

    def rack_publish_url(self, rack_id: int) -> str:
        if rack_id < 1 or rack_id > 16:
            raise ValueError("rack_id must be 1..16")

        parsed = urlsplit(self.publish_url)
        hostname = parsed.hostname or ""
        if ":" in hostname and not hostname.startswith("["):
            hostname = f"[{hostname}]"
        port = f":{parsed.port}" if parsed.port else ""
        credentials = (
            f"{quote(self.publish_user, safe='')}:{quote(self.publish_password, safe='')}@"
        )
        netloc = f"{credentials}{hostname}{port}"
        base_path = parsed.path.rstrip("/")
        stream_path = f"{base_path}/farm/{self.farm_slug}/rack_{rack_id}"
        return urlunsplit((parsed.scheme, netloc, stream_path, "", ""))


def build_ffmpeg_command(
    settings: CameraLiveStreamSettings,
    *,
    rack_id: int,
    width: int,
    height: int,
    fps: int,
    bitrate_kbps: int,
    encoder: str,
) -> list[str]:
    gop = max(fps, fps * 2)
    command = [
        settings.ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "warning",
        "-nostdin",
        "-f",
        "rawvideo",
        "-pixel_format",
        "bgr24",
        "-video_size",
        f"{width}x{height}",
        "-framerate",
        str(fps),
        "-i",
        "pipe:0",
        "-an",
        "-c:v",
        encoder,
    ]

    if encoder == "libx264":
        command.extend([
            "-preset",
            "ultrafast",
            "-tune",
            "zerolatency",
            "-profile:v",
            "baseline",
        ])

    command.extend([
        "-pix_fmt",
        "yuv420p",
        "-b:v",
        f"{bitrate_kbps}k",
        "-maxrate",
        f"{bitrate_kbps}k",
        "-bufsize",
        f"{bitrate_kbps * 2}k",
        "-g",
        str(gop),
        "-keyint_min",
        str(gop),
        "-f",
        "rtsp",
        "-rtsp_transport",
        "tcp",
        settings.rack_publish_url(rack_id),
    ])
    return command
