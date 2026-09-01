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


def test_camera_control_value_is_clamped_to_reported_range():
    worker = CameraWorker("/dev/video-test")
    worker._supported_controls_cache = {"focus_absolute"}
    worker._control_ranges_cache = {"focus_absolute": (0, 255, 5)}

    assert worker._normalize_control_value("focus_absolute", 512) == 130
    assert worker._normalize_control_value("focus_absolute", 100) == 25


def test_warp_points_are_normalized_after_a_vertical_flip():
    points = [600, 450, 20, 20, 600, 20, 20, 450]

    ordered = CameraWorker._order_warp_points(points).tolist()

    assert ordered == [
        [20.0, 20.0],
        [600.0, 20.0],
        [600.0, 450.0],
        [20.0, 450.0],
    ]
