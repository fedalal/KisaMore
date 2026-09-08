from __future__ import annotations

import asyncio
import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from pydantic import ValidationError

from .api import process_edge_snapshot
from .config import get_settings
from .schemas import EdgeSnapshotIn


@dataclass
class _PendingSnapshot:
    created_at: float
    total_chunks: int
    chunks: dict[int, bytes] = field(default_factory=dict)
    done: dict | None = None


class MqttSnapshotConsumer:
    def __init__(self) -> None:
        self._client = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._pending: dict[tuple[str, str], _PendingSnapshot] = {}
        self._lock = threading.Lock()

    async def start(self) -> None:
        settings = get_settings()
        if not settings.mqtt_host:
            print("[cloud-mqtt] disabled: KISAMORE_MQTT_HOST is not configured")
            return
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            print("[cloud-mqtt] disabled: paho-mqtt is not installed")
            return

        self._loop = asyncio.get_running_loop()
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="kisamore-cloud-api",
            protocol=mqtt.MQTTv311,
        )
        if settings.mqtt_username:
            client.username_pw_set(settings.mqtt_username, settings.mqtt_password or None)
        if settings.mqtt_tls:
            client.tls_set()

        topic = f"{settings.mqtt_topic_prefix}/edge/+/snapshot/#"
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        try:
            client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=60)
            client.subscribe(topic, qos=1)
        except OSError as exc:
            print(f"[cloud-mqtt] disabled: cannot connect to MQTT broker: {exc}")
            return
        client.loop_start()
        self._client = client
        print(
            f"[cloud-mqtt] enabled: host={settings.mqtt_host}, "
            f"port={settings.mqtt_port}, topic={topic}"
        )

    async def stop(self) -> None:
        if self._client is None:
            return
        self._client.loop_stop()
        self._client.disconnect()
        self._client = None

    def _on_connect(self, client, _userdata, _flags, reason_code, _properties) -> None:
        settings = get_settings()
        if _mqtt_reason_code_failed(reason_code):
            print(f"[cloud-mqtt] connect failed: reason={reason_code}")
            return
        client.subscribe(f"{settings.mqtt_topic_prefix}/edge/+/snapshot/#", qos=1)

    def _on_message(self, _client, _userdata, message) -> None:
        try:
            self._handle_message(message.topic, bytes(message.payload))
        except Exception as exc:
            print(f"[cloud-mqtt] message rejected: {type(exc).__name__}: {exc!r}")

    def _handle_message(self, topic: str, payload: bytes) -> None:
        settings = get_settings()
        prefix = settings.mqtt_topic_prefix.strip("/")
        parts = topic.split("/")
        if len(parts) < 5 or parts[0] != prefix or parts[1] != "edge" or parts[3] != "snapshot":
            return
        device_id = parts[2]
        message_id = parts[4]
        key = (device_id, message_id)

        ready_payload: bytes | None = None
        with self._lock:
            self._discard_stale_locked(time.monotonic())
            if len(parts) == 8 and parts[5] == "chunk":
                index = int(parts[6])
                total = int(parts[7])
                if total < 1 or total > 1000 or index < 0 or index >= total:
                    raise ValueError("invalid MQTT chunk index")
                pending = self._pending.setdefault(
                    key,
                    _PendingSnapshot(created_at=time.monotonic(), total_chunks=total),
                )
                if pending.total_chunks == 0:
                    pending.total_chunks = total
                if pending.total_chunks != total:
                    raise ValueError("MQTT chunk count changed")
                pending.chunks[index] = payload
            elif len(parts) == 6 and parts[5] == "done":
                pending = self._pending.setdefault(
                    key,
                    _PendingSnapshot(created_at=time.monotonic(), total_chunks=0),
                )
                pending.done = json.loads(payload.decode("ascii"))
            else:
                return

            pending = self._pending.get(key)
            if pending and pending.done and pending.total_chunks:
                if len(pending.chunks) == pending.total_chunks:
                    ready_payload = b"".join(pending.chunks[index] for index in range(pending.total_chunks))
                    self._pending.pop(key, None)

        if ready_payload is not None:
            self._schedule_snapshot(device_id, message_id, ready_payload, pending.done)

    def _discard_stale_locked(self, now: float) -> None:
        ttl = get_settings().mqtt_message_ttl_seconds
        stale = [
            key
            for key, pending in self._pending.items()
            if now - pending.created_at > ttl
        ]
        for key in stale:
            self._pending.pop(key, None)

    def _schedule_snapshot(
        self,
        device_id: str,
        message_id: str,
        payload_bytes: bytes,
        done: dict | None,
    ) -> None:
        if self._loop is None:
            return
        future = asyncio.run_coroutine_threadsafe(
            self._process_snapshot(device_id, message_id, payload_bytes, done or {}),
            self._loop,
        )
        future.add_done_callback(self._log_task_error)

    async def _process_snapshot(
        self,
        device_id: str,
        message_id: str,
        payload_bytes: bytes,
        done: dict,
    ) -> None:
        expected_hash = done.get("sha256")
        actual_hash = hashlib.sha256(payload_bytes).hexdigest()
        if expected_hash and expected_hash != actual_hash:
            raise ValueError("MQTT snapshot checksum mismatch")
        if done.get("bytes") is not None and int(done["bytes"]) != len(payload_bytes):
            raise ValueError("MQTT snapshot byte count mismatch")

        try:
            payload = EdgeSnapshotIn.model_validate_json(payload_bytes)
        except ValidationError:
            raise
        now = datetime.now(timezone.utc)
        if payload.observed_at > now + timedelta(minutes=5):
            raise ValueError("observed_at is too far in the future")

        has_growing_data = await process_edge_snapshot(device_id, payload, now)
        print(
            f"[cloud-mqtt] snapshot accepted: device={device_id}, "
            f"message={message_id}, bytes={len(payload_bytes)}, "
            f"chunks={done.get('chunks')}, growing={has_growing_data}"
        )

    @staticmethod
    def _log_task_error(future) -> None:
        try:
            future.result()
        except Exception as exc:
            print(f"[cloud-mqtt] snapshot failed: {type(exc).__name__}: {exc!r}")


mqtt_snapshot_consumer = MqttSnapshotConsumer()


def _mqtt_reason_code_failed(reason_code) -> bool:
    is_failure = getattr(reason_code, "is_failure", None)
    if is_failure is not None:
        return bool(is_failure() if callable(is_failure) else is_failure)
    value = getattr(reason_code, "value", None)
    if value is not None:
        return int(value) != 0
    return int(reason_code) != 0
