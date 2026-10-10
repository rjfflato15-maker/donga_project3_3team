"""Audited recovery edges. All sources/DBs are synthetic; AI services stay disabled."""
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.app.db.models import (
    Contract, ContractExclusion, ContractPayment, Document, DocumentFileInfo,
    DocumentUploadJob, PaymentCorrection, AuditEvent, RegistrationAttempt,
)
from backend.app.services import pipeline_service
from backend.app.services.storage_service import resolve_path
from test_api import create_contract
from test_operational_recovery import registration_body, registration_files
from test_payment_records import approved_contract, payment_body
from test_storage_concurrency import block_analysis
from test_upload_jobs import submit


def fail_analysis(*args, **kwargs):
    raise RuntimeError('Synthetic transient OCR failure')


def post_registration(client, **extra):
    return client.post('/api/contracts/auto-create-batch',
        data={**registration_body(), **extra}, files=registration_files())


def test_registration_real_ocr_failure_is_retryable_and_receipt_only_after_success(operator_client, db_factory, monkeypatch):
    original = pipeline_service.analyze_document
    monkeypatch.setattr(pipeline_service, 'analyze_document', fail_analysis)
    first = post_registration(operator_client)
    assert first.status_code == 201
    data = first.json()
    assert not data['registration']['complete']
    assert data['registration']['failed_files'][0]['index'] == 0
    assert data['documents'] == []
    cid = data['contract_id']
    with db_factory() as db:
        assert json.loads(db.query(RegistrationAttempt).one().receipts_json) == {}
        assert db.query(Document).count() == 0
    # Failed recognition still preserves the original immutable bytes on disk.
    from backend.app.services import storage_service
    retained = list((storage_service.STORAGE_DIR / 'raw' / str(cid)).glob('*'))
    assert retained and retained[0].read_bytes() == registration_files()[0][1][1]
    monkeypatch.setattr(pipeline_service, 'analyze_document', original)
    for _ in range(2):
        recovered = post_registration(operator_client)
        assert recovered.status_code == 201
        assert recovered.json()['contract_id'] == cid
        assert recovered.json()['registration']['complete']
        assert recovered.json()['documents'][0]['processing_status'] == 'COMPLETED'
        assert recovered.json()['documents'][0]['document_type'] == 'bank_account'
    with db_factory() as db:
        assert db.query(Contract).count() == db.query(Document).count() == 1


def test_unreadable_pdf_is_incomplete_without_mock_and_repeated_failure_does_not_publish(operator_client, db_factory):
    for _ in range(2):
        response = operator_client.post('/api/contracts/auto-create-batch',
            data={**registration_body(), 'idempotency_key': 'unreadable-pdf'},
            files=[('files', ('bad.pdf', b'%PDF-1.7\nnot a valid PDF body', 'application/pdf'))])
        assert response.status_code == 201
        assert response.json()['registration']['complete'] is False
        assert response.json()['registration']['failed_files'][0]['index'] == 0
        assert response.json()['documents'] == []
    with db_factory() as db:
        assert db.query(Contract).count() == 1 and db.query(Document).count() == 0


def test_partial_registration_retry_skips_successful_file_and_preserves_original(operator_client, db_factory, monkeypatch):
    original = pipeline_service.analyze_document
    calls = []
    def partial(*args, **kwargs):
        calls.append(kwargs['file_name'])
        if kwargs['file_name'] == 'fail.txt':
            return fail_analysis()
        return original(*args, **kwargs)
    monkeypatch.setattr(pipeline_service, 'analyze_document', partial)
    body = {**registration_body(), 'document_types': json.dumps(['contract', 'bank_account'])}
    files = [('files', ('ok.txt', b'contract amount 1100', 'text/plain')),
             ('files', ('fail.txt', b'bank account 123', 'text/plain'))]
    first = operator_client.post('/api/contracts/auto-create-batch', data=body, files=files).json()
    assert not first['registration']['complete'] and len(first['documents']) == 1
    did = first['documents'][0]['document_id']
    with db_factory() as db:
        source = db.get(Document, did).storage_path
        source_bytes = resolve_path(source).read_bytes()
    def healthy(*args, **kwargs):
        calls.append(kwargs['file_name'])
        return original(*args, **kwargs)
    monkeypatch.setattr(pipeline_service, 'analyze_document', healthy)
    for _ in range(2):
        retry = operator_client.post('/api/contracts/auto-create-batch', data=body, files=files).json()
        assert retry['registration']['complete'] and len(retry['documents']) == 2
    assert calls == ['ok.txt', 'fail.txt', 'fail.txt']
    with db_factory() as db:
        assert db.query(Document).count() == 2
        assert db.get(Document, did).storage_path == source
        assert resolve_path(source).read_bytes() == source_bytes


