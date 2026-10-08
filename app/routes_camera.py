from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from . import runtime
from .camera_one_shot import capture_one_shot_jpeg
from .camera_profiles import profile_controls, profile_format
from .hw_config import CameraHW
import os

router = APIRouter(prefix="/api", tags=["camera"])


def _camera_quality() -> int:
    if runtime.cfg and runtime.cfg.camera_capture:
        return int(runtime.cfg.camera_capture.jpeg_quality)
    return 90


def _default_capture_size() -> tuple[int, int]:
    if runtime.cfg and runtime.cfg.camera_capture:
        return (
            int(runtime.cfg.camera_capture.frame_width),
            int(runtime.cfg.camera_capture.frame_height),
        )
    return 2592, 1944


def _capture_settings(camera_id: str) -> tuple[int, int, str, int, dict[str, int]]:
    default_width, default_height = _default_capture_size()
    profile = runtime.camera_profiles.get(camera_id) if runtime.camera_profiles else None
    width, height, pixelformat, fps = profile_format(
        profile,
        default_width=default_width,
        default_height=default_height,
        default_pixelformat="MJPG",
        default_fps=30,
    )
    return width, height, pixelformat, fps, profile_controls(profile)


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


def _camera_ids_for_rack(rack_id: int) -> list[str]:
    if not runtime.cfg:
        raise HTTPException(status_code=503, detail="Конфигурация ещё не загружена")

    rack_cfg = runtime.cfg.racks.get(str(rack_id))
    if not rack_cfg:
        raise HTTPException(status_code=404, detail=f"Полка не найдена: {rack_id}")

    result = list(rack_cfg.camera_ids or [])
    if rack_cfg.camera_id and rack_cfg.camera_id not in result:
        result.insert(0, rack_cfg.camera_id)
    if rack_cfg.camera_id and result and result[0] != rack_cfg.camera_id:
        result = [rack_cfg.camera_id] + [item for item in result if item != rack_cfg.camera_id]
    return result


def _get_cameras_by_rack(rack_id: int) -> list[tuple[str, CameraHW]]:
    if not runtime.cfg:
        raise HTTPException(status_code=503, detail="Конфигурация ещё не загружена")

    rack_cfg = runtime.cfg.racks.get(str(rack_id))
    if not rack_cfg:
        raise HTTPException(status_code=404, detail=f"Полка не найдена: {rack_id}")

    result: list[tuple[str, CameraHW]] = []
    for camera_id in _camera_ids_for_rack(rack_id):
        cam = runtime.cfg.cameras.get(camera_id)
        if not cam:
            raise HTTPException(status_code=404, detail=f"Камера полки не найдена: {camera_id}")
        _validate_device(cam.device)
        result.append((camera_id, cam))

    if result:
        return result

    # Совместимость со старым config/kisamore.yaml.
    device = (rack_cfg.camera_device or "").strip()
    if not device:
        raise HTTPException(status_code=404, detail="Для этой полки web камера не указана")

    _validate_device(device)
    return [(
        f"rack_{rack_id}_legacy",
        CameraHW(
            name=f"Камера полки {rack_id}",
            device=device,
            flip_vertical=rack_cfg.camera_flip_vertical,
            flip_horizontal=rack_cfg.camera_flip_horizontal,
            warp_enabled=rack_cfg.camera_warp_enabled,
            warp_points=rack_cfg.camera_warp_points,
        ),
    )]


def _get_camera_by_rack(rack_id: int) -> tuple[str, CameraHW]:
    return _get_cameras_by_rack(rack_id)[0]


def _get_assigned_camera(rack_id: int, camera_id: str) -> CameraHW:
    cameras = dict(_get_cameras_by_rack(rack_id))
    cam = cameras.get(camera_id)
    if cam is None:
        raise HTTPException(
            status_code=404,
            detail=f"Камера {camera_id} не привязана к полке {rack_id}",
        )
    return cam


def _capture_camera_frame(camera_id: str, cam: CameraHW, *, corrected: bool) -> bytes:
    frame_width, frame_height, pixel_format, fps, saved_controls = _capture_settings(camera_id)

    jpeg = capture_one_shot_jpeg(
        device=cam.device,
        jpeg_quality=_camera_quality(),
        frame_width=frame_width,
        frame_height=frame_height,
        pixel_format=pixel_format,
        fps=fps,
        flip_vertical=cam.flip_vertical,
        flip_horizontal=cam.flip_horizontal,
        warp_enabled=cam.warp_enabled if corrected else False,
        warp_points=cam.warp_points if corrected else None,
        autofocus_enabled=cam.autofocus_enabled,
        focus_absolute=cam.focus_absolute,
        white_balance_auto=cam.white_balance_auto,
        white_balance_temperature=cam.white_balance_temperature,
        brightness=cam.brightness,
        contrast=cam.contrast,
        saturation=cam.saturation,
        sharpness=cam.sharpness,
        profile_controls=saved_controls or None,
        focus_ramp=False,
    )

    if not jpeg:
        raise HTTPException(
            status_code=503,
            detail=f"Не удалось получить кадр с камеры {cam.device}",
        )
    return jpeg


