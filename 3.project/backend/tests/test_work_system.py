"""Real API work loops on synthetic, disposable records; no held-out evaluation."""
import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from backend.app.db.models import AuditEvent, CompanySetting, Contract, ContractReview, Document, WorkAssignment
from backend.app.main import app
from test_api import create_contract
from test_document_versions import reissue
from test_payment_records import approved_contract, payment_body
from test_request_bundles import create, patch
from test_review_workflow_api import configured_contract


def surfaces(client, cid):
    detail = client.get(f'/api/contracts/{cid}').json()
    listing = next(c for c in client.get('/api/contracts').json() if c['contract_id'] == cid)
    context = client.get(f'/api/contracts/{cid}/review-context').json()
    work = client.get(f'/api/contracts/{cid}/work-state').json()
    assert listing['stage'] == detail['stage'] == context['stage'] == work['stage']
    assert listing['work_state'] == detail['work_state'] == context['work_state'] == work
    assert work['revision'] == detail['workflow']['revision']
    assert work['fingerprint'] == detail['workflow']['fingerprint'] == listing['fingerprint']
    return detail, work


def test_one_state_across_screens_and_partial_receipt_is_not_document_submission(operator_client, db_factory):
    with db_factory() as db:
        db.add(CompanySetting(key='required_documents', value=json.dumps(['bank_account', 'inspection_confirmation'])))
        db.commit()
    cid = create_contract(operator_client)['contract_id']
    _, before = surfaces(operator_client, cid)
    assert before['stage'] == 'RECEIVING'
    row = create(operator_client, cid, keys=['missing:bank_account'])
    _, waiting = surfaces(operator_client, cid)
    assert waiting['stage'] == 'WAITING'
    assert waiting['waiting_for'] == ['VENDOR']
    assert waiting['counts']['immediate_check_items'] == before['counts']['immediate_check_items'] - 1
    assert waiting['counts']['immediate_check_items'] >= 1  # internal inspection remains
    assert waiting['next_actions'][0]['role'] == 'operator'
    received = patch(operator_client, cid, row, [{'item_id': row['bundle']['items'][0]['item_id'],
                                                'status': 'RECEIVED', 'note': '연락으로 받았다고 확인한 가상 기록'}])
    assert received.status_code == 200, received.text
    detail, after = surfaces(operator_client, cid)
    assert after['stage'] == 'RECEIVING'
    assert after['counts']['missing_document_types'] == 2
    assert not detail['documents']
    assert after['counts']['waiting_requests'] == 0


def test_reissue_v2_v3_return_and_new_review_keep_history_and_current_state(operator_client, separate_client):
    rep, cid, body = configured_contract(operator_client, separate_client)
    assert operator_client.post(f'/api/pilot/contracts/{cid}/approvals', json={**body, 'step': 1}).status_code == 200
    returned = rep.post(f'/api/contracts/{cid}/reviews', json={**body, 'decision': 'RETURNED', 'note': '가상 원문 내용을 다시 확인해 주세요'})
    assert returned.status_code == 200, returned.text
    detail, work = surfaces(operator_client, cid)
    assert work['stage'] == 'CHECK' and work['approval_status'] == 'RETURNED'
    for version in [2, 3]:
        old = detail['documents'][0]
        changed = reissue(operator_client, cid, old['document_id'], detail['workflow']['revision'])
        assert changed.status_code == 200, changed.text
        detail, work = surfaces(operator_client, cid)
        assert detail['documents'][0]['version']['version_number'] == version
        assert work['stage'] == 'APPROVAL' and work['approval_status'] == 'STALE'
        assert work['next_actions'][0]['role'] == 'operator'  # real first approval step
        assert rep.post(f'/api/contracts/{cid}/reviews', json=body).status_code == 409
    timeline = operator_client.get(f'/api/contracts/{cid}/activity', params={'masked': False}).json()
    revisions = [e for e in timeline['items'] if e['type'] == 'DOCUMENT_REISSUED']
    assert [e['data']['version_number'] for e in revisions] == [3, 2]
    assert all(e['data']['previous_fields']['total_amount'] == 110 for e in revisions)
    assert any(e['type'] == 'REPRESENTATIVE_RETURNED' and e['review_id'] for e in timeline['items'])
    assert any(e['type'] == 'RULE_VALIDATION' and e['data']['checks'] for e in timeline['items'])
    new_body = {**body, 'revision': detail['workflow']['revision'], 'fingerprint': detail['workflow']['fingerprint']}
    assert operator_client.post(f'/api/pilot/contracts/{cid}/approvals', json={**new_body, 'step': 1}).status_code == 200
    assert rep.post(f'/api/contracts/{cid}/reviews', json=new_body).status_code == 200
    _, final = surfaces(operator_client, cid)
    assert final['stage'] == 'PAYMENT'


