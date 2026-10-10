"""Build an allowlisted Windows payload from the tested Python 3.12 environment.

Does not copy a venv, customer storage, dotenv files, tests, or model caches.
Every build uses a new directory; existing packages/data are never deleted.
"""
import argparse
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import uuid

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

PROJECT = Path(__file__).resolve().parents[2]
RUNTIME_REQUIREMENTS = ('fastapi', 'uvicorn[standard]', 'pydantic', 'sqlalchemy', 'psycopg2-binary',
    'python-dotenv', 'requests', 'python-multipart', 'pypdf', 'pillow', 'pypdfium2', 'winocr',
    'python-docx', 'openpyxl', 'xlrd', 'olefile', 'pyhwp')


def copy_file(source, target):
    if source.is_symlink() or not source.is_file():
        raise RuntimeError(f'배포 원본 파일을 확인하세요: {source.name}')
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def copy_tree(source, target, *, suffixes=None, excluded=()):
    if not source.is_dir():
        raise RuntimeError(f'배포 원본 폴더가 없습니다: {source.name}')
    for path in sorted(source.rglob('*')):
        relative = path.relative_to(source)
        if any(part in excluded or part == '__pycache__' or part.startswith('.env') for part in relative.parts):
            continue
        if path.is_file() and path.suffix not in {'.pyc', '.pyo'} and (suffixes is None or path.suffix in suffixes):
            copy_file(path, target / relative)


def copy_app(project, stage):
    for folder in ('backend/app', 'backend/launcher'):
        copy_tree(project / folder, stage / folder, suffixes={'.py'})
    for name in ('backend/pilot_launcher.py', 'backend/manage_pilot.py', 'C-Pilot.exe'):
        copy_file(project / name, stage / name)
    # Root package import needs this file when present; namespace packages also work.
    if (project / 'backend/__init__.py').exists():
        copy_file(project / 'backend/__init__.py', stage / 'backend/__init__.py')
    if not (project / 'frontend/dist/index.html').is_file():
        raise RuntimeError('먼저 프론트엔드를 빌드하세요.')
    copy_tree(project / 'frontend/dist', stage / 'frontend/dist')
    for name in ('scheduled_launcher.ps1', 'install_pilot_startup.ps1', 'install_pilot_backup.ps1'):
        copy_file(project / 'tools/ops' / name, stage / 'tools/ops' / name)
    for name in ('customer_package.md', 'accounts_security.md', 'backup_restore.md', 'network.md',
                 'startup_settings.md', 'maintenance.md'):
        copy_file(project / 'docs/operations' / name, stage / 'docs/operations' / name)
    copy_file(project / 'tools/installer/customer-install.txt', stage / '사용안내.txt')


def dependency_closure(requirements=RUNTIME_REQUIREMENTS):
    pending = [Requirement(value) for value in requirements]
    selected, extras_seen = {}, {}
    while pending:
        requirement = pending.pop()
        name = canonicalize_name(requirement.name)
        extras = set(requirement.extras)
        if name in selected and extras <= extras_seen[name]:
            continue
        distribution = metadata.distribution(requirement.name)
        if requirement.specifier and distribution.version not in requirement.specifier:
            raise RuntimeError(f'패키지 버전을 확인하세요: {name}')
        selected[name] = distribution
        extras_seen.setdefault(name, set()).update(extras)
        for value in distribution.requires or []:
            dependency = Requirement(value)
            contexts = ['', *extras_seen[name]]
            if dependency.marker is None or any(dependency.marker.evaluate({'extra': extra}) for extra in contexts):
                pending.append(dependency)
    return selected


