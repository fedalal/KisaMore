from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import tempfile
import time
from base64 import urlsafe_b64encode
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from pathlib import Path

from sqlalchemy import select

from . import runtime
from .db import SessionLocal
from .models import Plant, Planting, RackSensorHistory, RackSlot, RackState


def _as_utc_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True)
class CloudSyncSettings:
    api_url: str
    device_id: str
    device_token: str
    interval_seconds: int = 30
    request_timeout_seconds: float = 10.0
    growing_sync_timeout_seconds: float = 120.0
    software_version: str = "unknown"
    mqtt_host: str = ""
    mqtt_port: int = 1883
    mqtt_username: str = ""
    mqtt_password: str = ""
    mqtt_tls: bool = False
    mqtt_topic_prefix: str = "kisamore"
    mqtt_chunk_bytes: int = 900

    @classmethod
    def from_env(cls) -> "CloudSyncSettings | None":
        api_url = os.getenv("KISAMORE_CLOUD_URL", "").strip().rstrip("/")
        device_id = os.getenv("KISAMORE_DEVICE_ID", "").strip()
        device_token = os.getenv("KISAMORE_DEVICE_TOKEN", "").strip()

        if not api_url or not device_id or not device_token:
            return None

        is_local_http = api_url.startswith(("http://127.0.0.1", "http://localhost"))
        if not api_url.startswith("https://") and not is_local_http:
            raise ValueError("KISAMORE_CLOUD_URL must use HTTPS")
        if len(device_id) > 80:
            raise ValueError("KISAMORE_DEVICE_ID must contain at most 80 characters")
        if len(device_token) < 32:
            raise ValueError("KISAMORE_DEVICE_TOKEN must contain at least 32 characters")

        interval = max(10, int(os.getenv("KISAMORE_CLOUD_INTERVAL_SECONDS", "30")))
        timeout = max(1.0, float(os.getenv("KISAMORE_CLOUD_TIMEOUT_SECONDS", "10")))
        growing_timeout = max(
            timeout,
            float(os.getenv("KISAMORE_GROWING_SYNC_TIMEOUT_SECONDS", "120")),
        )

        return cls(
            api_url=api_url,
            device_id=device_id,
            device_token=device_token,
            interval_seconds=interval,
            request_timeout_seconds=timeout,
            growing_sync_timeout_seconds=growing_timeout,
            software_version=os.getenv("KISAMORE_SOFTWARE_VERSION", "unknown").strip() or "unknown",
            mqtt_host=os.getenv("KISAMORE_MQTT_HOST", "").strip(),
            mqtt_port=int(os.getenv("KISAMORE_MQTT_PORT", "1883")),
            mqtt_username=os.getenv("KISAMORE_MQTT_USERNAME", "").strip(),
            mqtt_password=os.getenv("KISAMORE_MQTT_PASSWORD", "").strip(),
            mqtt_tls=os.getenv("KISAMORE_MQTT_TLS", "false").strip().lower()
            in ("1", "true", "yes", "on"),
            mqtt_topic_prefix=(
                os.getenv("KISAMORE_MQTT_TOPIC_PREFIX", "kisamore").strip().strip("/")
                or "kisamore"
            ),
            mqtt_chunk_bytes=max(
                256,
                min(1200, int(os.getenv("KISAMORE_MQTT_CHUNK_BYTES", "900"))),
            ),
        )

    @property
    def mqtt_enabled(self) -> bool:
        return bool(self.mqtt_host)


def _retry_delays(
    exc: Exception,
    *,
    interval_seconds: int,
    failure_delay: int,
) -> tuple[int, int]:
    """Return the next wait and backoff values after a failed send.

    A read timeout is special: the VPS can finish committing the snapshot after
    the Pi has stopped waiting for the response. Backing off in that situation
    makes otherwise accepted telemetry appear stale for several minutes.
    """
    if _is_timeout_error(exc):
        return interval_seconds, interval_seconds

    return failure_delay, min(failure_delay * 2, 300)


def _is_timeout_error(exc: Exception) -> bool:
    """Recognize request timeouts reported by the curl transport."""
    return isinstance(exc, TimeoutError)


def _remaining_delay(period_seconds: float, elapsed_seconds: float) -> float:
    """Keep attempts on their configured start-to-start cadence."""
    return max(0.0, period_seconds - elapsed_seconds)


