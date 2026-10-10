"""Explicit first-install downloads. Never send documents or enable AI on failure."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

import requests

from .environment import LauncherError
from .settings import save_settings

OLLAMA_INSTALLER_URL = 'https://github.com/ollama/ollama/releases/download/v0.35.1/OllamaSetup.exe'
MODELS = ('qwen3:latest', 'qwen2.5vl:7b')


def installed_ollama():
    local = Path(os.getenv('LOCALAPPDATA', str(Path.home() / 'AppData/Local'))) / 'Programs/Ollama/ollama.exe'
    return str(local) if local.is_file() else shutil.which('ollama.exe')


def local_models(session):
    try:
        reply = session.get('http://127.0.0.1:11434/api/tags', timeout=2, allow_redirects=False)
        reply.raise_for_status()
        result = reply.json()['models']
        return result if isinstance(result, list) else None
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None


def disable_cloud(config_path):
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding='utf-8-sig'))
            if not isinstance(config, dict):
                raise ValueError()
        except (OSError, ValueError):
            raise LauncherError('Ollama 설정을 읽지 못했습니다. 기존 설정을 덮어쓰지 않았습니다.') from None
    else:
        config = {}
    changed = config.get('disable_ollama_cloud') is not True
    if changed:
        config['disable_ollama_cloud'] = True
        config_path.parent.mkdir(parents=True, exist_ok=True)
        pending = config_path.with_suffix('.cpilot-pending')
        pending.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
        pending.replace(config_path)
    return changed


def verify_installer(path):
    literal = str(path).replace("'", "''")
    command = (f"$s=Get-AuthenticodeSignature -FilePath '{literal}'; "
               "if ($s.Status -ne 'Valid' -or $s.SignerCertificate.Subject -notmatch '(?:^|, )O=Ollama Inc\\.(?:,|$)') { exit 1 }")
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
                            capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise LauncherError('Ollama 설치 파일의 공식 서명을 확인하지 못했습니다. 실행하지 않았습니다.')


def download_installer(session, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix('.download')
    try:
        print('Ollama 공식 설치 프로그램을 다운로드합니다. 문서는 전송하지 않습니다.', flush=True)
        with session.get(OLLAMA_INSTALLER_URL, stream=True, timeout=(10, 60)) as response:
            response.raise_for_status()
            received = 0
            with pending.open('wb') as handle:
                for block in response.iter_content(1024 * 1024):
                    handle.write(block)
                    received += len(block)
                    if received > 4 * 1024**3:
                        raise LauncherError('Ollama 설치 파일 크기를 확인하세요.')
        verify_installer(pending)
        pending.replace(path)
    except requests.RequestException:
        raise LauncherError('Ollama를 다운로드하지 못했습니다. 인터넷 연결을 확인하고 AI 준비를 다시 실행하세요.') from None
    finally:
        pending.unlink(missing_ok=True)


def prepare_ai(settings, settings_path, *, session=None):
    session = session or requests.Session()
    session.trust_env = False
    running = local_models(session)
    changed = disable_cloud(Path.home() / '.ollama/server.json')
    if changed and running is not None:
        raise LauncherError('Ollama 클라우드 기능을 껐습니다. 현재 Ollama를 종료 후 다시 실행하고 AI 준비를 재시도하세요. 기존 서버는 종료하지 않았습니다.')
    executable = installed_ollama()
    if not executable:
        installer = settings_path.parent.parent / 'downloads/OllamaSetup-0.35.1.exe'
        if not installer.exists():
            download_installer(session, installer)
        verify_installer(installer)
        print('Ollama를 현재 사용자 계정에 설치합니다.', flush=True)
        result = subprocess.run([str(installer), '/CURRENTUSER', '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/NOICONS'])
        if result.returncode:
            raise LauncherError('Ollama 설치가 완료되지 않았습니다. AI 준비를 다시 실행하세요.')
        executable = installed_ollama()
        if not executable:
            raise LauncherError('설치한 Ollama 실행 파일을 확인하지 못했습니다.')
    env = dict(os.environ, OLLAMA_NO_CLOUD='1', OLLAMA_HOST='127.0.0.1:11434')
    if local_models(session) is None:
        subprocess.Popen([executable, 'serve'], env=env, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=subprocess.CREATE_NO_WINDOW)
    deadline = time.monotonic() + 30
    while local_models(session) is None and time.monotonic() < deadline:
        time.sleep(0.5)
    if local_models(session) is None:
        raise LauncherError('Ollama의 로컬 응답을 확인하지 못했습니다. AI 준비를 다시 실행하세요.')
    for model in MODELS:
        existing = local_models(session) or []
        if not any(item.get('name') == model and item.get('size') and not item.get('remote_model')
                   and not item.get('remote_host') for item in existing):
            print(f'로컬 모델 준비: {model} (설치 후에는 인터넷 없이 분석)', flush=True)
            result = subprocess.run([executable, 'pull', model], env=env)
            if result.returncode:
                raise LauncherError('모델 다운로드가 완료되지 않았습니다. 기존 저장값은 유지됩니다. AI 준비를 재시도하세요.')
    models = local_models(session) or []
    if any(not any(item.get('name') == model and item.get('size') and item.get('digest')
                   and not item.get('remote_model') and not item.get('remote_host') for item in models) for model in MODELS):
        raise LauncherError('설치된 로컬 모델을 확인하지 못했습니다.')
    try:
        response = session.post('http://127.0.0.1:11434/api/show', json={'model': MODELS[1]}, timeout=5, allow_redirects=False)
        response.raise_for_status()
        if 'vision' not in response.json().get('capabilities', []):
            raise ValueError()
    except (requests.RequestException, ValueError, TypeError):
        raise LauncherError('이미지 모델의 준비 상태를 확인하지 못했습니다.') from None
    settings.update(llm_enabled=True, vlm_enabled=True)
    save_settings(settings_path, settings)
    print('Qwen 텍스트 보완과 이미지 재판독 준비 완료. C-Pilot을 실행하세요.', flush=True)
