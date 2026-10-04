"""Exercise real authenticated APIs and restore a fresh DEV-only company backup.

No application DB overrides, fake extraction, network server, or model execution.
Artifacts and temporary credentials remain under ignored storage/demo/team-test.
Run from 3.project: backend/.venv/Scripts/python.exe backend/scripts/rehearse_team_workflow.py
  --output storage/demo/team-test/flow-run-01
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import subprocess
import sys
import threading
import zipfile

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))
from backend.scripts import prepare_team_test_inbox as inbox
from backend.scripts.prepare_team_test_materials import BUNDLE, read_json, save_json, sha256

BUSINESS_TABLES = ('contracts', 'documents', 'document_extracts', 'pilot_document_versions',
                  'pilot_resubmission_requests', 'pilot_work_assignments', 'pilot_contract_reviews',
                  'pilot_approval_signoffs', 'pilot_contract_workflows', 'pilot_audit_events')


def boundary():
    """Apply the existing protection to TestClient's worker threads as well."""
    counts = inbox.install_execution_boundary(allow_event_loop_socketpair=True)
    threading.setprofile(sys.getprofile())
    return counts


def snapshot(storage):
    with sqlite3.connect(storage / 'pilot.db') as db:
        names = {r[0] for r in db.execute("select name from sqlite_master where type='table'")}
        tables = {}
        for name in BUSINESS_TABLES:
            if name not in names:
                raise AssertionError(f'Missing business table: {name}')
            rows = db.execute(f'SELECT * FROM "{name}" ORDER BY rowid').fetchall()
            tables[name] = {'rows': len(rows), 'sha256': hashlib.sha256(
                json.dumps(rows, ensure_ascii=False).encode()).hexdigest()}
        sessions = db.execute('select count(*) from pilot_auth_sessions').fetchone()[0]
    files = {p.relative_to(storage).as_posix(): sha256(p)
             for folder in ('raw', 'masked', 'text') for p in sorted((storage / folder).rglob('*')) if p.is_file()}
    return {'tables': tables, 'files': files, 'sessions': sessions}


class Checks:
    def __init__(self):
        self.steps = []

    def call(self, client, method, path, *, expected=200, label=None, **kwargs):
        response = client.request(method, path, **kwargs)
        self.steps.append({'step': label or f'{method} {path}', 'http_status': response.status_code,
                           'expected_status': expected, 'passed': response.status_code == expected})
        assert response.status_code == expected, f'{method} {path}: {response.status_code} {response.text[:500]}'
        return response

    def check(self, label, condition):
        self.steps.append({'step': label, 'passed': bool(condition)})
        assert condition, label


def login(checks, client, account):
    return checks.call(client, 'POST', '/api/auth/login', json=account).json()


def approval_body(detail):
    return {'decision': 'CONFIRMED', 'note': '가상 흐름 점검: 원문 금액 대조 및 국세청 미연동 범위 확인',
            'acknowledge_unverified': True, 'revision': detail['workflow']['revision'],
            'fingerprint': detail['workflow']['fingerprint'], 'step': 1}


