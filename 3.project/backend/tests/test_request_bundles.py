"""Synthetic request bundles preserve facts without extraction or sending."""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from uuid import uuid4

import pytest

from backend.app.db.models import (AuditEvent, Document, RequestBundle, RequestBundleItem,
                                   ResubmissionRequest, UserProfile)
from backend.app.services import request_bundle_service as service
from test_api import create_contract
from test_document_versions import reissue
from test_review_workflow_api import upload


def context(client, cid):
    response = client.get(f'/api/pilot/contracts/{cid}/resubmission-bundle-context')
    assert response.status_code == 200, response.text
    return response.json()


def body(client, cid, keys=None, **extra):
    c = context(client, cid)
    keys = keys or [item['issue_key'] for item in c['vendor_candidates']]
    return {'revision': c['revision'], 'fingerprint': c['fingerprint'], 'idempotency_key': str(uuid4()),
            'contact_method': 'EMAIL', 'memo': '가상 계약의 누락·보완 서류를 한 번에 요청한 기록',
            'items': [{'issue_key': key} for key in keys], **extra}


def create(client, cid, payload=None, keys=None):
    payload = payload or body(client, cid, keys)
    response = client.post(f'/api/pilot/contracts/{cid}/resubmission-bundles', json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def resolution(client, cid, row, changes, **extra):
    c = context(client, cid)
    return {'revision': c['revision'], 'fingerprint': c['fingerprint'],
            'request_revision': row['bundle']['request_revision'], 'items': changes, **extra}


def patch(client, cid, row, changes, **extra):
    return client.patch(f'/api/pilot/contracts/{cid}/resubmission-bundles/{row["request_id"]}/items',
        json=resolution(client, cid, row, changes, **extra))


def contract(client):
    return create_contract(client, vendor_name='가상 검증업체', contract_amount=220)['contract_id']


def upload_kind(client, cid, kind):
    titles = {'contract': '외주 용역 계약서', 'business_registration': '사업자등록증',
              'tax_invoice': '전자세금계산서'}
    text = titles[kind] + '\n상호: 가상 검증업체\n사업자등록번호: 220-88-12345\n공급가액: 100원\n세액: 10원\n합계금액: 110원\n전액 청구\n'
    response = client.post(f'/api/contracts/{cid}/documents',
        files=[('files', (kind+'.txt', text.encode(), 'text/plain'))])
    assert response.status_code == 200, response.text
    assert response.json()[0]['document_type'] == kind


def test_six_kinds_three_missing_and_legacy_reads_remain_compatible(operator_client):
    cid = contract(operator_client)
    for kind in ('contract', 'business_registration', 'tax_invoice'):
        upload_kind(operator_client, cid, kind)
    c = context(operator_client, cid)
    assert c['document_counts'] == {'required': 6, 'received': 3, 'missing': 3}
    missing_vendor = {i['issue_key'] for i in c['vendor_candidates'] if i['document_id'] is None}
    assert missing_vendor == {'missing:estimate', 'missing:bank_account'}
    assert any(i['issue_key'] == 'missing:inspection_confirmation' for i in c['internal_items'])
    assert all(check['rule_id'] != 'BUSINESS_STATUS' for item in c['internal_items'] for check in item['checks'])
    assert len(c['notices']) == 1 and c['notices'][0]['requires_action'] is False
    row = create(operator_client, cid, keys=sorted(missing_vendor))
    assert row['bundle']['counts'] == {'total': 2, 'waiting': 2, 'received': 0, 'cancelled': 0}
    legacy = operator_client.post(f'/api/pilot/contracts/{cid}/resubmission-requests',
        json={'contact_method': 'PHONE', 'memo': '기존 자유 메모 요청 기록'})
    assert legacy.status_code == 201 and legacy.json()['bundle'] is None
    listed = operator_client.get(f'/api/pilot/contracts/{cid}/resubmission-requests').json()
    assert {i['request_id'] for i in listed} == {row['request_id'], legacy.json()['request_id']}
    c = context(operator_client, cid)
    assert c['legacy_pending_request_count'] == 1 and len(c['pending_items']) == 2


@pytest.mark.parametrize('missing_amount', [False, True])
def test_only_fail_reasons_go_to_vendor_while_reading_stays_separate(operator_client, db_factory, missing_amount):
    cid = contract(operator_client)
    doc = upload(operator_client, cid, 'estimate')
    with db_factory() as db:
        stored = db.get(Document, doc['document_id'])
        values = json.loads(stored.extract.raw_fields)
        values['business_registration_no'] = '220-88-99999' if missing_amount else None
        if missing_amount:
            for key in ('amount', 'total_amount', 'supply_amount', 'tax_amount'):
                values[key] = None
        stored.extract.raw_fields = json.dumps(values, ensure_ascii=False)
        db.commit()
    c = context(operator_client, cid)
    candidate = next(i for i in c['vendor_candidates'] if i['document_id'] == doc['document_id'])
    reading = next(i for i in c['reading_items'] if i['document_id'] == doc['document_id'])
    assert all(check['status'] == 'FAIL' for check in candidate['checks'])
    assert all(check['status'] == 'REVIEW' for check in reading['checks'])
    assert candidate['reason'] == '\n'.join(check['message'] for check in candidate['checks'])
    assert candidate['requires_original_review'] is True
    payload = body(operator_client, cid, [candidate['issue_key']])
    path = f'/api/pilot/contracts/{cid}/resubmission-bundles'
    assert operator_client.post(path, json=payload).status_code == 400
    payload['items'][0]['reviewed_original'] = True
    row = create(operator_client, cid, payload)
    item = row['bundle']['items'][0]
    assert item['reason'] == candidate['reason'] and item['snapshot']['checks'] == candidate['checks']
    assert item['snapshot']['document']['version'] == doc['version']


@pytest.mark.parametrize('problem', ['missing_source', 'changed_source', 'failed', 'unknown'])
def test_unavailable_original_or_type_cannot_be_overridden_by_acknowledgment(operator_client, db_factory, problem):
    from backend.app.services.storage_service import resolve_path
    cid = contract(operator_client)
    doc = upload(operator_client, cid, 'estimate')
    with db_factory() as db:
        stored = db.get(Document, doc['document_id'])
        source = resolve_path(stored.storage_path)
        if problem == 'missing_source':
            source.unlink()
        elif problem == 'changed_source':
            source.write_bytes(source.read_bytes() + b' changed unit bytes')
        elif problem == 'failed':
            stored.processing_status = 'FAILED'
        else:
            stored.document_type = 'unknown'
        db.commit()
    c = context(operator_client, cid)
    assert not any(i['document_id'] == doc['document_id'] for i in c['vendor_candidates'])
    assert any(i['document_id'] == doc['document_id'] for i in c['internal_items'])
    payload = body(operator_client, cid, [f'document:{doc["version"]["logical_document_id"]}'])
    payload['items'][0]['reviewed_original'] = True
    assert operator_client.post(f'/api/pilot/contracts/{cid}/resubmission-bundles', json=payload).status_code == 400


def test_internal_and_reading_items_are_not_implicitly_sent(operator_client):
    cid = contract(operator_client)
    doc = upload(operator_client, cid, 'estimate')
    payload = body(operator_client, cid, ['missing:inspection_confirmation'])
    assert operator_client.post(f'/api/pilot/contracts/{cid}/resubmission-bundles', json=payload).status_code == 400
    assert context(operator_client, cid)['internal_items']


def test_partial_reply_remains_waiting_until_all_items_and_does_not_change_checks(operator_client, db_factory):
    cid = contract(operator_client)
    before = operator_client.get(f'/api/contracts/{cid}').json()
    row = create(operator_client, cid, keys=['missing:contract', 'missing:estimate', 'missing:bank_account'])
    first, second, third = row['bundle']['items']
    legacy_close = operator_client.patch(f'/api/pilot/contracts/{cid}/resubmission-requests/{row["request_id"]}',
        json={'status': 'RECEIVED', 'note': '전체 종료 우회 시도'})
    assert legacy_close.status_code == 409
    partial = patch(operator_client, cid, row, [{'item_id': first['item_id'], 'status': 'RECEIVED', 'note': '계약서 회신만 수령'}])
    assert partial.status_code == 200, partial.text
    row = partial.json()
    assert row['status'] == 'WAITING_RESPONSE' and row['resolved_at'] is None
    assert row['bundle']['request_revision'] == 2
    assert row['bundle']['counts'] == {'total': 3, 'waiting': 2, 'received': 1, 'cancelled': 0}
    context_response = operator_client.get(f'/api/contracts/{cid}/review-context').json()
    assert context_response['follow_up']['waiting_count'] == 1
    assert len(context(operator_client, cid)['pending_items']) == 2
    assert operator_client.get('/api/contracts').json()[0]['waiting_request_count'] == 1
    complete = patch(operator_client, cid, row, [
        {'item_id': second['item_id'], 'status': 'RECEIVED', 'note': '견적서 회신 수령'},
        {'item_id': third['item_id'], 'status': 'CANCELLED', 'note': '통장사본 요청 취소'}])
    assert complete.status_code == 200 and complete.json()['status'] == 'RECEIVED'
    assert complete.json()['bundle']['request_revision'] == 3 and complete.json()['resolved_at']
    after = operator_client.get(f'/api/contracts/{cid}').json()
    assert after['checks'] == before['checks'] and after['workflow'] == before['workflow']
    assert operator_client.get('/api/contracts').json()[0]['waiting_request_count'] == 0
    with db_factory() as db:
        assert db.query(ResubmissionRequest).count() == 1
        assert db.query(AuditEvent).filter_by(action='RESUBMISSION_BUNDLE_RECORDED').count() == 1
        assert db.query(AuditEvent).filter_by(action='RESUBMISSION_BUNDLE_ITEMS_RESOLVED').count() == 2


def test_all_cancelled_and_closed_item_changes_rejected(operator_client):
    cid = contract(operator_client)
    row = create(operator_client, cid, keys=['missing:bank_account'])
    changes = [{'item_id': row['bundle']['items'][0]['item_id'], 'status': 'CANCELLED', 'note': '요청 취소 사유'}]
    completed = patch(operator_client, cid, row, changes)
    assert completed.status_code == 200 and completed.json()['status'] == 'CANCELLED'
    assert patch(operator_client, cid, completed.json(), changes).status_code == 409


def test_idempotent_replay_survives_changed_contract_and_partial_reply(operator_client):
    cid = contract(operator_client)
    payload = body(operator_client, cid, ['missing:contract', 'missing:bank_account'])
    row = create(operator_client, cid, payload)
    partial = patch(operator_client, cid, row, [{'item_id': row['bundle']['items'][0]['item_id'],
        'status': 'RECEIVED', 'note': '일부 회신만 수령'}])
    assert partial.status_code == 200
    changed = operator_client.put(f'/api/contracts/{cid}', json={'title': '자료 기준 변경됨',
        'revision': payload['revision'], 'change_note': '요청 기록 이후 계약 변경'})
    assert changed.status_code == 200
    replay = operator_client.post(f'/api/pilot/contracts/{cid}/resubmission-bundles', json=payload)
    assert replay.status_code == 200 and replay.json() == partial.json()
    assert operator_client.post(f'/api/pilot/contracts/{cid}/resubmission-bundles',
        json={**payload, 'memo': '같은 키지만 다른 내용'}).status_code == 409
    stale = {**payload, 'idempotency_key': str(uuid4())}
    assert operator_client.post(f'/api/pilot/contracts/{cid}/resubmission-bundles', json=stale).status_code == 409


def test_omitted_day_and_today_deadline_replay_after_midnight_but_new_past_deadline_rejected(operator_client, monkeypatch):
    from backend.app.api import workflow
    class Clock(datetime):
        day = 5
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, cls.day, 12, tzinfo=tz)
    monkeypatch.setattr(workflow, 'datetime', Clock)
    cid = contract(operator_client)
    payload = body(operator_client, cid, ['missing:bank_account'], due_on='2026-10-05')
    row = create(operator_client, cid, payload)
    assert row['requested_on'] == '2026-10-05'
    Clock.day = 6
    replay = operator_client.post(f'/api/pilot/contracts/{cid}/resubmission-bundles', json=payload)
    assert replay.status_code == 200 and replay.json()['request_id'] == row['request_id']
    new = operator_client.post(f'/api/pilot/contracts/{cid}/resubmission-bundles',
        json={**payload, 'idempotency_key': str(uuid4())})
    assert new.status_code == 422


