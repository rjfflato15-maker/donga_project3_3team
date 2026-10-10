import json
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from backend.app.db.models import AuditEvent, ContractReview, Document
from test_api import create_contract
from test_review_workflow_api import upload
from submission_helpers import complete_source_review, submission_body, submit_ready


def setup_case(operator, separate, *, steps=1, required=None):
    rep = separate('representative')
    policy = rep.get('/api/pilot/company-policy/presets').json()[2 if steps == 2 else 1]
    policy['required_document_types'] = required or ['contract']
    assert rep.put('/api/pilot/company-policy', json=policy).status_code == 200
    cid = create_contract(operator, vendor_name='가상 검증업체', contract_amount=110)['contract_id']
    doc = upload(operator, cid)
    return rep, cid, doc


def decision(detail, decision='CONFIRMED'):
    wf = detail['workflow']
    return {'review_cycle':wf['reviews'][0]['review_id'] if wf['reviews'] else 0, 'submission_event_id':wf['submission']['event_id'], 'revision': wf['revision'], 'fingerprint': wf['fingerprint'], 'decision': decision,
            'note': '합성 자료의 원문 및 미조회·예외 항목을 직접 검토한 판단입니다.',
            'acknowledge_unverified': True}


@pytest.mark.parametrize('steps', [1, 2])
def test_operator_submission_and_representative_decision_are_separate(operator_client, separate_client, db_factory, steps):
    rep, cid, doc = setup_case(operator_client, separate_client, steps=steps)
    initial = operator_client.get(f'/api/contracts/{cid}').json()
    assert initial['stage'] == 'CHECK'
    assert any(b['code'] == 'HUMAN_REVIEW_REQUIRED' for b in initial['workflow']['submission']['gate']['blockers'])
    assert rep.post(f'/api/contracts/{cid}/reviews', json=decision(initial)).status_code == 400
    assert operator_client.post(f'/api/pilot/contracts/{cid}/submission', json=submission_body(initial)).status_code == 400
    reviewed = complete_source_review(operator_client, cid)
    assert rep.post(f'/api/contracts/{cid}/reviews', json=decision(reviewed)).status_code == 409
    assert rep.post(f'/api/pilot/contracts/{cid}/submission', json=submission_body(reviewed)).status_code == 403
    submitted = submit_ready(operator_client, cid)
    assert submitted['stage'] == 'APPROVAL'
    assert submitted['workflow']['submission']['current']
    state = rep.get(f'/api/pilot/contracts/{cid}/approvals').json()
    assert state['completed_steps'] == steps - 1
    assert state['next_step'] == steps
    assert operator_client.post(f'/api/contracts/{cid}/reviews', json=decision(submitted)).status_code == 403
    result = rep.post(f'/api/contracts/{cid}/reviews', json=decision(submitted))
    assert result.status_code == 200, result.text
    assert result.json()['stage'] == 'PAYMENT'
    assert result.json()['workflow']['submission']['status'] == 'APPROVED'
    assert rep.post(f'/api/contracts/{cid}/reviews', json=decision(submitted)).status_code == 409
    with db_factory() as db:
        stored = db.query(ContractReview).filter_by(contract_id=cid).one()
        assert json.loads(stored.snapshot_json)['submission']['event_id']


def test_return_requires_new_submission_even_without_value_change(operator_client, separate_client):
    rep, cid, _ = setup_case(operator_client, separate_client)
    submitted = submit_ready(operator_client, cid)
    result = rep.post(f'/api/contracts/{cid}/reviews', json=decision(submitted, 'RETURNED'))
    assert result.status_code == 200, result.text
    returned = result.json()
    assert returned['workflow']['submission']['status'] == 'RETURNED'
    assert rep.post(f'/api/contracts/{cid}/reviews', json=decision(returned)).status_code == 409
    again = submit_ready(operator_client, cid)
    assert again['workflow']['submission']['current'] and again['stage'] == 'APPROVAL'
    assert rep.post(f'/api/contracts/{cid}/reviews', json=decision(again)).status_code == 200


def test_change_after_approval_preserves_history_and_requires_resubmission(operator_client, separate_client, db_factory):
    rep, cid, _ = setup_case(operator_client, separate_client)
    ready = submit_ready(operator_client, cid)
    approved = rep.post(f'/api/contracts/{cid}/reviews', json=decision(ready)).json()
    result = operator_client.put(f'/api/contracts/{cid}', json={'title': '합성 계약 변경',
        'revision': approved['workflow']['revision'], 'change_note': '추가 검토할 계약 설명 변경'})
    assert result.status_code == 200
    changed = result.json()
    assert changed['workflow']['approval_status'] == 'STALE'
    assert changed['workflow']['submission']['status'] == 'STALE'
    assert rep.post(f'/api/contracts/{cid}/reviews', json=decision(changed)).status_code == 409
    resubmitted = submit_ready(operator_client, cid)
    assert rep.post(f'/api/contracts/{cid}/reviews', json=decision(resubmitted)).status_code == 200
    with db_factory() as db:
        assert db.query(ContractReview).filter_by(contract_id=cid).count() == 2


