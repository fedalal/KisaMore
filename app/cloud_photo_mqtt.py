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
    return max(10.0, float(os.getenv("KISAMORE_MQTT_PHOTO_TIMEOUT_SECONDS", "30")))


def _message_id(data: bytes, rack_id: int) -> str:
    nonce = f"{time.time_ns()}:{os.getpid()}:{rack_id}".encode("ascii")
    return hashlib.sha256(nonce + data).hexdigest()[:24]


def _publish_photo_mqtt_blocking(settings, rack_id: int, path: Path, captured_at: str) -> None:
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

    message_id = _message_id(data, rack_id)
    base_topic = (
        f"{settings.mqtt_topic_prefix}/edge/{settings.device_id}/photo/"
        f"{rack_id}/{message_id}"
    )
    ack_topic = (
        f"{settings.mqtt_topic_prefix}/cloud/{settings.device_id}/photo/"
        f"{rack_id}/{message_id}/ack"
    )
    timeout = _photo_timeout_seconds()
    deadline = time.monotonic() + timeout
    ack_event = threading.Event()
    ack_result: dict[str, object] = {}

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"kisamore-photo-{os.getpid()}-{rack_id}",
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
        except Exception as exc:  # pragma: no cover - defensive logging path
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
            f"[cloud-sync] MQTT photo: rack={rack_id}, bytes={len(data)}, "
            f"chunks={len(chunks)}, chunk={chunk_size}, timeout={timeout:g}s"
        )
        for index, chunk in enumerate(chunks):
            publish(
                f"{base_topic}/chunk/{index}/{len(chunks)}",
                chunk,
                f"rack={rack_id} chunk={index + 1}/{len(chunks)}",
            )

        done = json.dumps(
            {
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
                "chunks": len(chunks),
                "captured_at": captured_at,
                "content_type": "image/jpeg",
            },
            separators=(",", ":"),
        ).encode("utf-8")
        publish(f"{base_topic}/done", done, f"rack={rack_id} done")

        remaining = deadline - time.monotonic()
        if remaining <= 0 or not ack_event.wait(remaining):
            raise TimeoutError(f"VPS did not confirm MQTT photo: rack={rack_id}")
        if ack_result.get("ok") is not True:
            raise RuntimeError(
                f"VPS rejected MQTT photo: rack={rack_id}: "
                f"{ack_result.get('error') or 'unknown error'}"
            )
        if ack_result.get("sha256") != hashlib.sha256(data).hexdigest():
            raise RuntimeError(f"VPS confirmed a different MQTT photo: rack={rack_id}")
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
            path = latest_dir / f"rack_{rack_id}.jpg"
            try:
                stat = path.stat()
            except FileNotFoundError:
                continue

            mtime_ns = stat.st_mtime_ns
            if service._uploaded_photo_mtimes.get(rack_id) == mtime_ns:
                continue

            captured_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
            try:
                await asyncio.to_thread(
                    _publish_photo_mqtt_blocking,
                    settings,
                    rack_id,
                    path,
                    captured_at,
                )
            except Exception as exc:
                # Do not mark this mtime as delivered. It will be retried on the
                # next cloud-sync cycle, while other racks can still proceed.
                print(
                    f"[cloud-sync] MQTT photo failed: rack={rack_id}: "
                    f"{type(exc).__name__}: {exc!r}"
                )
                continue

            service._uploaded_photo_mtimes[rack_id] = mtime_ns
            sent += 1
            print(f"[cloud-sync] MQTT photo confirmed by VPS: rack={rack_id}")
        return sent

    service._send_changed_photos = send_changed_photos
    service._cloud_photo_mqtt_installed = True