def test_pending_duplicates_share_logical_document_across_reissue_but_separate_add_allowed(operator_client, separate_client):
    cid = contract(operator_client)
    doc = upload(operator_client, cid, 'estimate')
    key = f'document:{doc["version"]["logical_document_id"]}'
    payload = body(operator_client, cid, [key], items=[{'issue_key': key, 'reviewed_original': True}])
    row = create(operator_client, cid, payload)
    other = separate_client('representative')
    assert other.post(f'/api/pilot/contracts/{cid}/resubmission-bundles',
        json={**payload, 'idempotency_key': str(uuid4())}).status_code == 409
    current = context(operator_client, cid)
    replaced = reissue(operator_client, cid, doc['document_id'], current['revision'], text=doc['raw_text'])
    assert replaced.status_code == 200, replaced.text
    c = context(operator_client, cid)
    candidate = next(i for i in c['vendor_candidates'] if i['issue_key'] == key)
    assert candidate['document_id'] == replaced.json()[0]['document_id'] and candidate['already_requested']
    newer = body(operator_client, cid, [key], items=[{'issue_key': key, 'reviewed_original': True}])
    assert operator_client.post(f'/api/pilot/contracts/{cid}/resubmission-bundles', json=newer).status_code == 409
    added = upload(operator_client, cid, 'estimate')
    different_key = f'document:{added["version"]["logical_document_id"]}'
    assert different_key != key
    create(operator_client, cid, body(operator_client, cid, [different_key], items=[{'issue_key': different_key, 'reviewed_original': True}]))
    resolved = patch(operator_client, cid, row, [{'item_id': row['bundle']['items'][0]['item_id'],
        'status': 'CANCELLED', 'note': '이전 요청을 닫고 현재본에서 다시 요청'}])
    assert resolved.status_code == 200
    create(operator_client, cid, body(operator_client, cid, [key], items=[{'issue_key': key, 'reviewed_original': True}]))