@pytest.mark.parametrize('problem', ['failed', 'incomplete', 'changed_source'])
def test_technical_failure_cannot_be_exception_submitted(operator_client, separate_client, db_factory, problem):
    rep, cid, doc = setup_case(operator_client, separate_client)
    complete_source_review(operator_client, cid)
    with db_factory() as db:
        row = db.get(Document, doc['document_id'])
        if problem == 'failed': row.processing_status = 'FAILED'
        elif problem == 'incomplete':
            stored = json.loads(row.extract.raw_fields)
            stored['extraction_metadata'] = {'evidence_complete': False}
            row.extract.raw_fields = json.dumps(stored)
        else:
            from backend.app.services.storage_service import resolve_path
            resolve_path(row.storage_path).write_bytes(b'changed synthetic source')
        db.commit()
    detail = operator_client.get(f'/api/contracts/{cid}').json()
    assert detail['workflow']['submission']['gate']['blockers']
    body = submission_body(detail, acknowledge_exception=True, exception_reason='기술 실패를 말만으로 넘기려는 합성 요청')
    assert operator_client.post(f'/api/pilot/contracts/{cid}/submission', json=body).status_code == 400
    assert rep.post(f'/api/contracts/{cid}/reviews', json=decision(detail)).status_code == 400


def test_real_mismatch_requires_explicit_exception_then_representative_ack(operator_client, separate_client):
    rep, cid, _ = setup_case(operator_client, separate_client, required=['contract','estimate'])
    upload(operator_client, cid, 'estimate')
    detail = complete_source_review(operator_client, cid)
    changed = operator_client.put(f'/api/contracts/{cid}', json={'contract_amount': 220,
        'revision': detail['workflow']['revision'], 'change_note': '예외 검토할 합성 금액 변경'}).json()
    gate = changed['workflow']['submission']['gate']
    assert not gate['blockers'] and gate['exception_items']
    assert operator_client.post(f'/api/pilot/contracts/{cid}/submission', json=submission_body(changed, acknowledge_exception=False)).status_code == 400
    assert operator_client.post(f'/api/pilot/contracts/{cid}/submission', json=submission_body(changed, exception_items=[])).status_code == 400
    submitted = submit_ready(operator_client, cid)
    assert submitted['workflow']['submission']['exception_reason']
    assert rep.post(f'/api/contracts/{cid}/reviews', json={**decision(submitted), 'acknowledge_unverified': False}).status_code == 400
    assert rep.post(f'/api/contracts/{cid}/reviews', json=decision(submitted)).status_code == 200


def test_duplicate_click_and_refresh_persist_one_submission(operator_client, separate_client, db_factory):
    _, cid, _ = setup_case(operator_client, separate_client)
    detail = complete_source_review(operator_client, cid)
    body = submission_body(detail)
    path = f'/api/pilot/contracts/{cid}/submission'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: operator_client.post(path, json=body), range(2)))
    assert all(r.status_code == 200 for r in results), [r.text for r in results]
    assert operator_client.get(f'/api/contracts/{cid}').json()['workflow']['submission']['current']
    assert operator_client.post(path, json={**body, 'note': '동일 키에 다른 검토 의견'}).status_code == 409
    assert operator_client.post(path, json={**body, 'idempotency_key': str(uuid4())}).status_code == 409
    with db_factory() as db:
        assert db.query(AuditEvent).filter_by(contract_id=cid, action='CONTRACT_SUBMITTED').count() == 1


