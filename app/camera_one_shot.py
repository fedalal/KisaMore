from __future__ import annotations

import os
import threading
import time
from typing import Optional

import cv2

from .camera_access import device_access_lock
from .camera_manager import CameraWorker, camera_manager


_focus_ready_lock = threading.Lock()
# device -> (target focus, /dev node ctime). A reconnect recreates the device
# node, so the next frame performs the focus approach again.
_focus_ready: dict[str, tuple[int, int]] = {}


def _device_signature(device: str) -> int:
    try:
        return int(os.stat(device).st_ctime_ns)
    except Exception:
        return 0


def _focus_needs_ramp(device: str, target: Optional[int], enabled: bool) -> bool:
    if not enabled or target is None:
        return False
    wanted = (int(target), _device_signature(device))
    with _focus_ready_lock:
        return _focus_ready.get(device) != wanted


def _mark_focus_ready(device: str, target: Optional[int]):
    if target is None:
        return
    with _focus_ready_lock:
        _focus_ready[device] = (int(target), _device_signature(device))


def _clear_focus_ready(device: str):
    with _focus_ready_lock:
        _focus_ready.pop(device, None)


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


def _focus_ramp_values(target: int) -> list[int]:
    """Approach manual focus from zero in several increasing steps.

    The current UVC camera can report the requested focus value while the real
    lens position is still slightly different after a reconnect/power cycle.
    During testing, approaching 120 as 0→20→...→120 produced repeatably sharper
    frames than jumping directly to 120.
    """
    target = max(0, int(target))
    if target == 0:
        return [0]

    segments = 6
    values = [round(target * i / segments) for i in range(segments + 1)]
    result: list[int] = []
    for value in values:
        if not result or result[-1] != value:
            result.append(value)
    return result


def _apply_one_shot_controls(
    helper: CameraWorker,
    *,
    autofocus_enabled: bool,
    focus_absolute: Optional[int],
    focus_ramp: bool,
    white_balance_auto: bool,
    white_balance_temperature: Optional[int],
    brightness: Optional[int],
    contrast: Optional[int],
    saturation: Optional[int],
    sharpness: Optional[int],
):
    """Apply only the native controls that were validated on the real camera.

    Exposure is deliberately not changed here. This camera returns to its usable
    automatic exposure state after reset, while explicitly writing the reported
    auto_exposure=0 state is rejected by its driver.
    """
    autofocus_control = helper._find_control(
        "focus_automatic_continuous",
        "focus_auto",
    )
    if autofocus_control:
        helper._run_v4l2_ctrl(
            autofocus_control,
            1 if autofocus_enabled else 0,
        )

    focus_control = helper._find_control("focus_absolute")
    if not autofocus_enabled and focus_absolute is not None and focus_control:
        values = (
            _focus_ramp_values(int(focus_absolute))
            if focus_ramp
            else [int(focus_absolute)]
        )
        for value in values:
            helper._run_v4l2_ctrl(focus_control, value)
            if focus_ramp:
                # Give the lens motor time to physically reach each intermediate
                # position. For focus=120 the full homing pass is about 0.8 s.
                time.sleep(0.12)

    white_balance_auto_control = helper._find_control(
        "white_balance_automatic",
        "white_balance_temperature_auto",
    )
    if white_balance_auto_control:
        helper._run_v4l2_ctrl(
            white_balance_auto_control,
            1 if white_balance_auto else 0,
        )

    temperature_control = helper._find_control("white_balance_temperature")
    if (
        not white_balance_auto
        and white_balance_temperature is not None
        and temperature_control
    ):
        helper._run_v4l2_ctrl(
            temperature_control,
            int(white_balance_temperature),
        )

    for name, value in (
        ("brightness", brightness),
        ("contrast", contrast),
        ("saturation", saturation),
        ("sharpness", sharpness),
    ):
        if value is None:
            continue
        control = helper._find_control(name)
        if control:
            helper._run_v4l2_ctrl(control, int(value))

    print(
        f"[camera-one-shot] controls applied for {helper.device}: "
        f"autofocus={autofocus_enabled}, focus={focus_absolute}, "
        f"focus_ramp={focus_ramp}, brightness={brightness}, contrast={contrast}, "
        f"saturation={saturation}, sharpness={sharpness}, "
        f"auto_wb={white_balance_auto}, wb={white_balance_temperature}"
    )


