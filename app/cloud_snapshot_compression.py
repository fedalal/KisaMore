from __future__ import annotations

import gzip


def install_snapshot_compression(service) -> None:
    """Gzip large MQTT snapshot payloads without changing HTTP transport.

    Facts are highly repetitive multilingual text, so compression keeps the
    one-time catalog delta small enough for the existing chunked MQTT link.
    The cloud consumer detects the standard gzip magic bytes automatically.
    """
    if getattr(service, "_snapshot_compression_installed", False):
        return

    original_payload_bytes = service._snapshot_payload_bytes

    def snapshot_payload_bytes(snapshot: dict) -> bytes:
        raw = original_payload_bytes(snapshot)
        if len(raw) < 4096:
            return raw
        compressed = gzip.compress(raw, compresslevel=6)
        if len(compressed) >= len(raw):
            return raw
        return compressed

    service._snapshot_payload_bytes = snapshot_payload_bytes
    service._snapshot_compression_installed = True