class CloudSyncService:
    """Pushes a read-only snapshot from the Pi to the central API."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._send_lock = asyncio.Lock()
        self._settings: CloudSyncSettings | None = None
        self._uploaded_photo_mtimes: dict[int, int] = {}

    async def start(self) -> None:
        if self._task and not self._task.done():
            return

        try:
            self._settings = CloudSyncSettings.from_env()
        except (TypeError, ValueError) as exc:
            self._settings = None
            print(f"[cloud-sync] disabled: invalid cloud configuration: {exc}")
            return
        if self._settings is None:
            print("[cloud-sync] disabled: cloud URL, device ID or device token is not configured")
            return

        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="kisamore-cloud-sync")
        print(
            f"[cloud-sync] enabled: device={self._settings.device_id}, "
            f"interval={self._settings.interval_seconds}s"
        )
        if self._settings.mqtt_enabled:
            print(
                f"[cloud-sync] MQTT transport enabled: host={self._settings.mqtt_host}, "
                f"port={self._settings.mqtt_port}, chunk={self._settings.mqtt_chunk_bytes} bytes"
            )

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def collect_snapshot(self, *, include_growing: bool = False) -> dict[str, Any]:
        if self._settings is None:
            raise RuntimeError("cloud sync is not configured")

        racks: list[dict[str, Any]] = []
        plants: list[Plant] = []
        max_racks = runtime.cfg.racks_count if runtime.cfg else 0

        async with SessionLocal() as session:
            if include_growing:
                plants = (
                    await session.execute(select(Plant).order_by(Plant.code))
                ).scalars().all()
            slots = []
            if include_growing:
                slots = (
                    await session.execute(
                        select(RackSlot)
                        .where(RackSlot.rack_id <= max_racks)
                        .order_by(RackSlot.rack_id, RackSlot.slot_number)
                    )
                ).scalars().all()
            slot_ids = [slot.id for slot in slots]
            active_plantings = []
            if slot_ids:
                active_plantings = (
                    await session.execute(
                        select(Planting).where(
                            Planting.slot_id.in_(slot_ids),
                            Planting.status.in_(("planned", "growing", "ready")),
                        )
                    )
                ).scalars().all()
            planting_by_slot = {planting.slot_id: planting for planting in active_plantings}
            slots_by_rack: dict[int, list[dict[str, Any]]] = {}
            for slot in slots:
                planting = planting_by_slot.get(slot.id)
                planting_data = None
                if planting:
                    planting_data = {
                        "planting_id": planting.id,
                        "plant_id": planting.plant_id,
                        "planted_at": _as_utc_iso(planting.planted_at),
                        "expected_harvest_at": _as_utc_iso(planting.expected_harvest_at),
                        "actual_harvest_at": _as_utc_iso(planting.actual_harvest_at),
                        "status": planting.status,
                        "cloud_allocation_id": planting.cloud_allocation_id,
                    }
                slots_by_rack.setdefault(slot.rack_id, []).append(
                    {
                        "slot_number": slot.slot_number,
                        "status": slot.status,
                        "enabled": slot.enabled,
                        "cloud_allocation_id": slot.cloud_allocation_id,
                        "requested_plant_id": slot.requested_plant_id,
                        "planting": planting_data,
                    }
                )

            states = (
                await session.execute(select(RackState).order_by(RackState.rack_id))
            ).scalars().all()

            for state in states:
                if state.rack_id > max_racks:
                    continue

                latest_sensor = (
                    await session.execute(
                        select(RackSensorHistory)
                        .where(RackSensorHistory.rack_id == state.rack_id)
                        .order_by(RackSensorHistory.created_at.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()

                rack_cfg = runtime.cfg.racks.get(str(state.rack_id)) if runtime.cfg else None
                racks.append(
                    {
                        "rack_id": state.rack_id,
                        "light_on": bool(state.light_on),
                        "water_on": bool(state.water_on),
                        "light_mode": state.light_mode,
                        "water_mode": state.water_mode,
                        "soil_moisture": latest_sensor.soil_moisture if latest_sensor else None,
                        "soil_temperature": latest_sensor.soil_temperature if latest_sensor else None,
                        "sensor_observed_at": _as_utc_iso(
                            latest_sensor.created_at if latest_sensor else None
                        ),
                        "camera_id": rack_cfg.camera_id if rack_cfg else None,
                        "slots": slots_by_rack.get(state.rack_id, []),
                    }
                )

        levels: dict[str, bool] = {}
        if runtime.inputs:
            try:
                levels = await asyncio.to_thread(runtime.inputs.snapshot)
            except Exception as exc:
                print(f"[cloud-sync] cannot read level sensors: {exc}")

        return {
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "software_version": self._settings.software_version,
            "racks_count": max_racks,
            "levels": levels,
            "plants": [
                {
                    "plant_id": plant.id,
                    "code": plant.code,
                    "names": plant.names,
                    "descriptions": plant.descriptions,
                    "seed_image_name": plant.seed_image_name,
                    "microgreen_image_name": plant.microgreen_image_name,
                    "grow_days": plant.grow_days,
                    "active": plant.active,
                    "updated_at": _as_utc_iso(plant.updated_at),
                }
                for plant in plants
            ],
            "racks": racks,
        }

    def _send_snapshot_blocking(
        self,
        snapshot: dict[str, Any],
        timeout_seconds: float | None = None,
    ) -> None:
        assert self._settings is not None
        if self._settings.mqtt_enabled:
            self._publish_snapshot_mqtt(snapshot, timeout_seconds)
            return

        payload_path: str | None = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                prefix="kisamore-cloud-snapshot-",
                suffix=".json",
                delete=False,
            ) as payload_file:
                json.dump(
                    snapshot,
                    payload_file,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                payload_path = payload_file.name

            headers = (
                f"Authorization: Bearer {self._settings.device_token}\n"
                f"X-Device-ID: {self._settings.device_id}\n"
                "Content-Type: application/json\n"
                "Accept: application/json\n"
                "Connection: close\n"
            ).encode("utf-8")
            timeout = timeout_seconds or self._settings.request_timeout_seconds
            command = [
                "curl",
                "--http1.1",
                "--noproxy",
                "*",
                "--silent",
                "--show-error",
                "--request",
                "POST",
                "--connect-timeout",
                f"{min(timeout, 5.0):g}",
                "--max-time",
                f"{timeout:g}",
                "--header",
                "@-",
                "--data-binary",
                f"@{payload_path}",
                "--output",
                os.devnull,
                "--write-out",
                "%{http_code} uploaded=%{size_upload} connect=%{time_connect} "
                "tls=%{time_appconnect} first_byte=%{time_starttransfer} total=%{time_total}",
                f"{self._settings.api_url}/api/v1/edge/snapshot",
            ]

            try:
                result = subprocess.run(
                    command,
                    input=headers,
                    capture_output=True,
                    check=False,
                    timeout=timeout + 1.0,
                )
            except subprocess.TimeoutExpired as exc:
                raise TimeoutError("curl request timed out") from exc
            except FileNotFoundError as exc:
                raise RuntimeError("curl executable is not installed") from exc

            error_message = result.stderr.decode("utf-8", errors="replace").strip()
            transfer_info = result.stdout.decode("ascii", errors="replace").strip()
            if result.returncode == 28:
                raise TimeoutError(f"{error_message or 'curl request timed out'}; {transfer_info}")
            if result.returncode != 0:
                raise RuntimeError(
                    f"curl failed with exit code {result.returncode}: "
                    f"{error_message or 'unknown error'}"
                )

            status_code = transfer_info.split()[0] if transfer_info else ""
            if status_code != "202":
                raise RuntimeError(f"cloud API returned HTTP {status_code or 'unknown'}")
        finally:
            if payload_path is not None:
                try:
                    os.unlink(payload_path)
                except FileNotFoundError:
                    pass

    def _snapshot_payload_bytes(self, snapshot: dict[str, Any]) -> bytes:
        return json.dumps(
            snapshot,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

    def _mqtt_message_id(self, payload: bytes) -> str:
        nonce = f"{time.time_ns()}:{os.getpid()}".encode("ascii")
        return urlsafe_b64encode(hashlib.sha256(nonce + payload).digest()[:12]).decode("ascii").rstrip("=")

    def _publish_snapshot_mqtt(
        self,
        snapshot: dict[str, Any],
        timeout_seconds: float | None = None,
    ) -> None:
        assert self._settings is not None
        try:
            import paho.mqtt.client as mqtt
        except ImportError as exc:
            raise RuntimeError("paho-mqtt is not installed") from exc

        payload = self._snapshot_payload_bytes(snapshot)
        chunk_size = self._settings.mqtt_chunk_bytes
        chunks = [payload[index : index + chunk_size] for index in range(0, len(payload), chunk_size)]
        if not chunks:
            chunks = [b""]
        message_id = self._mqtt_message_id(payload)
        digest = hashlib.sha256(payload).hexdigest()
        base_topic = (
            f"{self._settings.mqtt_topic_prefix}/edge/"
            f"{self._settings.device_id}/snapshot/{message_id}"
        )
        # A snapshot may require many short connections. Keep a separate budget
        # for the complete transfer and for each individual message.
        timeout = timeout_seconds or self._settings.growing_sync_timeout_seconds
        deadline = time.monotonic() + timeout
        print(
            f"[cloud-sync] MQTT snapshot: bytes={len(payload)}, chunks={len(chunks)}, "
            f"connection=per-message, timeout={timeout:g}s"
        )

        def publish_message(topic: str, body: bytes, label: str) -> None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"MQTT snapshot timed out before {label}")
            message_timeout = min(self._settings.request_timeout_seconds, remaining)
            try:
                self._publish_mqtt_message(mqtt, topic, body, message_timeout)
            except TimeoutError as exc:
                raise TimeoutError(
                    f"MQTT publish timed out: {label}, bytes={len(body)}, "
                    f"message_timeout={message_timeout:g}s"
                ) from exc
            except (OSError, RuntimeError) as exc:
                raise RuntimeError(f"MQTT publish failed: {label}: {exc}") from exc

        for index, chunk in enumerate(chunks):
            publish_message(
                f"{base_topic}/chunk/{index}/{len(chunks)}",
                chunk,
                f"chunk={index + 1}/{len(chunks)}",
            )

        done_payload = json.dumps(
            {
                "sha256": digest,
                "bytes": len(payload),
                "chunks": len(chunks),
                "observed_at": snapshot.get("observed_at"),
            },
            separators=(",", ":"),
        ).encode("ascii")
        publish_message(f"{base_topic}/done", done_payload, "done")

    def _publish_mqtt_message(
        self, mqtt, topic: str, payload: bytes, timeout: float
    ) -> None:
        """Send one QoS 1 message over a fresh, short-lived TCP connection.

        The receiver groups chunks by the snapshot ID in the topic, so it does
        not require the publisher to keep one connection open for the snapshot.
        """
        assert self._settings is not None
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"kisamore-edge-{self._settings.device_id}",
            protocol=mqtt.MQTTv311,
            reconnect_on_failure=False,
        )
        if self._settings.mqtt_username:
            client.username_pw_set(
                self._settings.mqtt_username, self._settings.mqtt_password or None
            )
        if self._settings.mqtt_tls:
            client.tls_set()
        client.connect_timeout = timeout
        deadline = time.monotonic() + timeout
        loop_started = False
        try:
            client.connect(
                self._settings.mqtt_host, self._settings.mqtt_port,
                keepalive=max(15, int(timeout) + 5),
            )
            client.loop_start()
            loop_started = True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("MQTT connection timed out")
            info = client.publish(topic, payload, qos=1, retain=False)
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                raise RuntimeError(f"MQTT publish failed with code {info.rc}")
            info.wait_for_publish(timeout=remaining)
            if not info.is_published():
                raise TimeoutError("MQTT acknowledgement timed out")
        finally:
            # Disconnect before joining the thread, including on failed sends.
            try:
                client.disconnect()
            finally:
                if loop_started:
                    client.loop_stop()

    async def _send_snapshot(
        self,
        snapshot: dict[str, Any],
        timeout_seconds: float | None = None,
    ) -> None:
        await asyncio.to_thread(
            self._send_snapshot_blocking,
            snapshot,
            timeout_seconds,
        )

    async def sync_growing_now(self) -> dict[str, int]:
        """Synchronize the plant catalog and rack placement after a UI request."""
        if self._settings is None:
            raise RuntimeError("cloud sync is not configured")
        async with self._send_lock:
            snapshot = await self.collect_snapshot(include_growing=True)
            await self._send_snapshot(
                snapshot,
                self._settings.growing_sync_timeout_seconds,
            )
            assignments_count = await self._sync_assignments()
        plants_count = len(snapshot["plants"])
        slots_count = sum(len(rack["slots"]) for rack in snapshot["racks"])
        print(
            f"[cloud-sync] growing data sent manually: plants={plants_count}, "
            f"slots={slots_count}, assignments={assignments_count}"
        )
        return {
            "plants_count": plants_count,
            "slots_count": slots_count,
            "assignments_count": assignments_count,
        }

    def _fetch_assignments_blocking(self) -> dict[str, Any]:
        assert self._settings is not None
        output_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix="kisamore-cloud-assignments-", suffix=".json", delete=False
            ) as output_file:
                output_path = output_file.name
            headers = (
                f"Authorization: Bearer {self._settings.device_token}\n"
                f"X-Device-ID: {self._settings.device_id}\n"
                "Accept: application/json\n"
                "Connection: close\n"
            ).encode("utf-8")
            timeout = self._settings.request_timeout_seconds
            command = [
                "curl",
                "--http1.1",
                "--noproxy",
                "*",
                "--silent",
                "--show-error",
                "--request",
                "GET",
                "--connect-timeout",
                f"{min(timeout, 5.0):g}",
                "--max-time",
                f"{timeout:g}",
                "--header",
                "@-",
                "--output",
                output_path,
                "--write-out",
                "%{http_code}",
                f"{self._settings.api_url}/api/v1/edge/assignments",
            ]
            try:
                result = subprocess.run(
                    command,
                    input=headers,
                    capture_output=True,
                    check=False,
                    timeout=timeout + 1.0,
                )
            except subprocess.TimeoutExpired as exc:
                raise TimeoutError("curl request timed out") from exc
            if result.returncode == 28:
                raise TimeoutError(
                    result.stderr.decode("utf-8", errors="replace").strip()
                    or "curl request timed out"
                )
            if result.returncode != 0:
                raise RuntimeError(f"assignment request failed with curl code {result.returncode}")
            status_code = result.stdout.decode("ascii", errors="replace").strip()
            if status_code != "200":
                raise RuntimeError(f"cloud assignment API returned HTTP {status_code or 'unknown'}")
            with open(output_path, encoding="utf-8") as response_file:
                return json.load(response_file)
        finally:
            if output_path:
                try:
                    os.unlink(output_path)
                except FileNotFoundError:
                    pass

    async def _apply_assignments(self, payload: dict[str, Any]) -> None:
        assignments = payload.get("assignments")
        if not isinstance(assignments, list):
            raise ValueError("cloud assignment response is invalid")
        desired_by_slot: dict[tuple[int, int], dict[str, Any]] = {}
        for assignment in assignments:
            rack_id = int(assignment["rack_id"])
            if assignment.get("resource_type") == "rack":
                slot_numbers = range(1, 7)
            else:
                slot_numbers = (int(assignment["slot_number"]),)
            for slot_number in slot_numbers:
                desired_by_slot[(rack_id, slot_number)] = assignment

        async with SessionLocal() as session:
            slots = (await session.execute(select(RackSlot))).scalars().all()
            for slot in slots:
                desired = desired_by_slot.get((slot.rack_id, slot.slot_number))
                if desired:
                    slot.cloud_allocation_id = desired["allocation_id"]
                    slot.requested_plant_id = desired.get("plant_id")
                    if slot.status == "available":
                        slot.status = "reserved"
                elif slot.status == "reserved" and slot.cloud_allocation_id:
                    slot.cloud_allocation_id = None
                    slot.requested_plant_id = None
                    slot.status = "available"
            await session.commit()

    async def _sync_assignments(self) -> int:
        payload = await asyncio.to_thread(self._fetch_assignments_blocking)
        await self._apply_assignments(payload)
        return len(payload.get("assignments", []))

    def _send_photo_blocking(self, rack_id: int, path: Path, captured_at: str) -> None:
        assert self._settings is not None
        headers = (
            f"Authorization: Bearer {self._settings.device_token}\n"
            f"X-Device-ID: {self._settings.device_id}\n"
            "Accept: application/json\n"
            "Connection: close\n"
        ).encode("utf-8")
        timeout = self._settings.request_timeout_seconds
        command = [
            "curl",
            "--http1.1",
            "--noproxy",
            "*",
            "--silent",
            "--show-error",
            "--request",
            "POST",
            "--connect-timeout",
            f"{min(timeout, 5.0):g}",
            "--max-time",
            f"{timeout:g}",
            "--header",
            "@-",
            "--form",
            f"photo=@{path};type=image/jpeg",
            "--form",
            f"captured_at={captured_at}",
            "--output",
            os.devnull,
            "--write-out",
            "%{http_code}",
            f"{self._settings.api_url}/api/v1/edge/racks/{rack_id}/photo",
        ]
        try:
            result = subprocess.run(
                command,
                input=headers,
                capture_output=True,
                check=False,
                timeout=timeout + 1.0,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError("photo upload timed out") from exc
        if result.returncode == 28:
            raise TimeoutError(
                result.stderr.decode("utf-8", errors="replace").strip()
                or "photo upload timed out"
            )
        if result.returncode != 0:
            raise RuntimeError(f"photo upload failed with curl code {result.returncode}")
        status_code = result.stdout.decode("ascii", errors="replace").strip()
        if status_code != "201":
            raise RuntimeError(f"cloud photo API returned HTTP {status_code or 'unknown'}")

    async def _send_changed_photos(self) -> int:
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
            if self._uploaded_photo_mtimes.get(rack_id) == mtime_ns:
                continue
            captured_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
            await asyncio.to_thread(
                self._send_photo_blocking, rack_id, path, captured_at
            )
            self._uploaded_photo_mtimes[rack_id] = mtime_ns
            sent += 1
        return sent

    async def _run(self) -> None:
        assert self._settings is not None
        failure_delay = self._settings.interval_seconds

        while not self._stop_event.is_set():
            attempt_started_at = asyncio.get_running_loop().time()
            try:
                snapshot = await self.collect_snapshot(include_growing=True)
                async with self._send_lock:
                    try:
                        await self._send_snapshot(snapshot)
                    except (TimeoutError, RuntimeError) as exc:
                        print(
                            f"[cloud-sync] full snapshot failed; sending telemetry only: "
                            f"{type(exc).__name__}: {exc!r}"
                        )
                        snapshot = {
                            **snapshot,
                            "plants": [],
                            "racks": [{**rack, "slots": []} for rack in snapshot["racks"]],
                        }
                        await self._send_snapshot(snapshot)
                    assignments_count = 0
                    try:
                        assignments_count = await self._sync_assignments()
                    except Exception as exc:
                        print(
                            f"[cloud-sync] assignments failed (snapshot already accepted): "
                            f"{type(exc).__name__}: {exc!r}"
                        )
                photos_count = 0
                try:
                    photos_count = await self._send_changed_photos()
                except Exception as photo_exc:
                    print(
                        f"[cloud-sync] photo upload failed: "
                        f"{type(photo_exc).__name__}: {photo_exc!r}"
                    )
                failure_delay = self._settings.interval_seconds
                period = self._settings.interval_seconds
                elapsed = asyncio.get_running_loop().time() - attempt_started_at
                plants_count = len(snapshot["plants"])
                slots_count = sum(len(rack["slots"]) for rack in snapshot["racks"])
                print(
                    f"[cloud-sync] snapshot sent: racks={len(snapshot['racks'])}, "
                    f"plants={plants_count}, slots={slots_count}, "
                    f"assignments={assignments_count}, photos={photos_count}, "
                    f"elapsed={elapsed:.2f}s"
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                period, failure_delay = _retry_delays(
                    exc,
                    interval_seconds=self._settings.interval_seconds,
                    failure_delay=failure_delay,
                )
                elapsed = asyncio.get_running_loop().time() - attempt_started_at
                delay = _remaining_delay(period, elapsed)
                print(
                    f"[cloud-sync] send failed after {elapsed:.2f}s; "
                    f"retry in {delay:.2f}s: "
                    f"{type(exc).__name__}: {exc!r}"
                )
            else:
                delay = _remaining_delay(period, elapsed)

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass


cloud_sync_service = CloudSyncService()
