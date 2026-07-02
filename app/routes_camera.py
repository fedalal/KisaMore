from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from . import runtime
from .camera_manager import camera_manager
import os
import time
from .hw_config import RackHW

router = APIRouter(prefix="/api", tags=["camera"])


def _get_camera_config(rack_id: int) -> tuple[str, RackHW]:
    if not runtime.cfg:
        raise HTTPException(status_code=503, detail="Конфигурация ещё не загружена")

    rack_cfg = runtime.cfg.racks.get(str(rack_id))
    device = (rack_cfg.camera_device or "").strip() if rack_cfg else ""

    if not rack_cfg or not device:
        raise HTTPException(status_code=404, detail="Для этой полки web камера не указана")

    if not device.startswith("/dev/video"):
        raise HTTPException(status_code=400, detail="Разрешены только устройства вида /dev/video0")

    if not os.path.exists(device):
        raise HTTPException(status_code=404, detail=f"Устройство камеры не найдено: {device}")

    return device, rack_cfg

def _mjpeg_generator(rack_id: int):
    while True:
        device, rack_cfg = _get_camera_config(rack_id)

        quality = 90
        frame_width = 1280
        frame_height = 720

        if runtime.cfg and runtime.cfg.camera_capture:
            quality = runtime.cfg.camera_capture.jpeg_quality
            frame_width = runtime.cfg.camera_capture.frame_width
            frame_height = runtime.cfg.camera_capture.frame_height

        jpeg = camera_manager.get_jpeg(
            device=device,
            jpeg_quality=quality,
            frame_width=frame_width,
            frame_height=frame_height,
            flip_vertical=rack_cfg.camera_flip_vertical,
            flip_horizontal=rack_cfg.camera_flip_horizontal,
        )

        if jpeg:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" +
                jpeg +
                b"\r\n"
            )

        time.sleep(0.08)


@router.get("/rack/{rack_id}/camera/stream")
def camera_stream(rack_id: int):
    _get_camera_config(rack_id)

    return StreamingResponse(
        _mjpeg_generator(rack_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/rack/{rack_id}/camera/info")
async def camera_info(rack_id: int):
    device, rack_cfg = _get_camera_config(rack_id)

    return {
        "rack_id": rack_id,
        "camera_device": device,
        "camera_flip_vertical": rack_cfg.camera_flip_vertical,
        "camera_flip_horizontal": rack_cfg.camera_flip_horizontal,
        "exists": True,
        "last_error": camera_manager.get_error(device),
    }