"""Start, identify, reuse, and stop only this launcher's Windows server."""
import ctypes
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import time
import urllib.request
import webbrowser

from .environment import PROJECT, LauncherError, check_runtime, pilot_environment, python_path

SERVICE = "AI Contract Evidence Manager"


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


def status(settings, state_path):
    state = owned_state(state_path)
    return {"runtime_ready": python_path().is_file(), "frontend_ready": (PROJECT / "frontend/dist/index.html").is_file(),
            "database_ready": (Path(settings["storage_root"]) / "pilot.db").is_file(),
            "server_running": bool(state), "server_ready": bool(state and ready_for(state, settings)),
            "port": settings["port"], "intranet": settings["intranet"], "llm_enabled": False}
