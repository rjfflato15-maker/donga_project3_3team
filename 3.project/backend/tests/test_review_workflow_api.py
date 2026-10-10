"""Workflow APIs run against temporary company data, never heldout documents."""
import json
import pytest
from backend.app.db.models import Document, AuditEvent, ResubmissionRequest
from test_api import create_contract

def upload(client, cid, kind='contract'):
    text = ('외주 용역 계약서' if kind == 'contract' else '견적서') + '\n상호: 가상 검증업체\n사업자등록번호: 220-88-12345\n공급가액: 100원\n세액: 10원\n합계금액: 110원\n전액 청구\n'
    result = client.post(f'/api/contracts/{cid}/documents', files=[('files', ('fixture.txt', text.encode('utf-8'), 'text/plain'))], data={'target_document_type': kind})
    assert result.status_code == 200, result.text
    return result.json()[0]

def configured_contract(operator_client, separate_client, first_role='operator'):
    representative = separate_client('representative')
    policy = representative.get('/api/pilot/company-policy/presets').json()[2]
    policy['required_document_types'] = ['contract']
    policy['approval_steps'][0]['role'] = first_role
    result = representative.put('/api/pilot/company-policy', json=policy)
    assert result.status_code == 200, result.text
    c = create_contract(operator_client, contract_amount=110, vendor_name='가상 검증업체')
    upload(operator_client, c['contract_id'])
    from submission_helpers import complete_source_review, submit_ready
    detail = complete_source_review(operator_client, c['contract_id'])
    if first_role == 'representative':
        detail = submit_ready(operator_client, c['contract_id'])
    body = {'decision': 'CONFIRMED', 'note': '국세청 미연동 항목은 원문으로 직접 검토한 단위 테스트', 'acknowledge_unverified': True, 'revision': detail['workflow']['revision'], 'fingerprint': detail['workflow']['fingerprint']}
    return (representative, c['contract_id'], body)

def test_followup_records_waiting_state_without_sending_or_changing_rule_status(operator_client, separate_client, db_factory):
    c = create_contract(operator_client)
    cid = c['contract_id']
    before = operator_client.get(f'/api/contracts/{cid}').json()
    representative = separate_client('representative')
    r = representative.post(f'/api/pilot/contracts/{cid}/resubmission-requests', json={'contact_method': 'KAKAO', 'requested_on': '2026-10-02', 'due_on': '2026-10-05', 'memo': '가상 사례의 누락 통장사본을 요청했다고 기록'})
    assert r.status_code == 201, r.text
    assert r.json()['status'] == 'WAITING_RESPONSE'
    context = operator_client.get(f'/api/contracts/{cid}/review-context').json()
    assert context['follow_up']['waiting_count'] == 1 and '회신 대기 1건' in context['action_summary']
    after = operator_client.get(f'/api/contracts/{cid}').json()
    assert after['workflow']['revision'] == before['workflow']['revision']
    assert after['checks'] == before['checks']
    rid = r.json()['request_id']
    resolved = operator_client.patch(f'/api/pilot/contracts/{cid}/resubmission-requests/{rid}', json={'status': 'RECEIVED', 'note': '원문 파일 회신 확인'})
    assert resolved.status_code == 200 and resolved.json()['resolved_at']
    assert operator_client.get(f'/api/contracts/{cid}/review-context').json()['follow_up']['waiting_count'] == 0
    assert operator_client.patch(f'/api/pilot/contracts/{cid}/resubmission-requests/{rid}', json={'status': 'CANCELLED', 'note': '중복 처리'}).status_code == 409
    with db_factory() as db:
        assert db.query(ResubmissionRequest).count() == 1
        assert db.query(AuditEvent).filter_by(action='RESUBMISSION_REQUEST_RECORDED').count() == 1

