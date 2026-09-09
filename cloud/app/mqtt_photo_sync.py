from __future__ import annotations

import asyncio
import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from .config import get_settings
from .db import SessionLocal
from .models import Device, RackPhoto


@dataclass
class _PendingPhoto:
    created_at: float
    rack_id: int
    total_chunks: int
    chunks: dict[int, bytes] = field(default_factory=dict)
    done: dict | None = None
    total_bytes: int = 0


class MqttPhotoConsumer:
    def __init__(self) -> None:
        self._client = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._pending: dict[tuple[str, int, str], _PendingPhoto] = {}
        self._lock = threading.Lock()

    async def start(self) -> None:
        settings = get_settings()
        if not settings.mqtt_host:
            print("[cloud-mqtt-photo] disabled: KISAMORE_MQTT_HOST is not configured")
            return
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            print("[cloud-mqtt-photo] disabled: paho-mqtt is not installed")
            return

        self._loop = asyncio.get_running_loop()
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="kisamore-cloud-photo",
            protocol=mqtt.MQTTv311,
        )
        if settings.mqtt_username:
            client.username_pw_set(settings.mqtt_username, settings.mqtt_password or None)
        if settings.mqtt_tls:
            client.tls_set()

        client.on_connect = self._on_connect
        client.on_message = self._on_message
        topic = f"{settings.mqtt_topic_prefix}/edge/+/photo/#"
        try:
            client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=60)
            client.subscribe(topic, qos=1)
        except OSError as exc:
            print(f"[cloud-mqtt-photo] disabled: cannot connect to MQTT broker: {exc}")
            return
        client.loop_start()
        self._client = client
        print(
            f"[cloud-mqtt-photo] enabled: host={settings.mqtt_host}, "
            f"port={settings.mqtt_port}, topic={topic}"
        )

    async def stop(self) -> None:
        if self._client is None:
            return
        self._client.loop_stop()
        self._client.disconnect()
        self._client = None

    def _on_connect(self, client, _userdata, _flags, reason_code, _properties) -> None:
        if _mqtt_reason_code_failed(reason_code):
            print(f"[cloud-mqtt-photo] connect failed: reason={reason_code}")
            return
        settings = get_settings()
        client.subscribe(f"{settings.mqtt_topic_prefix}/edge/+/photo/#", qos=1)

    def _on_message(self, _client, _userdata, message) -> None:
        try:
            self._handle_message(message.topic, bytes(message.payload))
        except Exception as exc:
            print(f"[cloud-mqtt-photo] message rejected: {type(exc).__name__}: {exc!r}")

    def _handle_message(self, topic: str, payload: bytes) -> None:
        settings = get_settings()
        prefix = settings.mqtt_topic_prefix.strip("/")
        parts = topic.split("/")
        if len(parts) < 7 or parts[0] != prefix or parts[1] != "edge" or parts[3] != "photo":
            return

        device_id = parts[2]
        try:
            rack_id = int(parts[4])
        except ValueError as exc:
            raise ValueError("invalid MQTT photo rack id") from exc
        if rack_id < 1 or rack_id > 16:
            raise ValueError("invalid MQTT photo rack id")
        message_id = parts[5]
        if not message_id or len(message_id) > 80:
            raise ValueError("invalid MQTT photo message id")
        key = (device_id, rack_id, message_id)

        ready_payload: bytes | None = None
        done_payload: dict | None = None
        with self._lock:
            self._discard_stale_locked(time.monotonic())
            if len(parts) == 9 and parts[6] == "chunk":
                try:
                    index = int(parts[7])
                    total = int(parts[8])
                except ValueError as exc:
                    raise ValueError("invalid MQTT photo chunk index") from exc
                if total < 1 or total > 512 or index < 0 or index >= total:
                    raise ValueError("invalid MQTT photo chunk index")
                if len(payload) > 64 * 1024:
                    raise ValueError("MQTT photo chunk is too large")
                pending = self._pending.setdefault(
                    key,
                    _PendingPhoto(
                        created_at=time.monotonic(),
                        rack_id=rack_id,
                        total_chunks=total,
                    ),
                )
                if pending.total_chunks == 0:
                    pending.total_chunks = total
                if pending.total_chunks != total:
                    raise ValueError("MQTT photo chunk count changed")
                previous = pending.chunks.get(index)
                new_total = pending.total_bytes - (len(previous) if previous is not None else 0) + len(payload)
                if new_total > settings.photo_max_bytes:
                    self._pending.pop(key, None)
                    raise ValueError("MQTT photo exceeds configured size limit")
                pending.chunks[index] = payload
                pending.total_bytes = new_total
            elif len(parts) == 7 and parts[6] == "done":
                pending = self._pending.setdefault(
                    key,
                    _PendingPhoto(
                        created_at=time.monotonic(),
                        rack_id=rack_id,
                        total_chunks=0,
                    ),
                )
                body = json.loads(payload.decode("utf-8"))
                if not isinstance(body, dict):
                    raise ValueError("invalid MQTT photo done payload")
                pending.done = body
            else:
                return

            pending = self._pending.get(key)
            if pending and pending.done and pending.total_chunks:
                expected_chunks = pending.done.get("chunks")
                if expected_chunks is not None and int(expected_chunks) != pending.total_chunks:
                    self._pending.pop(key, None)
                    raise ValueError("MQTT photo done chunk count mismatch")
                if len(pending.chunks) == pending.total_chunks:
                    ready_payload = b"".join(
                        pending.chunks[index] for index in range(pending.total_chunks)
                    )
                    done_payload = pending.done
                    self._pending.pop(key, None)

        if ready_payload is not None:
            self._schedule_photo(device_id, rack_id, message_id, ready_payload, done_payload or {})

    def _discard_stale_locked(self, now: float) -> None:
        ttl = get_settings().mqtt_message_ttl_seconds
        stale = [
            key
            for key, pending in self._pending.items()
            if now - pending.created_at > ttl
        ]
        for key in stale:
            self._pending.pop(key, None)

    def _schedule_photo(
        self,
        device_id: str,
        rack_id: int,
        message_id: str,
        payload_bytes: bytes,
        done: dict,
    ) -> None:
        if self._loop is None:
            return
        future = asyncio.run_coroutine_threadsafe(
            self._process_photo(device_id, rack_id, message_id, payload_bytes, done),
            self._loop,
        )
        future.add_done_callback(
            lambda item: self._finish_photo(item, device_id, rack_id, message_id)
        )

    async def _process_photo(
        self,
        device_id: str,
        rack_id: int,
        message_id: str,
        payload_bytes: bytes,
        done: dict,
    ) -> dict[str, object]:
        settings = get_settings()
        if len(payload_bytes) > settings.photo_max_bytes:
            raise ValueError("MQTT photo exceeds configured size limit")
        if len(payload_bytes) < 4 or not payload_bytes.startswith(b"\xff\xd8\xff"):
            raise ValueError("invalid JPEG photo")
        if done.get("content_type") not in (None, "image/jpeg", "image/jpg"):
            raise ValueError("unsupported MQTT photo content type")

        expected_hash = str(done.get("sha256") or "")
        actual_hash = hashlib.sha256(payload_bytes).hexdigest()
        if expected_hash and expected_hash != actual_hash:
            raise ValueError("MQTT photo checksum mismatch")
        if done.get("bytes") is not None and int(done["bytes"]) != len(payload_bytes):
            raise ValueError("MQTT photo byte count mismatch")

        raw_captured_at = done.get("captured_at")
        if not raw_captured_at:
            raise ValueError("MQTT photo captured_at is required")
        try:
            captured_at = datetime.fromisoformat(str(raw_captured_at).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("invalid MQTT photo captured_at") from exc
        if captured_at.tzinfo is None:
            captured_at = captured_at.replace(tzinfo=timezone.utc)
        else:
            captured_at = captured_at.astimezone(timezone.utc)

        async with SessionLocal() as session:
            device = await session.get(Device, device_id)
            if device is None or not device.is_active:
                raise ValueError("active MQTT photo device was not found")
            if rack_id < 1 or rack_id > max(device.racks_count, 1):
                raise ValueError("MQTT photo rack was not found")

            device_dir = hashlib.sha256(device.id.encode("utf-8")).hexdigest()[:20]
            target_dir = Path(settings.photo_dir) / device_dir
            await asyncio.to_thread(target_dir.mkdir, parents=True, exist_ok=True)
            target = target_dir / f"rack_{rack_id}.jpg"
            temporary = target.with_suffix(".jpg.tmp")
            await asyncio.to_thread(temporary.write_bytes, payload_bytes)
            await asyncio.to_thread(temporary.replace, target)

            now = datetime.now(timezone.utc)
            record = (
                await session.execute(
                    select(RackPhoto).where(
                        RackPhoto.device_id == device.id,
                        RackPhoto.rack_id == rack_id,
                    )
                )
            ).scalar_one_or_none()
            if record is None:
                record = RackPhoto(
                    device_id=device.id,
                    rack_id=rack_id,
                    file_path=str(target),
                    content_type="image/jpeg",
                    size_bytes=len(payload_bytes),
                    captured_at=captured_at,
                    updated_at=now,
                )
                session.add(record)
            else:
                record.file_path = str(target)
                record.content_type = "image/jpeg"
                record.size_bytes = len(payload_bytes)
                record.captured_at = captured_at
                record.updated_at = now
            await session.commit()

        print(
            f"[cloud-mqtt-photo] photo accepted: device={device_id}, rack={rack_id}, "
            f"message={message_id}, bytes={len(payload_bytes)}, chunks={done.get('chunks')}"
        )
        return {"sha256": actual_hash, "bytes": len(payload_bytes)}

    def _finish_photo(self, future, device_id: str, rack_id: int, message_id: str) -> None:
        try:
            result = future.result()
        except Exception as exc:
            print(
                f"[cloud-mqtt-photo] photo failed: device={device_id}, rack={rack_id}, "
                f"message={message_id}, error={type(exc).__name__}: {exc!r}"
            )
            self._publish_ack(
                device_id,
                rack_id,
                message_id,
                {"ok": False, "error": str(exc)[:200]},
            )
            return

        self._publish_ack(
            device_id,
            rack_id,
            message_id,
            {"ok": True, **result},
        )

    def _publish_ack(
        self,
        device_id: str,
        rack_id: int,
        message_id: str,
        payload: dict[str, object],
    ) -> None:
        if self._client is None:
            return
        settings = get_settings()
        topic = (
            f"{settings.mqtt_topic_prefix}/cloud/{device_id}/photo/"
            f"{rack_id}/{message_id}/ack"
        )
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        info = self._client.publish(topic, body, qos=1, retain=False)
        if info.rc != 0:
            print(
                f"[cloud-mqtt-photo] ack publish failed: device={device_id}, "
                f"rack={rack_id}, message={message_id}, rc={info.rc}"
            )


mqtt_photo_consumer = MqttPhotoConsumer()


def _mqtt_reason_code_failed(reason_code) -> bool:
    is_failure = getattr(reason_code, "is_failure", None)
    if is_failure is not None:
        return bool(is_failure() if callable(is_failure) else is_failure)
    value = getattr(reason_code, "value", None)
    if value is not None:
        return int(value) != 0
    return int(reason_code) != 0
