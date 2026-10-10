"""Validate/save launcher settings and serialize management operations."""
import contextlib
import json
import os
from pathlib import Path

from .environment import PROJECT, LauncherError, is_packaged, user_data_directory

DEFAULT_SETTINGS = (user_data_directory() / 'launcher/settings.json' if is_packaged()
                    else PROJECT / "storage/launcher/settings.json")


def load_settings(path):
    root = user_data_directory() if is_packaged() else PROJECT / 'storage'
    defaults = {"storage_root": str(root / "pilot"), "port": 8000, "intranet": False,
                "backup_directory": str(root / "backups"), 'llm_enabled': False, 'vlm_enabled': True}
    if path.exists():
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise LauncherError("실행 설정을 읽지 못했습니다. 관리 메뉴에서 설정 파일을 확인하세요.") from exc
        if not isinstance(saved, dict) or set(saved) - set(defaults):
            raise LauncherError("실행 설정 항목을 확인하세요.")
        defaults.update(saved)
    if type(defaults["port"]) is not int or not 1024 <= defaults["port"] <= 65535 or type(defaults["intranet"]) is not bool:
        raise LauncherError("접속 포트는 1024~65535, 사내망 사용은 true/false로 지정하세요.")
    if any(type(defaults[key]) is not bool for key in ('llm_enabled', 'vlm_enabled')):
        raise LauncherError('AI 사용 설정은 true/false로 지정하세요.')
    for key in ("storage_root", "backup_directory"):
        if not isinstance(defaults[key], str) or not defaults[key].strip():
            raise LauncherError("자료·백업 폴더를 확인하세요.")
        candidate = Path(defaults[key])
        defaults[key] = str((PROJECT / candidate).resolve() if not candidate.is_absolute() else candidate.resolve())
    if Path(defaults["backup_directory"]).is_relative_to(Path(defaults["storage_root"])):
        raise LauncherError("백업 폴더는 업무 자료 폴더 밖으로 지정하세요.")
    return defaults


def save_settings(path, settings):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".pending")
    temporary.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


@contextlib.contextmanager
def launch_lock(directory):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "launcher.lock").open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise LauncherError("다른 실행·관리 작업이 진행 중입니다. 잠시 후 다시 실행하세요.") from exc
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def validate_pending(settings):
    if type(settings["port"]) is not int or not 1024 <= settings["port"] <= 65535:
        raise LauncherError("접속 포트는 1024~65535로 지정하세요.")
    for key in ("storage_root", "backup_directory"):
        candidate = Path(settings[key])
        settings[key] = str((PROJECT / candidate).resolve() if not candidate.is_absolute() else candidate.resolve())
    if Path(settings["backup_directory"]).is_relative_to(Path(settings["storage_root"])):
        raise LauncherError("백업 폴더는 업무 자료 폴더 밖으로 지정하세요.")
