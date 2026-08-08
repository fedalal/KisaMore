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
            frame_fps: int = 8,
            autofocus_enabled: bool = True,
            focus_absolute: Optional[int] = None,
            white_balance_auto: bool = True,
            white_balance_temperature: Optional[int] = None,
    ):
        self.device = device
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.frame_fps = frame_fps

        self.autofocus_enabled = autofocus_enabled
        self.focus_absolute = focus_absolute
        self.white_balance_auto = white_balance_auto
        self.white_balance_temperature = white_balance_temperature

        self.frame = CameraFrame()
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.lifecycle_lock = threading.RLock()
        self.thread: Optional[threading.Thread] = None
        self.cap = None

    def update_settings(
            self,
            frame_width: int = 1280,
            frame_height: int = 720,
            frame_fps: int = 8,
            autofocus_enabled: bool = True,
            focus_absolute: Optional[int] = None,
            white_balance_auto: bool = True,
            white_balance_temperature: Optional[int] = None,
    ):
        with self.lifecycle_lock:
            need_restart = False
            need_apply_controls = False

            with self.lock:
                if (
                    self.frame_width != frame_width
                    or self.frame_height != frame_height
                    or self.frame_fps != frame_fps
                ):
                    need_restart = True

                if (
                        self.autofocus_enabled != autofocus_enabled
                        or self.focus_absolute != focus_absolute
                        or self.white_balance_auto != white_balance_auto
                        or self.white_balance_temperature != white_balance_temperature
                ):
                    need_apply_controls = True

                self.frame_width = frame_width
                self.frame_height = frame_height
                self.frame_fps = frame_fps
                self.autofocus_enabled = autofocus_enabled
                self.focus_absolute = focus_absolute
                self.white_balance_auto = white_balance_auto
                self.white_balance_temperature = white_balance_temperature

            if need_restart:
                self.restart()
            elif need_apply_controls:
                self._apply_camera_controls()

    def start(self):
        with self.lifecycle_lock:
            if self.thread and self.thread.is_alive():
                return

            self.stop_event.clear()
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()

    def restart(self):
        with self.lifecycle_lock:
            if self.stop():
                self.start()

    def stop(self) -> bool:
        with self.lifecycle_lock:
            self.stop_event.set()

            # release() обычно выводит V4L2 read() из блокировки быстрее, чем
            # ожидание thread.join(). Это особенно важно для зависших UVC-камер.
            cap = self.cap
            if cap:
                try:
                    cap.release()
                except Exception:
                    pass

            thread = self.thread
            if thread and thread.is_alive() and thread is not threading.current_thread():
                thread.join(timeout=4)

            if thread and thread.is_alive():
                print(f"[camera-manager] worker did not stop in time: {self.device}")
            else:
                self.thread = None

            self.cap = None

            with self.lock:
                self.frame.frame = None

            return not bool(thread and thread.is_alive())

    def _set_error(self, message: str):
        with self.lock:
            self.frame.last_error = message
            self.frame.updated_at = time.time()

    def _run_v4l2_ctrl(self, ctrl: str):
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

    def _apply_camera_controls(self):
        with self.lock:
            autofocus_enabled = self.autofocus_enabled
            focus_absolute = self.focus_absolute
            white_balance_auto = self.white_balance_auto
            white_balance_temperature = self.white_balance_temperature

        # Фокус.
        # Для твоей камеры автофокус называется focus_automatic_continuous.
        self._run_v4l2_ctrl(
            f"focus_automatic_continuous={1 if autofocus_enabled else 0}"
        )

        if not autofocus_enabled and focus_absolute is not None:
            time.sleep(0.1)
            self._run_v4l2_ctrl(f"focus_absolute={int(focus_absolute)}")

        # Баланс белого.
        self._run_v4l2_ctrl(
            f"white_balance_automatic={1 if white_balance_auto else 0}"
        )

        if not white_balance_auto and white_balance_temperature is not None:
            self._run_v4l2_ctrl(
                f"white_balance_temperature={int(white_balance_temperature)}"
            )

    def _run(self):
        while not self.stop_event.is_set():
            try:
                self.cap = cv2.VideoCapture(self.device, cv2.CAP_V4L2)

                if not self.cap.isOpened():
                    self._set_error(f"Не удалось открыть камеру {self.device}")
                    time.sleep(3)
                    continue

                self._apply_camera_controls()

                with self.lock:
                    width = self.frame_width
                    height = self.frame_height
                    fps = self.frame_fps

                # Важно: у новой камеры высокие разрешения доступны именно в MJPG.
                # Если не указать FOURCC, OpenCV может открыть камеру в YUYV
                # и получить более низкое разрешение.
                self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                self.cap.set(cv2.CAP_PROP_FPS, fps)

                actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                actual_fourcc = int(self.cap.get(cv2.CAP_PROP_FOURCC))
                actual_fourcc_text = "".join(
                    chr((actual_fourcc >> 8 * i) & 0xFF)
                    for i in range(4)
                )

                print(
                    f"[camera-manager] {self.device} requested={width}x{height}, "
                    f"actual={actual_width}x{actual_height}, fps={fps}, "
                    f"fourcc={actual_fourcc_text}"
                )

                while not self.stop_event.is_set():
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

    def get_frame(
        self,
        flip_vertical: bool = False,
        flip_horizontal: bool = False,
        warp_enabled: bool = False,
        warp_points: Optional[list[float]] = None,
        warp_reference_width: int = 1280,
        warp_reference_height: int = 720,
        output_width: Optional[int] = None,
        output_height: Optional[int] = None,
    ) -> Optional[Any]:
        with self.lock:
            if self.frame.frame is None:
                return None
            frame = self.frame.frame.copy()

        # Сначала поворот/зеркало. Точки перспективы задаются для изображения
        # после поворота, но могут быть выбраны на другом разрешении.
        if flip_vertical and flip_horizontal:
            frame = cv2.flip(frame, -1)
        elif flip_vertical:
            frame = cv2.flip(frame, 0)
        elif flip_horizontal:
            frame = cv2.flip(frame, 1)

        frame = self._apply_perspective_warp(
            frame,
            warp_enabled,
            warp_points,
            warp_reference_width,
            warp_reference_height,
        )

        if output_width and output_height:
            if frame.shape[1] != output_width or frame.shape[0] != output_height:
                frame = cv2.resize(frame, (output_width, output_height), interpolation=cv2.INTER_AREA)

        return frame

    def get_jpeg(
        self,
        jpeg_quality: int = 90,
        flip_vertical: bool = False,
        flip_horizontal: bool = False,
        warp_enabled: bool = False,
        warp_points: Optional[list[float]] = None,
        warp_reference_width: int = 1280,
        warp_reference_height: int = 720,
        output_width: Optional[int] = None,
        output_height: Optional[int] = None,
    ) -> Optional[bytes]:
        frame = self.get_frame(
            flip_vertical=flip_vertical,
            flip_horizontal=flip_horizontal,
            warp_enabled=warp_enabled,
            warp_points=warp_points,
            warp_reference_width=warp_reference_width,
            warp_reference_height=warp_reference_height,
            output_width=output_width,
            output_height=output_height,
        )

        if frame is None:
            return None

        ok, jpg = cv2.imencode(
            ".jpg",
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality],
        )

        if not ok:
            self._set_error(f"Не удалось закодировать кадр с {self.device}")
            return None

        return jpg.tobytes()

    def capture_still_jpeg(
        self,
        frame_width: int,
        frame_height: int,
        jpeg_quality: int = 95,
        flip_vertical: bool = False,
        flip_horizontal: bool = False,
        warp_enabled: bool = False,
        warp_points: Optional[list[float]] = None,
        warp_reference_width: int = 1280,
        warp_reference_height: int = 720,
    ) -> Optional[bytes]:
        """Temporarily pause the live worker and take one full-resolution photo."""
        with self.lifecycle_lock:
            was_running = bool(self.thread and self.thread.is_alive())
            if not self.stop():
                self._set_error(
                    f"Не удалось безопасно остановить поток {self.device} для фото"
                )
                return None
            capture = None

            try:
                capture = cv2.VideoCapture(self.device, cv2.CAP_V4L2)
                if not capture.isOpened():
                    self._set_error(f"Не удалось открыть камеру {self.device} для фото")
                    return None

                self._apply_camera_controls()
                capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
                capture.set(cv2.CAP_PROP_FRAME_WIDTH, frame_width)
                capture.set(cv2.CAP_PROP_FRAME_HEIGHT, frame_height)
                capture.set(cv2.CAP_PROP_FPS, 5)

                actual_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
                print(
                    f"[camera-manager] still {self.device} requested={frame_width}x{frame_height}, "
                    f"actual={actual_width}x{actual_height}"
                )

                if actual_width != frame_width or actual_height != frame_height:
                    self._set_error(
                        f"Камера {self.device} не установила разрешение "
                        f"{frame_width}x{frame_height}: получено {actual_width}x{actual_height}"
                    )
                    return None

                frame = None
                # Несколько кадров дают автоэкспозиции и автофокусу время после
                # переключения режима. Берём последний успешно полученный кадр.
                for _ in range(5):
                    ok, candidate = capture.read()
                    if ok:
                        frame = candidate
                    time.sleep(0.08)

                if frame is None:
                    self._set_error(f"Не удалось получить полноразмерный кадр с {self.device}")
                    return None

                if flip_vertical and flip_horizontal:
                    frame = cv2.flip(frame, -1)
                elif flip_vertical:
                    frame = cv2.flip(frame, 0)
                elif flip_horizontal:
                    frame = cv2.flip(frame, 1)

                frame = self._apply_perspective_warp(
                    frame,
                    warp_enabled,
                    warp_points,
                    warp_reference_width,
                    warp_reference_height,
                )
                ok, jpg = cv2.imencode(
                    ".jpg",
                    frame,
                    [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality],
                )
                if not ok:
                    self._set_error(f"Не удалось закодировать фото с {self.device}")
                    return None

                with self.lock:
                    self.frame.last_error = None
                    self.frame.updated_at = time.time()
                return jpg.tobytes()
            except Exception as exc:
                self._set_error(str(exc))
                return None
            finally:
                if capture:
                    capture.release()
                if was_running:
                    self.start()


    @staticmethod
    def _apply_perspective_warp(
        frame: Any,
        enabled: bool,
        points: Optional[list[float]],
        reference_width: int = 1280,
        reference_height: int = 720,
    ) -> Any:
        if not enabled or not points or len(points) != 8:
            return frame

        try:
            actual_height, actual_width = frame.shape[:2]
            scale_x = actual_width / max(1, reference_width)
            scale_y = actual_height / max(1, reference_height)
            src = np.float32([
                [points[0] * scale_x, points[1] * scale_y],  # левый верхний
                [points[2] * scale_x, points[3] * scale_y],  # правый верхний
                [points[4] * scale_x, points[5] * scale_y],  # правый нижний
                [points[6] * scale_x, points[7] * scale_y],  # левый нижний
            ])

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
        self.max_mjpg_resolutions: dict[str, tuple[int, int]] = {}
        self.lock = threading.Lock()

    def get_worker(
            self,
            device: str,
            frame_width: int = 1280,
            frame_height: int = 720,
            frame_fps: int = 8,
            autofocus_enabled: bool = True,
            focus_absolute: Optional[int] = None,
            white_balance_auto: bool = True,
            white_balance_temperature: Optional[int] = None,
    ) -> CameraWorker:
        with self.lock:
            worker = self.workers.get(device)
            if worker is None:
                worker = CameraWorker(
                    device=device,
                    frame_width=frame_width,
                    frame_height=frame_height,
                    frame_fps=frame_fps,
                    autofocus_enabled=autofocus_enabled,
                    focus_absolute=focus_absolute,
                    white_balance_auto=white_balance_auto,
                    white_balance_temperature=white_balance_temperature,
                )
                self.workers[device] = worker
                created = True
            else:
                created = False

        # Не держим общий lock менеджера, пока конкретная камера переключает
        # режим для полноразмерного фото. Остальные камеры продолжают работать.
        if not created:
            worker.update_settings(
                frame_width=frame_width,
                frame_height=frame_height,
                frame_fps=frame_fps,
                autofocus_enabled=autofocus_enabled,
                focus_absolute=focus_absolute,
                white_balance_auto=white_balance_auto,
                white_balance_temperature=white_balance_temperature,
            )
        worker.start()
        return worker

    def get_frame(
            self,
            device: str,
            frame_width: int = 1024,
            frame_height: int = 768,
            frame_fps: int = 8,
            flip_vertical: bool = False,
            flip_horizontal: bool = False,
            warp_enabled: bool = False,
            warp_points: Optional[list[float]] = None,
            warp_reference_width: int = 1280,
            warp_reference_height: int = 720,
            output_width: Optional[int] = None,
            output_height: Optional[int] = None,
            autofocus_enabled: bool = True,
            focus_absolute: Optional[int] = None,
            white_balance_auto: bool = True,
            white_balance_temperature: Optional[int] = None,
    ) -> Optional[Any]:
        worker = self.get_worker(
            device=device,
            frame_width=frame_width,
            frame_height=frame_height,
            frame_fps=frame_fps,
            autofocus_enabled=autofocus_enabled,
            focus_absolute=focus_absolute,
            white_balance_auto=white_balance_auto,
            white_balance_temperature=white_balance_temperature,
        )
        return worker.get_frame(
            flip_vertical=flip_vertical,
            flip_horizontal=flip_horizontal,
            warp_enabled=warp_enabled,
            warp_points=warp_points,
            warp_reference_width=warp_reference_width,
            warp_reference_height=warp_reference_height,
            output_width=output_width,
            output_height=output_height,
        )

    def get_jpeg(
            self,
            device: str,
            jpeg_quality: int = 90,
            frame_width: int = 1280,
            frame_height: int = 720,
            frame_fps: int = 8,
            flip_vertical: bool = False,
            flip_horizontal: bool = False,
            warp_enabled: bool = False,
            warp_points: Optional[list[float]] = None,
            warp_reference_width: int = 1280,
            warp_reference_height: int = 720,
            output_width: Optional[int] = None,
            output_height: Optional[int] = None,
            autofocus_enabled: bool = True,
            focus_absolute: Optional[int] = None,
            white_balance_auto: bool = True,
            white_balance_temperature: Optional[int] = None,
    ) -> Optional[bytes]:
        worker = self.get_worker(
            device=device,
            frame_width=frame_width,
            frame_height=frame_height,
            frame_fps=frame_fps,
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
            warp_reference_width=warp_reference_width,
            warp_reference_height=warp_reference_height,
            output_width=output_width,
            output_height=output_height,
        )

    @staticmethod
    def _parse_max_mjpg_resolution(output: str) -> Optional[tuple[int, int]]:
        in_mjpg = False
        sizes: list[tuple[int, int]] = []

        for line in output.splitlines():
            format_match = re.search(r"\[\d+\]:\s+'([^']+)'", line)
            if format_match:
                in_mjpg = format_match.group(1).upper() in {"MJPG", "MJPEG"}
                continue

            if not in_mjpg:
                continue

            size_match = re.search(r"Size:\s+Discrete\s+(\d+)x(\d+)", line)
            if size_match:
                sizes.append((int(size_match.group(1)), int(size_match.group(2))))

        if not sizes:
            return None
        return max(sizes, key=lambda size: (size[0] * size[1], size[0], size[1]))

    def get_max_mjpg_resolution(
            self,
            device: str,
            fallback_width: int,
            fallback_height: int,
    ) -> tuple[int, int]:
        with self.lock:
            cached = self.max_mjpg_resolutions.get(device)
        if cached:
            return cached

        selected: Optional[tuple[int, int]] = None
        try:
            result = subprocess.run(
                ["v4l2-ctl", "--device", device, "--list-formats-ext"],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                selected = self._parse_max_mjpg_resolution(result.stdout)
            else:
                print(
                    f"[camera-manager] cannot list formats for {device}: "
                    f"{result.stderr.strip()}"
                )
        except Exception as exc:
            print(f"[camera-manager] resolution probe failed for {device}: {exc}")

        selected = selected or (fallback_width, fallback_height)
        with self.lock:
            self.max_mjpg_resolutions[device] = selected

        print(
            f"[camera-manager] maximum MJPG resolution for {device}: "
            f"{selected[0]}x{selected[1]}"
        )
        return selected

    def capture_still_jpeg(
            self,
            device: str,
            jpeg_quality: int,
            fallback_width: int,
            fallback_height: int,
            use_max_resolution: bool = True,
            flip_vertical: bool = False,
            flip_horizontal: bool = False,
            warp_enabled: bool = False,
            warp_points: Optional[list[float]] = None,
            warp_reference_width: int = 1280,
            warp_reference_height: int = 720,
            autofocus_enabled: bool = True,
            focus_absolute: Optional[int] = None,
            white_balance_auto: bool = True,
            white_balance_temperature: Optional[int] = None,
            live_frame_width: int = 1024,
            live_frame_height: int = 768,
            live_frame_fps: int = 8,
    ) -> Optional[bytes]:
        worker = self.get_worker(
            device=device,
            frame_width=live_frame_width,
            frame_height=live_frame_height,
            frame_fps=live_frame_fps,
            autofocus_enabled=autofocus_enabled,
            focus_absolute=focus_absolute,
            white_balance_auto=white_balance_auto,
            white_balance_temperature=white_balance_temperature,
        )
        if use_max_resolution:
            width, height = self.get_max_mjpg_resolution(
                device,
                fallback_width,
                fallback_height,
            )
        else:
            width, height = fallback_width, fallback_height

        return worker.capture_still_jpeg(
            frame_width=width,
            frame_height=height,
            jpeg_quality=jpeg_quality,
            flip_vertical=flip_vertical,
            flip_horizontal=flip_horizontal,
            warp_enabled=warp_enabled,
            warp_points=warp_points,
            warp_reference_width=warp_reference_width,
            warp_reference_height=warp_reference_height,
        )

    def get_error(self, device: str) -> Optional[str]:
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