def test_done_payment_returns_to_current_review_after_reissue_without_another_payment(operator_client, separate_client):
    _, cid, body = approved_contract(operator_client, separate_client)
    assert operator_client.post(f'/api/pilot/contracts/{cid}/payment', json=payment_body(body['revision'])).status_code == 201
    detail, work = surfaces(operator_client, cid)
    assert work['stage'] == 'DONE'
    old_fingerprint = detail['workflow']['fingerprint']
    # Operational display metadata does not change the reviewed fingerprint.
    assert operator_client.get(f'/api/contracts/{cid}/activity').json()['fingerprint'] == old_fingerprint
    old = detail['documents'][0]
    assert reissue(operator_client, cid, old['document_id'], body['revision']).status_code == 200
    changed, work = surfaces(operator_client, cid)
    assert work['stage'] == 'APPROVAL'
    assert work['payment_already_recorded'] is True
    assert changed['payment']['status'] == 'RECONFIRMATION_REQUIRED'
    assert changed['payment']['payment_id'] == detail['payment']['payment_id']
    assert changed['workflow']['fingerprint'] != old_fingerprint


def test_unreadable_legacy_metadata_does_not_block_a_valid_reissue(operator_client, separate_client, db_factory):
    _, cid, body = configured_contract(operator_client, separate_client)
    old = operator_client.get(f'/api/contracts/{cid}').json()['documents'][0]
    with db_factory() as db:
        db.get(Document, old['document_id']).extract.raw_fields = '{invalid legacy fields'
        db.commit()
    result = reissue(operator_client, cid, old['document_id'], body['revision'])
    assert result.status_code == 200, result.text
    event = next(e for e in operator_client.get(f'/api/contracts/{cid}/activity').json()['items']
                 if e['type'] == 'DOCUMENT_REISSUED')
    assert event['data']['previous_fields'] is None
    assert event['data']['new_fields']['total_amount'] == 110


def test_activity_keeps_partial_receipt_cancel_and_request_reason_snapshots(operator_client):
    cid = create_contract(operator_client)['contract_id']
    row = create(operator_client, cid, keys=['missing:bank_account', 'missing:tax_invoice'])
    a, b = row['bundle']['items']
    result = patch(operator_client, cid, row, [{'item_id': a['item_id'], 'status': 'RECEIVED', 'note': '통장사본만 받은 가상 회신'}])
    assert result.status_code == 200
    assert patch(operator_client, cid, result.json(), [{'item_id': b['item_id'], 'status': 'CANCELLED', 'note': '가상 요청 대상을 다시 정리함'}]).status_code == 200
    items = operator_client.get(f'/api/contracts/{cid}/activity').json()['items']
    changes = [e for e in items if e['type'] == 'RESUBMISSION_BUNDLE_ITEMS_RESOLVED']
    assert [e['data']['items'][0]['status'] for e in changes] == ['CANCELLED', 'RECEIVED']
    assert changes[1]['data']['items'][0]['note'] == '통장사본만 받은 가상 회신'
    recorded = next(e for e in items if e['type'] == 'RESUBMISSION_BUNDLE_RECORDED')
    assert len(recorded['data']['items']) == 2
    assert recorded['data']['items'][0]['reason']


def test_unverified_source_routes_to_recovery_instead_of_a_blocked_reconfirmation(operator_client, separate_client, db_factory):
    _, cid, body = approved_contract(operator_client, separate_client)
    assert operator_client.post(f'/api/pilot/contracts/{cid}/payment', json=payment_body(body['revision'])).status_code == 201
    detail = operator_client.get(f'/api/contracts/{cid}').json()
    from backend.app.services.storage_service import resolve_path
    with db_factory() as db:
        path = resolve_path(db.get(Document, detail['documents'][0]['document_id']).storage_path)
        path.write_bytes(path.read_bytes() + b'\nsynthetic source tamper')
    _, work = surfaces(operator_client, cid)
    assert work['stage'] != 'DONE'
    assert work['payment_blocked_reason'] == 'SOURCE_VERSION_UNVERIFIED'
    assert [a['code'] for a in work['next_actions']] == ['RESTORE_ORIGINAL']