def copy_python(stage):
    base = Path(sys.base_prefix)
    runtime = stage / 'runtime/python'
    for name in ('python.exe', 'pythonw.exe', 'python3.dll', 'python312.dll', 'vcruntime140.dll',
                 'vcruntime140_1.dll', 'LICENSE.txt'):
        copy_file(base / name, runtime / name)
    copy_tree(base / 'DLLs', runtime / 'DLLs', suffixes={'.pyd', '.dll'})
    copy_tree(base / 'Lib', runtime / 'Lib', excluded={'site-packages', 'test', 'tests', 'idlelib',
              'tkinter', 'turtledemo', 'ensurepip'})
    # No user PATH/PYTHONPATH/registry dependency. Both script import styles remain supported.
    (runtime / 'python312._pth').write_text(
        'Lib\nDLLs\nLib/site-packages\n../../.\n../../backend\nimport site\n', encoding='utf-8')
    inventory = []
    for name, distribution in sorted(dependency_closure().items()):
        source_site = Path(distribution.locate_file('')).resolve()
        files = distribution.files
        if not files:
            raise RuntimeError(f'설치 패키지 파일 목록이 없습니다: {name}')
        for relative in files:
            source = Path(distribution.locate_file(relative)).resolve()
            if not source.is_relative_to(source_site):
                continue  # CLI entry scripts outside site-packages are not runtime dependencies.
            if source.suffix in {'.pyc', '.pyo'} or '__pycache__' in source.parts:
                continue
            copy_file(source, runtime / 'Lib/site-packages' / source.relative_to(source_site))
        inventory.append({'name': distribution.metadata['Name'], 'version': distribution.version,
            'license': distribution.metadata.get('License-Expression') or distribution.metadata.get('License'),
            'project_urls': distribution.metadata.get_all('Project-URL', [])})
    (stage / 'runtime-lock.txt').write_text('\n'.join(f"{item['name']}=={item['version']}" for item in inventory) + '\n', encoding='utf-8')
    (stage / 'licenses').mkdir(exist_ok=True)
    copy_file(base / 'LICENSE.txt', stage / 'licenses/Python-LICENSE.txt')
    (stage / 'licenses/python-packages.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding='utf-8')
    return inventory


def copy_frontend_licenses(project, stage):
    for name in ('react', 'react-dom', 'scheduler', 'lucide-react'):
        folder = project / 'frontend/node_modules' / name
        license_files = [path for path in folder.iterdir() if path.is_file() and path.name.lower().startswith(('license', 'copying'))]
        if not license_files:
            raise RuntimeError(f'화면 라이브러리 고지 파일을 확인하세요: {name}')
        for path in license_files:
            copy_file(path, stage / 'licenses/frontend' / name / path.name)


def build_payload(project, output, version):
    if os.name != 'nt' or sys.version_info[:2] != (3, 12) or platform.machine().lower() not in {'amd64', 'x86_64'}:
        raise RuntimeError('Windows x64 Python 3.12 빌드 환경을 사용하세요.')
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise RuntimeError('버전은 숫자 3개 형식으로 지정하세요.')
    output.mkdir(parents=True, exist_ok=True)
    stage = output / f'C-Pilot-{version}-{uuid.uuid4().hex[:8]}'
    stage.mkdir()
    copy_app(project, stage)
    inventory = copy_python(stage)
    copy_frontend_licenses(project, stage)
    (stage / 'package-info.json').write_text(json.dumps({'version': version, 'python': platform.python_version(),
        'platform': 'windows-x64', 'models_included': False, 'customer_data_included': False}, indent=2), encoding='utf-8')
    (stage / 'licenses/NOTICE.txt').write_text(
        'C-Pilot includes CPython and the third-party libraries listed in python-packages.json.\n'
        'Original notices and available license files remain in runtime/python/Lib/site-packages/*.dist-info.\n'
        'Frontend library licenses are in frontend/.\n'
        'HWP parsing uses unmodified pyhwp (AGPLv3+). Its Python source and license are included.\n'
        'Commercial distribution and corresponding-source obligations require review before sale.\n'
        'Models are downloaded separately through Ollama. Qwen model licenses are separate from app/library licenses.\n'
        'Installer generated with Inno Setup: https://jrsoftware.org/\n', encoding='utf-8')
    # Test imports in the copied runtime, from a different cwd, with host Python paths removed.
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    env.pop('PYTHONHOME', None)
    env['PATH'] = str(Path(os.environ['WINDIR']) / 'System32')
    check = "import backend.launcher.environment as e; e.check_runtime(); import hwp5,winocr,openpyxl; print('bundled runtime ready')"
    subprocess.run([str(stage / 'runtime/python/python.exe'), '-X', 'utf8', '-c', check],
                   cwd=output, env=env, check=True)
    files = []
    for path in sorted(stage.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            files.append({'path': path.relative_to(stage).as_posix(), 'bytes': path.stat().st_size,
                          'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    (stage / 'package-manifest.json').write_text(json.dumps({'version': version, 'files': files}, indent=2), encoding='utf-8')
    return stage


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=PROJECT / 'build/windows-payload')
    parser.add_argument('--version', default='1.0.0')
    args = parser.parse_args()
    stage = build_payload(PROJECT, args.output.resolve(), args.version)
    print(str(stage))


if __name__ == '__main__':
    main()
