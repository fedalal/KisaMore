from __future__ import annotations

import time
from typing import Optional

import cv2

from .camera_access import device_access_lock
from .camera_manager import CameraWorker, camera_manager


def _configured_camera_for_device(device: str):
    """Return the current CameraHW for a device without introducing import cycles."""
    try:
        from . import runtime

        if not runtime.cfg:
            return None
        wanted = str(device or "").strip()
        for cam in runtime.cfg.cameras.values():
            if str(cam.device or "").strip() == wanted:
                return cam
    except Exception:
        pass
    return None


def _resolve_control(device: str, name: str, value, fallback):
    if value is not None:
        return value
    cam = _configured_camera_for_device(device)
    if cam is not None:
        configured = getattr(cam, name, None)
        if configured is not None:
            return configured
    return fallback


def _fallback_controls(
    *,
    device: str,
    autofocus_enabled: bool,
    focus_absolute: Optional[int],
    white_balance_auto: bool,
    white_balance_temperature: Optional[int],
    brightness: Optional[int],
    contrast: Optional[int],
    saturation: Optional[int],
    sharpness: Optional[int],
) -> dict[str, int]:
    brightness = _resolve_control(device, "brightness", brightness, 1)
    contrast = _resolve_control(device, "contrast", contrast, 8)
    saturation = _resolve_control(device, "saturation", saturation, 10)
    sharpness = _resolve_control(device, "sharpness", sharpness, 0)

    controls: dict[str, int] = {
        "focus_automatic_continuous": 1 if autofocus_enabled else 0,
        "white_balance_automatic": 1 if white_balance_auto else 0,
    }

    if not autofocus_enabled and focus_absolute is not None:
        controls["focus_absolute"] = int(focus_absolute)
    if not white_balance_auto and white_balance_temperature is not None:
        controls["white_balance_temperature"] = int(white_balance_temperature)

    for name, value in (
        ("brightness", brightness),
        ("contrast", contrast),
        ("saturation", saturation),
        ("sharpness", sharpness),
    ):
        if value is not None:
            controls[name] = int(value)

    return controls


def _apply_profile_controls(helper: CameraWorker, controls: dict[str, int]):
    """Apply the exact saved Linux V4L2 profile after STREAMON.

    Focus is written exactly once. There is deliberately no 0→...→target focus
    approach: repeated movement is slow and unnecessarily wears the lens motor.
    Dependent controls are skipped when their corresponding automatic mode is on.
    """
    supported = helper._read_supported_controls()

    # Some cameras expose alternate names. Convert the common saved names only
    # when the profile name itself is not supported by this device.
    normalized = dict(controls)
    if "focus_automatic_continuous" in normalized and "focus_automatic_continuous" not in supported:
        if "focus_auto" in supported:
            normalized["focus_auto"] = normalized.pop("focus_automatic_continuous")
    if "white_balance_automatic" in normalized and "white_balance_automatic" not in supported:
        if "white_balance_temperature_auto" in supported:
            normalized["white_balance_temperature_auto"] = normalized.pop("white_balance_automatic")

    autofocus = normalized.get(
        "focus_automatic_continuous",
        normalized.get("focus_auto"),
    )
    auto_wb = normalized.get(
        "white_balance_automatic",
        normalized.get("white_balance_temperature_auto"),
    )
    auto_exposure = normalized.get("auto_exposure")

    # Automatic/manual mode controls must be set before their dependent values.
    priority = [
        "focus_automatic_continuous",
        "focus_auto",
        "white_balance_automatic",
        "white_balance_temperature_auto",
        "auto_exposure",
    ]

    ordered_names = []
    for name in priority:
        if name in normalized and name not in ordered_names:
            ordered_names.append(name)
    for name in normalized:
        if name not in ordered_names:
            ordered_names.append(name)

    applied: list[str] = []
    skipped: list[str] = []

    for name in ordered_names:
        value = normalized[name]
        if name not in supported:
            skipped.append(f"{name}=unsupported")
            continue

        if name == "focus_absolute" and autofocus == 1:
            skipped.append("focus_absolute=auto")
            continue
        if name == "white_balance_temperature" and auto_wb == 1:
            skipped.append("white_balance_temperature=auto")
            continue
        if name == "exposure_time_absolute" and auto_exposure != 1:
            skipped.append("exposure_time_absolute=auto")
            continue

        helper._run_v4l2_ctrl(name, int(value))
        applied.append(f"{name}={int(value)}")

    print(
        f"[camera-one-shot] profile applied for {helper.device}: "
        + ", ".join(applied)
        + (f"; skipped: {', '.join(skipped)}" if skipped else "")
    )


def _read_valid_frame(cap, width: int, height: int, deadline: float):
    while time.monotonic() < deadline:
        ok, candidate = cap.read()
        if not ok or candidate is None:
            time.sleep(0.03)
            continue
        candidate_height, candidate_width = candidate.shape[:2]
        if candidate_width != width or candidate_height != height:
            continue
        return candidate
    return None