def _jpeg_response(jpeg: bytes) -> Response:
    return Response(
        content=jpeg,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@router.get("/rack/{rack_id}/camera/frame")
def rack_camera_frame(
    rack_id: int,
    t: int | None = Query(default=None),
):
    _ = t
    camera_id, cam = _get_camera_by_rack(rack_id)
    return _jpeg_response(_capture_camera_frame(camera_id, cam, corrected=True))


@router.get("/rack/{rack_id}/cameras/{camera_id}/frame")
def rack_named_camera_frame(
    rack_id: int,
    camera_id: str,
    corrected: bool = Query(default=True),
    t: int | None = Query(default=None),
):
    _ = t
    cam = _get_assigned_camera(rack_id, camera_id)
    return _jpeg_response(_capture_camera_frame(camera_id, cam, corrected=corrected))


@router.get("/camera/{camera_id}/frame")
def camera_frame(
    camera_id: str,
    corrected: bool = Query(default=True),
    t: int | None = Query(default=None),
):
    _ = t
    cam = _get_camera_by_id(camera_id)
    return _jpeg_response(_capture_camera_frame(camera_id, cam, corrected=corrected))


@router.get("/rack/{rack_id}/camera/stream")
def rack_camera_stream_disabled(rack_id: int):
    _ = rack_id
    raise HTTPException(
        status_code=410,
        detail="Прямой эфир отключён. Используйте /camera/frame для одиночного кадра.",
    )


@router.get("/camera/{camera_id}/stream")
def camera_stream_disabled(camera_id: str):
    _ = camera_id
    raise HTTPException(
        status_code=410,
        detail="Прямой эфир отключён. Используйте /camera/{camera_id}/frame.",
    )


@router.get("/rack/{rack_id}/cameras")
async def rack_cameras(rack_id: int):
    rows = []
    cameras = _get_cameras_by_rack(rack_id)
    for index, (camera_id, cam) in enumerate(cameras):
        frame_width, frame_height, pixel_format, fps, saved_controls = _capture_settings(camera_id)
        rows.append({
            "rack_id": rack_id,
            "camera_id": camera_id,
            "camera_name": cam.name,
            "camera_device": cam.device,
            "primary": index == 0,
            "camera_flip_vertical": cam.flip_vertical,
            "camera_flip_horizontal": cam.flip_horizontal,
            "camera_warp_enabled": cam.warp_enabled,
            "camera_warp_points": cam.warp_points,
            "frame_width": frame_width,
            "frame_height": frame_height,
            "pixel_format": pixel_format,
            "fps": fps,
            "profile_loaded": bool(saved_controls),
        })
    return rows


@router.get("/rack/{rack_id}/camera/info")
async def rack_camera_info(rack_id: int):
    camera_id, cam = _get_camera_by_rack(rack_id)
    frame_width, frame_height, pixel_format, fps, saved_controls = _capture_settings(camera_id)
    all_camera_ids = [item[0] for item in _get_cameras_by_rack(rack_id)]

    return {
        "rack_id": rack_id,
        "camera_id": camera_id,
        "camera_ids": all_camera_ids,
        "camera_name": cam.name,
        "camera_device": cam.device,
        "camera_flip_vertical": cam.flip_vertical,
        "camera_flip_horizontal": cam.flip_horizontal,
        "camera_warp_enabled": cam.warp_enabled,
        "camera_warp_points": cam.warp_points,
        "frame_width": frame_width,
        "frame_height": frame_height,
        "pixel_format": pixel_format,
        "fps": fps,
        "profile_loaded": bool(saved_controls),
        "exists": True,
        "last_error": None,
    }


@router.get("/camera/{camera_id}/info")
async def camera_info(camera_id: str):
    cam = _get_camera_by_id(camera_id)
    frame_width, frame_height, pixel_format, fps, saved_controls = _capture_settings(camera_id)

    return {
        "camera_id": camera_id,
        "camera_name": cam.name,
        "camera_device": cam.device,
        "camera_flip_vertical": cam.flip_vertical,
        "camera_flip_horizontal": cam.flip_horizontal,
        "camera_warp_enabled": cam.warp_enabled,
        "camera_warp_points": cam.warp_points,
        "frame_width": frame_width,
        "frame_height": frame_height,
        "pixel_format": pixel_format,
        "fps": fps,
        "profile_loaded": bool(saved_controls),
        "exists": True,
        "last_error": None,
    }
