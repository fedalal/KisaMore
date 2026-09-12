from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Mapping, Optional


PROFILE_DIR_ENV = "KISAMORE_CAMERA_PROFILE_DIR"
DEFAULT_PROFILE_DIR = "data/camera_profiles"


def camera_profile_dir() -> Path:
    return Path(os.getenv(PROFILE_DIR_ENV, DEFAULT_PROFILE_DIR))


def _safe_name(name: str) -> str:
    value = str(name or "").strip()
    if not value:
        raise ValueError("camera name is empty")

    value = value.replace("/", "_").replace("\\", "_")
    value = re.sub(r"[^\w.\-]+", "_", value, flags=re.UNICODE).strip("._")
    if not value:
        raise ValueError("camera name cannot be converted to a safe file name")
    return value


def camera_profile_path(camera_name: str) -> Path:
    return camera_profile_dir() / f"{_safe_name(camera_name)}.json"


def camera_profile_shell_path(camera_name: str) -> Path:
    return camera_profile_dir() / f"{_safe_name(camera_name)}.sh"


def load_camera_profile(camera_name: str) -> dict[str, Any] | None:
    path = camera_profile_path(camera_name)
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[camera-profile] cannot read {path}: {exc}")
        return None

    if not isinstance(data, dict):
        print(f"[camera-profile] invalid profile {path}: root must be an object")
        return None

    return data


