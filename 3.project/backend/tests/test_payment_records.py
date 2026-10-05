"""Whole-contract payment facts use disposable text fixtures, never heldout data."""
import json
import sqlite3
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from io import BytesIO

import pytest
from sqlalchemy.orm import Session
from sqlalchemy import create_engine

from backend.app.db.models import ContractPayment, PaymentConfirmation, AuditEvent, UserProfile
from backend.app.services import backup_service
from test_api import create_contract
from test_review_workflow_api import configured_contract
from test_document_versions import reissue
from test_backup_restore import backup_source


def approved_contract(operator_client, separate_client, *, payment_mode='FULL'):
    representative, cid, body = configured_contract(operator_client, separate_client)
    if payment_mode != 'FULL':
        changed = operator_client.put(f'/api/contracts/{cid}', json={'payment_mode': payment_mode,
            'revision': body['revision'], 'change_note': '분할 계약 지급 기록 검증'})
        assert changed.status_code == 200
        body.update(revision=changed.json()['workflow']['revision'], fingerprint=changed.json()['workflow']['fingerprint'])
    approve(operator_client, representative, cid, body)
    return representative, cid, body


def approve(operator_client, representative, cid, body):
    assert operator_client.post(f'/api/pilot/contracts/{cid}/approvals', json={**body, 'step': 1}).status_code == 200
    final = representative.post(f'/api/contracts/{cid}/reviews', json=body)
    assert final.status_code == 200, final.text


def payment_body(current_revision, **extra):
    return {'paid_on': '2026-01-02', 'method': 'TRANSFER', 'note': '가상 계약의 전체 지급 완료 기록', 'revision': current_revision, **extra}


@pytest.mark.parametrize('role', ['operator', 'representative'])
def test_record_is_full_contract_fact_available_in_list_detail_and_export(operator_client, separate_client, db_factory, role):
    representative, cid, review = approved_contract(operator_client, separate_client, payment_mode='INSTALLMENT')
    actor = operator_client if role == 'operator' else representative
    path = f'/api/pilot/contracts/{cid}/payment'
    payload = payment_body(review['revision'])
    first = actor.post(path, json=payload)
    assert first.status_code == 201, first.text
    fact = first.json()
    assert fact['scope'] == 'WHOLE_CONTRACT' and fact['status'] == 'RECORDED'
    assert fact['reconfirmation_allowed'] is False and fact['blocked_reason'] is None
    assert fact['paid_on'] == '2026-01-02' and fact['original_snapshot']['payment_mode'] == 'INSTALLMENT'
    assert actor.post(path, json=payload).status_code == 200
    for body in (actor.get(f'/api/contracts/{cid}').json(), actor.get('/api/contracts').json()[0]):
        assert body['payment'] == fact
    assert actor.get(path).json() == fact
    assert actor.get(f'/api/contracts/{cid}').json()['workflow']['revision'] == review['revision']
    exported = actor.get(f'/api/contracts/{cid}/export', params={'masked': False, 'revision': review['revision']})
    assert exported.status_code == 200, exported.text
    with zipfile.ZipFile(BytesIO(exported.content)) as bundle:
        history = json.loads(bundle.read('history.json'))
    assert len(history['payments']) == len(history['payment_confirmations']) == 1
    assert history['payments'][0]['paid_on'] == fact['paid_on']
    with db_factory() as db:
        assert db.query(ContractPayment).count() == db.query(PaymentConfirmation).count() == 1
        assert db.query(AuditEvent).filter_by(action='PAYMENT_RECORDED').count() == 1


def test_payment_requires_current_final_review_and_latest_revision(operator_client, separate_client):
    representative, cid, review = configured_contract(operator_client, separate_client)
    path = f'/api/pilot/contracts/{cid}/payment'
    assert operator_client.get(path).json() is None
    assert operator_client.post(path, json=payment_body(review['revision'])).status_code == 409
    assert operator_client.post(f'/api/pilot/contracts/{cid}/approvals', json={**review, 'step': 1}).status_code == 200
    assert operator_client.post(path, json=payment_body(review['revision'])).status_code == 409
    assert representative.post(f'/api/contracts/{cid}/reviews', json=review).status_code == 200
    assert operator_client.post(path, json=payment_body(review['revision'] + 1)).status_code == 409
    assert representative.post(f'/api/contracts/{cid}/reviews', json={**review, 'decision': 'RETURNED'}).status_code == 200
    assert operator_client.post(path, json=payment_body(review['revision'])).status_code == 409


