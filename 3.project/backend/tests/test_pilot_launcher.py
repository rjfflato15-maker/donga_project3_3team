"""Launcher safety checks use disposable folders and mocked server identities."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backend import pilot_launcher as launcher


@pytest.fixture
def settings(tmp_path):
    return {"storage_root": str(tmp_path / "data"), "port": 18765, "intranet": False,
            "backup_directory": str(tmp_path / "backups")}


def state_for(settings):
    return {**settings, "identity": {"pid": 42, "created": 123, "image": "python.exe"}, "instance": "owned-instance"}


@pytest.mark.parametrize("change", [{"port": True}, {"port": 80}, {"intranet": "false"}, {"password": "must-not-store"}])
def test_invalid_settings_rejected(tmp_path, change):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(change), encoding="utf-8")
    with pytest.raises(launcher.LauncherError):
        launcher.load_settings(path)


def test_settings_roundtrip_and_nested_backup_rejected(tmp_path, settings):
    path = tmp_path / "settings.json"
    launcher.save_settings(path, settings)
    assert launcher.load_settings(path) == settings
    settings["backup_directory"] = str(Path(settings["storage_root"]) / "backups")
    with pytest.raises(launcher.LauncherError):
        launcher.validate_pending(settings)


def test_launch_lock_excludes_concurrent_action_and_releases(tmp_path):
    with launcher.launch_lock(tmp_path):
        with pytest.raises(launcher.LauncherError):
            with launcher.launch_lock(tmp_path):
                pytest.fail("concurrent action acquired the lock")
    with pytest.raises(RuntimeError):
        with launcher.launch_lock(tmp_path):
            raise RuntimeError("abort")
    with launcher.launch_lock(tmp_path):
        pass


def test_owned_ready_server_reused_without_second_process(tmp_path, settings, monkeypatch):
    state = state_for(settings)
    monkeypatch.setattr(launcher, "owned_state", lambda _: state)
    monkeypatch.setattr(launcher, "health", lambda _: {"status": "ok", "service": launcher.SERVICE,
        "launcher_instance": state["instance"], "launcher_pid": state["identity"]["pid"]})
    popen = Mock()
    monkeypatch.setattr(launcher.subprocess, "Popen", popen)
    assert launcher.start(settings, tmp_path / "server.json", open_browser=False) == "reused"
    popen.assert_not_called()


def test_foreign_health_identity_not_reused(tmp_path, settings, monkeypatch):
    monkeypatch.setattr(launcher, "owned_state", lambda _: state_for(settings))
    monkeypatch.setattr(launcher, "health", lambda _: {"status": "ok", "service": launcher.SERVICE,
        "launcher_instance": "another-server", "launcher_pid": 42})
    popen = Mock()
    monkeypatch.setattr(launcher.subprocess, "Popen", popen)
    with pytest.raises(launcher.LauncherError):
        launcher.start(settings, tmp_path / "server.json", open_browser=False)
    popen.assert_not_called()


def test_stop_never_terminates_reused_pid(tmp_path, settings, monkeypatch):
    path = tmp_path / "server.json"
    state = state_for(settings)
    path.write_text(json.dumps(state), encoding="utf-8")
    kernel = SimpleNamespace(TerminateProcess=Mock(), CloseHandle=Mock())
    foreign = {**state["identity"], "created": 999}
    monkeypatch.setattr(launcher, "process_identity", lambda *a, **kw: (foreign, "held-handle", kernel))
    with pytest.raises(launcher.LauncherError):
        launcher.stop(path)
    kernel.TerminateProcess.assert_not_called()
    kernel.CloseHandle.assert_called_once_with("held-handle")
    assert path.exists()


def test_foreign_occupied_port_not_started(tmp_path, settings, monkeypatch):
    root = Path(settings["storage_root"])
    root.mkdir()
    (root / "pilot.db").touch()
    monkeypatch.setattr(launcher, "owned_state", lambda _: None)
    monkeypatch.setattr(launcher, "check_runtime", lambda: None)
    monkeypatch.setattr(launcher, "port_available", lambda _: False)
    popen = Mock()
    monkeypatch.setattr(launcher.subprocess, "Popen", popen)
    with pytest.raises(launcher.LauncherError):
        launcher.start(settings, tmp_path / "server.json", open_browser=False)
    popen.assert_not_called()


def test_failed_restore_keeps_active_settings(tmp_path, settings, monkeypatch):
    path = tmp_path / "settings.json"
    launcher.save_settings(path, settings)
    monkeypatch.setattr(launcher, "require_stopped", lambda _: None)
    monkeypatch.setattr(launcher, "check_runtime", lambda: None)
    monkeypatch.setattr(launcher, "manager", Mock(side_effect=launcher.LauncherError("bad archive")))
    with pytest.raises(launcher.LauncherError):
        launcher.restore(settings, path, tmp_path / "server.json", tmp_path / "invalid.zip", tmp_path / "restored")
    assert launcher.load_settings(path) == settings


def test_restore_cannot_make_backup_inside_new_storage(tmp_path, settings, monkeypatch):
    settings["backup_directory"] = str(tmp_path / "restored" / "backup")
    monkeypatch.setattr(launcher, "require_stopped", lambda _: None)
    monkeypatch.setattr(launcher, "check_runtime", lambda: None)
    manager = Mock()
    monkeypatch.setattr(launcher, "manager", manager)
    with pytest.raises(launcher.LauncherError):
        launcher.restore(settings, tmp_path / "settings.json", tmp_path / "server.json", tmp_path / "x.zip", tmp_path / "restored")
    manager.assert_not_called()


def test_existing_database_cannot_be_initialized_again(tmp_path, settings, monkeypatch):
    root = Path(settings["storage_root"])
    root.mkdir()
    (root / "pilot.db").write_bytes(b"keep")
    monkeypatch.setattr(launcher, "require_stopped", lambda _: None)
    monkeypatch.setattr(launcher, "check_runtime", lambda: None)
    manager = Mock()
    monkeypatch.setattr(launcher, "manager", manager)
    with pytest.raises(launcher.LauncherError):
        launcher.initialize(settings, tmp_path / "server.json", empty=True)
    manager.assert_not_called()
    assert (root / "pilot.db").read_bytes() == b"keep"


def test_dependency_failure_stops_preparation(tmp_path, monkeypatch):
    python = tmp_path / "python.exe"
    python.touch()
    monkeypatch.setattr(launcher, "python_path", lambda: python)
    monkeypatch.setattr(launcher.shutil, "which", lambda name: str(tmp_path / name))
    run = Mock(side_effect=launcher.LauncherError("pip failed"))
    monkeypatch.setattr(launcher, "run_checked", run)
    with pytest.raises(launcher.LauncherError):
        launcher.prepare_environment()
    assert run.call_count == 1
    assert "pip" in run.call_args.args[0]


def test_pilot_environment_keeps_cloud_and_llm_off(settings, monkeypatch):
    monkeypatch.setenv("APP_LLM_ENABLED", "true")
    monkeypatch.setenv("APP_NTS_MODE", "real")
    env = launcher.pilot_environment(settings)
    assert env["APP_DEPLOYMENT_MODE"] == "pilot"
    assert env["APP_STORAGE_ROOT"] == settings["storage_root"]
    assert env["APP_NTS_MODE"] == "disabled"
    assert env["APP_LLM_ENABLED"] == "false"


def test_health_identity_never_exposes_data_location(monkeypatch):
    from backend.app.main import health_check
    monkeypatch.setenv("APP_LAUNCHER_INSTANCE", "opaque-value")
    reply = health_check()
    assert reply["launcher_instance"] == "opaque-value"
    assert type(reply["launcher_pid"]) is int
    assert set(reply) == {"status", "service", "version", "launcher_instance", "launcher_pid"}
