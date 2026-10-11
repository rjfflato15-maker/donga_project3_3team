"""Contract-level normal/problem workflows, with source-backed false-PASS cases."""
import json
import pytest
from backend.app.db.models import Document, Contract, AuditEvent
from test_api import create_contract
from test_business_identity_review import native_pdf
from test_submission_flow import decision
from submission_helpers import complete_source_review, submission_body


def risk_case(client, *, estimate_total=110, scope='FULL', missing=None):
    cid=create_contract(client,vendor_name='Synthetic Vendor',business_number='000-00-00000',contract_amount=110)['contract_id']
    identity=['상호: Synthetic Vendor','사업자등록번호: 000-00-00000']
    docs={}
    for kind,title,extras in [
        ('contract','계약서',['합계금액: 110원','선금 없이 최종 검수 후 전액 정산']),
        ('estimate','견적서',[f'합계금액: {estimate_total}원']),
        ('business_registration','사업자등록증',[]),
        ('bank_account','통장사본',['은행: 국민은행','계좌번호: 000-000-000000']),
        ('tax_invoice','세금계산서',['공급가액: 100원','세액: 10원','합계금액: 110원','전액 청구' if scope=='FULL' else '청구 범위 미정']),
        ('inspection_confirmation','검수확인서',['용역 검수 완료']),
    ]:
        if kind==missing:continue
        data=native_pdf([title]+identity+extras)
        r=client.post(f'/api/contracts/{cid}/documents',files=[('files',(kind+'.pdf',data,'application/pdf'))],data={'target_document_type':kind})
        assert r.status_code==200,r.text;docs[kind]=r.json()[0]['document_id']
    return cid,docs


def test_normal_flow_never_requires_opening_estimate_registration_or_inspection(operator_client,separate_client,db_factory):
    cid,docs=risk_case(operator_client)
    detail=operator_client.get(f'/api/contracts/{cid}').json();gate=detail['workflow']['submission']['gate']
    assert len(gate['automatic_review'])==13
    required=[b for b in gate['blockers'] if b['code']=='HUMAN_REVIEW_REQUIRED']
    assert len(required)==7
    assert {b['document_type'] for b in required}=={'contract','bank_account','tax_invoice'}
    assert all(b['category']=='RISK' for b in required)
    assert not gate['can_submit']  # automatic comparison never removes contract/payment judgement
    ready=complete_source_review(operator_client,cid)
    assert ready['workflow']['submission']['gate']['can_submit']
    assert operator_client.post(f'/api/pilot/contracts/{cid}/submission',json=submission_body(ready,acknowledge_work_completed=False)).status_code==400
    posted=operator_client.post(f'/api/pilot/contracts/{cid}/submission',json=submission_body(ready))
    assert posted.status_code==200,posted.text
    rep=separate_client('representative');approved=rep.post(f'/api/contracts/{cid}/reviews',json=decision(posted.json()))
    assert approved.status_code==200,approved.text;assert approved.json()['stage']=='PAYMENT'
    with db_factory() as db:
        for kind in ('estimate','business_registration','inspection_confirmation'):
            stored=json.loads(db.get(Document,docs[kind]).extract.raw_fields)
            assert not (stored.get('human_review') or {}).get('field_confirmations')
        event=db.query(AuditEvent).filter_by(contract_id=cid,action='CONTRACT_SUBMITTED').one()
        data=json.loads(event.details)
        assert data['acknowledge_work_completed'] is True and len(data['automatic_review'])==13


def test_problem_amount_keeps_its_source_task_and_explicit_exception_controls(operator_client):
    cid,docs=risk_case(operator_client,estimate_total=120)
    detail=operator_client.get(f'/api/contracts/{cid}').json();gate=detail['workflow']['submission']['gate']
    assert any(c['rule_id']=='AMOUNT_MATCH_ESTIMATE' and c['status']=='FAIL' for c in detail['checks'])
    assert any(b['document_id']==docs['estimate'] and b['field']=='total_amount' and b['category']=='EVIDENCE' for b in gate['blockers'])
    assert not any(b['document_id']==docs['estimate'] and b['field']=='total_amount' for b in gate['automatic_review'])
    ready=complete_source_review(operator_client,cid)
    assert ready['workflow']['submission']['gate']['exception_items']
    assert operator_client.post(f'/api/pilot/contracts/{cid}/submission',json=submission_body(ready,acknowledge_exception=False)).status_code==400