def capture_one_shot_jpeg(
    *,
    device: str,
    jpeg_quality: int,
    frame_width: int,
    frame_height: int,
    pixel_format: str = "MJPG",
    fps: int = 30,
    flip_vertical: bool = False,
    flip_horizontal: bool = False,
    warp_enabled: bool = False,
    warp_points: Optional[list[float]] = None,
    autofocus_enabled: bool = False,
    focus_absolute: Optional[int] = 120,
    white_balance_auto: bool = False,
    white_balance_temperature: Optional[int] = 5,
    brightness: Optional[int] = None,
    contrast: Optional[int] = None,
    saturation: Optional[int] = None,
    sharpness: Optional[int] = None,
    profile_controls: Optional[dict[str, int]] = None,
    focus_ramp: bool = False,  # retained only for backwards call compatibility; ignored
    timeout_seconds: float = 10.0,
) -> Optional[bytes]:
    """Open the camera, apply one saved profile, obtain one frame, release it.

    There is no permanent stream and no focus ramp. If profile_controls is
    supplied it is the source of truth; otherwise the old kisamore.yaml camera
    fields are used as a fallback for installations that have not been tuned yet.
    """
    _ = focus_ramp

    if profile_controls:
        controls = {str(k): int(v) for k, v in profile_controls.items()}
        profile_source = "saved-profile"
    else:
        controls = _fallback_controls(
            device=device,
            autofocus_enabled=autofocus_enabled,
            focus_absolute=focus_absolute,
            white_balance_auto=white_balance_auto,
            white_balance_temperature=white_balance_temperature,
            brightness=brightness,
            contrast=contrast,
            saturation=saturation,
            sharpness=sharpness,
        )
        profile_source = "kisamore-yaml"

    access_lock = device_access_lock(device)

    with access_lock:
        previous_worker: CameraWorker | None = None
        with camera_manager.lock:
            previous_worker = camera_manager.workers.pop(device, None)

        if previous_worker is not None:
            previous_worker.stop()
            if previous_worker.thread and previous_worker.thread.is_alive():
                with camera_manager.lock:
                    camera_manager.workers[device] = previous_worker
                print(
                    f"[camera-one-shot] cannot stop old worker for {device}; "
                    "one-shot capture skipped"
                )
                return None

        helper = CameraWorker(
            device=device,
            frame_width=frame_width,
            frame_height=frame_height,
            autofocus_enabled=autofocus_enabled,
            focus_absolute=focus_absolute,
            white_balance_auto=white_balance_auto,
            white_balance_temperature=white_balance_temperature,
        )
        cap = None

        try:
            helper._read_supported_controls()

            cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
            if not cap.isOpened():
                print(f"[camera-one-shot] cannot open camera {device}")
                return None

            helper.cap = cap
            fourcc_text = str(pixel_format or "MJPG").upper()
            if len(fourcc_text) != 4:
                fourcc_text = "MJPG"

            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc_text))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(frame_width))
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(frame_height))
            cap.set(cv2.CAP_PROP_FPS, int(fps))
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass

            actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = float(cap.get(cv2.CAP_PROP_FPS))
            actual_fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
            actual_fourcc_text = "".join(
                chr((actual_fourcc >> 8 * i) & 0xFF)
                for i in range(4)
            )

            deadline = time.monotonic() + max(2.0, float(timeout_seconds))

            # OpenCV normally performs VIDIOC_STREAMON on the first read(). Some
            # camera firmware resets image controls at that point, so apply the
            # saved profile only after one priming frame has started the stream.
            priming_frame = _read_valid_frame(
                cap,
                actual_width,
                actual_height,
                deadline,
            )
            if priming_frame is None:
                print(f"[camera-one-shot] no priming frame received from {device}")
                return None

            _apply_profile_controls(helper, controls)

            print(
                f"[camera-one-shot] {device} source={profile_source}, "
                f"requested={frame_width}x{frame_height} {fourcc_text}@{fps}, "
                f"actual={actual_width}x{actual_height} {actual_fourcc_text}@{actual_fps:.1f}, "
                "focus_ramp=disabled"
            )

            # Let automatic WB/exposure or the lens settle without moving focus
            # repeatedly. Manual profiles need fewer frames; automatic modes get
            # a longer warm-up.
            autofocus = controls.get(
                "focus_automatic_continuous",
                controls.get("focus_auto", 0),
            )
            auto_wb = controls.get(
                "white_balance_automatic",
                controls.get("white_balance_temperature_auto", 0),
            )
            auto_exposure = controls.get("auto_exposure", 0)
            required_good_frames = 60 if (autofocus == 1 or auto_wb == 1 or auto_exposure == 0) else 30

            frame = priming_frame
            good_frames = 0
            while time.monotonic() < deadline:
                candidate = _read_valid_frame(
                    cap,
                    actual_width,
                    actual_height,
                    deadline,
                )
                if candidate is None:
                    break
                frame = candidate
                good_frames += 1
                if good_frames >= required_good_frames:
                    break

            if good_frames < required_good_frames:
                print(
                    f"[camera-one-shot] {device} warm-up ended early: "
                    f"frames={good_frames}/{required_good_frames}"
                )

            if actual_width != int(frame_width) or actual_height != int(frame_height):
                print(
                    f"[camera-one-shot] warning: {device} did not accept requested "
                    f"resolution {frame_width}x{frame_height}"
                )

            with helper.lock:
                helper.frame.frame = frame
                helper.frame.last_error = None
                helper.frame.updated_at = time.time()

            return helper.get_jpeg(
                jpeg_quality=jpeg_quality,
                flip_vertical=flip_vertical,
                flip_horizontal=flip_horizontal,
                warp_enabled=warp_enabled,
                warp_points=warp_points,
            )

        except Exception as exc:
            print(
                f"[camera-one-shot] capture failed for {device}: "
                f"{type(exc).__name__}: {exc}"
            )
            return None

        finally:
            helper.cap = None
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass

            if previous_worker is not None:
                with camera_manager.lock:
                    camera_manager.workers[device] = previous_worker
                previous_worker.start()
