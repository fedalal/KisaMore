import threading
import time
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
    ):
        self.device = device
        self.frame_width = frame_width
        self.frame_height = frame_height

        self.frame = CameraFrame()
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.cap = None

    def update_settings(
        self,
        frame_width: int = 1280,
        frame_height: int = 720,
    ):
        need_restart = False

        with self.lock:
            if self.frame_width != frame_width or self.frame_height != frame_height:
                need_restart = True

            self.frame_width = frame_width
            self.frame_height = frame_height

        if need_restart:
            self.restart()

    def start(self):
        if self.thread and self.thread.is_alive():
            return

        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def restart(self):
        self.stop()
        self.start()

    def stop(self):
        self.stop_event.set()

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)

        if self.cap:
            self.cap.release()
            self.cap = None

    def _set_error(self, message: str):
        with self.lock:
            self.frame.last_error = message
            self.frame.updated_at = time.time()

    def _run(self):
        while not self.stop_event.is_set():
            try:
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
    def _apply_perspective_warp(frame: Any, enabled: bool, points: Optional[list[float]]) -> Any:
        if not enabled or not points or len(points) != 8:
            return frame

        try:
            h, w = frame.shape[:2]
            src = np.float32([
                [points[0], points[1]],  # левый верхний
                [points[2], points[3]],  # правый верхний
                [points[4], points[5]],  # правый нижний
                [points[6], points[7]],  # левый нижний
            ])

            dst = np.float32([
                [0, 0],
                [w - 1, 0],
                [w - 1, h - 1],
                [0, h - 1],
            ])

            matrix = cv2.getPerspectiveTransform(src, dst)
            return cv2.warpPerspective(frame, matrix, (w, h))
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
    ) -> CameraWorker:
        with self.lock:
            if device not in self.workers:
                worker = CameraWorker(
                    device=device,
                    frame_width=frame_width,
                    frame_height=frame_height,
                )
                self.workers[device] = worker
                worker.start()
            else:
                worker = self.workers[device]
                worker.update_settings(
                    frame_width=frame_width,
                    frame_height=frame_height,
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
    ) -> Optional[bytes]:
        worker = self.get_worker(
            device=device,
            frame_width=frame_width,
            frame_height=frame_height,
        )
        return worker.get_jpeg(
            jpeg_quality=jpeg_quality,
            flip_vertical=flip_vertical,
            flip_horizontal=flip_horizontal,
            warp_enabled=warp_enabled,
            warp_points=warp_points,
        )

    def get_error(self, device: str) -> Optional[str]:
        worker = self.get_worker(device)
        return worker.get_error()

    def stop_all(self):
        with self.lock:
            for worker in self.workers.values():
                worker.stop()

            self.workers.clear()


camera_manager = CameraManager()