def guarded_payment_body(revision, **extra):
    return payment_body(revision, idempotency_key='initial-payment-request', payment_revision=0,
                        acknowledge_new_payment=False, **extra)


def record_then_void(client, separate_client):
    _, cid, review = approved_contract(client, separate_client)
    path = f'/api/pilot/contracts/{cid}/payment'
    body = guarded_payment_body(review['revision'])
    first = client.post(path, json=body)
    assert first.status_code == 201, first.text
    endpoint = f'{path}/{first.json()["payment_id"]}/corrections'
    voided = client.post(endpoint, json={'action': 'VOID', 'revision': review['revision'],
        'fingerprint': review['fingerprint'], 'payment_revision': 0, 'reason': '지급 전 잘못 기록하여 취소'})
    assert voided.status_code == 200, voided.text
    return cid, review, path, body, voided.json()


def test_original_payment_key_replay_after_void_cannot_revive_fact(operator_client, separate_client, db_factory):
    cid, review, path, body, voided = record_then_void(operator_client, separate_client)
    repeated = operator_client.post(path, json=body)
    assert repeated.status_code == 200
    assert repeated.json()['status'] == 'VOIDED'
    assert repeated.json()['correction_revision'] == voided['correction_revision']
    assert operator_client.get(f'/api/contracts/{cid}').json()['stage'] == 'PAYMENT'
    with db_factory() as db:
        assert [r.action for r in db.query(PaymentCorrection)] == ['VOID']
        assert db.query(AuditEvent).filter_by(action='PAYMENT_RECORDED').count() == 1


@pytest.mark.parametrize('patch', [
    {'idempotency_key': 'fresh-payment-request'},
    {'idempotency_key': 'fresh-payment-request', 'acknowledge_new_payment': True},
    {'idempotency_key': 'fresh-payment-request', 'payment_revision': 'current'},
    {'payment_revision': 'current', 'acknowledge_new_payment': True},
])
def test_void_requires_current_version_explicit_intent_and_unused_key(operator_client, separate_client, db_factory, patch):
    cid, _, path, body, voided = record_then_void(operator_client, separate_client)
    patch = dict(patch)
    if patch.get('payment_revision') == 'current':
        patch['payment_revision'] = voided['correction_revision']
    response = operator_client.post(path, json={**body, **patch})
    assert response.status_code == 409, response.text
    assert operator_client.get(path).json()['status'] == 'VOIDED'
    with db_factory() as db:
        assert db.query(PaymentCorrection).count() == 1


def test_deliberate_record_current_revision_and_duplicate_preserve_original_history(operator_client, separate_client, db_factory):
    cid, _, path, body, voided = record_then_void(operator_client, separate_client)
    new_body = {**body, 'payment_revision': voided['correction_revision'],
                'idempotency_key': 'new-payment-request', 'acknowledge_new_payment': True, 'paid_on': '2026-01-04'}
    first = operator_client.post(path, json=new_body)
    assert first.status_code == 201 and first.json()['status'] == 'RECORDED'
    assert operator_client.post(path, json=new_body).status_code == 200
    assert operator_client.post(path, json={**new_body, 'idempotency_key': 'different-duplicate-key'}).status_code == 409
    assert operator_client.post(path, json={**new_body, 'note': 'changed under same key'}).status_code == 409
    # A still older request returns the current state; it cannot overwrite the new fact.
    replay = operator_client.post(path, json=body)
    assert replay.status_code == 200 and replay.json()['paid_on'] == '2026-01-04'
    with db_factory() as db:
        assert db.query(ContractPayment).one().paid_on == '2026-01-02'
        assert [r.action for r in db.query(PaymentCorrection).order_by(PaymentCorrection.correction_id)] == ['VOID', 'RECORD']
        assert db.query(AuditEvent).filter_by(action='PAYMENT_RECORDED').count() == 2


