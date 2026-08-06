from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select

from . import runtime
from .db import SessionLocal
from .models import RackSensorHistory, RackState


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
    if isinstance(exc, httpx.ReadTimeout):
        return interval_seconds, interval_seconds

    return failure_delay, min(failure_delay * 2, 300)


def _remaining_delay(period_seconds: float, elapsed_seconds: float) -> float:
    """Keep attempts on their configured start-to-start cadence."""
    return max(0.0, period_seconds - elapsed_seconds)


class CloudSyncService:
    """Pushes a read-only snapshot from the Pi to the central API."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._settings: CloudSyncSettings | None = None

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
            "racks": racks,
        }

    async def _send_snapshot(self, client: httpx.AsyncClient, snapshot: dict[str, Any]) -> None:
        assert self._settings is not None
        response = await client.post(
            f"{self._settings.api_url}/api/v1/edge/snapshot",
            headers={
                "Authorization": f"Bearer {self._settings.device_token}",
                "X-Device-ID": self._settings.device_id,
            },
            json=snapshot,
        )
        response.raise_for_status()

    async def _run(self) -> None:
        assert self._settings is not None
        failure_delay = self._settings.interval_seconds

        async with httpx.AsyncClient(timeout=self._settings.request_timeout_seconds) as client:
            while not self._stop_event.is_set():
                attempt_started_at = asyncio.get_running_loop().time()
                try:
                    snapshot = await self.collect_snapshot()
                    await self._send_snapshot(client, snapshot)
                    failure_delay = self._settings.interval_seconds
                    period = self._settings.interval_seconds
                    elapsed = asyncio.get_running_loop().time() - attempt_started_at
                    print(
                        f"[cloud-sync] snapshot sent: racks={len(snapshot['racks'])}, "
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