def capture_one_shot_jpeg(
    *,
    device: str,
    jpeg_quality: int,
    frame_width: int,
    frame_height: int,
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
    focus_ramp: bool = True,
    timeout_seconds: float = 10.0,
) -> Optional[bytes]:
    """Open the camera, obtain one stable MJPG frame, then release the device.

    No permanent camera stream is needed. This same path is used by scheduled
    photos, the rack UI and camera-settings snapshots.

    Some UVC cameras reset controls when VIDIOC_STREAMON happens. OpenCV normally
    starts the stream on the first read(), so controls are applied only after one
    valid priming frame has been received.
    """
    brightness = _resolve_control(device, "brightness", brightness, 1)
    contrast = _resolve_control(device, "contrast", contrast, 8)
    saturation = _resolve_control(device, "saturation", saturation, 10)
    sharpness = _resolve_control(device, "sharpness", sharpness, 0)

    ramp_this_capture = (
        not autofocus_enabled
        and _focus_needs_ramp(device, focus_absolute, focus_ramp)
    )

    access_lock = device_access_lock(device)

    with access_lock:
        # Defensive compatibility with an old process state. New UI routes no
        # longer create live CameraWorkers, but stop one if it somehow exists.
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
            # Cache supported control names/ranges before OpenCV owns the device.
            helper._read_supported_controls()

            cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
            if not cap.isOpened():
                _clear_focus_ready(device)
                print(f"[camera-one-shot] cannot open camera {device}")
                return None

            helper.cap = cap
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(frame_width))
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(frame_height))
            cap.set(cv2.CAP_PROP_FPS, 30)
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass

            actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
            actual_fourcc_text = "".join(
                chr((actual_fourcc >> 8 * i) & 0xFF)
                for i in range(4)
            )

            deadline = time.monotonic() + max(2.0, float(timeout_seconds))

            # VideoCapture usually performs VIDIOC_STREAMON on the first read().
            # Receive one valid frame first, then apply native controls while no
            # read() call is in progress.
            priming_frame = None
            while time.monotonic() < deadline:
                ok, candidate = cap.read()
                if not ok or candidate is None:
                    time.sleep(0.05)
                    continue

                height, width = candidate.shape[:2]
                if width != actual_width or height != actual_height:
                    continue

                priming_frame = candidate
                break

            if priming_frame is None:
                _clear_focus_ready(device)
                print(f"[camera-one-shot] no priming frame received from {device}")
                return None

            _apply_one_shot_controls(
                helper,
                autofocus_enabled=autofocus_enabled,
                focus_absolute=focus_absolute,
                focus_ramp=ramp_this_capture,
                white_balance_auto=white_balance_auto,
                white_balance_temperature=white_balance_temperature,
                brightness=brightness,
                contrast=contrast,
                saturation=saturation,
                sharpness=sharpness,
            )

            print(
                f"[camera-one-shot] {device} requested={frame_width}x{frame_height}, "
                f"actual={actual_width}x{actual_height}, fourcc={actual_fourcc_text}, "
                "controls_after_streamon=yes"
            )

            frame = priming_frame
            good_frames = 0

            # Match the successful manual tests: discard enough frames after
            # changing controls for focus and camera processing to settle.
            required_good_frames = 60 if (autofocus_enabled or white_balance_auto) else 30

            while time.monotonic() < deadline:
                ok, candidate = cap.read()
                if not ok or candidate is None:
                    time.sleep(0.05)
                    continue

                height, width = candidate.shape[:2]
                if width != actual_width or height != actual_height:
                    continue

                frame = candidate
                good_frames += 1
                if good_frames >= required_good_frames:
                    break

            if frame is None:
                _clear_focus_ready(device)
                print(f"[camera-one-shot] no frame received from {device}")
                return None

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

            jpeg = helper.get_jpeg(
                jpeg_quality=jpeg_quality,
                flip_vertical=flip_vertical,
                flip_horizontal=flip_horizontal,
                warp_enabled=warp_enabled,
                warp_points=warp_points,
            )
            if jpeg and not autofocus_enabled:
                _mark_focus_ready(device, focus_absolute)
            return jpeg

        except Exception as exc:
            _clear_focus_ready(device)
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
                # This should only happen while upgrading from an old process
                # state. Do not recreate permanent streaming workers in normal
                # operation.
                with camera_manager.lock:
                    camera_manager.workers[device] = previous_worker
                previous_worker.start()
