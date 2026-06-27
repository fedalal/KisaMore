from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from . import runtime
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
    try:
        import cv2
    except Exception as e:
        raise RuntimeError(
            "Не установлен OpenCV. Установи на Raspberry Pi: sudo apt install -y python3-opencv"
        ) from e

    cap = cv2.VideoCapture(device, cv2.CAP_V4L2)

    if not cap.isOpened():
        raise RuntimeError(f"Не удалось открыть камеру {device}")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 15)

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.2)
                continue

            ok, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if not ok:
                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" +
                jpg.tobytes() +
                b"\r\n"
            )

            time.sleep(0.06)

    finally:
        cap.release()


@router.get("/rack/{rack_id}/camera/stream")
def camera_stream(rack_id: int):
    device = _get_camera_device(rack_id)

    try:
        generator = _mjpeg_generator(device)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return StreamingResponse(
        generator,
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
    }