@pytest.mark.parametrize('patch', [{'contact_method': 'SLACK'}, {'due_on': '2026-10-01'}, {'memo': '   '}])
def test_request_rejects_invalid_channel_dates_or_blank_memo(operator_client, patch):
    c = create_contract(operator_client)
    body = {'contact_method': 'EMAIL', 'requested_on': '2026-10-02', 'memo': 'fixture', **patch}
    assert operator_client.post(f"/api/pilot/contracts/{c['contract_id']}/resubmission-requests", json=body).status_code == 422

def test_request_is_bound_to_contract_and_requires_login(operator_client, separate_client):
    a = create_contract(operator_client)
    b = create_contract(operator_client)
    r = operator_client.post(f"/api/pilot/contracts/{a['contract_id']}/resubmission-requests", json={'contact_method': 'PHONE', 'memo': 'fixture'}).json()
    assert operator_client.patch(f"/api/pilot/contracts/{b['contract_id']}/resubmission-requests/{r['request_id']}", json={'status': 'RECEIVED', 'note': 'other contract'}).status_code == 404
    operator_client.post('/api/auth/logout')
    assert operator_client.get(f"/api/contracts/{a['contract_id']}/review-context").status_code == 401

def test_company_policy_permissions_limit_and_old_settings_compatibility(operator_client, separate_client):
    representative = separate_client('representative')
    policy = representative.get('/api/pilot/company-policy').json()
    assert operator_client.put('/api/pilot/company-policy', json=policy).status_code == 403
    bad = {**policy, 'approval_steps': policy['approval_steps'] * 3}
    assert representative.put('/api/pilot/company-policy', json=bad).status_code == 422
    bad = {**policy, 'approval_steps': [{'role': 'operator', 'label': 'final'}]}
    assert representative.put('/api/pilot/company-policy', json=bad).status_code == 422
    bad = {**policy, 'roles': {'operator': '담당자', 'representative': '대표', 'superuser': '전체'}}
    assert representative.put('/api/pilot/company-policy', json=bad).status_code == 422
    assert representative.put('/api/pilot/settings', json={'company_name': '가상 회사', 'required_document_types': ['contract']}).status_code == 200
    assert representative.get('/api/pilot/company-policy').json()['required_document_types'] == ['contract']

def test_two_step_approval_prevents_old_api_bypass_and_enforces_roles(operator_client, separate_client):
    representative, cid, body = configured_contract(operator_client, separate_client)
    assert representative.post(f'/api/contracts/{cid}/reviews', json=body).status_code == 409
    assert representative.post(f'/api/pilot/contracts/{cid}/approvals', json={**body, 'step': 1}).status_code == 403
    first = operator_client.post(f'/api/pilot/contracts/{cid}/approvals', json={**body, 'step': 1})
    assert first.status_code == 200, first.text
    assert first.json()['completed_steps'] == 1 and first.json()['next_step'] == 2
    assert '2단계 결재 대기' in operator_client.get(f'/api/contracts/{cid}/review-context').json()['action_summary']
    assert operator_client.post(f'/api/pilot/contracts/{cid}/approvals', json={**body, 'step': 1}).status_code == 409
    final = representative.post(f'/api/contracts/{cid}/reviews', json=body)
    assert final.status_code == 200, final.text
    assert final.json()['workflow']['approval_status'] == 'CONFIRMED'
    assert representative.get(f'/api/pilot/contracts/{cid}/approvals').json()['completed_steps'] == 2
    context = operator_client.get(f'/api/contracts/{cid}/review-context').json()
    assert '최종 확인 완료' in context['action_summary']
    assert '담당자 최종 확인 필요' not in context['action_summary']

def test_two_step_approval_requires_different_people(operator_client, separate_client):
    representative, cid, body = configured_contract(operator_client, separate_client, first_role='representative')
    assert representative.post(f'/api/pilot/contracts/{cid}/approvals', json={**body, 'step': 1}).status_code == 200
    assert representative.post(f'/api/contracts/{cid}/reviews', json=body).status_code == 403