def test_optimistic_guards_batch_rollback_and_wrong_ids(operator_client):
    cid = contract(operator_client)
    row = create(operator_client, cid, keys=['missing:contract', 'missing:bank_account'])
    first, second = row['bundle']['items']
    change = {'item_id': first['item_id'], 'status': 'RECEIVED', 'note': '계약서 회신 수령'}
    assert patch(operator_client, cid, row, [change], request_revision=99).status_code == 409
    assert patch(operator_client, cid, row, [change], revision=99).status_code == 409
    assert patch(operator_client, cid, row, [change], fingerprint='f' * 64).status_code == 409
    assert patch(operator_client, cid, row, [change, {**change, 'item_id': 99999}]).status_code == 404
    unchanged = operator_client.get(f'/api/pilot/contracts/{cid}/resubmission-requests').json()[0]
    assert unchanged == row
    assert patch(operator_client, cid, row, [change, change]).status_code == 422
    other_cid = contract(operator_client)
    assert patch(operator_client, other_cid, row, [change]).status_code == 404
    assert patch(operator_client, cid, row, [change]).status_code == 200
    assert patch(operator_client, cid, row, [{**change, 'item_id': second['item_id']}]).status_code == 409


def test_simultaneous_creation_and_partial_revision_collision(operator_client, separate_client, db_factory):
    cid = contract(operator_client)
    payload = body(operator_client, cid, ['missing:contract', 'missing:bank_account'])
    other = separate_client('operator')
    path = f'/api/pilot/contracts/{cid}/resubmission-bundles'
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(client.post, path, json=payload) for client in (operator_client, other)]
        results = [future.result(timeout=10) for future in futures]
    assert sorted(response.status_code for response in results) == [200, 201]
    row = results[0].json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(patch, client, cid, row,
            [{'item_id': item['item_id'], 'status': 'RECEIVED', 'note': '동시 회신 처리'}])
            for client, item in zip((operator_client, other), row['bundle']['items'])]
        results = [future.result(timeout=10) for future in futures]
    assert sorted(response.status_code for response in results) == [200, 409]
    with db_factory() as db:
        assert db.query(RequestBundle).count() == 1
        assert db.query(RequestBundleItem).filter_by(status='RECEIVED').count() == 1


