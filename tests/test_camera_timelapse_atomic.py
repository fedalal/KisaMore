"""Regression: camera MP4 is atomically published on its mounted filesystem."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from subprocess import CalledProcessError
from cloud.app.camera_timelapse_service import (
    RENDER_VERSION, camera_battle_timelapse_path, generate_camera_battle_timelapse
)
t=datetime(2026,10,12,14,0,tzinfo=timezone.utc)
with TemporaryDirectory() as tmp:
    base=Path(tmp)
    frames=[]
    for i in range(12):
        folder=base/"archive"/"2026-10-12"
        folder.mkdir(parents=True,exist_ok=True)
        frame=folder/f"140000_{i*1000:06d}_sample.jpg"
        frame.write_bytes(b"pretend-jpg")
        frames.append(frame)
    def write_frame(source, dest, stamp):
        dest.write_bytes(b"pretend-frame")
    ffmpeg_calls=[]
    def successful(command, **kwargs):
        staging=Path(command[-1])
        assert staging.parent == camera_battle_timelapse_path(
            base, "battle-test", "camera_1", "24h"
        ).parent, "Rendered MP4 must be on target filesystem"
        assert staging.suffix == ".mp4"
        staging.write_bytes(b"valid-mp4-for-test")
        ffmpeg_calls.append(command)
    with patch("cloud.app.camera_timelapse_service.camera_archive_frames", return_value=frames), \
         patch("cloud.app.camera_timelapse_service._prepare_whole_rack_frame", side_effect=write_frame), \
         patch("cloud.app.camera_timelapse_service.subprocess.run", side_effect=successful):
        result=generate_camera_battle_timelapse(
            photo_dir=base,device_id="device",rack_id=1,camera_id="camera_1",
            is_primary=True,battle_id="battle-test",period="24h",start_at=t,end_at=t+timedelta(hours=1)
        )
    assert result.read_bytes()==b"valid-mp4-for-test"
    assert result.with_suffix(".version").read_text()==RENDER_VERSION
    assert len(ffmpeg_calls)==1
    assert not list(result.parent.glob(".24h-render-*.mp4"))
    def failing(command, **kwargs):
        Path(command[-1]).write_bytes(b"partial")
        raise CalledProcessError(1,command,stderr=b"test-failure")
    result.with_suffix(".version").unlink()
    with patch("cloud.app.camera_timelapse_service.camera_archive_frames", return_value=frames), \
         patch("cloud.app.camera_timelapse_service._prepare_whole_rack_frame", side_effect=write_frame), \
         patch("cloud.app.camera_timelapse_service.subprocess.run", side_effect=failing):
        try:
            generate_camera_battle_timelapse(
                photo_dir=base,device_id="device",rack_id=1,camera_id="camera_1",
                is_primary=True,battle_id="battle-test",period="24h",start_at=t,end_at=t+timedelta(hours=1)
            )
        except RuntimeError:
            pass
        else:
            raise AssertionError("Must fail on ffmpeg error")
    assert result.read_bytes()==b"valid-mp4-for-test", "Existing video must survive failed rebuild"
    assert not list(result.parent.glob(".24h-render-*.mp4")), "Temporary MP4 must be removed"
print("PASS: same-filesystem atomic MP4 output, no partial file on failure")