@pytest.mark.parametrize('patch', [
    {'paid_on': '2026-02-30'}, {'paid_on': '20260102'}, {'paid_on': '2026-1-2'},
    {'paid_on': '2026-01-02T00:00:00'}, {'paid_on': (date.today() + timedelta(days=3)).isoformat()},
    {'method': 'BANK'}, {'revision': 0}, {'revision': True}, {'revision': '1'},
    {'note': 'x' * 2001}, {'amount': 100},
])
def test_payment_rejects_invalid_dates_method_revision_note_and_extra_fields(operator_client, patch):
    cid = create_contract(operator_client)['contract_id']
    response = operator_client.post(f'/api/pilot/contracts/{cid}/payment', json=payment_body(1, **patch))
    assert response.status_code == 422, response.text


def test_no_auth_forbidden_role_wrong_contract_and_conflicting_retry(operator_client, separate_client, db_factory, accounts):
    representative, cid, review = approved_contract(operator_client, separate_client)
    path = f'/api/pilot/contracts/{cid}/payment'
    assert operator_client.post('/api/pilot/contracts/999999/payment', json=payment_body(1)).status_code == 404
    assert operator_client.post(path, json=payment_body(review['revision'])).status_code == 201
    assert operator_client.post(path, json=payment_body(review['revision'], method='OTHER')).status_code == 409
    with db_factory() as db:
        db.get(UserProfile, accounts['operator']['user_id']).role = 'viewer'
        db.commit()
    assert operator_client.post(path, json=payment_body(review['revision'])).status_code == 403
    operator_client.post('/api/auth/logout')
    assert operator_client.get(path).status_code == 401
    assert operator_client.post(path, json=payment_body(review['revision'])).status_code == 401


def test_concurrent_duplicate_records_create_one_fact_and_one_audit(operator_client, separate_client, db_factory):
    _, cid, review = approved_contract(operator_client, separate_client)
    other = separate_client('operator')
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(client.post, f'/api/pilot/contracts/{cid}/payment', json=payment_body(review['revision']))
                   for client in (operator_client, other)]
        results = [future.result(timeout=10) for future in futures]
    assert sorted(r.status_code for r in results) == [200, 201]
    assert results[0].json()['payment_id'] == results[1].json()['payment_id']
    with db_factory() as db:
        assert db.query(ContractPayment).count() == db.query(PaymentConfirmation).count() == 1
        assert db.query(AuditEvent).filter_by(action='PAYMENT_RECORDED').count() == 1


def test_reissue_preserves_history_reopens_work_then_reconfirms_same_payment(operator_client, separate_client, db_factory):
    representative, cid, review = approved_contract(operator_client, separate_client)
    path = f'/api/pilot/contracts/{cid}/payment'
    original = operator_client.post(path, json=payment_body(review['revision'])).json()
    old = operator_client.get(f'/api/contracts/{cid}').json()['documents'][0]
    response = reissue(operator_client, cid, old['document_id'], review['revision'])
    assert response.status_code == 200, response.text
    current = operator_client.get(f'/api/contracts/{cid}').json()
    state = current['payment']
    assert state['paid_on'] is None and state['recorded_paid_on'] == original['paid_on']
    assert state['status'] == 'RECONFIRMATION_REQUIRED' and current['workflow']['approval_status'] == 'STALE'
    assert state['reconfirmation_allowed'] is False and state['blocked_reason'] == 'FINAL_REVIEW_REQUIRED'
    assert operator_client.get('/api/contracts').json()[0]['payment']['paid_on'] is None
    endpoint = f'{path}/{original["payment_id"]}/reconfirm'
    body = {'revision': current['workflow']['revision'], 'note': '기존 전체 지급 사실이 수정본에도 해당함을 검토함', 'acknowledge_same_payment': True}
    assert operator_client.post(endpoint, json=body).status_code == 409
    review.update(revision=current['workflow']['revision'], fingerprint=current['workflow']['fingerprint'])
    approve(operator_client, representative, cid, review)
    available = operator_client.get(path).json()
    assert available['reconfirmation_allowed'] is True and available['blocked_reason'] is None
    assert operator_client.post(path, json=payment_body(review['revision'])).status_code == 409
    assert operator_client.post(endpoint, json={**body, 'acknowledge_same_payment': False}).status_code == 422
    assert operator_client.post(endpoint, json={**body, 'acknowledge_same_payment': 1}).status_code == 422
    assert operator_client.post(endpoint, json={**body, 'note': '짧음'}).status_code == 422
    assert operator_client.post(endpoint, json={**body, 'revision': body['revision']-1}).status_code == 409
    assert operator_client.post(f'{path}/9999/reconfirm', json=body).status_code == 404
    confirmed = operator_client.post(endpoint, json=body)
    assert confirmed.status_code == 200 and confirmed.json()['paid_on'] == original['paid_on']
    assert confirmed.json()['payment_id'] == original['payment_id']
    assert operator_client.post(endpoint, json=body).status_code == 200
    with db_factory() as db:
        assert db.query(ContractPayment).count() == 1 and db.query(PaymentConfirmation).count() == 2
        assert db.query(AuditEvent).filter_by(action='PAYMENT_RECORDED').count() == 1
        assert db.query(AuditEvent).filter_by(action='PAYMENT_RECONFIRMED').count() == 1
    assert operator_client.delete(f'/api/contracts/{cid}').status_code == 204
    with db_factory() as db:
        assert db.query(ContractPayment).count() == db.query(PaymentConfirmation).count() == 0


