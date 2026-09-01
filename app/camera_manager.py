import threading
import time
import subprocess
import re
from dataclasses import dataclass
from typing import Optional, Any

import cv2
import numpy as np


@dataclass
class CameraFrame:
    frame: Optional[Any] = None
    last_error: Optional[str] = None
    updated_at: float = 0.0


class CameraWorker:
    def __init__(
            self,
            device: str,
            frame_width: int = 1280,
            frame_height: int = 720,
            autofocus_enabled: bool = True,
            focus_absolute: Optional[int] = None,
            white_balance_auto: bool = True,
            white_balance_temperature: Optional[int] = None,
    ):
        self.device = device
        self.frame_width = frame_width
        self.frame_height = frame_height

        self.autofocus_enabled = autofocus_enabled
        self.focus_absolute = focus_absolute
        self.white_balance_auto = white_balance_auto
        self.white_balance_temperature = white_balance_temperature

        self.frame = CameraFrame()
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.reconfigure_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.cap = None
        self._supported_controls_cache: Optional[set[str]] = None
        self._control_ranges_cache: dict[str, tuple[int, int, int]] = {}

    def update_settings(
            self,
            frame_width: int = 1280,
            frame_height: int = 720,
            autofocus_enabled: bool = True,
            focus_absolute: Optional[int] = None,
            white_balance_auto: bool = True,
            white_balance_temperature: Optional[int] = None,
    ):
        need_reconfigure = False

        with self.lock:
            if self.frame_width != frame_width or self.frame_height != frame_height:
                need_reconfigure = True

            if (
                    self.autofocus_enabled != autofocus_enabled
                    or self.focus_absolute != focus_absolute
                    or self.white_balance_auto != white_balance_auto
                    or self.white_balance_temperature != white_balance_temperature
            ):
                need_reconfigure = True

            self.frame_width = frame_width
            self.frame_height = frame_height
            self.autofocus_enabled = autofocus_enabled
            self.focus_absolute = focus_absolute
            self.white_balance_auto = white_balance_auto
            self.white_balance_temperature = white_balance_temperature

        # VideoCapture.read(), VideoCapture.release() and v4l2-ctl must never run
        # concurrently for the same USB camera. Some UVC drivers block in the
        # kernel when a control ioctl is sent while a frame is being read.
        # The worker owns the device and performs the reconfiguration itself.
        if need_reconfigure:
            self.reconfigure_event.set()

    def start(self):
        if self.thread and self.thread.is_alive():
            return

        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def restart(self):
        self.reconfigure_event.set()

    def stop(self):
        self.stop_event.set()
        self.reconfigure_event.set()

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3)

        # Never release a VideoCapture from a thread different from the one
        # executing read(). The worker's finally block owns that operation.
        if self.thread and self.thread.is_alive():
            print(f"[camera-manager] worker did not stop in time for {self.device}")
        else:
            self.thread = None

    def _set_error(self, message: str):
        with self.lock:
            self.frame.last_error = message
            self.frame.updated_at = time.time()

    def _read_supported_controls(self) -> set[str]:
        if self._supported_controls_cache is not None:
            return self._supported_controls_cache

        try:
            result = subprocess.run(
                [
                    "v4l2-ctl",
                    "--device",
                    self.device,
                    "--list-ctrls",
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=3,
            )
        except Exception as e:
            print(
                f"[camera-manager] cannot list controls for {self.device}: {e}"
            )
            return set()

        if result.returncode != 0:
            print(
                f"[camera-manager] cannot list controls for {self.device}: "
                f"{result.stderr.strip()}"
            )
            return set()

        controls: set[str] = set()
        ranges: dict[str, tuple[int, int, int]] = {}
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            name = stripped.split(maxsplit=1)[0]
            if name.replace("_", "").isalnum():
                controls.add(name)

            minimum = re.search(r"\bmin=(-?\d+)", stripped)
            maximum = re.search(r"\bmax=(-?\d+)", stripped)
            step = re.search(r"\bstep=(\d+)", stripped)
            if minimum and maximum:
                ranges[name] = (
                    int(minimum.group(1)),
                    int(maximum.group(1)),
                    max(1, int(step.group(1))) if step else 1,
                )

        self._supported_controls_cache = controls
        self._control_ranges_cache = ranges
        return controls

    def _find_control(self, *candidates: str) -> Optional[str]:
        supported = self._read_supported_controls()
        return next((name for name in candidates if name in supported), None)

    def _normalize_control_value(self, name: str, value: int) -> int:
        self._read_supported_controls()
        limits = self._control_ranges_cache.get(name)
        if limits is None:
            return value

        minimum, maximum, step = limits
        # The UI represents focus on a stable 0..1023 scale, while many UVC
        # cameras expose only 0..255. Preserve the relative focus position.
        if (
                name == "focus_absolute"
                and minimum >= 0
                and maximum < 1023
                and 0 <= value <= 1023
        ):
            normalized = minimum + round(value / 1023 * (maximum - minimum))
        else:
            normalized = min(max(value, minimum), maximum)
        normalized = minimum + round((normalized - minimum) / step) * step
        normalized = min(max(normalized, minimum), maximum)
        if normalized != value:
            print(
                f"[camera-manager] adjusted {name} for {self.device}: "
                f"requested={value}, applied={normalized}, "
                f"range={minimum}..{maximum}, step={step}"
            )
        return normalized

    def _run_v4l2_ctrl(self, name: str, value: int):
        value = self._normalize_control_value(name, value)
        ctrl = f"{name}={value}"
        try:
            result = subprocess.run(
                [
                    "v4l2-ctl",
                    "--device",
                    self.device,
                    "--set-ctrl",
                    ctrl,
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=3,
            )

            if result.returncode != 0:
                print(
                    f"[camera-manager] v4l2 ctrl failed for {self.device}: "
                    f"{ctrl}; {result.stderr.strip()}"
                )

        except Exception as e:
            print(f"[camera-manager] v4l2 ctrl exception for {self.device}: {ctrl}; {e}")

    def _set_opencv_control(self, property_name: str, value: int) -> bool:
        if self.cap is None:
            return False
        property_id = getattr(cv2, property_name, None)
        if property_id is None:
            return False
        try:
            return bool(self.cap.set(property_id, value))
        except Exception as e:
            print(
                f"[camera-manager] OpenCV ctrl exception for {self.device}: "
                f"{property_name}={value}; {e}"
            )
            return False

    def _apply_opencv_controls(self):
        """Reapply controls after VideoCapture opens, before the first read()."""
        with self.lock:
            autofocus_enabled = self.autofocus_enabled
            focus_absolute = self.focus_absolute
            white_balance_auto = self.white_balance_auto
            white_balance_temperature = self.white_balance_temperature

        self._set_opencv_control(
            "CAP_PROP_AUTOFOCUS",
            1 if autofocus_enabled else 0,
        )
        if not autofocus_enabled and focus_absolute is not None:
            focus_control = self._find_control("focus_absolute")
            focus_value = (
                self._normalize_control_value(focus_control, int(focus_absolute))
                if focus_control
                else int(focus_absolute)
            )
            self._set_opencv_control("CAP_PROP_FOCUS", focus_value)

        self._set_opencv_control(
            "CAP_PROP_AUTO_WB",
            1 if white_balance_auto else 0,
        )
        if not white_balance_auto and white_balance_temperature is not None:
            temperature_control = self._find_control("white_balance_temperature")
            temperature_value = (
                self._normalize_control_value(
                    temperature_control,
                    int(white_balance_temperature),
                )
                if temperature_control
                else int(white_balance_temperature)
            )
            self._set_opencv_control(
                "CAP_PROP_WB_TEMPERATURE",
                temperature_value,
            )

        print(
            f"[camera-manager] controls applied for {self.device}: "
            f"autofocus={autofocus_enabled}, focus={focus_absolute}, "
            f"auto_wb={white_balance_auto}, wb_temperature={white_balance_temperature}"
        )

    def _apply_camera_controls(self):
        with self.lock:
            autofocus_enabled = self.autofocus_enabled
            focus_absolute = self.focus_absolute
            white_balance_auto = self.white_balance_auto
            white_balance_temperature = self.white_balance_temperature

        # Different UVC cameras expose different names for the same controls.
        # Apply only controls that the selected device actually reports.
        autofocus_control = self._find_control(
            "focus_automatic_continuous",
            "focus_auto",
        )
        if autofocus_control:
            self._run_v4l2_ctrl(
                autofocus_control,
                1 if autofocus_enabled else 0,
            )

        focus_control = self._find_control("focus_absolute")
        if not autofocus_enabled and focus_absolute is not None and focus_control:
            time.sleep(0.1)
            self._run_v4l2_ctrl(focus_control, int(focus_absolute))

        white_balance_auto_control = self._find_control(
            "white_balance_automatic",
            "white_balance_temperature_auto",
        )
        if white_balance_auto_control:
            self._run_v4l2_ctrl(
                white_balance_auto_control,
                1 if white_balance_auto else 0,
            )

        temperature_control = self._find_control("white_balance_temperature")
        if (
                not white_balance_auto
                and white_balance_temperature is not None
                and temperature_control
        ):
            self._run_v4l2_ctrl(
                temperature_control,
                int(white_balance_temperature),
            )

    def _run(self):
        while not self.stop_event.is_set():
            try:
                # Clear the request before taking a settings snapshot. A request
                # arriving afterwards remains set and causes another clean cycle.
                self.reconfigure_event.clear()

                # v4l2-ctl gets exclusive access before OpenCV opens the stream.
                self._apply_camera_controls()

                self.cap = cv2.VideoCapture(self.device, cv2.CAP_V4L2)

                if not self.cap.isOpened():
                    self._set_error(f"Не удалось открыть камеру {self.device}")
                    time.sleep(3)
                    continue

                with self.lock:
                    width = self.frame_width
                    height = self.frame_height

                # Важно: у новой камеры высокие разрешения доступны именно в MJPG.
                # Если не указать FOURCC, OpenCV может открыть камеру в YUYV
                # и получить более низкое разрешение.
                self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                self.cap.set(cv2.CAP_PROP_FPS, 15)

                # Opening or changing the UVC format can reset automatic
                # controls. Apply them again through the same capture handle,
                # still before read(), so there is no concurrent USB ioctl.
                self._apply_opencv_controls()

                actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                actual_fourcc = int(self.cap.get(cv2.CAP_PROP_FOURCC))
                actual_fourcc_text = "".join(
                    chr((actual_fourcc >> 8 * i) & 0xFF)
                    for i in range(4)
                )

                print(
                    f"[camera-manager] {self.device} requested={width}x{height}, "
                    f"actual={actual_width}x{actual_height}, fourcc={actual_fourcc_text}"
                )

                while (
                        not self.stop_event.is_set()
                        and not self.reconfigure_event.is_set()
                ):
                    ok, frame = self.cap.read()

                    if not ok:
                        self._set_error(f"Не удалось получить кадр с {self.device}")
                        time.sleep(0.3)
                        continue

                    with self.lock:
                        self.frame.frame = frame
                        self.frame.last_error = None
                        self.frame.updated_at = time.time()

                    time.sleep(0.05)

            except Exception as e:
                self._set_error(str(e))
                time.sleep(3)

            finally:
                if self.cap:
                    self.cap.release()
                    self.cap = None

    def get_jpeg(
        self,
        jpeg_quality: int = 90,
        flip_vertical: bool = False,
        flip_horizontal: bool = False,
        warp_enabled: bool = False,
        warp_points: Optional[list[float]] = None,
    ) -> Optional[bytes]:
        with self.lock:
            if self.frame.frame is None:
                return None
            frame = self.frame.frame.copy()

        # Сначала поворот/зеркало. Точки перспективы задаются уже для изображения после поворота.
        if flip_vertical and flip_horizontal:
            frame = cv2.flip(frame, -1)
        elif flip_vertical:
            frame = cv2.flip(frame, 0)
        elif flip_horizontal:
            frame = cv2.flip(frame, 1)

        frame = self._apply_perspective_warp(frame, warp_enabled, warp_points)

        ok, jpg = cv2.imencode(
            ".jpg",
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality],
        )

        if not ok:
            self._set_error(f"Не удалось закодировать кадр с {self.device}")
            return None

        return jpg.tobytes()


    @staticmethod
    def _order_warp_points(points: list[float]) -> Any:
        """Return corners as top-left, top-right, bottom-right, bottom-left."""
        src = np.float32(points).reshape(4, 2)
        center = src.mean(axis=0)
        angles = np.arctan2(src[:, 1] - center[1], src[:, 0] - center[0])
        ordered = src[np.argsort(angles)]
        top_left_index = int(np.argmin(ordered.sum(axis=1)))
        ordered = np.roll(ordered, -top_left_index, axis=0)

        # In image coordinates Y grows downwards. Ensure the point after the
        # top-left corner is the right-hand corner, not the bottom-left one.
        if ordered[1][0] < ordered[-1][0]:
            ordered = ordered[[0, 3, 2, 1]]
        return ordered

    @staticmethod
    def _apply_perspective_warp(frame: Any, enabled: bool, points: Optional[list[float]]) -> Any:
        if not enabled or not points or len(points) != 8:
            return frame

        try:
            src = CameraWorker._order_warp_points(points)
            frame_height, frame_width = frame.shape[:2]
            if (
                    np.any(src[:, 0] < -1)
                    or np.any(src[:, 0] > frame_width)
                    or np.any(src[:, 1] < -1)
                    or np.any(src[:, 1] > frame_height)
            ):
                print(
                    "[camera-manager] perspective points do not match "
                    f"the current frame size {frame_width}x{frame_height}: {points}"
                )
                return frame
            src[:, 0] = np.clip(src[:, 0], 0, frame_width - 1)
            src[:, 1] = np.clip(src[:, 1], 0, frame_height - 1)

            # Итоговый размер считаем по выбранной трапеции, а не по размеру всего кадра.
            # Иначе область растягивается на 1280x720 и перспектива выглядит неестественно.
            width_top = np.linalg.norm(src[1] - src[0])
            width_bottom = np.linalg.norm(src[2] - src[3])
            max_width = int(round(max(width_top, width_bottom)))

            height_right = np.linalg.norm(src[2] - src[1])
            height_left = np.linalg.norm(src[3] - src[0])
            max_height = int(round(max(height_left, height_right)))

            if max_width < 2 or max_height < 2:
                return frame

            dst = np.float32([
                [0, 0],
                [max_width - 1, 0],
                [max_width - 1, max_height - 1],
                [0, max_height - 1],
            ])

            matrix = cv2.getPerspectiveTransform(src, dst)
            return cv2.warpPerspective(frame, matrix, (max_width, max_height))

        except Exception as e:
            print(f"[camera-manager] perspective warp error: {e}")
            return frame
        
    def get_error(self) -> Optional[str]:
        with self.lock:
            return self.frame.last_error


class CameraManager:
    def __init__(self):
        self.workers: dict[str, CameraWorker] = {}
        self.lock = threading.Lock()

    def get_worker(
            self,
            device: str,
            frame_width: int = 1280,
            frame_height: int = 720,
            autofocus_enabled: bool = True,
            focus_absolute: Optional[int] = None,
            white_balance_auto: bool = True,
            white_balance_temperature: Optional[int] = None,
    ) -> CameraWorker:
        created = False
        with self.lock:
            worker = self.workers.get(device)
            if worker is None:
                worker = CameraWorker(
                    device=device,
                    frame_width=frame_width,
                    frame_height=frame_height,
                    autofocus_enabled=autofocus_enabled,
                    focus_absolute=focus_absolute,
                    white_balance_auto=white_balance_auto,
                    white_balance_temperature=white_balance_temperature,
                )
                self.workers[device] = worker
                created = True

        if created:
            worker.start()
        else:
            # Do not hold the manager lock while touching a worker. This keeps
            # an unhealthy camera from delaying all other cameras.
            worker.update_settings(
                frame_width=frame_width,
                frame_height=frame_height,
                autofocus_enabled=autofocus_enabled,
                focus_absolute=focus_absolute,
                white_balance_auto=white_balance_auto,
                white_balance_temperature=white_balance_temperature,
            )

        return worker

    def get_jpeg(
            self,
            device: str,
            jpeg_quality: int = 90,
            frame_width: int = 1280,
            frame_height: int = 720,
            flip_vertical: bool = False,
            flip_horizontal: bool = False,
            warp_enabled: bool = False,
            warp_points: Optional[list[float]] = None,
            autofocus_enabled: bool = True,
            focus_absolute: Optional[int] = None,
            white_balance_auto: bool = True,
            white_balance_temperature: Optional[int] = None,
    ) -> Optional[bytes]:
        worker = self.get_worker(
            device=device,
            frame_width=frame_width,
            frame_height=frame_height,
            autofocus_enabled=autofocus_enabled,
            focus_absolute=focus_absolute,
            white_balance_auto=white_balance_auto,
            white_balance_temperature=white_balance_temperature,
        )
        return worker.get_jpeg(
            jpeg_quality=jpeg_quality,
            flip_vertical=flip_vertical,
            flip_horizontal=flip_horizontal,
            warp_enabled=warp_enabled,
            warp_points=warp_points,
        )

    def get_error(self, device: str) -> Optional[str]:
        # Status reads must not create a worker or reset camera settings to
        # defaults. Previously every /info request could trigger a restart and
        # toggle autofocus/white balance back and forth.
        with self.lock:
            worker = self.workers.get(device)
        return worker.get_error() if worker else None

    def stop_all(self):
        with self.lock:
            workers = list(self.workers.values())
            self.workers.clear()

        for worker in workers:
            worker.stop()


camera_manager = CameraManager()