@pytest.mark.parametrize('field', ['idempotency_key', 'payment_revision'])
def test_payment_missing_tokens_rejected_without_mutation(operator_client, separate_client, db_factory, field):
    _, cid, review = approved_contract(operator_client, separate_client)
    body = guarded_payment_body(review['revision'])
    body.pop(field)
    result = operator_client.post(f'/api/pilot/contracts/{cid}/payment', json=body)
    assert result.status_code == 422
    with db_factory() as db:
        assert db.query(ContractPayment).count() == 0


@pytest.mark.parametrize('patch', [{'payment_revision': True}, {'payment_revision': -1},
    {'idempotency_key': ''}, {'idempotency_key': ' ' * 8}, {'acknowledge_new_payment': 1}])
def test_payment_request_tokens_have_strict_validation(operator_client, patch):
    cid = create_contract(operator_client)['contract_id']
    response = operator_client.post(f'/api/pilot/contracts/{cid}/payment', json={**guarded_payment_body(1), **patch})
    assert response.status_code == 422


def test_excluded_job_get_and_retry_are_404_then_restore_allows_original_retry(operator_client, db_factory, monkeypatch):
    contract = create_contract(operator_client)
    cid = contract['contract_id']
    original = pipeline_service.analyze_document
    monkeypatch.setattr(pipeline_service, 'analyze_document', fail_analysis)
    created = submit(operator_client, cid, contract['workflow']['revision'])
    jid = created.json()['job_id']
    job = operator_client.get(f'/api/pilot/document-jobs/{jid}').json()
    assert job['status'] == 'FAILED'
    with db_factory() as db:
        source = db.get(DocumentUploadJob, jid).source_path
        original_bytes = resolve_path(source).read_bytes()
    assert operator_client.delete(f'/api/contracts/{cid}').status_code == 204
    monkeypatch.setattr(pipeline_service, 'analyze_document', original)
    request = {'job_revision': job['job_revision'], 'contract_revision': contract['workflow']['revision']}
    assert operator_client.get(f'/api/pilot/document-jobs/{jid}').status_code == 404
    assert operator_client.post(f'/api/pilot/document-jobs/{jid}/retry', json=request).status_code == 404
    with db_factory() as db:
        row = db.get(DocumentUploadJob, jid)
        assert row.job_revision == job['job_revision'] and row.status == 'FAILED'
        assert db.query(Document).count() == 0
        assert resolve_path(source).read_bytes() == original_bytes
    assert operator_client.post(f'/api/contracts/{cid}/restore', json={'note': '다시 검토하려고 복원'}).status_code == 200
    assert operator_client.post(f'/api/pilot/document-jobs/{jid}/retry', json=request).status_code == 202
    assert operator_client.get(f'/api/pilot/document-jobs/{jid}').json()['status'] == 'COMPLETED'
    with db_factory() as db:
        assert db.query(Document).count() == 1


def test_exclusion_during_job_analysis_blocks_publication_and_is_recoverable(operator_client, separate_client, db_factory, monkeypatch):
    contract = create_contract(operator_client)
    cid = contract['contract_id']
    other = separate_client('operator')
    original = pipeline_service.analyze_document
    started, finish = block_analysis(monkeypatch)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(submit, operator_client, cid, contract['workflow']['revision'])
        try:
            assert started.wait(3)
            assert other.delete(f'/api/contracts/{cid}').status_code == 204
        finally:
            finish.set()
        response = pending.result(timeout=10)
    jid = response.json()['job_id']
    with db_factory() as db:
        job = db.get(DocumentUploadJob, jid)
        assert job.status == 'FAILED' and job.error_code == 'NOT_FOUND'
        assert job.document_id is None and db.query(Document).count() == 0
        assert resolve_path(job.source_path)
    monkeypatch.setattr(pipeline_service, 'analyze_document', original)
    assert operator_client.post(f'/api/contracts/{cid}/restore', json={'note': '중단 작업을 다시 처리'}).status_code == 200
    job = operator_client.get(f'/api/pilot/document-jobs/{jid}').json()
    retry = operator_client.post(f'/api/pilot/document-jobs/{jid}/retry', json={
        'job_revision': job['job_revision'], 'contract_revision': contract['workflow']['revision']})
    assert retry.status_code == 202
    assert operator_client.get(f'/api/pilot/document-jobs/{jid}').json()['status'] == 'COMPLETED'