def flow(root):
    storage = root / 'inbox/storage'
    os.environ.update(inbox.isolated_environment(root / 'inbox'))
    counts = boundary()
    from fastapi.testclient import TestClient
    from backend.app.main import app
    cases = {e['case_id']: e for e in inbox.verify_bundle()['cases']}
    c = Checks()
    credentials = {}
    text = (storage / 'initial-accounts.txt').read_text(encoding='utf-8')
    for email, password in re.findall(r'(\S+@team.local)\n임시 비밀번호: (\S+)', text):
        credentials[email.split('@')[0]] = {'email': email, 'password': password}
    assert set(credentials) == {'operator', 'representative'}
    try:
        with TestClient(app) as operator, TestClient(app) as representative, TestClient(app) as anonymous:
            for role, client in (('operator', operator), ('representative', representative)):
                login(c, client, credentials[role])
                new = secrets.token_urlsafe(24)
                c.call(client, 'POST', '/api/auth/password', json={
                    'current_password': credentials[role]['password'], 'new_password': new})
                credentials[role]['password'] = new
            operator_id = c.call(operator, 'GET', '/api/auth/me').json()['user_id']
            c.call(anonymous, 'GET', '/api/contracts', expected=401)
            policy = c.call(representative, 'GET', '/api/pilot/company-policy').json()
            c.check('소기업·필수 6종·대표 1단계', policy['company_type'] == 'SMALL_BUSINESS'
                    and len(policy['required_document_types']) == 6 and len(policy['approval_steps']) == 1)
            ids = {}
            for case_key in ('task_1_A', 'task_2_A'):
                case = cases[case_key]
                cid = c.call(operator, 'POST', '/api/contracts', expected=201, json=case['registration']).json()['contract_id']
                ids[case_key] = cid
                files = [('files', (Path(d['path']).name, (BUNDLE / d['path']).read_bytes(), 'application/pdf'))
                         for d in case['documents']]
                uploaded = c.call(operator, 'POST', f'/api/contracts/{cid}/documents', files=files).json()
                c.check(f'{case_key}: 실제 PDF 판독·분류', [d['document_type'] for d in uploaded] == [d['kind'] for d in case['documents']])
                context = c.call(operator, 'GET', f'/api/contracts/{cid}/review-context').json()
                listed = next(r for r in c.call(operator, 'GET', '/api/contracts').json() if r['contract_id'] == cid)
                c.check(f'{case_key}: 목록/상세 한 줄·문제 1건 일치', listed['action_summary'] == context['action_summary']
                        and listed['open_issue_count'] == 1 and listed['waiting_request_count'] == 0)
                request = c.call(operator, 'POST', f'/api/pilot/contracts/{cid}/resubmission-requests', expected=201,
                    json={'contact_method': 'KAKAO', 'requested_on': '2026-10-03', 'due_on': '2026-10-08',
                          'memo': '가상 과제 원문에 근거한 보완 요청 기록'}).json()
                listed = next(r for r in c.call(operator, 'GET', '/api/contracts').json() if r['contract_id'] == cid)
                c.check(f'{case_key}: 회신 대기·기한 반영', listed['waiting_request_count'] == 1 and listed['earliest_due_on'] == '2026-10-08')
                detail = c.call(operator, 'GET', f'/api/contracts/{cid}').json()
                body = approval_body(detail)
                if case_key == 'task_1_A':
                    c.call(representative, 'POST', f'/api/pilot/contracts/{cid}/approvals', expected=400, json=body,
                           label='필수 서류 누락은 대표도 완료 불가')
                    continue
                old = next(d for d in uploaded if d['document_type'] == 'estimate')['document_id']
                evidence = c.call(operator, 'GET', f'/api/documents/{old}/provenance').json()['fields']['total_amount']
                c.check('견적 합계의 규칙 출처·원문 근거', evidence['source'] == 'RULE' and evidence['evidence'])
                assignments = []
                for did in (None, old):
                    assignments.append(c.call(operator, 'POST', f'/api/pilot/contracts/{cid}/assignments', expected=201,
                        json={'assignee_id': operator_id, 'contract_revision': detail['workflow']['revision'],
                              'document_id': did, 'title': '가상 보완 업무', 'memo': '자료 보완 후 확인'}).json())
                task = assignments[0]
                task_url = f"/api/pilot/contracts/{cid}/assignments/{task['assignment_id']}"
                task = c.call(operator, 'PATCH', task_url, json={'action': 'START',
                    'assignment_revision': task['assignment_revision'], 'note': '담당 업무 시작'}).json()
                c.call(operator, 'POST', f'/api/pilot/contracts/{cid}/approvals', expected=403, json=body,
                       label='담당자는 대표 최종 결재 불가')
                c.call(representative, 'POST', f'/api/contracts/{cid}/reviews',
                       json={k: v for k, v in {**body, 'decision': 'RETURNED'}.items() if k != 'step'})
                replacement = BUNDLE / case['replacement']['path']
                new = c.call(operator, 'POST', f'/api/contracts/{cid}/documents',
                    files=[('files', ('received_document.pdf', replacement.read_bytes(), 'application/pdf'))],
                    data={'upload_mode': 'REISSUE', 'replaces_document_id': old,
                          'revision': body['revision'], 'change_note': '가상 거래처 정정 견적서 수령'}).json()[0]['document_id']
                current = c.call(operator, 'GET', f'/api/contracts/{cid}').json()
                c.check('수정본 반영 후 금액 오류 해소·결재 재확인', current['summary']['fail_count'] == 0
                        and current['workflow']['approval_status'] == 'STALE')
                prior = assignments[1]
                c.call(operator, 'PATCH', f"/api/pilot/contracts/{cid}/assignments/{prior['assignment_id']}", expected=409,
                    json={'action': 'COMPLETE', 'assignment_revision': prior['assignment_revision'], 'note': '이전본 업무 완료 시도'},
                    label='재발행된 이전 서류의 업무 완료 차단')
                c.call(operator, 'PATCH', f"/api/pilot/contracts/{cid}/assignments/{prior['assignment_id']}",
                    json={'action': 'CANCEL', 'assignment_revision': prior['assignment_revision'], 'note': '현재본으로 보완해 이전본 업무 취소'})
                versions = c.call(operator, 'GET', f'/api/documents/{new}/versions').json()['versions']
                c.check('이전본 1개·현재본 1개', [v['is_current'] for v in versions] == [False, True])
                original = c.call(operator, 'GET', f'/api/documents/{old}/download', params={'masked': False}).content
                initial = next(d for d in case['documents'] if d['kind'] == 'estimate')
                c.check('이전 원본 바이트 유지', hashlib.sha256(original).hexdigest() == initial['sha256'])
                c.call(operator, 'PUT', f'/api/documents/{new}/fields', json={'fields': {'total_amount': case['registration']['contract_amount']},
                    'confirmed_fields': ['total_amount'], 'document_type': 'estimate',
                    'revision': current['workflow']['revision'], 'note': '가상 리허설: 현재본 합계 한 칸만 확인'})
                fields = c.call(operator, 'GET', f'/api/documents/{new}/provenance').json()['fields']
                c.check('확인한 합계 한 칸만 사람 확인 출처', fields['total_amount']['source'] == 'HUMAN_CONFIRMATION'
                        and fields['business_registration_no']['source'] == 'RULE')
                completed = c.call(operator, 'PATCH', task_url, json={'action': 'COMPLETE',
                    'assignment_revision': task['assignment_revision'], 'note': '수정 견적 원문 확인과 보완 처리 완료'}).json()
                c.check('자료 변경 후 계약 업무 완료 가능', completed['status'] == 'COMPLETED')
                current = c.call(operator, 'GET', f'/api/contracts/{cid}').json()
                c.check('맡긴 일 완료가 자동 결재하지 않음', current['workflow']['approval_status'] != 'CONFIRMED')
                request_url = f"/api/pilot/contracts/{cid}/resubmission-requests/{request['request_id']}"
                received = {'status': 'RECEIVED', 'note': '정정 견적서 수령 및 차액 해소 확인'}
                c.call(operator, 'PATCH', request_url, json=received)
                c.call(operator, 'PATCH', request_url, expected=409, json=received, label='회신 중복 처리 차단')
                listed = next(r for r in c.call(operator, 'GET', '/api/contracts').json() if r['contract_id'] == cid)
                c.check('회신 대기·기한·문제 수 해제', listed['waiting_request_count'] == 0
                        and listed['earliest_due_on'] is None and listed['open_issue_count'] == 0)
                c.call(representative, 'POST', f'/api/pilot/contracts/{cid}/approvals', expected=409,
                       json=body, label='이전 자료 기준 결재 차단')
                c.call(representative, 'POST', f'/api/pilot/contracts/{cid}/approvals', json=approval_body(current))
                listed = next(r for r in c.call(operator, 'GET', '/api/contracts').json() if r['contract_id'] == cid)
                c.check('대표 확인 후 다음 결재 단계 없음', listed['approval_status'] == 'CONFIRMED' and listed['approval_next_step'] is None)
                (root / 'exports').mkdir()
                for masked in (True, False):
                    response = c.call(operator, 'GET', f'/api/contracts/{cid}/export', params={'masked': masked})
                    (root / 'exports' / ('masked.zip' if masked else 'original.zip')).write_bytes(response.content)
                    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                        c.check(f'ZIP {masked}: 압축 무결성', z.testzip() is None)
                        manifest = json.loads(z.read('manifest.json'))
                        c.check(f'ZIP {masked}: 현재 6개·이전 1개', len(manifest['documents']) == 7
                                and sum(d['is_current'] for d in manifest['documents']) == 6)
                        for d in manifest['documents']:
                            c.check(f'ZIP {masked}: 문서 {d["document_id"]} 파일 해시',
                                    hashlib.sha256(z.read(d['entry'])).hexdigest() == d['export_sha256'])
                        history = json.loads(z.read('history.json'))
                        c.check(f'ZIP {masked}: 요청·맡기기·결재 이력', bool(history['requests'] and history['assignments'] and history['final_reviews']))
                        if masked:
                            metadata = '\n'.join(z.read(n).decode() for n in z.namelist() if n.endswith('.json'))
                            c.check('가린 ZIP 메타데이터의 공급자 이름·번호 제거', case['registration']['vendor_name'] not in metadata
                                    and case['registration']['business_number'] not in metadata)
                        else:
                            c.check('원본 ZIP의 모든 원본 해시', all(d['source_sha256'] == d['export_sha256'] for d in manifest['documents']))
                events = c.call(operator, 'GET', '/api/pilot/audit', params={'contract_id': cid}).json()
                exports = [json.loads(e['details']) if isinstance(e['details'], str) else e['details']
                           for e in events if e['action'] == 'CONTRACT_BUNDLE_EXPORT_REQUEST']
                c.check('감사 기록에 가림/원본 구분', {e['masked'] for e in exports} == {True, False})
                c.call(anonymous, 'GET', f'/api/contracts/{cid}/export', expected=401)
            c.call(operator, 'GET', '/api/pilot/backup', expected=403, label='담당자 전체 업무 백업 다운로드 차단')
            backup = c.call(representative, 'GET', '/api/pilot/backup')
            (root / 'backup.zip').write_bytes(backup.content)
            with zipfile.ZipFile(io.BytesIO(backup.content)) as z:
                c.check('업무 백업 ZIP 무결성·임시 계정 안내 제외', z.testzip() is None and 'initial-accounts.txt' not in z.namelist())
            before = snapshot(storage)
            save_json(root / 'private_login.json', {'accounts': credentials, 'cookies': dict(operator.cookies)})
            save_json(root / 'before_restore.json', {'snapshot': before, 'contracts': ids})
        c.check('모델·가드·외부 접속·보호 자료 접근 0건', not any(counts.values()))
    finally:
        sys.setprofile(None)
        threading.setprofile(None)
        save_json(root / 'flow_checks.json', {'steps': c.steps, 'runtime_boundary': counts})


