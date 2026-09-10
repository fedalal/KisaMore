from __future__ import annotations

import time
from typing import Optional

import cv2

from .camera_access import device_access_lock
from .camera_manager import CameraWorker, camera_manager


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
    autofocus_enabled: bool = True,
    focus_absolute: Optional[int] = None,
    white_balance_auto: bool = True,
    white_balance_temperature: Optional[int] = None,
    timeout_seconds: float = 10.0,
) -> Optional[bytes]:
    """Capture one full-resolution frame without keeping a 4K stream open.

    If this camera currently has a live-preview worker, pause only that worker,
    take the high-resolution frame, release the USB camera, then restore the
    previous live worker. Other cameras are not interrupted.
    """
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
                    f"[camera-one-shot] cannot pause live worker for {device}; "
                    "high-resolution capture skipped"
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
            # Apply UVC controls before opening the stream. This mirrors the
            # normal CameraWorker startup sequence and avoids control ioctls
            # racing with VideoCapture.read().
            helper._apply_camera_controls()

            cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
            if not cap.isOpened():
                print(f"[camera-one-shot] cannot open camera {device}")
                return None

            helper.cap = cap
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(frame_width))
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(frame_height))
            # The 3840x2160 mode reported by the current cameras is a native
            # MJPG 30 fps mode. We only read a handful of frames and close it.
            cap.set(cv2.CAP_PROP_FPS, 30)
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass

            helper._apply_opencv_controls()

            actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
            actual_fourcc_text = "".join(
                chr((actual_fourcc >> 8 * i) & 0xFF)
                for i in range(4)
            )
            print(
                f"[camera-one-shot] {device} requested={frame_width}x{frame_height}, "
                f"actual={actual_width}x{actual_height}, fourcc={actual_fourcc_text}"
            )

            deadline = time.monotonic() + max(2.0, float(timeout_seconds))
            frame = None
            good_frames = 0

            # Discard initial frames after switching the UVC mode. Some cameras
            # produce one or two incomplete MJPG frames immediately after open.
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
                if good_frames >= 3:
                    break

            if frame is None:
                print(f"[camera-one-shot] no frame received from {device}")
                return None

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
                    # Live requests are blocked by device_access_lock while this
                    # function runs, so the old worker can be restored safely.
                    camera_manager.workers[device] = previous_worker
                previous_worker.start()
