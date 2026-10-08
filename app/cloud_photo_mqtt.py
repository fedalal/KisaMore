from __future__ import annotations

import asyncio
import hashlib
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from . import runtime


def _photo_chunk_bytes() -> int:
    return max(
        4 * 1024,
        min(64 * 1024, int(os.getenv("KISAMORE_MQTT_PHOTO_CHUNK_BYTES", "16384"))),
    )


def _photo_timeout_seconds() -> float:
    # Full-resolution 4K JPEGs are much larger than the previous 720p frames.
    # Keep enough time for sequential QoS1 chunk delivery over Tailscale/VPN.
    return max(10.0, float(os.getenv("KISAMORE_MQTT_PHOTO_TIMEOUT_SECONDS", "120")))


def _message_id(data: bytes, rack_id: int, camera_id: str) -> str:
    nonce = f"{time.time_ns()}:{os.getpid()}:{rack_id}:{camera_id}".encode("utf-8")
    return hashlib.sha256(nonce + data).hexdigest()[:24]


def _publish_photo_mqtt_blocking(
    settings,
    rack_id: int,
    camera_id: str,
    is_primary: bool,
    path: Path,
    captured_at: str,
) -> None:
    try:
        import paho.mqtt.client as mqtt
    except ImportError as exc:
        raise RuntimeError("paho-mqtt is not installed") from exc

    data = path.read_bytes()
    if len(data) < 4 or not data.startswith(b"\xff\xd8\xff"):
        raise ValueError(f"latest rack photo is not a JPEG: {path}")

    chunk_size = _photo_chunk_bytes()
    chunks = [data[index : index + chunk_size] for index in range(0, len(data), chunk_size)]
    if not chunks:
        chunks = [b""]

    message_id = _message_id(data, rack_id, camera_id)
    safe_camera_id = "".join(
        ch if ch.isalnum() or ch in ("-", "_") else "_"
        for ch in str(camera_id)
    ).strip("_") or "camera"
    base_topic = (
        f"{settings.mqtt_topic_prefix}/edge/{settings.device_id}/photo/"
        f"{rack_id}/{safe_camera_id}/{message_id}"
    )
    ack_topic = (
        f"{settings.mqtt_topic_prefix}/cloud/{settings.device_id}/photo/"
        f"{rack_id}/{safe_camera_id}/{message_id}/ack"
    )
    timeout = _photo_timeout_seconds()
    deadline = time.monotonic() + timeout
    ack_event = threading.Event()
    ack_result: dict[str, object] = {}

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"kisamore-photo-{os.getpid()}-{rack_id}-{safe_camera_id}",
        protocol=mqtt.MQTTv311,
        reconnect_on_failure=False,
    )
    if settings.mqtt_username:
        client.username_pw_set(settings.mqtt_username, settings.mqtt_password or None)
    if settings.mqtt_tls:
        client.tls_set()

    def on_message(_client, _userdata, message) -> None:
        if message.topic != ack_topic:
            return
        try:
            body = json.loads(bytes(message.payload).decode("utf-8"))
            ack_result.update(body if isinstance(body, dict) else {})
        except Exception as exc:
            ack_result.update({"ok": False, "error": f"invalid ack: {exc}"})
        finally:
            ack_event.set()

    client.on_message = on_message
    client.connect_timeout = min(settings.request_timeout_seconds, timeout)
    loop_started = False
    try:
        client.connect(
            settings.mqtt_host,
            settings.mqtt_port,
            keepalive=max(30, int(timeout) + 5),
        )
        client.loop_start()
        loop_started = True
        client.subscribe(ack_topic, qos=1)

        def publish(topic: str, payload: bytes, label: str) -> None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"MQTT photo timed out before {label}")
            info = client.publish(topic, payload, qos=1, retain=False)
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                raise RuntimeError(f"MQTT photo publish failed with code {info.rc}: {label}")
            info.wait_for_publish(timeout=remaining)
            if not info.is_published():
                raise TimeoutError(f"MQTT photo acknowledgement timed out: {label}")

        print(
            f"[cloud-sync] MQTT photo: rack={rack_id}, camera={camera_id}, "
            f"primary={is_primary}, bytes={len(data)}, chunks={len(chunks)}, "
            f"chunk={chunk_size}, timeout={timeout:g}s"
        )
        for index, chunk in enumerate(chunks):
            publish(
                f"{base_topic}/chunk/{index}/{len(chunks)}",
                chunk,
                f"rack={rack_id} camera={camera_id} chunk={index + 1}/{len(chunks)}",
            )

        done = json.dumps(
            {
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
                "chunks": len(chunks),
                "captured_at": captured_at,
                "content_type": "image/jpeg",
                "camera_id": camera_id,
                "is_primary": bool(is_primary),
            },
            separators=(",", ":"),
        ).encode("utf-8")
        publish(
            f"{base_topic}/done",
            done,
            f"rack={rack_id} camera={camera_id} done",
        )

        remaining = deadline - time.monotonic()
        if remaining <= 0 or not ack_event.wait(remaining):
            raise TimeoutError(
                f"VPS did not confirm MQTT photo: rack={rack_id}, camera={camera_id}"
            )
        if ack_result.get("ok") is not True:
            raise RuntimeError(
                f"VPS rejected MQTT photo: rack={rack_id}, camera={camera_id}: "
                f"{ack_result.get('error') or 'unknown error'}"
            )
        if ack_result.get("sha256") != hashlib.sha256(data).hexdigest():
            raise RuntimeError(
                f"VPS confirmed a different MQTT photo: rack={rack_id}, camera={camera_id}"
            )
    finally:
        try:
            client.disconnect()
        finally:
            if loop_started:
                client.loop_stop()


