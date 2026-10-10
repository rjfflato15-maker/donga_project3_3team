import json

from backend.app.api import auto_contract
from backend.app.db.models import Contract, Document, ContractPayment, PaymentCorrection, AuditEvent, RequestBundle
from test_payment_records import approved_contract, payment_body
from test_request_bundles import contract, create, patch, resolution


def registration_files():
    return [('files', ('scan.txt', '견적서\n합계: 1100원'.encode(), 'text/plain'))]


def registration_body():
    return dict(title='가상 등록 복구', vendor_name='가상업체', business_number='220-88-12345',
                contract_amount='1100', amount_basis='TOTAL', payment_mode='FULL',
                document_types=json.dumps(['bank_account']), idempotency_key='registration-retry')


def test_registration_failure_retry_and_lost_response_do_not_duplicate(operator_client, db_factory, monkeypatch):
    real = auto_contract.pipeline_service.process_document_upload
    def fail(**kwargs):
        raise RuntimeError('controlled processing failure')
    monkeypatch.setattr(auto_contract.pipeline_service, 'process_document_upload', fail)
    first = operator_client.post('/api/contracts/auto-create-batch', data=registration_body(), files=registration_files())
    assert first.status_code == 201, first.text
    cid = first.json()['contract_id']
    assert first.json()['registration']['complete'] is False
    monkeypatch.setattr(auto_contract.pipeline_service, 'process_document_upload', real)
    for _ in range(2):
        retry = operator_client.post('/api/contracts/auto-create-batch', data=registration_body(), files=registration_files())
        assert retry.status_code == 201 and retry.json()['contract_id'] == cid
        assert retry.json()['registration']['complete'] is True
        assert retry.json()['documents'][0]['document_type'] == 'bank_account'
        assert any('자동 분류' in note for note in retry.json()['documents'][0]['analysis']['warnings'])
        assert retry.json()['workflow']['amount_basis'] == 'TOTAL'
    with db_factory() as db:
        assert db.query(Contract).count() == db.query(Document).count() == 1
    changed = operator_client.post('/api/contracts/auto-create-batch',
        data={**registration_body(), 'contract_amount': '2200'}, files=registration_files())
    assert changed.status_code == 409


def test_excluded_contract_keeps_payment_evidence_and_can_restore(operator_client, separate_client, db_factory):
    _, cid, review = approved_contract(operator_client, separate_client)
    payment = operator_client.post(f'/api/pilot/contracts/{cid}/payment', json=payment_body(review['revision'])).json()
    original = operator_client.get(f'/api/contracts/{cid}').json()
    assert operator_client.delete(f'/api/contracts/{cid}').status_code == 204
    assert operator_client.get(f'/api/contracts/{cid}').status_code == 404
    assert not operator_client.get('/api/contracts').json()
    assert operator_client.get('/api/contracts/search').json()['total'] == 0
    excluded = operator_client.get('/api/contracts/excluded').json()
    assert excluded[0]['contract_id'] == cid
    assert operator_client.post(f'/api/contracts/{cid}/validate').status_code == 404
    with db_factory() as db:
        assert db.query(ContractPayment).count() == 1 and db.query(Document).count() == len(original['documents'])
    restored = operator_client.post(f'/api/contracts/{cid}/restore', json={'note': '잘못 제외하여 복원'})
    assert restored.status_code == 200, restored.text
    assert restored.json()['workflow']['fingerprint'] == original['workflow']['fingerprint']
    assert restored.json()['payment']['payment_id'] == payment['payment_id']
    assert restored.json()['stage'] == 'DONE'


def test_payment_correct_void_and_record_preserve_original_and_guard_stale(operator_client, separate_client, db_factory):
    _, cid, review = approved_contract(operator_client, separate_client)
    path = f'/api/pilot/contracts/{cid}/payment'
    original = operator_client.post(path, json=payment_body(review['revision'])).json()
    endpoint = f'{path}/{original["payment_id"]}/corrections'
    payload = {'revision': review['revision'], 'fingerprint': review['fingerprint'], 'payment_revision': 0,
               'action': 'CORRECT', 'reason': '지급일을 잘못 기록함', 'paid_on': '2026-01-03', 'method': 'OTHER', 'note': '정정 메모'}
    corrected = operator_client.post(endpoint, json=payload)
    assert corrected.status_code == 200, corrected.text
    state = corrected.json()
    assert state['paid_on'] == '2026-01-03' and state['method'] == 'OTHER'
    assert operator_client.post(endpoint, json=payload).status_code == 409
    assert operator_client.get(f'/api/contracts/{cid}').json()['stage'] == 'DONE'
    voided = operator_client.post(endpoint, json={**payload, 'action': 'VOID',
        'payment_revision': state['correction_revision'], 'reason': '실제 지급 전 완료로 잘못 기록'})
    assert voided.status_code == 200 and voided.json()['status'] == 'VOIDED'
    assert operator_client.get(f'/api/contracts/{cid}').json()['stage'] == 'PAYMENT'
    recorded = operator_client.post(path, json=payment_body(review['revision'], paid_on='2026-01-04',
        payment_revision=voided.json()['correction_revision'], idempotency_key='new-payment-request',
        acknowledge_new_payment=True))
    assert recorded.status_code == 201 and recorded.json()['paid_on'] == '2026-01-04'
    with db_factory() as db:
        fact = db.query(ContractPayment).one()
        assert fact.paid_on == '2026-01-02'  # Original fact is immutable.
        assert db.query(PaymentCorrection).count() == 3
        assert db.query(AuditEvent).filter(AuditEvent.action.in_(['PAYMENT_VOIDED','PAYMENT_CORRECTED'])).count() == 2


def test_closed_reply_can_reopen_without_losing_request_or_checks(operator_client, db_factory):
    cid = contract(operator_client)
    row = create(operator_client, cid, keys=['missing:bank_account'])
    item_id = row['bundle']['items'][0]['item_id']
    before_checks = operator_client.get(f'/api/contracts/{cid}').json()['checks']
    closed = patch(operator_client, cid, row, [{'item_id': item_id, 'status': 'RECEIVED', 'note': '받았다고 잘못 기록'}]).json()
    endpoint = f'/api/pilot/contracts/{cid}/resubmission-bundles/{row["request_id"]}/corrections'
    body = resolution(operator_client, cid, closed, [{'item_id': item_id, 'status': 'WAITING_RESPONSE', 'note': '아직 서류를 받지 않아 정정'}])
    response = operator_client.post(endpoint, json=body)
    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'WAITING_RESPONSE'
    assert response.json()['bundle']['counts']['waiting'] == 1
    assert operator_client.get(f'/api/contracts/{cid}').json()['checks'] == before_checks
    assert operator_client.post(endpoint, json=body).status_code == 409
    assert operator_client.delete(f'/api/contracts/{cid}').status_code == 204
    with db_factory() as db:
        assert db.query(RequestBundle).count() == 1
