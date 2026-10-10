"""Project runtime and subprocess environment; no server or menu policy."""
import os
from pathlib import Path
import subprocess

PROJECT = Path(__file__).resolve().parents[2]


class LauncherError(Exception):
    pass


def packaged_runtime():
    return PROJECT / 'runtime/python/python.exe'


def is_packaged():
    return packaged_runtime().is_file()


def user_data_directory():
    return Path(os.getenv('LOCALAPPDATA', str(Path.home() / 'AppData/Local'))) / 'C-Pilot'


def python_path():
    if is_packaged():
        return packaged_runtime()
    return PROJECT / "backend/.venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def pilot_environment(settings):
    env = dict(os.environ)
    env.update(APP_DEPLOYMENT_MODE="pilot", APP_STORAGE_ROOT=settings["storage_root"], APP_NTS_MODE="disabled",
               APP_LLM_ENABLED=str(settings.get('llm_enabled', False)).lower(),
               APP_VLM_ENABLED=str(settings.get('vlm_enabled', True)).lower(),
               APP_LLM_MODEL='qwen3:latest', APP_VLM_MODEL='qwen2.5vl:7b',
               APP_OLLAMA_URL='http://127.0.0.1:11434', APP_COOKIE_SECURE="false", PYTHONIOENCODING="utf-8")
    # HTTPS is an IT deployment step. The simple launcher serves local HTTP.
    env["APP_ALLOWED_ORIGINS"] = f"http://127.0.0.1:{settings['port']},http://localhost:{settings['port']}"
    return env


def run_checked(args, *, cwd=PROJECT, env=None):
    result = subprocess.run([str(a) for a in args], cwd=cwd, env=env, check=False,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    if result.returncode:
        raise LauncherError("작업이 실패했습니다. 위의 오류를 확인한 뒤 다시 실행하세요.")


def check_runtime():
    python = python_path()
    if not python.is_file():
        raise LauncherError("최초 환경 준비가 필요합니다. 관리 메뉴의 '환경 준비'를 실행하세요.")
    modules = ("uvicorn", "fastapi", "sqlalchemy", "dotenv", "multipart", "pypdf", "PIL", "pypdfium2", "docx", "requests", "openpyxl", "xlrd", "olefile", "hwp5", "winocr")
    code = "import importlib.util,sys; sys.exit(any(importlib.util.find_spec(m) is None for m in " + repr(modules) + "))"
    result = subprocess.run([str(python), "-c", code], capture_output=True, cwd=PROJECT,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    if result.returncode:
        raise LauncherError("필수 실행 모듈이 부족합니다. 관리 메뉴의 '환경 준비'를 실행하세요.")
    if not (PROJECT / "frontend/dist/index.html").is_file():
        raise LauncherError("앱 화면 빌드가 없습니다. 관리 메뉴의 '환경 준비'를 실행하세요.")
