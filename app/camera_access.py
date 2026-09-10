from __future__ import annotations

import threading


_locks_guard = threading.Lock()
_device_locks: dict[str, threading.RLock] = {}


def device_access_lock(device: str) -> threading.RLock:
    """Return a stable per-device lock shared by live video and one-shot capture."""
    key = str(device or "").strip()
    with _locks_guard:
        lock = _device_locks.get(key)
        if lock is None:
            lock = threading.RLock()
            _device_locks[key] = lock
        return lock
