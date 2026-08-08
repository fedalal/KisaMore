from __future__ import annotations

from urllib.parse import urlsplit

import pytest

from app.camera_live_stream_config import (
    CameraLiveStreamSettings,
    build_ffmpeg_command,
)


def test_live_stream_is_disabled_without_publish_url(monkeypatch):
    monkeypatch.delenv("KISAMORE_MEDIA_PUBLISH_URL", raising=False)

    assert CameraLiveStreamSettings.from_env() is None


def test_settings_build_authenticated_rack_url(monkeypatch):
    monkeypatch.setenv("KISAMORE_MEDIA_PUBLISH_URL", "rtsp://media.example.test:8554/")
    monkeypatch.setenv("KISAMORE_MEDIA_PUBLISH_USER", "edge user")
    monkeypatch.setenv("KISAMORE_MEDIA_PUBLISH_PASSWORD", "secret:/?#[]@")
    monkeypatch.setenv("KISAMORE_MEDIA_FARM_SLUG", "demo-farm")

    settings = CameraLiveStreamSettings.from_env()

    assert settings is not None
    publish_url = settings.rack_publish_url(3)
    parsed = urlsplit(publish_url)
    assert parsed.scheme == "rtsp"
    assert parsed.hostname == "media.example.test"
    assert parsed.port == 8554
    assert parsed.username == "edge%20user"
    assert parsed.password == "secret%3A%2F%3F%23%5B%5D%40"
    assert parsed.path == "/farm/demo-farm/rack_3"


def test_ffmpeg_command_uses_requested_1024_by_768_stream():
    settings = CameraLiveStreamSettings(
        publish_url="rtsp://media.example.test:8554",
        publish_user="edge",
        publish_password="a-strong-password",
        farm_slug="demo-farm",
    )

    command = build_ffmpeg_command(
        settings,
        rack_id=1,
        width=1024,
        height=768,
        fps=8,
        bitrate_kbps=1200,
        encoder="libx264",
    )

    assert command[command.index("-video_size") + 1] == "1024x768"
    assert command[command.index("-framerate") + 1] == "8"
    assert command[command.index("-b:v") + 1] == "1200k"
    assert command[command.index("-g") + 1] == "16"
    assert command[-1].endswith("/farm/demo-farm/rack_1")


def test_settings_reject_invalid_farm_slug(monkeypatch):
    monkeypatch.setenv("KISAMORE_MEDIA_PUBLISH_URL", "rtsp://media.example.test:8554")
    monkeypatch.setenv("KISAMORE_MEDIA_PUBLISH_USER", "edge")
    monkeypatch.setenv("KISAMORE_MEDIA_PUBLISH_PASSWORD", "a-strong-password")
    monkeypatch.setenv("KISAMORE_MEDIA_FARM_SLUG", "Bad Farm")

    with pytest.raises(ValueError, match="FARM_SLUG"):
        CameraLiveStreamSettings.from_env()
