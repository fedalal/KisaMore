from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from . import runtime
from .camera_manager import camera_manager
import os
import time

router = APIRouter(prefix="/api", tags=["camera"])


def _get_camera_device(rack_id: int) -> str:
    if not runtime.cfg:
        raise HTTPException(status_code=503, detail="Конфигурация ещё не загружена")

    rack_cfg = runtime.cfg.racks.get(str(rack_id))
    device = (rack_cfg.camera_device or "").strip() if rack_cfg else ""

    if not device:
        raise HTTPException(status_code=404, detail="Для этой полки web камера не указана")

    if not device.startswith("/dev/video"):
        raise HTTPException(status_code=400, detail="Разрешены только устройства вида /dev/video0")

    if not os.path.exists(device):
        raise HTTPException(status_code=404, detail=f"Устройство камеры не найдено: {device}")

    return device


def _mjpeg_generator(device: str):
    while True:
        jpeg = camera_manager.get_jpeg(device)

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
    device = _get_camera_device(rack_id)

    return StreamingResponse(
        _mjpeg_generator(device),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/rack/{rack_id}/camera/info")
async def camera_info(rack_id: int):
    device = _get_camera_device(rack_id)

    return {
        "rack_id": rack_id,
        "camera_device": device,
        "exists": True,
        "last_error": camera_manager.get_error(device),
    }