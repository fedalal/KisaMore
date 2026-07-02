import asyncio
from datetime import datetime
import os

from pathlib import Path

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

    def _reset_uploader(self):
        # После сетевой ошибки лучше пересоздать Google Drive service при следующей попытке.
        if self.uploader:
            self.uploader.service = None

    def _pending_dir(self) -> Path:
        if runtime.cfg and runtime.cfg.camera_capture:
            pending_dir = runtime.cfg.camera_capture.pending_dir or "data/camera_pending"
        else:
            pending_dir = "data/camera_pending"

        return Path(pending_dir)

    def _save_pending_file(self, jpeg: bytes, filename: str, reason: str):
        pending_dir = self._pending_dir()
        pending_dir.mkdir(parents=True, exist_ok=True)

        path = pending_dir / filename

        # На всякий случай, если имя уже есть, добавим микросекунды.
        if path.exists():
            stem = path.stem
            suffix = path.suffix or ".jpg"
            path = pending_dir / f"{stem}_{datetime.now().strftime('%f')}{suffix}"

        tmp_path = path.with_suffix(path.suffix + ".tmp")

        # Сначала пишем во временный файл, потом атомарно переименовываем.
        # Так в очереди не появятся битые .jpg, если питание пропадёт во время записи.
        tmp_path.write_bytes(jpeg)
        tmp_path.replace(path)

        print(f"[camera-capture] saved locally {path}: {reason}")

    async def _upload_pending_files(self, uploader: GoogleDriveUploader):
        pending_dir = self._pending_dir()
        if not pending_dir.exists():
            return

        files = sorted(pending_dir.glob("*.jpg"))
        if not files:
            return

        print(f"[camera-capture] pending files: {len(files)}")

        # Чтобы при большом накоплении не блокировать обычные снимки слишком надолго.
        for path in files[:50]:
            if self.stop_event.is_set():
                return

            try:
                data = await asyncio.to_thread(path.read_bytes)
                result = await asyncio.to_thread(
                    uploader.upload_jpeg_bytes,
                    data,
                    path.name,
                )
                await asyncio.to_thread(path.unlink)
                print(f"[camera-capture] uploaded pending {path.name}: {result}")

            except Exception as e:
                self._reset_uploader()
                print(f"[camera-capture] cannot upload pending {path.name}: {e}")

                # Если интернет всё ещё недоступен, остальные файлы тоже, скорее всего, не загрузятся.
                return

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

        # В начале каждого цикла сначала пытаемся отправить накопленные локальные фото.
        # Если интернета нет, файлы останутся в локальной очереди до следующей попытки.
        if uploader is not None:
            await self._upload_pending_files(uploader)
        else:
            print("[camera-capture] Google Drive не настроен: credentials_file, token_file или google_folder_id пустые")


        light_states = await self._get_light_states()

        quality = cfg.jpeg_quality
        frame_width = cfg.frame_width
        frame_height = cfg.frame_height

        for rack_id_str, rack_cfg in runtime.cfg.racks.items():
            rack_id = int(rack_id_str)
            camera_cfg = runtime.cfg.cameras.get(rack_cfg.camera_id) if rack_cfg.camera_id else None

            if camera_cfg:
                device = camera_cfg.device.strip()
                flip_vertical = camera_cfg.flip_vertical
                flip_horizontal = camera_cfg.flip_horizontal
                warp_enabled = camera_cfg.warp_enabled
                warp_points = camera_cfg.warp_points
            else:
                # Совместимость со старым config/kisamore.yaml.
                device = (rack_cfg.camera_device or "").strip()
                flip_vertical = rack_cfg.camera_flip_vertical
                flip_horizontal = rack_cfg.camera_flip_horizontal
                warp_enabled = rack_cfg.camera_warp_enabled
                warp_points = rack_cfg.camera_warp_points

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
                flip_vertical=flip_vertical,
                flip_horizontal=flip_horizontal,
                warp_enabled=warp_enabled,
                warp_points=warp_points,
            )

            if not jpeg:
                print(f"[camera-capture] no frame yet: rack={rack_id}, device={device}")
                continue

            now = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"rack_{rack_id}_{now}.jpg"

            if uploader is None:
                self._save_pending_file(jpeg, filename, "Google Drive uploader is not configured")
                continue

            try:
                result = await asyncio.to_thread(
                    uploader.upload_jpeg_bytes,
                    jpeg,
                    filename,
                )
                print(f"[camera-capture] uploaded {filename}: {result}")

            except Exception as e:
                self._reset_uploader()
                self._save_pending_file(jpeg, filename, f"upload failed: {e}")
                


camera_capture_service = CameraCaptureService()