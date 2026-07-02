import asyncio
from datetime import datetime
import os

from sqlalchemy import select
from .db import SessionLocal
from .models import RackState

from . import runtime
from .camera_manager import camera_manager
from .google_drive_uploader import GoogleDriveUploader


class CameraCaptureService:
    def __init__(self):
        self.task: asyncio.Task | None = None
        self.stop_event = asyncio.Event()
        self.uploader: GoogleDriveUploader | None = None
        self.uploader_key: tuple[str, str] | None = None

    async def _get_light_states(self) -> dict[int, bool]:
        async with SessionLocal() as s:
            rows = (await s.execute(select(RackState))).scalars().all()

        return {
            int(row.rack_id): bool(row.light_on)
            for row in rows
        }

    async def start(self):
        if self.task and not self.task.done():
            return

        self.stop_event.clear()
        self.task = asyncio.create_task(self._run())

    async def stop(self):
        self.stop_event.set()

        if self.task:
            self.task.cancel()

            try:
                await self.task
            except asyncio.CancelledError:
                pass

    def _get_uploader(self):
        if not runtime.cfg:
            return None

        cfg = runtime.cfg.camera_capture

        if not cfg.credentials_file or not cfg.google_folder_id or not cfg.token_file:
            return None

        key = (cfg.credentials_file, cfg.google_folder_id, cfg.token_file)

        if self.uploader is None or self.uploader_key != key:
            self.uploader = GoogleDriveUploader(
                credentials_file=cfg.credentials_file,
                folder_id=cfg.google_folder_id,
                token_file=cfg.token_file,
            )
            self.uploader_key = key

        return self.uploader

    async def _run(self):
        await asyncio.sleep(5)

        while not self.stop_event.is_set():
            try:
                await self._capture_once()
            except Exception as e:
                print(f"[camera-capture] error: {e}")

            interval = 30

            if runtime.cfg and runtime.cfg.camera_capture:
                interval = runtime.cfg.camera_capture.interval_seconds

            await asyncio.sleep(interval)

    async def _capture_once(self):
        if not runtime.cfg:
            print("[camera-capture] config is not loaded")
            return

        cfg = runtime.cfg.camera_capture

        if not cfg.enabled:
            return

        uploader = self._get_uploader()

        if uploader is None:
            print("[camera-capture] Google Drive не настроен: credentials_file, token_file или google_folder_id пустые")
            return

        light_states = await self._get_light_states()

        quality = cfg.jpeg_quality
        frame_width = cfg.frame_width
        frame_height = cfg.frame_height

        for rack_id_str, rack_cfg in runtime.cfg.racks.items():
            rack_id = int(rack_id_str)
            device = (rack_cfg.camera_device or "").strip()

            if not device:
                continue

            if cfg.only_when_light_on and not light_states.get(rack_id, False):
                print(f"[camera-capture] skip rack={rack_id}: light is off")
                continue

            if not os.path.exists(device):
                print(f"[camera-capture] camera not found: rack={rack_id}, device={device}")
                continue

            jpeg = camera_manager.get_jpeg(
                device=device,
                jpeg_quality=quality,
                frame_width=frame_width,
                frame_height=frame_height,
                flip_vertical=rack_cfg.camera_flip_vertical,
                flip_horizontal=rack_cfg.camera_flip_horizontal,
            )

            if not jpeg:
                print(f"[camera-capture] no frame yet: rack={rack_id}, device={device}")
                continue

            now = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"rack_{rack_id}_{now}.jpg"

            result = await asyncio.to_thread(
                uploader.upload_jpeg_bytes,
                jpeg,
                filename,
            )

            print(f"[camera-capture] uploaded {filename}: {result}")


camera_capture_service = CameraCaptureService()