def restored(root):
    os.environ.update(inbox.isolated_environment(root / 'inbox'))
    os.environ['APP_STORAGE_ROOT'] = str(root / 'restored')
    counts = boundary()
    from fastapi.testclient import TestClient
    from backend.app.main import app
    c = Checks()
    expected = read_json(root / 'before_restore.json')
    current = snapshot(root / 'restored')
    c.check('복원 전후 업무 테이블 내용 일치', current['tables'] == expected['snapshot']['tables'])
    c.check('복원 전후 원문·본문·가림 파일 해시 일치', current['files'] == expected['snapshot']['files'])
    c.check('복원 뒤 로그인 세션 폐기', current['sessions'] == 0 and expected['snapshot']['sessions'] > 0)
    private = read_json(root / 'private_login.json')
    try:
        with TestClient(app) as client:
            client.cookies.update(private['cookies'])
            c.call(client, 'GET', '/api/contracts', expected=401, label='복원 후 이전 로그인 쿠키 거부')
            client.cookies.clear()
            login(c, client, private['accounts']['operator'])
            rows = c.call(client, 'GET', '/api/contracts').json()
            missing = next(r for r in rows if r['contract_id'] == expected['contracts']['task_1_A'])
            approved = next(r for r in rows if r['contract_id'] == expected['contracts']['task_2_A'])
            c.check('복원 후 누락·회신 대기 유지', missing['open_issue_count'] == 1 and missing['waiting_request_count'] == 1)
            c.check('복원 후 수정·회신·결재 완료 유지', approved['open_issue_count'] == 0
                    and approved['waiting_request_count'] == 0 and approved['approval_status'] == 'CONFIRMED')
            cid = approved['contract_id']
            response = c.call(client, 'GET', f'/api/contracts/{cid}/export', params={'masked': False})
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                manifest = json.loads(z.read('manifest.json'))
                c.check('새 복원 폴더에서 이전본 포함 7개 파일 내려받기', len(manifest['documents']) == 7
                        and all(hashlib.sha256(z.read(d['entry'])).hexdigest() == d['source_sha256'] for d in manifest['documents']))
        c.check('복원 점검도 모델·가드·외부 접속 0건', not any(counts.values()))
    finally:
        sys.setprofile(None)
        threading.setprofile(None)
        save_json(root / 'restore_checks.json', {'steps': c.steps, 'runtime_boundary': counts,
            'verified_file_count': len(current['files']), 'verified_table_count': len(current['tables'])})


