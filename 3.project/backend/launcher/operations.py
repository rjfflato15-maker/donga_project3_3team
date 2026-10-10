"""Prepare the environment and delegate data operations to manage_pilot."""
import os
from pathlib import Path
import shutil
import sys

from .environment import PROJECT, LauncherError, check_runtime, pilot_environment, python_path, run_checked, is_packaged
from .server import require_stopped
from .settings import save_settings, validate_pending


def prepare_environment():
    if is_packaged():
        check_runtime()
        return
    node = shutil.which("node")
    if not node:
        raise LauncherError("최초 환경 준비에는 Node.js 설치가 필요합니다. 설치 후 다시 실행하세요.")
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not npm:
        raise LauncherError("npm을 찾지 못했습니다. Node.js 설치 상태를 확인하세요.")
    if not python_path().exists():
        run_checked([sys.executable, "-m", "venv", PROJECT / "backend/.venv"])
    run_checked([python_path(), "-m", "pip", "install", "-r", PROJECT / "backend/requirements.txt"])
    run_checked([npm, "ci"], cwd=PROJECT / "frontend")
    run_checked([npm, "run", "build"], cwd=PROJECT / "frontend")
    check_runtime()


def manager(settings, *args):
    run_checked([python_path(), PROJECT / "backend/manage_pilot.py", *args], env=pilot_environment(settings))


def initialize(settings, state_path, *, empty=False):
    require_stopped(state_path)
    check_runtime()
    if (Path(settings["storage_root"]) / "pilot.db").exists():
        raise LauncherError("업무함이 이미 있습니다. 기존 자료는 그대로 사용하세요.")
    manager(settings, "migrate", *(["--empty"] if empty else []))


def backup(settings):
    check_runtime()
    target = Path(settings["backup_directory"])
    target.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    archive = target / ("C-pilot-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".zip")
    manager(settings, "backup", "--output", str(archive))
    return archive


def restore(settings, settings_path, state_path, archive, destination):
    require_stopped(state_path)
    check_runtime()
    destination = Path(destination).resolve()
    if destination.exists():
        raise LauncherError("복원은 아직 존재하지 않는 새 폴더에만 가능합니다.")
    new_settings = dict(settings, storage_root=str(destination))
    validate_pending(new_settings)
    manager(settings, "restore", "--archive", str(Path(archive).resolve()), "--destination", str(destination))
    save_settings(settings_path, new_settings)
