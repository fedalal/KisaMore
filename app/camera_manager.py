import threading
import time
from dataclasses import dataclass
from typing import Optional

import cv2


@dataclass
class CameraFrame:
    frame_jpeg: Optional[bytes] = None
    last_error: Optional[str] = None
    updated_at: float = 0.0


class CameraWorker:
    def __init__(self, device: str, jpeg_quality: int = 85):
        self.device = device
        self.jpeg_quality = jpeg_quality
        self.frame = CameraFrame()
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.cap = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return

        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

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

                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                self.cap.set(cv2.CAP_PROP_FPS, 15)

                while not self.stop_event.is_set():
                    ok, frame = self.cap.read()

                    if not ok:
                        self._set_error(f"Не удалось получить кадр с {self.device}")
                        time.sleep(0.3)
                        continue

                    ok, jpg = cv2.imencode(
                        ".jpg",
                        frame,
                        [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality],
                    )

                    if not ok:
                        self._set_error(f"Не удалось закодировать кадр с {self.device}")
                        continue

                    with self.lock:
                        self.frame.frame_jpeg = jpg.tobytes()
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

    def get_jpeg(self) -> Optional[bytes]:
        with self.lock:
            return self.frame.frame_jpeg

    def get_error(self) -> Optional[str]:
        with self.lock:
            return self.frame.last_error


class CameraManager:
    def __init__(self):
        self.workers: dict[str, CameraWorker] = {}
        self.lock = threading.Lock()

    def get_worker(self, device: str, jpeg_quality: int = 85) -> CameraWorker:
        with self.lock:
            if device not in self.workers:
                worker = CameraWorker(device, jpeg_quality)
                self.workers[device] = worker
                worker.start()

            return self.workers[device]

    def get_jpeg(self, device: str, jpeg_quality: int = 85) -> Optional[bytes]:
        worker = self.get_worker(device, jpeg_quality)
        return worker.get_jpeg()

    def get_error(self, device: str) -> Optional[str]:
        worker = self.get_worker(device)
        return worker.get_error()

    def stop_all(self):
        with self.lock:
            for worker in self.workers.values():
                worker.stop()

            self.workers.clear()


camera_manager = CameraManager()