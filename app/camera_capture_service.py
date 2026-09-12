import asyncio
from datetime import datetime, timedelta
import os

from pathlib import Path

from sqlalchemy import select
from .db import SessionLocal
from .models import RackState

from . import runtime
from .camera_one_shot import capture_one_shot_jpeg
from .camera_profiles import profile_controls, profile_format
from .google_drive_uploader import GoogleDriveUploader


class CameraCaptureService:
    def __init__(self):
        self.task: asyncio.Task | None = None
        self.stop_event = asyncio.Event()
        self.uploader: GoogleDriveUploader | None = None
        self.uploader_key: tuple[str, str, str] | None = None

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
        if path.exists():
            stem = path.stem
            suffix = path.suffix or ".jpg"
            path = pending_dir / f"{stem}_{datetime.now().strftime('%f')}{suffix}"

        tmp_path = path.with_suffix(path.suffix + ".tmp")
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
                return

    def _archive_dir(self) -> Path:
        if runtime.cfg and runtime.cfg.camera_capture:
            archive_dir = runtime.cfg.camera_capture.local_archive_dir or "data/camera_archive"
        else:
            archive_dir = "data/camera_archive"

        return Path(archive_dir)

    def _save_archive_file(self, jpeg: bytes, filename: str, rack_id: int):
        if not runtime.cfg or not runtime.cfg.camera_capture.local_archive_enabled:
            return

        day = datetime.now().strftime("%Y-%m-%d")
        archive_dir = self._archive_dir() / f"rack_{rack_id}" / day
        archive_dir.mkdir(parents=True, exist_ok=True)

        path = archive_dir / filename
        if path.exists():
            stem = path.stem
            suffix = path.suffix or ".jpg"
            path = archive_dir / f"{stem}_{datetime.now().strftime('%f')}{suffix}"

        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_bytes(jpeg)
        tmp_path.replace(path)

        print(f"[camera-capture] saved archive {path}")

    def _save_latest_file(self, jpeg: bytes, rack_id: int):
        latest_dir = Path(runtime.cfg.camera_capture.latest_dir or "data/camera_latest")
        latest_dir.mkdir(parents=True, exist_ok=True)
        path = latest_dir / f"rack_{rack_id}.jpg"
        tmp_path = path.with_suffix(".jpg.tmp")
        tmp_path.write_bytes(jpeg)
        tmp_path.replace(path)

    async def _cleanup_archive_files(self):
        if not runtime.cfg or not runtime.cfg.camera_capture.local_archive_enabled:
            return

        archive_dir = self._archive_dir()
        if not archive_dir.exists():
            return

        keep_days = runtime.cfg.camera_capture.local_archive_days
        cutoff = datetime.now() - timedelta(days=keep_days)
        deleted = 0

        for path in archive_dir.rglob("*.jpg"):
            if self.stop_event.is_set():
                return

            try:
                mtime = datetime.fromtimestamp(path.stat().st_mtime)
                if mtime < cutoff:
                    await asyncio.to_thread(path.unlink)
                    deleted += 1
            except Exception as e:
                print(f"[camera-capture] cannot cleanup archive file {path}: {e}")

        for folder in sorted(archive_dir.rglob("*"), reverse=True):
            if folder.is_dir():
                try:
                    folder.rmdir()
                except OSError:
                    pass

        if deleted:
            print(f"[camera-capture] cleanup archive: deleted {deleted} old files")

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

        if uploader is not None:
            await self._upload_pending_files(uploader)
        else:
            print("[camera-capture] Google Drive не настроен: credentials_file, token_file или google_folder_id пустые")

        await self._cleanup_archive_files()

        light_states = await self._get_light_states()

        quality = cfg.jpeg_quality
        default_width = cfg.frame_width
        default_height = cfg.frame_height

        # Cameras are opened strictly one after another. The saved profile for a
        # camera controls its own format and all V4L2 image settings.
        for rack_id_str, rack_cfg in runtime.cfg.racks.items():
            rack_id = int(rack_id_str)
            camera_id = rack_cfg.camera_id or f"rack_{rack_id}_legacy"
            camera_cfg = runtime.cfg.cameras.get(rack_cfg.camera_id) if rack_cfg.camera_id else None

            if camera_cfg:
                device = camera_cfg.device.strip()
                flip_vertical = camera_cfg.flip_vertical
                flip_horizontal = camera_cfg.flip_horizontal
                warp_enabled = camera_cfg.warp_enabled
                warp_points = camera_cfg.warp_points
                autofocus_enabled = camera_cfg.autofocus_enabled
                focus_absolute = camera_cfg.focus_absolute
                white_balance_auto = camera_cfg.white_balance_auto
                white_balance_temperature = camera_cfg.white_balance_temperature
                brightness = camera_cfg.brightness
                contrast = camera_cfg.contrast
                saturation = camera_cfg.saturation
                sharpness = camera_cfg.sharpness
            else:
                device = (rack_cfg.camera_device or "").strip()
                flip_vertical = rack_cfg.camera_flip_vertical
                flip_horizontal = rack_cfg.camera_flip_horizontal
                warp_enabled = rack_cfg.camera_warp_enabled
                warp_points = rack_cfg.camera_warp_points
                autofocus_enabled = True
                focus_absolute = None
                white_balance_auto = True
                white_balance_temperature = None
                brightness = None
                contrast = None
                saturation = None
                sharpness = None

            if not device:
                continue

            if cfg.only_when_light_on and not light_states.get(rack_id, False):
                print(f"[camera-capture] skip rack={rack_id}: light is off")
                continue

            if not os.path.exists(device):
                print(f"[camera-capture] camera not found: rack={rack_id}, device={device}")
                continue

            saved_profile = runtime.camera_profiles.get(camera_id) if runtime.camera_profiles else None
            frame_width, frame_height, pixel_format, fps = profile_format(
                saved_profile,
                default_width=default_width,
                default_height=default_height,
                default_pixelformat="MJPG",
                default_fps=30,
            )
            saved_controls = profile_controls(saved_profile)

            jpeg = await asyncio.to_thread(
                capture_one_shot_jpeg,
                device=device,
                jpeg_quality=quality,
                frame_width=frame_width,
                frame_height=frame_height,
                pixel_format=pixel_format,
                fps=fps,
                flip_vertical=flip_vertical,
                flip_horizontal=flip_horizontal,
                warp_enabled=warp_enabled,
                warp_points=warp_points,
                autofocus_enabled=autofocus_enabled,
                focus_absolute=focus_absolute,
                white_balance_auto=white_balance_auto,
                white_balance_temperature=white_balance_temperature,
                brightness=brightness,
                contrast=contrast,
                saturation=saturation,
                sharpness=sharpness,
                profile_controls=saved_controls or None,
                focus_ramp=False,
            )

            if not jpeg:
                print(f"[camera-capture] no high-resolution frame: rack={rack_id}, device={device}")
                continue

            now = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"rack_{rack_id}_{now}.jpg"

            self._save_latest_file(jpeg, rack_id)
            self._save_archive_file(jpeg, filename, rack_id)

            print(
                f"[camera-capture] frame saved: rack={rack_id}, camera={camera_id}, "
                f"profile={'saved' if saved_profile else 'yaml-fallback'}, "
                f"requested={frame_width}x{frame_height} {pixel_format}@{fps}, bytes={len(jpeg)}"
            )

            if uploader is None:
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
