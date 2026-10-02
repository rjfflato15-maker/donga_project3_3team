"""One local entry point for the existing pilot app. No business/UI/AI changes."""
import argparse
import contextlib
import ctypes
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser

PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_SETTINGS = PROJECT / "storage/launcher/settings.json"
SERVICE = "AI Contract Evidence Manager"


class LauncherError(Exception):
    pass


def load_settings(path):
    defaults = {"storage_root": str(PROJECT / "storage/pilot"), "port": 8000, "intranet": False,
                "backup_directory": str(PROJECT / "storage/backups")}
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


def python_path():
    return PROJECT / "backend/.venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def pilot_environment(settings):
    env = dict(os.environ)
    env.update(APP_DEPLOYMENT_MODE="pilot", APP_STORAGE_ROOT=settings["storage_root"], APP_NTS_MODE="disabled",
               APP_LLM_ENABLED="false", APP_COOKIE_SECURE="false", PYTHONIOENCODING="utf-8")
    # HTTPS is an IT deployment step. The simple launcher serves local HTTP.
    env["APP_ALLOWED_ORIGINS"] = f"http://127.0.0.1:{settings['port']},http://localhost:{settings['port']}"
    return env


def run_checked(args, *, cwd=PROJECT, env=None):
    result = subprocess.run([str(a) for a in args], cwd=cwd, env=env, check=False)
    if result.returncode:
        raise LauncherError("작업이 실패했습니다. 위의 오류를 확인한 뒤 다시 실행하세요.")


def check_runtime():
    python = python_path()
    if not python.is_file():
        raise LauncherError("최초 환경 준비가 필요합니다. 관리 메뉴의 '환경 준비'를 실행하세요.")
    modules = ("uvicorn", "fastapi", "sqlalchemy", "dotenv", "multipart", "pypdf", "PIL", "pypdfium2", "docx", "requests")
    code = "import importlib.util,sys; sys.exit(any(importlib.util.find_spec(m) is None for m in " + repr(modules) + "))"
    result = subprocess.run([str(python), "-c", code], capture_output=True, cwd=PROJECT)
    if result.returncode:
        raise LauncherError("필수 실행 모듈이 부족합니다. 관리 메뉴의 '환경 준비'를 실행하세요.")
    if not (PROJECT / "frontend/dist/index.html").is_file():
        raise LauncherError("앱 화면 빌드가 없습니다. 관리 메뉴의 '환경 준비'를 실행하세요.")