def test_activity_pagination_is_contract_scoped_stable_and_masks_historical_names(operator_client, db_factory):
    cid = create_contract(operator_client, vendor_name='현재 가상거래처')['contract_id']
    other = create_contract(operator_client, vendor_name='다른 가상거래처')['contract_id']
    with db_factory() as db:
        db.add(AuditEvent(contract_id=cid, actor_name='가상 담당자', action='CONTRACT_UPDATED',
            details=json.dumps({'before': {'vendor_name': '이전 가상거래처'}, 'note': '이전 가상거래처와 220-88-12345 원문 확인'}, ensure_ascii=False)))
        db.add(AuditEvent(contract_id=other, actor_name='다른 사람', action='CONTRACT_UPDATED', details='{}'))
        db.commit()
    first = operator_client.get(f'/api/contracts/{cid}/activity', params={'limit': 1}).json()
    assert first['has_more'] and first['next_before_event_id'] == first['items'][-1]['event_id']
    rendered = json.dumps(first, ensure_ascii=False)
    assert '이전 가상거래처' not in rendered and '220-88-12345' not in rendered
    older = operator_client.get(f'/api/contracts/{cid}/activity', params={'limit': 1, 'before_event_id': first['next_before_event_id']}).json()
    assert older['items'][0]['event_id'] < first['items'][0]['event_id']
    assert all(e['actor_name'] != '다른 사람' for e in first['items'] + older['items'])
    raw = operator_client.get(f'/api/contracts/{cid}/activity', params={'limit': 1, 'masked': False}).json()
    assert raw['items'][0]['data']['before']['vendor_name'] == '이전 가상거래처'
    assert first['fingerprint'] == raw['fingerprint']


def test_masked_activity_keeps_internal_actor_but_masks_details_and_export(operator_client, db_factory, accounts):
    cid = create_contract(operator_client, vendor_name='C업체')['contract_id']
    with db_factory() as db:
        db.add(AuditEvent(contract_id=cid, actor_id=accounts['operator']['user_id'],
            actor_name='C업체 담당자', action='CONTRACT_UPDATED',
            details=json.dumps({'note': 'C업체 220-88-12345 확인',
                                'actor_name': 'C업체가 보낸 문구'}, ensure_ascii=False)))
        db.commit()
    masked = operator_client.get(f'/api/contracts/{cid}/activity').json()
    event = masked['items'][0]
    assert event['actor_name'] == 'C업체 담당자'
    assert event['actor_id'] == accounts['operator']['user_id']
    assert 'C업체' not in json.dumps(event['data'], ensure_ascii=False)
    assert '220-88-12345' not in json.dumps(event['data'], ensure_ascii=False)
    raw = operator_client.get(f'/api/contracts/{cid}/activity', params={'masked': False}).json()
    assert raw['items'][0]['actor_name'] == event['actor_name']
    assert raw['items'][0]['data']['note'] == 'C업체 220-88-12345 확인'
    # A timeline-specific exemption must not spread to shared ZIP redaction.
    from backend.app.services.contract_export_service import public_data
    assert 'C업체' not in public_data({'actor_name': event['actor_name']}, True,
                                    {'vendor_name': 'C업체'})['actor_name']


def test_activity_masks_a_name_only_preserved_in_a_historical_review_snapshot(operator_client, db_factory, accounts):
    cid = create_contract(operator_client, vendor_name='현재 이름')['contract_id']
    with db_factory() as db:
        db.add(ContractReview(contract_id=cid, revision=1, actor_id=accounts['representative']['user_id'],
            actor_name='가상 대표', decision='RETURNED', note='가상 과거 기록',
            snapshot_json=json.dumps({'contract': {'vendor_name': '아주 이전 가상거래처'}}, ensure_ascii=False)))
        db.add(AuditEvent(contract_id=cid, actor_name='가상 담당자', action='CONTRACT_UPDATED',
            details=json.dumps({'note': '아주 이전 가상거래처 자료를 회수했습니다'}, ensure_ascii=False)))
        db.commit()
    result = operator_client.get(f'/api/contracts/{cid}/activity').json()
    assert '아주 이전 가상거래처' not in json.dumps(result, ensure_ascii=False)
    raw = operator_client.get(f'/api/contracts/{cid}/activity', params={'masked': False}).json()
    assert '아주 이전 가상거래처' in json.dumps(raw, ensure_ascii=False)


def test_new_read_apis_do_not_extract_revalidate_or_write_audit(operator_client, db_factory, monkeypatch):
    cid = create_contract(operator_client)['contract_id']
    from backend.app.services import pipeline_service
    def forbidden(*args, **kwargs):
        pytest.fail('read-only work APIs must not extract or publish validation')
    monkeypatch.setattr(pipeline_service, 'analyze_document', forbidden)
    monkeypatch.setattr(pipeline_service.PipelineService, 'revalidate_contract', forbidden)
    with db_factory() as db:
        before = db.query(AuditEvent).count()
    for path in [f'/api/contracts/{cid}/work-state', f'/api/contracts/{cid}/activity', '/api/contracts/search']:
        assert operator_client.get(path).status_code == 200
    with db_factory() as db:
        assert db.query(AuditEvent).count() == before


