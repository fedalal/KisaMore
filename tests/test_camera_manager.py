import importlib.util
import sys
from types import SimpleNamespace


# CI tests the synchronization logic without opening a real camera. OpenCV is
# installed by the Raspberry Pi system image rather than requirements.txt.
if importlib.util.find_spec("cv2") is None:
    sys.modules["cv2"] = SimpleNamespace()

from app.camera_manager import CameraManager, CameraWorker


def test_update_settings_is_deferred_to_camera_worker():
    worker = CameraWorker("/dev/video-test")
    direct_calls = []
    worker.restart = lambda: direct_calls.append("restart")
    worker._apply_camera_controls = lambda: direct_calls.append("controls")

    worker.update_settings(
        frame_width=640,
        frame_height=480,
        autofocus_enabled=False,
        focus_absolute=100,
        white_balance_auto=False,
        white_balance_temperature=4500,
    )

    assert worker.reconfigure_event.is_set()
    assert direct_calls == []


def test_get_error_does_not_create_or_reconfigure_worker():
    manager = CameraManager()

    assert manager.get_error("/dev/video-missing") is None
    assert manager.workers == {}

    worker = CameraWorker("/dev/video-rack-1")
    worker.frame.last_error = "camera error"
    manager.workers[worker.device] = worker

    assert manager.get_error(worker.device) == "camera error"
    assert manager.workers == {worker.device: worker}


def test_camera_control_aliases_are_selected_only_when_supported():
    worker = CameraWorker("/dev/video-test")
    worker._supported_controls_cache = {
        "focus_auto",
        "focus_absolute",
        "white_balance_temperature_auto",
        "white_balance_temperature",
    }

    assert worker._find_control("focus_automatic_continuous", "focus_auto") == "focus_auto"
    assert (
        worker._find_control("white_balance_automatic", "white_balance_temperature_auto")
        == "white_balance_temperature_auto"
    )
    assert worker._find_control("unsupported") is None