@pytest.mark.parametrize('hints, expected_type', [(json.dumps(['bank_account']), 'bank_account'), ('[]', 'estimate')])
def test_legacy_failed_registration_receipt_reissues_without_erasing_original(operator_client, db_factory, hints, expected_type):
    first = post_registration(operator_client, document_types=hints).json()
    assert first['registration']['complete']
    did = first['documents'][0]['document_id']
    with db_factory() as db:
        # Model the exact pre-fix persisted state: failed unknown document with
        # a success receipt. The old source remains an immutable history entry.
        old = db.get(Document, did)
        source = old.storage_path
        original_bytes = resolve_path(source).read_bytes()
        old.processing_status = 'FAILED'
        old.document_type = 'unknown'
        old.extract.extracted_status = 'FAILED'
        old.extract.raw_fields = '{}'
        old.version.initial_fields_json = '{}'
        db.commit()
    recovered = post_registration(operator_client, document_types=hints)
    assert recovered.status_code == 201, recovered.text
    data = recovered.json()
    assert data['registration']['complete']
    assert len(data['documents']) == 1
    assert data['documents'][0]['document_id'] != did
    assert data['documents'][0]['document_type'] == expected_type
    assert post_registration(operator_client, document_types=hints).json()['registration']['complete']
    with db_factory() as db:
        old = db.get(Document, did)
        assert old.processing_status == 'FAILED' and not old.version.is_current
        assert resolve_path(source).read_bytes() == original_bytes
        assert db.query(Document).count() == 2
        new_id = json.loads(db.query(RegistrationAttempt).one().receipts_json)['0']
        assert db.get(Document, new_id).version.previous_document_id == did


def test_registration_crash_between_publication_and_receipt_does_not_repeat_ocr(operator_client, db_factory, monkeypatch):
    from backend.app.api import auto_contract
    real = auto_contract.pipeline_service.process_document_upload
    calls = []
    def lost_receipt(**kwargs):
        calls.append(1)
        real(**kwargs)
        raise RuntimeError('Synthetic lost response after publication')
    monkeypatch.setattr(auto_contract.pipeline_service, 'process_document_upload', lost_receipt)
    first = post_registration(operator_client).json()
    assert not first['registration']['complete'] and len(first['documents']) == 1
    did = first['documents'][0]['document_id']
    second = post_registration(operator_client).json()
    assert second['registration']['complete'] and second['documents'][0]['document_id'] == did
    assert len(calls) == 1
    with db_factory() as db:
        assert db.query(Document).count() == 1


def test_pre_upgrade_payment_without_receipt_is_readable_but_requires_current_void_intent(operator_client, separate_client, db_factory):
    cid, review, path, body, voided = record_then_void(operator_client, separate_client)
    with db_factory() as db:
        fact = db.query(ContractPayment).one()
        snapshot = json.loads(fact.snapshot_json)
        snapshot.pop('record_request')
        fact.snapshot_json = json.dumps(snapshot)
        for correction in db.query(PaymentCorrection):
            snapshot = json.loads(correction.snapshot_json)
            snapshot['reference'].pop('record_request', None)
            correction.snapshot_json = json.dumps(snapshot)
        db.commit()
    assert operator_client.get(path).json()['status'] == 'VOIDED'
    legacy_body = {key: body[key] for key in ('paid_on', 'method', 'note', 'revision')}
    assert operator_client.post(path, json=legacy_body).status_code == 422
    assert operator_client.post(path, json=body).status_code == 409
    fresh = {**body, 'idempotency_key': 'post-upgrade-payment', 'payment_revision': voided['correction_revision'],
             'acknowledge_new_payment': True}
    assert operator_client.post(path, json=fresh).status_code == 201
    with db_factory() as db:
        assert 'record_request' not in json.loads(db.query(ContractPayment).one().snapshot_json)
        assert db.query(PaymentCorrection).count() == 2


