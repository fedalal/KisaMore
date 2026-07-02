from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from . import runtime
from .camera_manager import camera_manager
from .hw_config import CameraHW
import os
import time

router = APIRouter(prefix="/api", tags=["camera"])


def _camera_runtime_settings():
    quality = 90
    frame_width = 1280
    frame_height = 720

    if runtime.cfg and runtime.cfg.camera_capture:
        quality = runtime.cfg.camera_capture.jpeg_quality
        frame_width = runtime.cfg.camera_capture.frame_width
        frame_height = runtime.cfg.camera_capture.frame_height

    return quality, frame_width, frame_height


def _validate_device(device: str):
    if not device.startswith("/dev/video"):
        raise HTTPException(status_code=400, detail="Разрешены только устройства вида /dev/video0")

    if not os.path.exists(device):
        raise HTTPException(status_code=404, detail=f"Устройство камеры не найдено: {device}")


def _get_camera_by_id(camera_id: str) -> CameraHW:
    if not runtime.cfg:
        raise HTTPException(status_code=503, detail="Конфигурация ещё не загружена")

    cam = runtime.cfg.cameras.get(camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail=f"Камера не найдена: {camera_id}")

    _validate_device(cam.device)
    return cam


def _get_camera_by_rack(rack_id: int) -> tuple[str, CameraHW]:
    if not runtime.cfg:
        raise HTTPException(status_code=503, detail="Конфигурация ещё не загружена")

    rack_cfg = runtime.cfg.racks.get(str(rack_id))
    if not rack_cfg:
        raise HTTPException(status_code=404, detail=f"Полка не найдена: {rack_id}")

    # Новая схема: полка ссылается на камеру через camera_id.
    if rack_cfg.camera_id:
        cam = runtime.cfg.cameras.get(rack_cfg.camera_id)
        if not cam:
            raise HTTPException(status_code=404, detail=f"Камера полки не найдена: {rack_cfg.camera_id}")
        _validate_device(cam.device)
        return rack_cfg.camera_id, cam

    # Совместимость со старым config/kisamore.yaml.
    device = (rack_cfg.camera_device or "").strip()
    if not device:
        raise HTTPException(status_code=404, detail="Для этой полки web камера не указана")

    _validate_device(device)
    return f"rack_{rack_id}_legacy", CameraHW(
        name=f"Камера полки {rack_id}",
        device=device,
        flip_vertical=rack_cfg.camera_flip_vertical,
        flip_horizontal=rack_cfg.camera_flip_horizontal,
        warp_enabled=rack_cfg.camera_warp_enabled,
        warp_points=rack_cfg.camera_warp_points,
    )


def _mjpeg_for_camera(cam: CameraHW, corrected: bool):
    while True:
        quality, frame_width, frame_height = _camera_runtime_settings()

        jpeg = camera_manager.get_jpeg(
            device=cam.device,
            jpeg_quality=quality,
            frame_width=frame_width,
            frame_height=frame_height,
            flip_vertical=cam.flip_vertical if corrected else False,
            flip_horizontal=cam.flip_horizontal if corrected else False,
            warp_enabled=cam.warp_enabled if corrected else False,
            warp_points=cam.warp_points if corrected else None,
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
def rack_camera_stream(rack_id: int):
    _, cam = _get_camera_by_rack(rack_id)

    return StreamingResponse(
        _mjpeg_for_camera(cam, corrected=True),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/camera/{camera_id}/stream")
def camera_stream(
    camera_id: str,
    corrected: bool = Query(default=True),
):
    cam = _get_camera_by_id(camera_id)

    return StreamingResponse(
        _mjpeg_for_camera(cam, corrected=corrected),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/rack/{rack_id}/camera/info")
async def rack_camera_info(rack_id: int):
    camera_id, cam = _get_camera_by_rack(rack_id)

    return {
        "rack_id": rack_id,
        "camera_id": camera_id,
        "camera_name": cam.name,
        "camera_device": cam.device,
        "camera_flip_vertical": cam.flip_vertical,
        "camera_flip_horizontal": cam.flip_horizontal,
        "camera_warp_enabled": cam.warp_enabled,
        "camera_warp_points": cam.warp_points,
        "exists": True,
        "last_error": camera_manager.get_error(cam.device),
    }


@router.get("/camera/{camera_id}/info")
async def camera_info(camera_id: str):
    cam = _get_camera_by_id(camera_id)

    return {
        "camera_id": camera_id,
        "camera_name": cam.name,
        "camera_device": cam.device,
        "camera_flip_vertical": cam.flip_vertical,
        "camera_flip_horizontal": cam.flip_horizontal,
        "camera_warp_enabled": cam.warp_enabled,
        "camera_warp_points": cam.warp_points,
        "exists": True,
        "last_error": camera_manager.get_error(cam.device),
    }