def install_cloud_photo_mqtt(service) -> None:
    """Use MQTT for latest rack photos whenever the main cloud transport uses MQTT.

    The original HTTPS uploader stays installed as a fallback for configurations
    where MQTT is disabled. A rack mtime is acknowledged only after the VPS has
    persisted the JPEG and sent a positive MQTT acknowledgement.
    """
    if getattr(service, "_cloud_photo_mqtt_installed", False):
        return

    original_send_changed_photos = service._send_changed_photos

    async def send_changed_photos() -> int:
        settings = service._settings
        if settings is None or not settings.mqtt_enabled:
            return await original_send_changed_photos()
        if not runtime.cfg or not runtime.cfg.camera_capture.enabled:
            return 0

        latest_dir = Path(runtime.cfg.camera_capture.latest_dir or "data/camera_latest")
        sent = 0
        for rack_id in range(1, runtime.cfg.racks_count + 1):
            rack_cfg = runtime.cfg.racks.get(str(rack_id))
            if rack_cfg is None:
                continue

            camera_ids = list(rack_cfg.camera_ids or [])
            if rack_cfg.camera_id and rack_cfg.camera_id not in camera_ids:
                camera_ids.insert(0, rack_cfg.camera_id)
            if rack_cfg.camera_id and camera_ids and camera_ids[0] != rack_cfg.camera_id:
                camera_ids = [rack_cfg.camera_id] + [
                    item for item in camera_ids if item != rack_cfg.camera_id
                ]
            if not camera_ids:
                camera_ids = [f"rack_{rack_id}_legacy"]

            for index, camera_id in enumerate(camera_ids):
                is_primary = index == 0
                camera_key = "".join(
                    ch if ch.isalnum() or ch in ("-", "_") else "_"
                    for ch in str(camera_id)
                ).strip("_") or "camera"
                path = latest_dir / f"rack_{rack_id}__{camera_key}.jpg"
                if is_primary and not path.is_file():
                    path = latest_dir / f"rack_{rack_id}.jpg"

                try:
                    stat = path.stat()
                except FileNotFoundError:
                    continue

                upload_key = f"{rack_id}:{camera_id}"
                mtime_ns = stat.st_mtime_ns
                if service._uploaded_photo_mtimes.get(upload_key) == mtime_ns:
                    continue

                captured_at = datetime.fromtimestamp(
                    stat.st_mtime,
                    tz=timezone.utc,
                ).isoformat()
                try:
                    await asyncio.to_thread(
                        _publish_photo_mqtt_blocking,
                        settings,
                        rack_id,
                        camera_id,
                        is_primary,
                        path,
                        captured_at,
                    )
                except Exception as exc:
                    print(
                        f"[cloud-sync] MQTT photo failed: rack={rack_id}, "
                        f"camera={camera_id}: {type(exc).__name__}: {exc!r}"
                    )
                    continue

                service._uploaded_photo_mtimes[upload_key] = mtime_ns
                sent += 1
                print(
                    f"[cloud-sync] MQTT photo confirmed by VPS: "
                    f"rack={rack_id}, camera={camera_id}, primary={is_primary}"
                )
        return sent

    service._send_changed_photos = send_changed_photos
    service._cloud_photo_mqtt_installed = True