def test_concurrent_rerecord_and_old_replay_after_second_void_remain_idempotent(operator_client, separate_client, db_factory):
    cid, review, path, body, voided = record_then_void(operator_client, separate_client)
    fresh = {**body, 'idempotency_key': 'new-payment-after-void', 'payment_revision': voided['correction_revision'],
             'acknowledge_new_payment': True}
    other = separate_client('operator')
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda client: client.post(path, json=fresh), (operator_client, other)))
    assert sorted(result.status_code for result in results) == [200, 201]
    state = operator_client.get(path).json()
    result = operator_client.post(f'{path}/{state["payment_id"]}/corrections', json={
        'action': 'VOID', 'revision': review['revision'], 'fingerprint': review['fingerprint'],
        'payment_revision': state['correction_revision'], 'reason': '재기록도 잘못되어 다시 취소'})
    assert result.status_code == 200
    for payload in (body, fresh):
        repeated = operator_client.post(path, json=payload)
        assert repeated.status_code == 200 and repeated.json()['status'] == 'VOIDED'
    with db_factory() as db:
        assert [r.action for r in db.query(PaymentCorrection).order_by(PaymentCorrection.correction_id)] == ['VOID', 'RECORD', 'VOID']
        assert db.query(AuditEvent).filter_by(action='PAYMENT_RECORDED').count() == 2


def test_queued_job_excluded_before_worker_start_never_calls_ocr(operator_client, db_factory, monkeypatch):
    from backend.app.api import upload_jobs
    from backend.app.services.upload_job_service import run_upload_job
    contract = create_contract(operator_client)
    cid = contract['contract_id']
    monkeypatch.setattr(upload_jobs, 'run_upload_job', lambda *args: None)
    jid = submit(operator_client, cid, contract['workflow']['revision']).json()['job_id']
    assert operator_client.delete(f'/api/contracts/{cid}').status_code == 204
    def forbidden(*args, **kwargs):
        pytest.fail('Excluded queued job must not run OCR')
    monkeypatch.setattr(pipeline_service, 'analyze_document', forbidden)
    run_upload_job(jid)
    with db_factory() as db:
        job = db.get(DocumentUploadJob, jid)
        assert job.status == 'FAILED' and job.error_code == 'NOT_FOUND'
        assert job.document_id is None and resolve_path(job.source_path)
        assert db.query(Document).count() == 0


def test_exclusion_during_registration_returns_404_without_hidden_document_and_recovers(operator_client, separate_client, db_factory, monkeypatch):
    other = separate_client('operator')
    original = pipeline_service.analyze_document
    started, finish = block_analysis(monkeypatch)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(post_registration, operator_client)
        try:
            assert started.wait(3)
            with db_factory() as db:
                cid = db.query(Contract).one().contract_id
            assert other.delete(f'/api/contracts/{cid}').status_code == 204
        finally:
            finish.set()
        response = pending.result(timeout=10)
    assert response.status_code == 404
    with db_factory() as db:
        assert db.query(Document).count() == 0
        assert json.loads(db.query(RegistrationAttempt).one().receipts_json) == {}
    assert operator_client.post(f'/api/contracts/{cid}/restore', json={'note': '최초 등록을 이어서 처리'}).status_code == 200
    monkeypatch.setattr(pipeline_service, 'analyze_document', original)
    recovered = post_registration(operator_client)
    assert recovered.status_code == 201 and recovered.json()['registration']['complete']
    assert recovered.json()['contract_id'] == cid


def test_legacy_failed_receipt_already_replaced_does_not_republish_old_input(operator_client, db_factory, monkeypatch):
    from test_document_versions import reissue
    first = post_registration(operator_client, document_types=json.dumps(['contract'])).json()
    cid, did = first['contract_id'], first['documents'][0]['document_id']
    with db_factory() as db:
        db.get(Document, did).processing_status = 'FAILED'
        db.commit()
    # A manually supplied different original already repaired this document.
    replaced = reissue(operator_client, cid, did, first['workflow']['revision'])
    assert replaced.status_code == 200, replaced.text
    new_id = replaced.json()[0]['document_id']
    def forbidden(*args, **kwargs):
        pytest.fail('A newer successful version must not be replaced by the old batch bytes')
    monkeypatch.setattr(pipeline_service, 'analyze_document', forbidden)
    retry = post_registration(operator_client, document_types=json.dumps(['contract']))
    assert retry.status_code == 201 and retry.json()['registration']['complete']
    assert [doc['document_id'] for doc in retry.json()['documents']] == [new_id]
    with db_factory() as db:
        assert db.query(Document).count() == 2
        assert json.loads(db.query(RegistrationAttempt).one().receipts_json)['0'] == new_id
