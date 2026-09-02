from __future__ import annotations

import asyncio
import json
import os
import subprocess
import tempfile
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
    software_version: str = "unknown"

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

        return cls(
            api_url=api_url,
            device_id=device_id,
            device_token=device_token,
            interval_seconds=interval,
            request_timeout_seconds=timeout,
            software_version=os.getenv("KISAMORE_SOFTWARE_VERSION", "unknown").strip() or "unknown",
        )


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

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def collect_snapshot(self) -> dict[str, Any]:
        if self._settings is None:
            raise RuntimeError("cloud sync is not configured")

        racks: list[dict[str, Any]] = []
        max_racks = runtime.cfg.racks_count if runtime.cfg else 0

        async with SessionLocal() as session:
            plants = (
                await session.execute(select(Plant).order_by(Plant.code))
            ).scalars().all()
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

    def _send_snapshot_blocking(self, snapshot: dict[str, Any]) -> None:
        assert self._settings is not None
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
                "--data-binary",
                f"@{payload_path}",
                "--output",
                os.devnull,
                "--write-out",
                "%{http_code}",
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
            if result.returncode == 28:
                raise TimeoutError(error_message or "curl request timed out")
            if result.returncode != 0:
                raise RuntimeError(
                    f"curl failed with exit code {result.returncode}: "
                    f"{error_message or 'unknown error'}"
                )

            status_code = result.stdout.decode("ascii", errors="replace").strip()
            if status_code != "202":
                raise RuntimeError(f"cloud API returned HTTP {status_code or 'unknown'}")
        finally:
            if payload_path is not None:
                try:
                    os.unlink(payload_path)
                except FileNotFoundError:
                    pass

    async def _send_snapshot(self, snapshot: dict[str, Any]) -> None:
        await asyncio.to_thread(self._send_snapshot_blocking, snapshot)

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
        if not runtime.cfg:
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
                snapshot = await self.collect_snapshot()
                await self._send_snapshot(snapshot)
                assignments_count = await self._sync_assignments()
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
                print(
                    f"[cloud-sync] snapshot sent: racks={len(snapshot['racks'])}, "
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
