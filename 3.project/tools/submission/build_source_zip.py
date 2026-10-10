"""Create a reviewable source ZIP from the working tree, never customer data.

Copies an allowlist to a fresh folder, records original and packaged hashes,
redirects omitted-reference links in the copy, checks secrets and doc links.
Existing application files, records and evaluation sources are not deleted.
"""
import argparse
from datetime import datetime
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.docs.lint_docs import destinations, inspect_document, lint, local_target
from tools.submission.privacy_scan import EMAIL, inspect_emails


def digest(data):
    return hashlib.sha256(data).hexdigest()


def metadata(title):
    return f'# {title}\n\n> 상태: 현재 기준\n> 확인일: {datetime.now():%Y-%m-%d}\n> 기준: 제출용 작업 트리 사본.\n\n'


def build(output, installer=None):
    policy = json.loads((ROOT / 'tools/submission/source_policy.json').read_text(encoding='utf-8'))
    docs = json.loads((ROOT / 'docs/documentation_manifest.json').read_text(encoding='utf-8'))
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    # Normalize '..' before resolve: on Windows a not-yet-existing output can
    # otherwise retain it and fail the packaged documentation boundary check.
    run = Path(os.path.abspath(output)).resolve() / (stamp + '_' + uuid.uuid4().hex[:8])
    stage = run / 'C-Pilot-source'
    app = stage / '3.project'
    app.mkdir(parents=True)
    included, changes = {}, []
    allowed = set(policy['root_files'])
    allowed.update('frontend/' + name for name in policy['frontend_files'])
    allowed.update('backend/' + name for name in policy['backend_files'])
    allowed.update(path.relative_to(ROOT).as_posix() for path in (ROOT / 'backend').glob('*.py'))
    allowed.update(record['path'] for record in docs['documents'] if not record['path'].startswith('../'))
    allowed.update(policy['report_files'])
    allowed.add('docs/documentation_manifest.json')
    for folder in policy['trees']:
        for directory, child_dirs, files in os.walk(ROOT / folder, followlinks=False):
            child_dirs[:] = [name for name in child_dirs if name not in policy['skip_directories'] and not (Path(directory) / name).is_symlink()]
            for name in files:
                path = Path(directory) / name
                relative = path.relative_to(ROOT).as_posix()
                if path.is_symlink() or relative in policy['excluded_tests']:
                    continue
                if name.startswith('.env') and name != '.env.example' or name == 'env':
                    continue
                if path.suffix.lower() in {'.pyc', '.pyo', '.log', '.db', '.sqlite', '.sqlite3', '.tsbuildinfo', '.zip', '.pem', '.key'}:
                    continue
                allowed.add(relative)
    # Classification fixtures are synthetic text. Remove unnecessary identifiers
    # from the submitted copies; preserve original frozen fixtures in the workspace.
    allowed.update(path.relative_to(ROOT).as_posix() for path in (ROOT / 'sample-data').glob('*.txt'))
    for relative in sorted(allowed):
        source = (ROOT / relative).resolve()
        if not source.is_relative_to(ROOT) or not source.is_file():
            raise RuntimeError('Missing/outside source: ' + relative)
        original = source.read_bytes()
        data = original
        if relative.startswith('sample-data/'):
            text = original.decode('utf-8-sig')
            text = '\n'.join(line for line in text.splitlines() if not re.search('주민등록번호|전화번호|주소:|소재지:|관리점:', line))
            text = text.replace('홍길동', '가상대표').replace('김철수', '가상담당자')
            text = EMAIL.sub('contact@example.com', text)
            data = ('[제출용 합성 예제 · 실제 고객/계약/송금 자료가 아님]\n' + text + '\n').encode('utf-8')
            changes.append({'path': relative, 'reason': 'synthetic fixture copy: remove unnecessary identifiers and replace example emails with example.com'})
        target = app / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        included[relative] = {'source_sha256': digest(original)}

    omitted = app / 'docs/submission/omitted_records.md'
    omitted.write_text(metadata('제출본에서 제외한 보존 기록')
        + '현재 앱의 코드·실행·유지보수 문서는 이 ZIP에 포함했습니다. 원본 평가 데이터·개발 일지·연구 자료·옛 시안·이전 공유본은 원래 작업 공간에 보존하고 제출본에서 제외했습니다. 이 페이지로 연결된 링크는 해당 자료가 제출본에 없다는 뜻입니다. 링크를 현재 구현의 완료 근거로 사용하지 마세요.\n\n'
        + '[문서 포털](../README.md) · [제출 범위](source_package.md)\n', encoding='utf-8')
    (stage / 'README.md').write_text(metadata('C-Pilot 제출용 소스 코드')
        + '앱 루트는 `3.project/`입니다. 이 폴더에서 명령을 실행하세요. 실제 업무 DB·계정·환경 파일·모델은 포함하지 않습니다.\n\n'
        + '[프로젝트 시작](3.project/README.md) · [제출본 안내](3.project/docs/submission/source_package.md)\n', encoding='utf-8')
    (stage / '.gitignore').write_text('**/.env\n**/.venv/\n**/node_modules/\n**/storage/\n**/__pycache__/\n**/build/\n**/outputs/\n', encoding='utf-8')
    installer_info = None
    if installer is not None:
        installer = installer.resolve()
        if not installer.is_file() or installer.suffix.lower() != '.exe':
            raise RuntimeError('Installer must be a built Setup EXE.')
        destination = stage / 'installer' / installer.name
        destination.parent.mkdir()
        shutil.copy2(installer, destination)
        installer_hash = digest(destination.read_bytes())
        destination.with_suffix('.exe.sha256').write_text(installer_hash + '  ' + installer.name + '\n', encoding='utf-8')
        shutil.copy2(ROOT / 'tools/installer/customer-install.txt', destination.parent / '사용안내.txt')
        installer_info = {'path': destination.relative_to(stage).as_posix(), 'sha256': installer_hash,
                          'models_included': False, 'customer_data_included': False}
        with (stage / 'README.md').open('a', encoding='utf-8') as page:
            page.write('\n일반 실행은 [Windows 설치 마법사](installer/' + installer.name + ')를 사용하세요. '
                       'Python·Node.js 별도 설치 없이 앱을 설치합니다. AI 모델은 선택 다운로드입니다. '
                       '[설치 안내](installer/사용안내.txt)를 먼저 읽으세요.\n')

    # Maintain links in the distributed copy without moving historical originals.
    for page in [*app.rglob('*.md'), stage / 'README.md']:
        text = page.read_text(encoding='utf-8-sig')
        missing = {}
        for _, destination in destinations(text):
            if destination is None:
                continue
            resolved = local_target(page, destination, app)
            if resolved is None:
                continue
            target, _ = resolved
            if not target.is_relative_to(stage) or not target.exists():
                replacement = Path(os.path.relpath(omitted, page.parent)).as_posix()
                missing[destination] = replacement
        if missing:
            # Paths may also occur in code snippets: replace link destinations only.
            for before, after in missing.items():
                text = text.replace('](' + before + ')', '](' + after + ')')
                text = text.replace('](<' + before + '>)', '](' + after + ')')
            changes.append({'path': page.relative_to(stage).as_posix(), 'reason': 'omitted references redirected', 'destinations': list(missing)})
            page.write_text(text, encoding='utf-8')

    # Snapshot the tested environment as version pins, without local install URLs.
    pins = sorted({(dist.metadata['Name'] + '==' + dist.version) for dist in importlib.metadata.distributions() if dist.metadata['Name']}, key=str.lower)
    (app / 'backend/requirements-verified.txt').write_text('# Windows / Python ' + sys.version.split()[0]
        + '\n# Tested environment snapshot; requirements.txt remains the maintained dependency declaration.\n'
        + '\n'.join(pins) + '\n', encoding='utf-8')
    changes.append({'path': '3.project/backend/requirements-verified.txt', 'reason': 'verified environment version snapshot generated from the packaging runtime'})
    (app / 'sample-data/README.md').write_text(metadata('제출용 합성 분류 예제')
        + 'ABC 주식회사 등은 테스트용 가상 예제입니다. 제출 사본에서는 불필요한 주민번호·연락처·주소·인명을 제거했습니다. 실제 업무 자료로 사용하지 마세요. 원본 평가 데이터의 해시·정답을 대체하지 않습니다.\n', encoding='utf-8')

    # Read local secret values only for comparison; never output their values.
    from dotenv import dotenv_values
    secret_values = set()
    for name in ('backend/.env', 'backend/env', '.env'):
        if (ROOT / name).is_file():
            for key, value in dotenv_values(ROOT / name).items():
                if value and len(value) >= 8 and re.search('password|secret|token|api.?key', key, re.I):
                    if not re.search('your_|placeholder|example', value, re.I):
                        secret_values.add(value)
    patterns = {
        'PRIVATE_KEY': r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
        'PROVIDER_TOKEN': r'\b(?:sk-(?:proj-|ant-)?[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{30,}|AKIA[A-Z0-9]{16}|AIza[A-Za-z0-9_-]{30,})\b',
    }
    findings, email_matches = [], 0
    for file in stage.rglob('*'):
        if not file.is_file():
            continue
        data = file.read_bytes()
        for value in secret_values:
            if value.encode() in data:
                findings.append({'path': file.relative_to(stage).as_posix(), 'rule': 'LOCAL_ENV_SECRET'})
        try:
            text = data.decode('utf-8-sig')
        except UnicodeDecodeError:
            continue
        for rule, pattern in patterns.items():
            if re.search(pattern, text):
                findings.append({'path': file.relative_to(stage).as_posix(), 'rule': rule})
        scan_path = file.relative_to(stage).as_posix().removeprefix('3.project/')
        match_count, email_findings = inspect_emails(text, scan_path, policy['email_policy'])
        email_matches += match_count
        findings.extend(email_findings)
    if findings:
        (run / 'blocked_secret_findings.json').write_text(json.dumps(findings, ensure_ascii=False, indent=2), encoding='utf-8')
        raise RuntimeError('Secret/email checks failed; see redacted file/rule report. No ZIP created.')

    # Guard both maintained links and all other Markdown links in the copy.
    copied_docs = json.loads((app / 'docs/documentation_manifest.json').read_text(encoding='utf-8'))
    doc_result = lint(app, copied_docs)
    extra_links = []
    for page in [*app.rglob('*.md'), stage / 'README.md']:
        issues, _ = inspect_document(page, stage)
        extra_links.extend({'path': page.relative_to(stage).as_posix(), **issue} for issue in issues)
    if doc_result['errors'] or extra_links:
        (run / 'blocked_document_findings.json').write_text(json.dumps({'current': doc_result, 'links': extra_links}, ensure_ascii=False, indent=2), encoding='utf-8')
        raise RuntimeError('Packaged document checks failed; see file/line report. No ZIP created.')

    # Reject mixed snapshots if a source changed while copies/checks were made.
    for relative, record in included.items():
        if digest((ROOT / relative).read_bytes()) != record['source_sha256']:
            raise RuntimeError('Source changed during packaging; rerun: ' + relative)
    head = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    files = []
    for file in sorted(stage.rglob('*')):
        if file.is_file():
            relative = file.relative_to(stage).as_posix()
            # Root wrapper files are generated and can share a basename with
            # app sources; do not attribute them to the app README/.gitignore.
            source = included.get(relative.removeprefix('3.project/')) if relative.startswith('3.project/') else None
            files.append({'path': relative, 'bytes': file.stat().st_size, 'sha256': digest(file.read_bytes()), **(source or {'generated': True})})
    report = {'created_at': datetime.now().astimezone().isoformat(), 'git_head': head,
              'basis': 'current working tree, including untracked source; no commit made',
              'installer': installer_info,
              'file_count': len(files), 'excluded_categories': policy['excluded_categories'],
              'excluded_tests': policy['excluded_tests'], 'changes_in_copy': changes,
              'secret_scan': {'findings': 0, 'rules': list(patterns) + ['LOCAL_ENV_SECRET', 'NON_EXAMPLE_EMAIL'], 'limits': 'Pattern checks, local env comparison and literal email policy; not proof that arbitrary personal data is absent.'},
              'email_scan': {'matches': email_matches, 'unapproved': 0, 'policy': policy['email_policy']},
              'document_checks': {'maintained': doc_result['maintained_documents'], 'errors': 0, 'all_markdown_link_errors': 0}, 'files': files}
    (stage / 'submission_manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    archive = run / ('C-Pilot_소스코드_' + stamp + '.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as packaged:
        for file in sorted(stage.rglob('*')):
            if file.is_file():
                packaged.write(file, 'C-Pilot-source/' + file.relative_to(stage).as_posix())
    with zipfile.ZipFile(archive) as packaged:
        assert packaged.testzip() is None
        for record in files:
            assert digest(packaged.read('C-Pilot-source/' + record['path'])) == record['sha256']
        assert not any(any(part in policy['skip_directories'] for part in Path(name).parts) for name in packaged.namelist())
    archive.with_suffix('.zip.sha256').write_text(digest(archive.read_bytes()) + '  ' + archive.name + '\n', encoding='utf-8')
    (run / '검사결과.json').write_text(json.dumps({key: value for key, value in report.items() if key != 'files'}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'zip': str(archive), 'stage': str(app), 'files': len(files), 'bytes': archive.stat().st_size,
                      'secret_findings': 0, 'document_errors': 0}, ensure_ascii=False))
    return archive


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/submission_source')
    parser.add_argument('--installer', type=Path, help='Include the verified Windows Setup EXE alongside source')
    args = parser.parse_args()
    build(args.output, args.installer)