def scan_camera_profiles() -> dict[str, dict[str, Any]]:
    """Return saved profiles indexed both by camera_name and file stem."""
    folder = camera_profile_dir()
    result: dict[str, dict[str, Any]] = {}
    if not folder.exists():
        return result

    for path in sorted(folder.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[camera-profile] cannot read {path}: {exc}")
            continue
        if not isinstance(data, dict):
            continue

        profile_name = str(data.get("camera_name") or "").strip()
        if profile_name:
            result[profile_name] = data
        result.setdefault(path.stem, data)

    return result


def load_runtime_camera_profiles(cameras: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Load one profile for every configured KisaMore camera.

    Primary key is the stable camera id (camera_1, camera_2, ...). For
    convenience a profile saved under the camera display name is also accepted.
    The device stored in a profile is informational only: KisaMore always uses
    the device from kisamore.yaml so a tuner can work with /dev/video0 while the
    service later uses /dev/video-rack-1.
    """
    available = scan_camera_profiles()
    loaded: dict[str, dict[str, Any]] = {}

    for camera_id, camera_cfg in cameras.items():
        profile = available.get(camera_id)
        if profile is None:
            display_name = str(getattr(camera_cfg, "name", "") or "").strip()
            if display_name:
                profile = available.get(display_name)

        if profile is None:
            print(f"[camera-profile] {camera_id}: no saved profile, using kisamore.yaml defaults")
            continue

        loaded[camera_id] = profile
        fmt = profile.get("format") if isinstance(profile.get("format"), dict) else {}
        controls = profile.get("controls") if isinstance(profile.get("controls"), dict) else {}
        area = profile.get("frame_area") if isinstance(profile.get("frame_area"), dict) else {}
        print(
            f"[camera-profile] {camera_id}: loaded "
            f"{fmt.get('width', '?')}x{fmt.get('height', '?')} "
            f"{fmt.get('pixelformat', '?')} @{fmt.get('fps', '?')}fps, "
            f"controls={len(controls)}, frame_area={'on' if area.get('enabled') else 'off'}"
        )

    return loaded


def profile_format(
    profile: dict[str, Any] | None,
    *,
    default_width: int,
    default_height: int,
    default_pixelformat: str = "MJPG",
    default_fps: int = 30,
) -> tuple[int, int, str, int]:
    fmt = profile.get("format") if profile and isinstance(profile.get("format"), dict) else {}

    width = int(fmt.get("width") or default_width)
    height = int(fmt.get("height") or default_height)
    pixelformat = str(fmt.get("pixelformat") or default_pixelformat).strip().upper()
    fps_value = fmt.get("fps")
    try:
        fps = max(1, int(round(float(fps_value)))) if fps_value is not None else int(default_fps)
    except Exception:
        fps = int(default_fps)

    if len(pixelformat) != 4:
        pixelformat = default_pixelformat

    return width, height, pixelformat, fps


def profile_controls(profile: dict[str, Any] | None) -> dict[str, int]:
    raw = profile.get("controls") if profile and isinstance(profile.get("controls"), dict) else {}
    result: dict[str, int] = {}
    for name, value in raw.items():
        try:
            result[str(name)] = int(value)
        except Exception:
            continue
    return result


def profile_frame_area(
    profile: dict[str, Any] | None,
    *,
    default_enabled: bool = False,
    default_points: Optional[list[float]] = None,
) -> tuple[bool, Optional[list[float]]]:
    """Return the perspective/crop area stored by camera_tuner.

    Old profiles do not contain frame_area. In that case the values from
    kisamore.yaml remain active, preserving backwards compatibility.
    """
    raw = profile.get("frame_area") if profile and isinstance(profile.get("frame_area"), dict) else None
    if raw is None:
        return bool(default_enabled), list(default_points) if default_points else None

    enabled = bool(raw.get("enabled", False))
    points_raw = raw.get("points")
    points: Optional[list[float]] = None
    if isinstance(points_raw, list) and len(points_raw) == 8:
        try:
            points = [float(value) for value in points_raw]
        except Exception:
            points = None

    if enabled and points is None:
        enabled = False

    return enabled, points


def shell_command_for_profile(
    *,
    device: str,
    fmt: dict[str, Any],
    controls: Mapping[str, int],
) -> str:
    width = int(fmt.get("width") or 2592)
    height = int(fmt.get("height") or 1944)
    pixelformat = str(fmt.get("pixelformat") or "MJPG")
    fps = max(1, int(round(float(fmt.get("fps") or 30))))

    lines = [
        f"v4l2-ctl --device={device} --set-fmt-video=width={width},height={height},pixelformat={pixelformat} --set-parm={fps}"
    ]

    if controls:
        parts = [f"--set-ctrl={name}={int(value)}" for name, value in controls.items()]
        lines.append("v4l2-ctl --device=" + device + " \\\n  " + " \\\n  ".join(parts))

    return "\n\n".join(lines)


def save_camera_profile(
    *,
    camera_name: str,
    device: str,
    fmt: dict[str, Any],
    controls: Mapping[str, int],
    saved_at: str,
    frame_area_enabled: bool = False,
    frame_area_points: Optional[list[float]] = None,
) -> tuple[Path, Path, dict[str, Any], str]:
    folder = camera_profile_dir()
    folder.mkdir(parents=True, exist_ok=True)

    normalized_points: Optional[list[float]] = None
    if isinstance(frame_area_points, list) and len(frame_area_points) == 8:
        try:
            normalized_points = [float(value) for value in frame_area_points]
        except Exception:
            normalized_points = None

    area_enabled = bool(frame_area_enabled and normalized_points is not None)

    profile = {
        "camera_name": str(camera_name).strip(),
        "saved_at": saved_at,
        # Informational only. KisaMore uses its own stable /dev/video-rack-* path.
        "tuner_device": str(device),
        "format": {
            "width": int(fmt.get("width") or 2592),
            "height": int(fmt.get("height") or 1944),
            "pixelformat": str(fmt.get("pixelformat") or "MJPG"),
            "fps": float(fmt.get("fps") or 30),
        },
        "controls": {str(k): int(v) for k, v in controls.items()},
        "frame_area": {
            "enabled": area_enabled,
            "points": normalized_points,
        },
    }

    json_path = camera_profile_path(camera_name)
    shell_path = camera_profile_shell_path(camera_name)

    json_text = json.dumps(profile, ensure_ascii=False, indent=2)
    tmp_json = json_path.with_suffix(".json.tmp")
    tmp_json.write_text(json_text, encoding="utf-8")
    tmp_json.replace(json_path)

    command = shell_command_for_profile(device=device, fmt=profile["format"], controls=profile["controls"])
    tmp_sh = shell_path.with_suffix(".sh.tmp")
    tmp_sh.write_text("#!/bin/sh\nset -e\n\n" + command + "\n", encoding="utf-8")
    tmp_sh.replace(shell_path)
    try:
        shell_path.chmod(0o755)
    except Exception:
        pass

    return json_path, shell_path, profile, command