def test_partial_reply_and_reissue_need_review_before_submission(operator_client, separate_client):
    from test_request_bundles import create, patch
    rep, cid, _ = setup_case(operator_client, separate_client, required=['contract','estimate','business_registration'])
    row = create(operator_client, cid, keys=['missing:estimate','missing:business_registration'])
    upload(operator_client, cid, 'estimate')
    item = next(i for i in row['bundle']['items'] if i['document_type'] == 'estimate')
    result = patch(operator_client, cid, row, [{'item_id':item['item_id'], 'status':'RECEIVED', 'note':'합성 견적서 부분 회신'}])
    assert result.status_code == 200, result.text
    row = result.json()
    assert row['bundle']['counts']['waiting'] == 1
    detail = complete_source_review(operator_client, cid)
    assert any(b['code']=='WAITING_VENDOR' for b in detail['workflow']['submission']['gate']['blockers'])
    assert operator_client.post(f'/api/pilot/contracts/{cid}/submission', json=submission_body(detail)).status_code == 400
    text='사업자등록증\n상호: 가상 검증업체\n사업자등록번호: 220-88-12345\n'
    assert operator_client.post(f'/api/contracts/{cid}/documents',files=[('files',('registration.txt',text.encode(),'text/plain'))]).status_code==200
    item = next(i for i in row['bundle']['items'] if i['document_type']=='business_registration')
    result = patch(operator_client,cid,row,[{'item_id':item['item_id'],'status':'RECEIVED','note':'합성 등록증 나머지 회신'}])
    assert result.status_code == 200, result.text
    submitted = submit_ready(operator_client, cid)
    assert submitted['workflow']['submission']['current']


def test_old_screen_cannot_resubmit_or_approve_after_return(operator_client, separate_client):
    rep,cid,_ = setup_case(operator_client,separate_client)
    submitted = submit_ready(operator_client,cid)
    old_submission = submission_body(submitted)
    old_decision = decision(submitted)
    assert rep.post(f'/api/contracts/{cid}/reviews',json=decision(submitted,'RETURNED')).status_code==200
    assert operator_client.post(f'/api/pilot/contracts/{cid}/submission',json=old_submission).status_code==409
    current = submit_ready(operator_client,cid)
    assert rep.post(f'/api/contracts/{cid}/reviews',json=old_decision).status_code==409
    assert rep.post(f'/api/contracts/{cid}/reviews',json=decision(current)).status_code==200


def test_no_issue_text_cannot_replace_required_original_review(operator_client,separate_client):
    _,cid,doc = setup_case(operator_client,separate_client)
    detail = operator_client.get(f'/api/contracts/{cid}').json()
    assert operator_client.post(f'/api/documents/{doc["document_id"]}/defer-field',json={
        'field':'total_amount','revision':detail['workflow']['revision'],'kind':'NO_ISSUE',
        'note':'업무 판단만으로 필수 원문 확인을 대신하려는 합성 요청'}).status_code==200
    latest = operator_client.get(f'/api/contracts/{cid}').json()
    assert any(b['code']=='HUMAN_REVIEW_REQUIRED' and b['field']=='total_amount' for b in latest['workflow']['submission']['gate']['blockers'])
    assert operator_client.post(f'/api/pilot/contracts/{cid}/submission',json=submission_body(latest)).status_code==400


def test_misread_correction_and_reissue_repeat_original_review(operator_client,separate_client,db_factory):
    from test_document_versions import reissue
    rep,cid,doc = setup_case(operator_client,separate_client,required=['contract','estimate'])
    estimate = upload(operator_client,cid,'estimate')
    with db_factory() as db:
        row=db.get(Document,estimate['document_id'])
        stored=json.loads(row.extract.raw_fields);stored['total_amount']=121;stored['amount']=121
        row.extract.raw_fields=json.dumps(stored);db.commit()
    before=operator_client.get(f'/api/contracts/{cid}').json()
    assert any(c['rule_id']=='AMOUNT_MATCH_ESTIMATE' and c['status']=='FAIL' for c in before['checks'])
    fixed=operator_client.put(f'/api/documents/{estimate["document_id"]}/fields',json={
        'fields':{'total_amount':110,'amount':110},'document_type':'estimate',
        'revision':before['workflow']['revision'],'note':'합성 원문 110원을 121원으로 오독해 정정',
        'confirmed_fields':['total_amount']})
    assert fixed.status_code==200,fixed.text
    submitted=submit_ready(operator_client,cid)
    assert submitted['workflow']['submission']['gate']['can_submit']
    assert rep.post(f'/api/contracts/{cid}/reviews',json=decision(submitted)).status_code==200
    revised=reissue(operator_client,cid,doc['document_id'],submitted['workflow']['revision'])
    assert revised.status_code==200,revised.text
    current=operator_client.get(f'/api/contracts/{cid}').json()
    assert current['workflow']['approval_status']=='STALE'
    assert next(d for d in current['documents'] if d['document_type']=='contract')['version']['previous_document_id']==doc['document_id']
    assert current['workflow']['submission']['gate']['blockers']
    assert operator_client.post(f'/api/pilot/contracts/{cid}/submission',json=submission_body(current)).status_code==400
    ready=submit_ready(operator_client,cid)
    assert rep.post(f'/api/contracts/{cid}/reviews',json=decision(ready)).status_code==200
