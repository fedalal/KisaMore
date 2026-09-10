from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from . import runtime
from .camera_access import device_access_lock
from .camera_manager import camera_manager
from .hw_config import CameraHW
import os
import time

router = APIRouter(prefix="/api", tags=["camera"])


# Ordinary live video is intentionally kept at 720p. Full-resolution frames for
# the VPS/archive are captured separately as short one-shot streams. The camera
# settings page is the only exception: it may temporarily preview one selected
# camera at calibration resolution so warp points remain pixel-perfect.
LIVE_FRAME_WIDTH = 1280
LIVE_FRAME_HEIGHT = 720


def _camera_quality() -> int:
    if runtime.cfg and runtime.cfg.camera_capture:
        return int(runtime.cfg.camera_capture.jpeg_quality)
    return 90


def _warp_reference_size() -> tuple[int, int]:
    if runtime.cfg and runtime.cfg.camera_capture:
        return (
            int(runtime.cfg.camera_capture.frame_width),
            int(runtime.cfg.camera_capture.frame_height),
        )
    return LIVE_FRAME_WIDTH, LIVE_FRAME_HEIGHT


def _scale_warp_points(
    points: list[float] | None,
    *,
    target_width: int,
    target_height: int,
) -> list[float] | None:
    """Scale calibration coordinates from photo resolution to a target frame."""
    if not points or len(points) != 8:
        return points

    source_width, source_height = _warp_reference_size()
    if source_width <= 1 or source_height <= 1:
        return points
    if source_width == target_width and source_height == target_height:
        return points

    scale_x = (target_width - 1) / (source_width - 1)
    scale_y = (target_height - 1) / (source_height - 1)
    scaled: list[float] = []
    for index in range(0, 8, 2):
        scaled.append(float(points[index]) * scale_x)
        scaled.append(float(points[index + 1]) * scale_y)
    return scaled


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


def _mjpeg_for_camera(
    cam: CameraHW,
    corrected: bool,
    *,
    frame_width: int,
    frame_height: int,
):
    while True:
        warp_points = (
            _scale_warp_points(
                cam.warp_points,
                target_width=frame_width,
                target_height=frame_height,
            )
            if corrected
            else None
        )

        # High-resolution one-shot capture takes the same device lock. While a
        # 4K photo is being taken this preview pauses briefly instead of opening
        # a second hardware stream on the USB camera.
        with device_access_lock(cam.device):
            jpeg = camera_manager.get_jpeg(
                device=cam.device,
                jpeg_quality=_camera_quality(),
                frame_width=frame_width,
                frame_height=frame_height,

                # Поворот должен применяться и к "До коррекции", и к "После коррекции".
                # Иначе точки выбираются на одном изображении, а применяются к другому.
                flip_vertical=cam.flip_vertical,
                flip_horizontal=cam.flip_horizontal,

                # Перспективу применяем только для правого изображения "После коррекции".
                warp_enabled=cam.warp_enabled if corrected else False,
                warp_points=warp_points,

                autofocus_enabled=cam.autofocus_enabled,
                focus_absolute=cam.focus_absolute,
                white_balance_auto=cam.white_balance_auto,
                white_balance_temperature=cam.white_balance_temperature,
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
        _mjpeg_for_camera(
            cam,
            corrected=True,
            frame_width=LIVE_FRAME_WIDTH,
            frame_height=LIVE_FRAME_HEIGHT,
        ),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/camera/{camera_id}/stream")
def camera_stream(
    camera_id: str,
    corrected: bool = Query(default=True),
    full_resolution: bool = Query(default=False),
    t: int | None = Query(default=None),
):
    cam = _get_camera_by_id(camera_id)

    # Existing camera-settings JS adds a cache-busting `t` query parameter.
    # That page displays only one selected camera at a time, so using the full
    # calibration resolution there is safe and keeps point picking compatible
    # with the 3840x2160 coordinates stored in config. Normal stream URLs have
    # no `t` and stay at 1280x720.
    calibration_preview = full_resolution or t is not None
    if calibration_preview:
        frame_width, frame_height = _warp_reference_size()
    else:
        frame_width, frame_height = LIVE_FRAME_WIDTH, LIVE_FRAME_HEIGHT

    return StreamingResponse(
        _mjpeg_for_camera(
            cam,
            corrected=corrected,
            frame_width=frame_width,
            frame_height=frame_height,
        ),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/rack/{rack_id}/camera/info")
async def rack_camera_info(rack_id: int):
    camera_id, cam = _get_camera_by_rack(rack_id)
    reference_width, reference_height = _warp_reference_size()

    return {
        "rack_id": rack_id,
        "camera_id": camera_id,
        "camera_name": cam.name,
        "camera_device": cam.device,
        "camera_flip_vertical": cam.flip_vertical,
        "camera_flip_horizontal": cam.flip_horizontal,
        "camera_warp_enabled": cam.warp_enabled,
        "camera_warp_points": cam.warp_points,
        "warp_reference_width": reference_width,
        "warp_reference_height": reference_height,
        "live_width": LIVE_FRAME_WIDTH,
        "live_height": LIVE_FRAME_HEIGHT,
        "exists": True,
        "last_error": camera_manager.get_error(cam.device),
    }


@router.get("/camera/{camera_id}/info")
async def camera_info(camera_id: str):
    cam = _get_camera_by_id(camera_id)
    reference_width, reference_height = _warp_reference_size()

    return {
        "camera_id": camera_id,
        "camera_name": cam.name,
        "camera_device": cam.device,
        "camera_flip_vertical": cam.flip_vertical,
        "camera_flip_horizontal": cam.flip_horizontal,
        "camera_warp_enabled": cam.warp_enabled,
        "camera_warp_points": cam.warp_points,
        "warp_reference_width": reference_width,
        "warp_reference_height": reference_height,
        "live_width": LIVE_FRAME_WIDTH,
        "live_height": LIVE_FRAME_HEIGHT,
        "exists": True,
        "last_error": camera_manager.get_error(cam.device),
    }