@pytest.mark.parametrize('change', ['edit', 'return'])
def test_revision_change_or_return_invalidates_prior_stage(operator_client, separate_client, change):
    representative, cid, body = configured_contract(operator_client, separate_client)
    assert operator_client.post(f'/api/pilot/contracts/{cid}/approvals', json={**body, 'step': 1}).status_code == 200
    if change == 'edit':
        assert operator_client.put(f'/api/contracts/{cid}', json={'title': '변경된 계약', 'revision': body['revision'], 'change_note': '새 자료로 검토'}).status_code == 200
        d = operator_client.get(f'/api/contracts/{cid}').json()
        body.update(revision=d['workflow']['revision'], fingerprint=d['workflow']['fingerprint'])
    else:
        assert representative.post(f'/api/contracts/{cid}/reviews', json={**body, 'decision': 'RETURNED'}).status_code == 200
    assert representative.post(f'/api/contracts/{cid}/reviews', json=body).status_code == 409

def test_provenance_preserves_rejected_ai_and_does_not_attach_old_anchor_to_human_value(operator_client, db_factory):
    c = create_contract(operator_client, contract_amount=110)
    doc = upload(operator_client, c['contract_id'], 'estimate')
    did = doc['document_id']
    with db_factory() as db:
        d = db.get(Document, did)
        values = json.loads(d.extract.raw_fields)
        values.update(total_amount=110, tax_amount=10)
        values['ai_review'] = {'status': 'COMPLETED', 'manual_review_required': True, 'human_confirmed': False, 'decisions': [{'field': 'total_amount', 'accepted': True, 'applied': True, 'reasons': [], 'proposal': {'state': 'VALUE', 'value': '110'}, 'anchor': {'page': None, 'line': 6, 'quote': '합계금액: 110원'}}, {'field': 'tax_amount', 'accepted': False, 'applied': False, 'reasons': ['FIELD_LABEL_OR_VALUE_MISMATCH'], 'proposal': {'state': 'VALUE', 'value': '110'}}]}
        d.extract.raw_fields = json.dumps(values, ensure_ascii=False)
        db.commit()
    result = operator_client.get(f'/api/documents/{did}/provenance')
    assert result.status_code == 200, result.text
    fields = result.json()['fields']
    assert fields['total_amount']['source'] == 'AI_SUPPLEMENT'
    assert fields['tax_amount']['source'] == 'RULE' and fields['tax_amount']['ai_decision']['accepted'] is False
    assert fields['total_amount']['evidence'] and fields['total_amount']['evidence'][0]['quote'] == '합계금액: 110원'
    context = operator_client.get(f"/api/contracts/{c['contract_id']}/review-context").json()
    assert any((row['rule_id'] == 'AMOUNT_MATCH_ESTIMATE' and row['evidence'] for row in context['checks']))
    revision = context['revision']
    values = operator_client.get(f'/api/documents/{did}').json()['analysis']['fields']
    values['total_amount'] = 121
    corrected = operator_client.put(f'/api/documents/{did}/fields', json={'fields': values, 'document_type': 'estimate', 'revision': revision, 'note': '단위 테스트 원문 재확인 기록'})
    assert corrected.status_code == 200, corrected.text
    result = operator_client.get(f'/api/documents/{did}/provenance').json()['fields']['total_amount']
    assert result['source'] == 'HUMAN_CONFIRMATION' and result['human_confirmation']
    assert result['evidence'] == [] and result['ai_decision']['proposal']['value'] == '110'

def test_deleting_contract_cleans_new_operational_rows(operator_client):
    c = create_contract(operator_client)
    assert operator_client.post(f"/api/pilot/contracts/{c['contract_id']}/resubmission-requests", json={'contact_method': 'OTHER', 'memo': 'fixture'}).status_code == 201
    assert operator_client.delete(f"/api/contracts/{c['contract_id']}").status_code == 204