def run(root):
    root = inbox.fresh_output(root)
    root.mkdir(parents=True)
    inbox.prepare(root / 'inbox')
    env = inbox.isolated_environment(root / 'inbox')
    for phase in ('flow', 'restore', 'restored'):
        if phase == 'restore':
            command = [sys.executable, str(PROJECT / 'backend/manage_pilot.py'), 'restore',
                       '--archive', str(root / 'backup.zip'), '--destination', str(root / 'restored')]
        else:
            command = [sys.executable, str(Path(__file__).resolve()), '--output', str(root), '--phase', phase]
        result = subprocess.run(command, cwd=PROJECT, env=env, capture_output=True, text=True, encoding='utf-8')
        if result.returncode:
            (root / f'{phase}_error.txt').write_text(result.stderr, encoding='utf-8')
            raise RuntimeError(f'{phase} 중단: {root / (phase + "_error.txt")}')
    report = {'source_base_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=PROJECT, encoding='utf-8').strip(),
              'review_context_source_sha256': sha256(PROJECT / 'backend/app/services/review_context_service.py'),
              'dataset': 'team-test-dev-v1', 'scope': 'authenticated in-process HTTP API; no UI clicks',
              'llm': False, 'nts': 'disabled', 'flow': read_json(root / 'flow_checks.json'),
              'restore': read_json(root / 'restore_checks.json'), 'passed': True}
    save_json(root / 'report.json', report)
    print(f"PASS: {sum(len(report[s]['steps']) for s in ('flow','restore'))} checks; {root / 'report.json'}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--phase', choices=['flow', 'restored'], help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = args.output.resolve()
    if args.phase:
        if not root.is_relative_to(inbox.DEMO_ROOT.resolve()) or root == inbox.DEMO_ROOT.resolve():
            raise ValueError('리허설 전용 새 폴더만 허용합니다.')
        {'flow': flow, 'restored': restored}[args.phase](root)
    else:
        run(root)