@pytest.mark.parametrize('path', ['work-state', 'activity'])
def test_work_reads_guard_revision_fingerprint_and_missing_contract(operator_client, path):
    cid = create_contract(operator_client)['contract_id']
    url = f'/api/contracts/{cid}/{path}'
    assert operator_client.get(url, params={'revision': 999}).status_code == 409
    assert operator_client.get(url, params={'fingerprint': '0' * 64}).status_code == 409
    assert operator_client.get(f'/api/contracts/999999/{path}').status_code == 404


def test_search_literal_text_amount_internal_id_and_state(operator_client):
    a = create_contract(operator_client, title='계약 %_ 특수문자', vendor_name='가상 새봄기획', contract_amount=2090000)
    b = create_contract(operator_client, title='다른 자료 검토', vendor_name='다른 가상업체')
    for q in ['%_', '새봄', '2090000', '2,090,000원']:
        result = operator_client.get('/api/contracts/search', params={'q': q}).json()
        assert [c['contract_id'] for c in result['items']] == [a['contract_id']]
    result = operator_client.get('/api/contracts/search', params={'q': str(b['contract_id'])}).json()
    assert b['contract_id'] in [c['contract_id'] for c in result['items']]
    assert operator_client.get('/api/contracts/search', params={'stage': 'DONE'}).json()['total'] == 0
    result = operator_client.get('/api/contracts/search', params={'completion': 'OPEN', 'limit': 1, 'offset': 1}).json()
    assert result['total'] == 2 and len(result['items']) == 1


def test_search_period_uses_korean_calendar_day_and_registrant_is_not_assignee(operator_client, db_factory, accounts):
    ids = [create_contract(operator_client, title=f'기간 검토 {i}')['contract_id'] for i in range(3)]
    with db_factory() as db:
        db.get(Contract, ids[0]).created_at = datetime(2026, 10, 4, 14, 59, 59)
        db.get(Contract, ids[1]).created_at = datetime(2026, 10, 4, 15)
        db.get(Contract, ids[2]).created_at = datetime(2026, 10, 5, 15)
        db.get(Contract, ids[1]).user_id = accounts['representative']['user_id']
        db.commit()
    result = operator_client.get('/api/contracts/search', params={'date_from': '2026-10-05', 'date_to': '2026-10-05'}).json()
    assert [c['contract_id'] for c in result['items']] == [ids[1]]
    assert result['date_basis'] == 'CONTRACT_CREATED_AT_ASIA_SEOUL'
    result = operator_client.get('/api/contracts/search', params={'registered_by_user_id': accounts['representative']['user_id']}).json()
    assert [c['contract_id'] for c in result['items']] == [ids[1]]
    assert operator_client.get('/api/contracts/search', params={'assignee_id': accounts['representative']['user_id']}).json()['total'] == 0
    with db_factory() as db:
        db.add(WorkAssignment(contract_id=ids[0], contract_revision=1, contract_fingerprint='0' * 64,
            assigner_id=accounts['operator']['user_id'], assigner_name='가상 맡긴 사람',
            assignee_id=accounts['representative']['user_id'], assignee_name='가상 맡은 사람',
            title='가상 진행 중 확인', status='IN_PROGRESS'))
        db.add(WorkAssignment(contract_id=ids[2], contract_revision=1, contract_fingerprint='0' * 64,
            assigner_id=accounts['operator']['user_id'], assigner_name='가상 맡긴 사람',
            assignee_id=accounts['representative']['user_id'], assignee_name='가상 맡은 사람',
            title='가상 완료한 확인', status='COMPLETED'))
        db.commit()
    result = operator_client.get('/api/contracts/search', params={'assignee_id': accounts['representative']['user_id']}).json()
    assert [c['contract_id'] for c in result['items']] == [ids[0]]


@pytest.mark.parametrize('params', [{'stage': 'UNKNOWN'}, {'completion': 'UNKNOWN'},
                                  {'date_from': '2026-10-06', 'date_to': '2026-10-05'},
                                  {'limit': 201}, {'offset': -1}])
def test_search_rejects_invalid_filters(operator_client, params):
    assert operator_client.get('/api/contracts/search', params=params).status_code == 422


def test_new_apis_require_login(operator_client):
    with TestClient(app) as anonymous:
        for path in ['/api/contracts/search', '/api/contracts/1/activity', '/api/contracts/1/work-state']:
            assert anonymous.get(path).status_code == 401