def test_evidence_reads_release_db_transaction_before_source_processing(operator_client, db_factory, monkeypatch):
    from backend.app.services import review_context_service as service
    c = create_contract(operator_client)
    doc = upload(operator_client, c['contract_id'])
    with db_factory() as db:
        row = db.get(Document, doc['document_id'])

        def locate(*args):
            assert not db.in_transaction()
            return []
        monkeypatch.setattr(service, 'source_pages', locate)
        service.document_provenance(db, row)

def test_evidence_does_not_reuse_saved_anchor_after_original_changes(operator_client, db_factory):
    from backend.app.services.storage_service import resolve_path
    c = create_contract(operator_client)
    doc = upload(operator_client, c['contract_id'], 'estimate')
    with db_factory() as db:
        row = db.get(Document, doc['document_id'])
        source = resolve_path(row.storage_path)
        source.write_text('altered hand-authored unit fixture', encoding='utf-8')
    result = operator_client.get(f"/api/documents/{doc['document_id']}/provenance").json()
    assert result['source_version_verified'] is False
    assert all((not field['evidence'] and field['evidence_error'] == 'ORIGINAL_VERSION_CHANGED' for field in result['fields'].values()))


@pytest.mark.parametrize('kind,title', [('estimate', '견적서'), ('tax_invoice', '전자세금계산서')])
def test_shared_amount_block_below_buyer_has_evidence_without_accepting_buyer_identity(
        operator_client, db_factory, kind, title):
    cid = create_contract(operator_client, contract_amount=110)['contract_id']
    text = (title + '\n공급자\n상호: 가상 검증업체\n사업자등록번호: 220-88-12345\n'
            '공급받는자\n상호: 가상 구매회사\n사업자등록번호: 123-45-67890\n'
            '공급가액: 100원\n세액: 10원\n합계금액: 110원\n전액 청구: 전체 계약 대금\n발행일: 2026-10-01')
    uploaded = operator_client.post(f'/api/contracts/{cid}/documents',
        files=[('files', ('shared-block.txt', text.encode(), 'text/plain'))], data={'target_document_type': kind})
    assert uploaded.status_code == 200, uploaded.text
    did = uploaded.json()[0]['document_id']
    fields = operator_client.get(f'/api/documents/{did}/provenance').json()['fields']
    for key in ('supply_amount', 'tax_amount', 'total_amount', 'issue_date'):
        assert fields[key]['evidence_status'] == 'AVAILABLE', (key, fields[key])
        assert fields[key]['source'] == 'RULE'
    assert all(e['party'] == 'supplier' for e in fields['business_registration_no']['evidence'])
    # Even if a stored prediction accidentally contains buyer identity, do not
    # present the buyer section as supplier evidence.
    with db_factory() as db:
        doc = db.get(Document, did)
        values = json.loads(doc.extract.raw_fields)
        values.update(company_name='가상 구매회사', business_registration_no='123-45-67890')
        doc.extract.raw_fields = json.dumps(values, ensure_ascii=False)
        db.commit()
    fields = operator_client.get(f'/api/documents/{did}/provenance').json()['fields']
    assert not fields['company_name']['evidence']
    assert not fields['business_registration_no']['evidence']


def test_duplicate_amount_evidence_stays_ambiguous(operator_client):
    cid = create_contract(operator_client, contract_amount=110)['contract_id']
    text = '견적서\n공급가액: 100원\n세액: 10원\n합계금액: 110원\n합계금액: 110원'
    response = operator_client.post(f'/api/contracts/{cid}/documents',
        files=[('files', ('duplicate-labels.txt', text.encode(), 'text/plain'))])
    assert response.status_code == 200
    did = response.json()[0]['document_id']
    total = operator_client.get(f'/api/documents/{did}/provenance').json()['fields']['total_amount']
    assert total['evidence_status'] == 'AMBIGUOUS' and len(total['evidence']) == 2