def process_identity(pid, terminate=False):
    """Hold a Windows process handle and verify creation time/image before stop."""
    if os.name != "nt":
        raise LauncherError("이 실행기는 Windows 환경에서 사용하세요.")
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel.GetProcessTimes.argtypes = (wintypes.HANDLE,) + (ctypes.POINTER(wintypes.FILETIME),) * 4
    kernel.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
    kernel.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT)
    handle = kernel.OpenProcess(0x1000 | (0x0001 if terminate else 0), False, pid)
    if not handle:
        return None
    keep_handle = False
    try:
        exit_code = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code)) or exit_code.value != 259:
            return None
        times = [wintypes.FILETIME() for _ in range(4)]
        buffer, size = ctypes.create_unicode_buffer(32768), wintypes.DWORD(32768)
        if not kernel.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)) or not kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            raise LauncherError("실행 중인 서버의 소유 정보를 확인하지 못했습니다.")
        identity = {"pid": pid, "created": (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime,
                    "image": str(Path(buffer.value).resolve())}
        if terminate:
            # Caller supplies the stored identity; compare using this same handle.
            keep_handle = True
            return identity, handle, kernel
        return identity
    finally:
        if not keep_handle:
            kernel.CloseHandle(handle)


def read_state(path):
    try:
        if not path.exists():
            return None
        state = json.loads(path.read_text(encoding="utf-8"))
        identity = state["identity"]
        if (set(identity) != {"pid", "created", "image"} or type(identity["pid"]) is not int or identity["pid"] <= 0
                or type(identity["created"]) is not int or not isinstance(identity["image"], str)
                or not isinstance(state["instance"], str)):
            raise ValueError("invalid identity")
        return state
    except (ValueError, OSError, KeyError, TypeError) as exc:
        raise LauncherError("서버 실행 기록이 손상되었습니다. 자동으로 새 서버를 실행하지 않습니다.") from exc


def owned_state(path):
    state = read_state(path)
    if not state:
        return None
    identity = process_identity(state["identity"]["pid"])
    if identity is None or identity != state["identity"]:
        return None  # stale PID, never stop/reuse an unrelated process
    return state


def health(port):
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(f"http://127.0.0.1:{port}/health", timeout=0.5) as response:
            result = json.loads(response.read(8192))
            return result if isinstance(result, dict) else None
    except (OSError, ValueError):
        return None


def ready_for(state, settings):
    reply = health(settings["port"])
    return bool(state["storage_root"] == settings["storage_root"] and state["port"] == settings["port"]
                and state["intranet"] == settings["intranet"] and reply and reply.get("status") == "ok"
                and reply.get("service") == SERVICE and reply.get("launcher_instance") == state["instance"]
                and reply.get("launcher_pid") == state["identity"]["pid"])


def port_available(port):
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def require_stopped(state_path):
    if owned_state(state_path):
        raise LauncherError("설정·복원 작업 전에 관리 메뉴에서 서버를 종료하세요.")


def start(settings, state_path, *, open_browser=True):
    state = owned_state(state_path)
    if state:
        if not ready_for(state, settings):
            raise LauncherError("기존 서버의 응답 또는 설정을 확인하세요. 중복 서버는 실행하지 않습니다.")
        if open_browser:
            webbrowser.open(f"http://127.0.0.1:{settings['port']}/")
        return "reused"
    check_runtime()
    if not (Path(settings["storage_root"]) / "pilot.db").is_file():
        raise LauncherError("처음 사용할 업무함이 필요합니다. 관리 메뉴에서 '업무함 준비'를 선택하세요.")
    if not port_available(settings["port"]):
        raise LauncherError("접속 포트를 다른 프로그램이 사용 중입니다. 기존 프로그램을 확인하거나 관리 메뉴에서 포트를 변경하세요.")
    instance = secrets.token_hex(16)
    env = pilot_environment(settings)
    env["APP_LAUNCHER_INSTANCE"] = instance
    log_path = state_path.parent / "server.log"
    with log_path.open("ab") as log:
        child = subprocess.Popen([str(python_path()), "-m", "uvicorn", "backend.app.main:app", "--host",
            "0.0.0.0" if settings["intranet"] else "127.0.0.1", "--port", str(settings["port"]),
            "--workers", "1", "--no-access-log"], cwd=PROJECT, env=env, stdin=subprocess.DEVNULL,
            stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and child.poll() is None:
        reply = health(settings["port"])
        if (reply and reply.get("status") == "ok" and reply.get("launcher_instance") == instance
                and reply.get("service") == SERVICE and type(reply.get("launcher_pid")) is int and reply["launcher_pid"] > 0):
            identity = process_identity(reply["launcher_pid"])
            if identity:
                state = {"identity": identity, "instance": instance, **settings}
                state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                if open_browser:
                    webbrowser.open(f"http://127.0.0.1:{settings['port']}/")
                return "started"
        time.sleep(0.2)
    if child.poll() is None:
        child.terminate()
        child.wait(timeout=10)
    raise LauncherError("서버 준비를 완료하지 못했습니다. 관리 메뉴의 상태 점검과 서버 로그를 확인하세요.")


def stop(state_path):
    state = read_state(state_path)
    if not state:
        return "not_running"
    result = process_identity(state["identity"]["pid"], terminate=True)
    if result is None:
        state_path.unlink(missing_ok=True)
        return "not_running"
    identity, handle, kernel = result
    try:
        if identity != state["identity"]:
            raise LauncherError("기록된 서버와 다른 프로세스입니다. 종료하지 않았습니다.")
        if not kernel.TerminateProcess(handle, 0):
            raise LauncherError("서버를 종료하지 못했습니다.")
    finally:
        kernel.CloseHandle(handle)
    state_path.unlink(missing_ok=True)
    return "stopped"


def prepare_environment():
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


def status(settings, state_path):
    state = owned_state(state_path)
    return {"runtime_ready": python_path().is_file(), "frontend_ready": (PROJECT / "frontend/dist/index.html").is_file(),
            "database_ready": (Path(settings["storage_root"]) / "pilot.db").is_file(),
            "server_running": bool(state), "server_ready": bool(state and ready_for(state, settings)),
            "port": settings["port"], "intranet": settings["intranet"], "llm_enabled": False}


def manage_menu(settings_path, state_path):
    while True:
        settings = load_settings(settings_path)
        print("\n계약 검수 관리: 1 실행  2 상태 점검  3 최초 환경 준비  4 업무함 준비")
        print("5 실행 설정  6 지금 백업  7 새 폴더에 복원  8 자동 실행·백업  9 서버 종료  0 닫기")
        choice = input("번호: ").strip()
        if choice == "0":
            return 0
        try:
            with launch_lock(settings_path.parent):
                if choice == "1":
                    start(settings, state_path)
                    print("앱 연결 준비 완료. 브라우저에서 로그인하세요.")
                elif choice == "2":
                    details = status(settings, state_path)
                    for key, label in (("runtime_ready", "Python 환경"), ("frontend_ready", "앱 화면"), ("database_ready", "업무함")):
                        print(label + ": " + ("준비됨" if details[key] else "준비 필요"))
                    print("서버: " + ("접속 가능" if details["server_ready"] else "응답 점검 필요" if details["server_running"] else "꺼짐"))
                    print(f"현재 PC 접속: http://127.0.0.1:{settings['port']}/")
                    print("다른 사내 PC 접속: " + ("허용" if settings["intranet"] else "꺼짐") + " / AI 보완: 꺼짐")
                    print("계정·회사·필수서류 설정은 로그인 후 앱의 '업무 설정 · 계정'에서 관리합니다.")
                    print("서버 로그: " + str(settings_path.parent / "server.log"))
                elif choice == "3":
                    require_stopped(state_path)
                    if input("필수 프로그램을 다운로드하고 앱을 준비합니다. 진행하려면 '준비': ").strip() == "준비":
                        prepare_environment()
                        print("환경 준비 완료")
                elif choice == "4":
                    answer = input("1 기존 자료 가져오기 / 2 빈 업무함 만들기 / 그 외 취소: ").strip()
                    if answer in {"1", "2"}:
                        initialize(settings, state_path, empty=answer == "2")
                        print("초기 계정 안내: " + str(Path(settings["storage_root"]) / "initial-accounts.txt"))
                elif choice == "5":
                    require_stopped(state_path)
                    port = input(f"접속 포트 [{settings['port']}]: ").strip()
                    storage = input(f"자료 폴더 [{settings['storage_root']}]: ").strip()
                    backups = input(f"백업 폴더 [{settings['backup_directory']}]: ").strip()
                    intranet = input("다른 사내 PC의 접속 허용? y/n (빈칸이면 유지): ").strip().lower()
                    if intranet not in {"", "y", "n"}:
                        raise LauncherError("사내망 설정은 y 또는 n을 입력하세요.")
                    pending = dict(settings, port=int(port) if port else settings["port"],
                        storage_root=storage or settings["storage_root"], backup_directory=backups or settings["backup_directory"],
                        intranet=(intranet == "y") if intranet else settings["intranet"])
                    # Reuse validation without modifying the saved settings first.
                    validate_pending(pending)
                    save_settings(settings_path, pending)
                    print("설정 저장 완료. 사내망 접속은 방화벽·HTTPS 운영 설정도 확인하세요.")
                elif choice == "6":
                    print("백업 완료: " + str(backup(settings)))
                elif choice == "7":
                    archive = input("백업 ZIP 경로: ").strip().strip('"')
                    destination = input("복원할 새 폴더: ").strip().strip('"')
                    if archive and destination:
                        restore(settings, settings_path, state_path, archive, destination)
                        print("복원 완료. 다음 실행부터 새 업무함을 사용하며 다시 로그인해야 합니다.")
                elif choice == "8":
                    print("1 Windows 로그인 시 자동 실행 / 2 매일 자동 백업 / 그 외 취소")
                    task = input("번호: ").strip()
                    if task in {"1", "2"}:
                        if not settings_path.exists():
                            save_settings(settings_path, settings)
                        script = "install_pilot_startup.ps1" if task == "1" else "install_pilot_backup.ps1"
                        run_checked(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", PROJECT / script,
                                     "-SettingsFile", settings_path])
                elif choice == "9":
                    if input("모든 접속이 종료됩니다. 진행하려면 '종료': ").strip() == "종료":
                        result = stop(state_path)
                        print("서버를 종료했습니다." if result == "stopped" else "실행 중인 서버가 없습니다.")
        except (LauncherError, ValueError, OSError) as exc:
            print(str(exc) if isinstance(exc, LauncherError) else "입력값을 확인하세요.")


def validate_pending(settings):
    if type(settings["port"]) is not int or not 1024 <= settings["port"] <= 65535:
        raise LauncherError("접속 포트는 1024~65535로 지정하세요.")
    for key in ("storage_root", "backup_directory"):
        candidate = Path(settings[key])
        settings[key] = str((PROJECT / candidate).resolve() if not candidate.is_absolute() else candidate.resolve())
    if Path(settings["backup_directory"]).is_relative_to(Path(settings["storage_root"])):
        raise LauncherError("백업 폴더는 업무 자료 폴더 밖으로 지정하세요.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="C업체 계약 검수 통합 실행기")
    parser.add_argument("action", nargs="?", default="start", choices=("start", "manage", "status", "setup", "init", "backup", "stop"))
    parser.add_argument("--settings-file", type=Path, default=DEFAULT_SETTINGS)
    parser.add_argument("--empty", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    path = args.settings_file.resolve()
    state_path = path.parent / "server.json"
    try:
        if args.action == "manage":
            return manage_menu(path, state_path)
        settings = load_settings(path)
        with launch_lock(path.parent):
            if args.action == "start":
                print(start(settings, state_path, open_browser=not args.no_browser))
            elif args.action == "status":
                print(json.dumps(status(settings, state_path), ensure_ascii=False, indent=2))
            elif args.action == "setup":
                require_stopped(state_path)
                prepare_environment()
            elif args.action == "init":
                initialize(settings, state_path, empty=args.empty)
            elif args.action == "backup":
                print("백업 완료: " + str(backup(settings)))
            elif args.action == "stop":
                print(stop(state_path))
        return 0
    except (LauncherError, OSError, ValueError, KeyError) as exc:
        print(str(exc) if isinstance(exc, LauncherError) else "실행·설정을 완료하지 못했습니다. 관리 메뉴에서 상태를 점검하세요.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