def test_audit_and_item_publication_are_atomic_when_commit_fails(operator_client, db_factory, monkeypatch):
    cid = contract(operator_client)
    payload = body(operator_client, cid, ['missing:contract', 'missing:bank_account'])
    original = db_factory.class_.commit
    def fail_commit(db):
        if any(isinstance(row, AuditEvent) and row.action == 'RESUBMISSION_BUNDLE_RECORDED' for row in db.new):
            raise RuntimeError('Synthetic database publication failure')
        return original(db)
    monkeypatch.setattr(db_factory.class_, 'commit', fail_commit)
    with pytest.raises(RuntimeError, match='Synthetic database publication failure'):
        operator_client.post(f'/api/pilot/contracts/{cid}/resubmission-bundles', json=payload)
    with db_factory() as db:
        assert db.query(ResubmissionRequest).count() == db.query(RequestBundle).count() == db.query(RequestBundleItem).count() == 0
        assert db.query(AuditEvent).filter_by(action='RESUBMISSION_BUNDLE_RECORDED').count() == 0


def test_authentication_roles_and_contract_delete_cascade(operator_client, accounts, db_factory):
    cid = contract(operator_client)
    payload = body(operator_client, cid, ['missing:bank_account'])
    row = create(operator_client, cid, payload)
    with db_factory() as db:
        db.get(UserProfile, accounts['operator']['user_id']).role = 'viewer'
        db.commit()
    assert operator_client.post(f'/api/pilot/contracts/{cid}/resubmission-bundles', json=payload).status_code == 403
    with db_factory() as db:
        db.get(UserProfile, accounts['operator']['user_id']).role = 'operator'
        db.commit()
    assert operator_client.delete(f'/api/contracts/{cid}').status_code == 204
    with db_factory() as db:
        assert db.query(RequestBundle).count() == db.query(RequestBundleItem).count() == 0
    operator_client.post('/api/auth/logout')
    assert operator_client.get(f'/api/pilot/contracts/{cid}/resubmission-bundle-context').status_code == 401
    assert operator_client.post(f'/api/pilot/contracts/{cid}/resubmission-bundles', json=payload).status_code == 401


@pytest.mark.parametrize('patch_data', [
    {'items': []}, {'items': [{'issue_key': 'missing:contract'}] * 2},
    {'items': [{'issue_key': 'missing:contract', 'reason': '임의 서버사유 덮어쓰기'}]},
    {'items': [{'issue_key': 'missing:contract', 'reviewed_original': 1}]},
    {'items': [{'issue_key': f'missing:unknown{i}'} for i in range(31)]},
    {'revision': True}, {'fingerprint': 'not-a-hash'}, {'idempotency_key': '   '},
    {'memo': '   '}, {'memo': 'x' * 2001}, {'contact_method': 'EXTERNAL_API'},
])
def test_bundle_request_validation(operator_client, patch_data):
    cid = contract(operator_client)
    payload = body(operator_client, cid, ['missing:contract'])
    assert operator_client.post(f'/api/pilot/contracts/{cid}/resubmission-bundles', json={**payload, **patch_data}).status_code == 422
