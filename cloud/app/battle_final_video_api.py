"""A permanent, per-plant final turntable video for completed Plant Battles.

Stored in the existing shared kisamore-photos Docker volume. Original QR
certificate URLs remain unchanged. No database schema migration is needed.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
from pathlib import Path
from uuid import uuid4, UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .battle_models import PlantBattle, PlantBattleEntry
from .config import get_settings
from .models import User
from .security import get_admin_user, get_session

router = APIRouter(prefix="/api/v1", tags=["battle-final-videos"])
MAX_FINAL_VIDEO_BYTES = 45 * 1024 * 1024
MAX_DURATION_SECONDS = 300


def final_video_path(entry_id: str) -> Path:
    """No path traversal: use exactly one UUID path component."""
    try:
        safe_id = str(UUID(str(entry_id)))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(404, "Unknown participant")
    return Path(get_settings().photo_dir) / "battle-final-videos" / f"{safe_id}.mp4"


def final_video_exists(entry_id: str) -> bool:
    path = final_video_path(entry_id)
    return path.is_file() and path.stat().st_size > 0


def _validate_video(path: Path) -> None:
    """Check actual media rather than trusting an MP4 filename or Content-Type."""
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration:stream=codec_type,codec_name", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=15, check=True,
        )
        data = json.loads(proc.stdout)
    except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError) as err:
        raise HTTPException(422, "Invalid video. Upload an H.264 MP4 file") from err
    streams = data.get("streams") or []
    if not any(s.get("codec_type") == "video" and s.get("codec_name") == "h264" for s in streams):
        raise HTTPException(422, "Video must be MP4 with H.264 encoding")
    duration = float(data.get("format", {}).get("duration") or 0)
    if duration < 1 or duration > MAX_DURATION_SECONDS:
        raise HTTPException(422, "Video duration must be 1–300 seconds")


async def _entry_in_battle(session: AsyncSession, battle_id: str, entry_id: str,
                           *, lock: bool = False):
    stmt = select(PlantBattle).where(PlantBattle.id == battle_id)
    if lock:
        stmt = stmt.with_for_update()
    battle = (await session.execute(stmt)).scalar_one_or_none()
    if battle is None:
        raise HTTPException(404, "Battle not found")
    entry = (await session.execute(
        select(PlantBattleEntry).where(
            PlantBattleEntry.id == entry_id,
            PlantBattleEntry.battle_id == battle_id,
            PlantBattleEntry.status.in_(("active", "finished")),
        )
    )).scalar_one_or_none()
    if entry is None:
        raise HTTPException(404, "Active participant not found")
    return battle, entry


@router.post("/admin/battles/{battle_id}/entries/{entry_id}/final-video")
async def upload_final_video(
    battle_id: str,
    entry_id: str,
    video: UploadFile = File(...),
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    battle, entry = await _entry_in_battle(session, battle_id, entry_id, lock=True)
    if battle.status not in ("growing", "judging", "planting"):
        raise HTTPException(409, "Final videos can be uploaded only before winner selection")
    if not video.filename or Path(video.filename).suffix.lower() != ".mp4":
        raise HTTPException(422, "Upload a .mp4 file (H.264)")
    dest = final_video_path(entry.id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    # A distinct temporary name avoids overwriting a previously accepted
    # video on invalid/rejected uploads.
    temporary = dest.parent / f".{entry.id}.{uuid4().hex}.upload"
    written = 0
    try:
        with temporary.open("xb") as fh:
            while data := await video.read(1024 * 1024):
                written += len(data)
                if written > MAX_FINAL_VIDEO_BYTES:
                    raise HTTPException(413, "Video is too large (maximum 45 MB)")
                fh.write(data)
        if not written:
            raise HTTPException(422, "Empty video")
        await asyncio.to_thread(_validate_video, temporary)
        os.replace(temporary, dest)
        return {
            "ok": True, "entry_id": entry.id, "slot_number": entry.slot_number,
            "size_bytes": written, "final_video_ready": True,
            "final_video_url": f"/api/v1/public/battle-entries/{entry.id}/final-video",
        }
    finally:
        await video.close()
        temporary.unlink(missing_ok=True)


@router.delete("/admin/battles/{battle_id}/entries/{entry_id}/final-video")
async def delete_final_video(
    battle_id: str,
    entry_id: str,
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    battle, entry = await _entry_in_battle(session, battle_id, entry_id, lock=True)
    if battle.status not in ("growing", "judging", "planting"):
        raise HTTPException(409, "Cannot remove a final video after the battle is finished")
    final_video_path(entry.id).unlink(missing_ok=True)
    return {"ok": True, "final_video_ready": False}


@router.get("/admin/battles/{battle_id}/entries/{entry_id}/final-video")
async def admin_final_video(
    battle_id: str,
    entry_id: str,
    _: User = Depends(get_admin_user),
    session: AsyncSession = Depends(get_session),
):
    _battle, entry = await _entry_in_battle(session, battle_id, entry_id)
    if not final_video_exists(entry.id):
        raise HTTPException(404, "Final video not uploaded")
    return FileResponse(final_video_path(entry.id), media_type="video/mp4",
                        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/public/battle-entries/{entry_id}/final-video")
async def public_final_video(
    entry_id: str,
    session: AsyncSession = Depends(get_session),
):
    # Preserve the same post-finish access rule as QR certificates.
    from .battle_api import _certificate_context
    entry, _battle, _plant, _user = await _certificate_context(session, entry_id)
    path = final_video_path(entry.id)
    if not final_video_exists(entry.id):
        raise HTTPException(404, "Final video not uploaded")
    return FileResponse(
        path, media_type="video/mp4",
        headers={"Cache-Control": "public, max-age=86400", "X-Content-Type-Options": "nosniff"},
    )