def test_changed_total_cannot_reuse_whole_payment_fact(operator_client, separate_client):
    representative, cid, review = approved_contract(operator_client, separate_client)
    original = operator_client.post(f'/api/pilot/contracts/{cid}/payment', json=payment_body(review['revision'])).json()
    changed = operator_client.put(f'/api/contracts/{cid}', json={'contract_amount': 120, 'revision': review['revision'],
        'change_note': '계약 전체 금액 변경'}).json()
    review.update(revision=changed['workflow']['revision'], fingerprint=changed['workflow']['fingerprint'])
    approve(operator_client, representative, cid, review)
    endpoint = f'/api/pilot/contracts/{cid}/payment/{original["payment_id"]}/reconfirm'
    response = operator_client.post(endpoint, json={'revision': review['revision'], 'note': '과거 지급을 새 총액에 연결하는 시도', 'acknowledge_same_payment': True})
    assert response.status_code == 409 and '계약 금액' in response.json()['detail']
    state = operator_client.get(f'/api/contracts/{cid}').json()['payment']
    assert state['paid_on'] is None and state['reconfirmation_allowed'] is False
    assert state['blocked_reason'] == 'PAYEE_OR_AMOUNT_CHANGED'


def test_original_disappearance_invalidates_payment_even_without_revision_change(operator_client, separate_client, db_factory):
    from backend.app.db.models import Document
    from backend.app.services.storage_service import resolve_path
    _, cid, review = approved_contract(operator_client, separate_client)
    path = f'/api/pilot/contracts/{cid}/payment'
    assert operator_client.post(path, json=payment_body(review['revision'])).status_code == 201
    with db_factory() as db:
        doc = db.query(Document).filter_by(contract_id=cid).first()
        resolve_path(doc.storage_path).unlink()
    current = operator_client.get(f'/api/contracts/{cid}').json()
    assert current['workflow']['revision'] == review['revision']
    assert current['payment']['paid_on'] is None
    assert current['payment']['recorded_paid_on'] == '2026-01-02'
    assert current['payment']['blocked_reason'] == 'SOURCE_VERSION_UNVERIFIED'
    assert operator_client.post(path, json=payment_body(review['revision'])).status_code == 409


def test_changed_payee_cannot_reuse_existing_whole_payment(operator_client, separate_client):
    representative, cid, review = approved_contract(operator_client, separate_client)
    original = operator_client.post(f'/api/pilot/contracts/{cid}/payment', json=payment_body(review['revision'])).json()
    changed = operator_client.put(f'/api/contracts/{cid}', json={'business_number': '220-88-99999',
        'revision': review['revision'], 'change_note': '계약 거래처 식별자를 바꿈'}).json()
    review.update(revision=changed['workflow']['revision'], fingerprint=changed['workflow']['fingerprint'])
    approve(operator_client, representative, cid, review)
    response = operator_client.post(f'/api/pilot/contracts/{cid}/payment/{original["payment_id"]}/reconfirm', json={
        'revision': review['revision'], 'note': '다른 사업자에게 과거 지급 사실 연결 시도', 'acknowledge_same_payment': True})
    assert response.status_code == 409 and '거래처 식별자' in response.json()['detail']
    assert operator_client.get(f'/api/contracts/{cid}').json()['payment']['paid_on'] is None


def test_backup_restore_preserves_payment_fact_and_confirmation(backup_source, tmp_path):
    import manage_pilot as pilot
    engine = create_engine('sqlite:///' + str(backup_source / 'pilot.db'))
    with Session(engine) as db:
        fact = ContractPayment(contract_id=1, paid_on='2026-01-02', method='OTHER', note='전체 지급 사실',
            actor_id=1, actor_name='가상 사용자', snapshot_json=json.dumps({'contract_amount': 1000, 'review_id': 1}))
        db.add(fact)
        db.flush()
        db.add(PaymentConfirmation(payment_id=fact.payment_id, contract_id=1, review_id=1, revision=1,
            fingerprint='a' * 64, actor_id=1, actor_name='가상 사용자', note='전체 지급 사실'))
        db.commit()
    engine.dispose()
    archive = tmp_path / 'with-payment.zip'
    backup_service.create_backup(archive)
    restored = tmp_path / 'restored-payment'
    pilot.restore(archive, restored)
    with sqlite3.connect(restored / 'pilot.db') as db:
        assert db.execute('SELECT paid_on, method, note FROM pilot_contract_payments').fetchone() == ('2026-01-02', 'OTHER', '전체 지급 사실')
        assert db.execute('SELECT count(*) FROM pilot_payment_confirmations').fetchone()[0] == 1
