from unittest.mock import patch

from fastapi_calf.autostart import ensure_collector


def test_existing_collector_is_reused():
    with (
        patch("fastapi_calf.autostart.collector_is_running", return_value=True),
        patch("fastapi_calf.autostart._spawn_collector") as spawn,
    ):
        assert ensure_collector("127.0.0.1", 8765) is True
    spawn.assert_not_called()


def test_missing_local_collector_is_started_once(tmp_path):
    with (
        patch("fastapi_calf.autostart.tempfile.gettempdir", return_value=str(tmp_path)),
        patch("fastapi_calf.autostart.collector_is_running", return_value=False),
        patch("fastapi_calf.autostart._spawn_collector") as spawn,
        patch("fastapi_calf.autostart._wait_for_collector", return_value=True),
    ):
        assert ensure_collector("127.0.0.1", 9876) is True
    spawn.assert_called_once_with("127.0.0.1", 9876)


def test_remote_collector_is_never_spawned():
    with (
        patch("fastapi_calf.autostart.collector_is_running", return_value=False),
        patch("fastapi_calf.autostart._spawn_collector") as spawn,
    ):
        assert ensure_collector("collector.internal", 8765) is False
    spawn.assert_not_called()