def test_changed_payment_conditions_require_fresh_scope_and_contract_judgement(operator_client):
    cid,docs=risk_case(operator_client)
    ready=complete_source_review(operator_client,cid)
    result=operator_client.put(f'/api/contracts/{cid}',json={'payment_mode':'INSTALLMENT','revision':ready['workflow']['revision'],'change_note':'합성 지급 조건 변경'})
    assert result.status_code==200,result.text
    gate=result.json()['workflow']['submission']['gate']
    assert any(b['document_id']==docs['contract'] and b['field']=='total_amount' for b in gate['blockers'])
    assert any(b['document_id']==docs['tax_invoice'] and b['field']=='amount_scope' for b in gate['blockers'])

def test_unknown_claim_meaning_does_not_require_rechecking_verified_numeric_values(operator_client):
    cid,docs=risk_case(operator_client,scope='UNKNOWN')
    gate=operator_client.get(f'/api/contracts/{cid}').json()['workflow']['submission']['gate']
    assert any(b['code']=='FIELD_VALUE_REQUIRED' and b['field']=='amount_scope' for b in gate['blockers'])
    assert not any(b['document_id']==docs['tax_invoice'] and b['field'] in {'supply_amount','tax_amount','total_amount'} for b in gate['blockers'])
    assert {b['field'] for b in gate['automatic_review'] if b['document_id']==docs['tax_invoice']} >= {'supply_amount','tax_amount','total_amount'}
    assert not gate['can_submit']


@pytest.mark.parametrize('fault',['correlated_number','correlated_amount','missing_account','source_changed','unknown_scope'])
def test_wrong_pass_and_unusable_important_information_never_take_the_normal_path(operator_client,db_factory,fault):
    cid,docs=risk_case(operator_client,scope='UNKNOWN' if fault=='unknown_scope' else 'FULL')
    if fault!='unknown_scope':
        with db_factory() as db:
            contract=db.get(Contract,cid)
            if fault=='correlated_number':contract.business_number='111-11-11111'
            if fault=='correlated_amount':contract.contract_amount=220
            for doc in contract.documents:
                values=json.loads(doc.extract.raw_fields)
                if fault=='correlated_number':values['business_registration_no']='111-11-11111'
                if fault=='correlated_amount':values.update(total_amount=220,amount=220,supply_amount=200,tax_amount=20)
                if fault=='missing_account' and doc.document_type=='bank_account':values['account_number']=None
                if fault=='source_changed' and doc.document_type=='estimate':
                    from backend.app.services.storage_service import resolve_path
                    resolve_path(doc.storage_path).write_bytes(native_pdf(['견적서','상호: Other','사업자등록번호: 111-11-11111','합계금액: 220원']))
                doc.extract.raw_fields=json.dumps(values,ensure_ascii=False)
            db.commit()
    detail=operator_client.get(f'/api/contracts/{cid}').json();gate=detail['workflow']['submission']['gate']
    if fault=='correlated_number':
        assert all(c['status']=='PASS' for c in detail['checks'] if c['rule_id']=='BUSINESS_NO_MATCH')
        assert gate['automatic_review']==[]
        assert any(b['category']=='EVIDENCE' for b in gate['blockers'])
    elif fault=='correlated_amount':
        assert all(c['status']=='PASS' for c in detail['checks'] if c['rule_id'].startswith('AMOUNT_MATCH_'))
        assert not any(b['field'].endswith('amount') for b in gate['automatic_review'])
    elif fault=='source_changed':assert any(b['code']=='SOURCE_UNVERIFIED' for b in gate['blockers'])
    else:assert any(b['code']=='FIELD_VALUE_REQUIRED' for b in gate['blockers'])
    assert not gate['can_submit']
    assert operator_client.post(f'/api/pilot/contracts/{cid}/submission',json=submission_body(detail)).status_code==400
