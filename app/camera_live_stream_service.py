from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import threading
import time
from typing import Optional
from urllib.parse import quote

from . import runtime
from .camera_live_stream_config import CameraLiveStreamSettings, build_ffmpeg_command
from .camera_manager import camera_manager
from .hw_config import CameraHW


class CameraLiveStreamService:
    def __init__(self):
        self._settings: CameraLiveStreamSettings | None = None
        self._encoder = "libx264"
        self._stop_event = threading.Event()
        self._threads: dict[int, threading.Thread] = {}
        self._processes: dict[int, subprocess.Popen] = {}
        self._lock = threading.Lock()

    async def start(self) -> None:
        if self._threads:
            return

        try:
            settings = CameraLiveStreamSettings.from_env()
        except Exception as exc:
            print(f"[camera-live] disabled: invalid settings: {exc}")
            return

        if settings is None:
            print("[camera-live] disabled: KISAMORE_MEDIA_PUBLISH_URL is not set")
            return
        if runtime.cfg is None:
            print("[camera-live] disabled: hardware config is not loaded")
            return
        if shutil.which(settings.ffmpeg_path) is None:
            print(f"[camera-live] disabled: ffmpeg not found: {settings.ffmpeg_path}")
            return

        self._settings = settings
        self._encoder = await asyncio.to_thread(self._select_encoder, settings)
        self._stop_event.clear()

        for rack_id in range(1, runtime.cfg.racks_count + 1):
            rack_cfg = runtime.cfg.racks.get(str(rack_id))
            if rack_cfg is None:
                continue
            if not rack_cfg.camera_id and not rack_cfg.camera_device:
                continue

            thread = threading.Thread(
                target=self._publisher_loop,
                args=(rack_id,),
                name=f"camera-live-rack-{rack_id}",
                daemon=True,
            )
            self._threads[rack_id] = thread
            thread.start()

        stream = runtime.cfg.camera_stream
        print(
            f"[camera-live] started: streams={len(self._threads)}, "
            f"resolution={stream.frame_width}x{stream.frame_height}, "
            f"fps={stream.fps}, encoder={self._encoder}"
        )

    async def stop(self) -> None:
        self._stop_event.set()

        with self._lock:
            processes = list(self._processes.values())
        for process in processes:
            self._terminate_process(process)

        threads = list(self._threads.values())
        for thread in threads:
            await asyncio.to_thread(thread.join, 6)

        self._threads.clear()
        with self._lock:
            self._processes.clear()
        self._settings = None

    async def restart(self) -> None:
        await self.stop()
        await self.start()

    @staticmethod
    def _select_encoder(settings: CameraLiveStreamSettings) -> str:
        if settings.video_codec != "auto":
            return settings.video_codec

        try:
            result = subprocess.run(
                [settings.ffmpeg_path, "-hide_banner", "-encoders"],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and "h264_v4l2m2m" in result.stdout:
                return "h264_v4l2m2m"
        except Exception as exc:
            print(f"[camera-live] cannot probe ffmpeg encoders: {exc}")

        return "libx264"

    @staticmethod
    def _camera_for_rack(rack_id: int) -> Optional[CameraHW]:
        if runtime.cfg is None:
            return None
        rack_cfg = runtime.cfg.racks.get(str(rack_id))
        if rack_cfg is None:
            return None
        if rack_cfg.camera_id:
            return runtime.cfg.cameras.get(rack_cfg.camera_id)

        device = (rack_cfg.camera_device or "").strip()
        if not device:
            return None
        return CameraHW(
            name=f"Камера полки {rack_id}",
            device=device,
            flip_vertical=rack_cfg.camera_flip_vertical,
            flip_horizontal=rack_cfg.camera_flip_horizontal,
            warp_enabled=rack_cfg.camera_warp_enabled,
            warp_points=rack_cfg.camera_warp_points,
        )

    def _publisher_loop(self, rack_id: int) -> None:
        assert self._settings is not None
        settings = self._settings

        while not self._stop_event.is_set():
            camera = self._camera_for_rack(rack_id)
            cfg = runtime.cfg
            if camera is None or cfg is None:
                self._stop_event.wait(settings.reconnect_seconds)
                continue
            if not os.path.exists(camera.device):
                print(
                    f"[camera-live] rack={rack_id}: camera not found: {camera.device}"
                )
                self._stop_event.wait(settings.reconnect_seconds)
                continue

            stream = cfg.camera_stream
            command = build_ffmpeg_command(
                settings,
                rack_id=rack_id,
                width=stream.frame_width,
                height=stream.frame_height,
                fps=stream.fps,
                bitrate_kbps=stream.bitrate_kbps,
                encoder=self._encoder,
            )
            process: Optional[subprocess.Popen] = None
            process_started_at = time.monotonic()

            try:
                process = subprocess.Popen(
                    command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    bufsize=0,
                )
                with self._lock:
                    self._processes[rack_id] = process

                stderr_thread = threading.Thread(
                    target=self._read_stderr,
                    args=(rack_id, process, settings),
                    daemon=True,
                )
                stderr_thread.start()
                print(f"[camera-live] rack={rack_id}: publisher connected")

                interval = 1.0 / stream.fps
                next_frame_at = time.monotonic()
                while not self._stop_event.is_set() and process.poll() is None:
                    frame = camera_manager.get_frame(
                        device=camera.device,
                        frame_width=stream.frame_width,
                        frame_height=stream.frame_height,
                        frame_fps=stream.fps,
                        flip_vertical=camera.flip_vertical,
                        flip_horizontal=camera.flip_horizontal,
                        warp_enabled=camera.warp_enabled,
                        warp_points=camera.warp_points,
                        warp_reference_width=camera.warp_reference_width,
                        warp_reference_height=camera.warp_reference_height,
                        output_width=stream.frame_width,
                        output_height=stream.frame_height,
                        autofocus_enabled=camera.autofocus_enabled,
                        focus_absolute=camera.focus_absolute,
                        white_balance_auto=camera.white_balance_auto,
                        white_balance_temperature=camera.white_balance_temperature,
                    )
                    if frame is None:
                        self._stop_event.wait(0.1)
                        next_frame_at = time.monotonic()
                        continue

                    if process.stdin is None:
                        break
                    process.stdin.write(frame.tobytes())

                    next_frame_at += interval
                    delay = next_frame_at - time.monotonic()
                    if delay > 0:
                        self._stop_event.wait(delay)
                    else:
                        next_frame_at = time.monotonic()

            except (BrokenPipeError, OSError) as exc:
                if not self._stop_event.is_set():
                    print(f"[camera-live] rack={rack_id}: publisher stopped: {exc}")
            except Exception as exc:
                if not self._stop_event.is_set():
                    print(f"[camera-live] rack={rack_id}: unexpected error: {exc}")
            finally:
                if process is not None:
                    self._terminate_process(process)
                with self._lock:
                    self._processes.pop(rack_id, None)

                # Некоторые сборки FFmpeg показывают h264_v4l2m2m в списке,
                # хотя драйвер кодировщика недоступен. Быстрый выход процесса
                # переводит все последующие попытки на совместимый libx264.
                if (
                    self._encoder == "h264_v4l2m2m"
                    and not self._stop_event.is_set()
                    and time.monotonic() - process_started_at < 5
                ):
                    with self._lock:
                        self._encoder = "libx264"
                    print(
                        "[camera-live] hardware H.264 encoder failed; "
                        "falling back to libx264"
                    )

            if not self._stop_event.is_set():
                print(
                    f"[camera-live] rack={rack_id}: reconnect in "
                    f"{settings.reconnect_seconds:g}s"
                )
                self._stop_event.wait(settings.reconnect_seconds)

    def _read_stderr(
        self,
        rack_id: int,
        process: subprocess.Popen,
        settings: CameraLiveStreamSettings,
    ) -> None:
        if process.stderr is None:
            return

        secrets = {
            settings.publish_password,
            quote(settings.publish_password, safe=""),
            settings.publish_user,
            quote(settings.publish_user, safe=""),
        }
        try:
            for raw_line in iter(process.stderr.readline, b""):
                line = raw_line.decode("utf-8", errors="replace").strip()
                for secret in secrets:
                    if secret:
                        line = line.replace(secret, "***")
                if line:
                    print(f"[camera-live] rack={rack_id}: ffmpeg: {line}")
        except Exception:
            pass

    @staticmethod
    def _terminate_process(process: subprocess.Popen) -> None:
        if process.stdin:
            try:
                process.stdin.close()
            except Exception:
                pass
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)


camera_live_stream_service = CameraLiveStreamService()
