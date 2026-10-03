import json
from backend.app.db.models import AuditEvent,Contract,ContractWorkflow,ValidationResult,ResubmissionRequest,WorkAssignment,ContractReview
from backend.app.services import readonly_review_service
from test_api import create_contract
from test_review_workflow_api import upload


def db_state(factory,cid):
    with factory() as db:
        return {'counts':[db.query(m).count() for m in (AuditEvent,ValidationResult,ResubmissionRequest,WorkAssignment,ContractReview)],
                'revision':db.get(ContractWorkflow,cid).revision,'review_status':db.get(Contract,cid).review_status,
                'checks':[(r.validation_id,r.status,r.actual,r.memo) for r in db.query(ValidationResult).filter_by(contract_id=cid).order_by(ValidationResult.validation_id)]}


def test_assistant_preview_is_read_only_and_distinguishes_internal_preparation_from_vendor_request(operator_client,db_factory,monkeypatch):
    cid=create_contract(operator_client)['contract_id'];upload(operator_client,cid,'estimate')
    workflow=operator_client.get(f'/api/contracts/{cid}').json()['workflow']
    before=db_state(db_factory,cid)
    def forbidden(*a,**kw):raise AssertionError('preview must not write validation or call external API')
    monkeypatch.setattr('backend.app.services.pipeline_service.PipelineService.revalidate_contract',forbidden)
    monkeypatch.setattr('requests.Session.post',forbidden)
    request={'revision':workflow['revision'],'fingerprint':workflow['fingerprint']}
    url=f'/api/pilot/contracts/{cid}/assistant-preview'
    result=operator_client.post(url,json=request)
    assert result.status_code==200,result.text
    data=result.json();assert data['preview_only'] and not data['persisted'] and data['external_api_calls']==0
    missing={i['field']:i for i in data['items'] if i['rule_id']=='REQUIRED_DOCUMENTS'}
    assert missing['contract']['request_draft'] is None and missing['contract']['assignment_draft']
    assert missing['inspection_confirmation']['request_draft'] is None
    assert missing['tax_invoice']['request_draft']['sent'] is False
    notice=next(i for i in data['items'] if i['rule_id']=='BUSINESS_STATUS')
    assert notice['next_action']=='INFORMATIONAL_NOTICE' and notice['actionable'] is False
    assert notice['request_draft'] is None and notice['assignment_draft'] is None
    assert data['actionable_item_count']==sum(i['actionable'] for i in data['items'])
    item=data['items'][0]
    selected=operator_client.post(url,json={**request,'issue_ids':[item['issue_id']]}).json()
    assert selected['item_count']==1
    assert operator_client.post(url,json={**request,'issue_ids':['unknown']}).status_code==422
    assert operator_client.post(url,json={**request,'revision':workflow['revision']+1}).status_code==409
    assert db_state(db_factory,cid)==before


def test_unreadable_amount_or_number_never_generates_vendor_request():
    from backend.app.services.review_assistant_service import prepare_item
    from backend.app.schemas.validation import ValidationCheck
    data={'documents':[{'document_id':7,'document_type':'estimate'}],
          'reference':{'title':'unit','vendor_name':'unit'},'revision':1,'fingerprint':'unit'}
    for rule in ('AMOUNT_EXTRACTION','BUSINESS_NO_MATCH','DOCUMENT_PROCESSING'):
        check=ValidationCheck(rule_id=rule,field='7',status='REVIEW',message='원문부터 확인')
        item=prepare_item(check,data)
        assert item['next_action']=='VERIFY_EXTRACTION_FIRST'
        assert item['request_draft'] is None and item['assignment_draft']


def test_preview_rechecks_changed_cached_rules_without_publishing(operator_client,db_factory):
    cid=create_contract(operator_client)['contract_id']
    detail=operator_client.get(f'/api/contracts/{cid}').json()
    with db_factory() as db:
        row=db.query(ValidationResult).filter_by(contract_id=cid,validation_type='REQUIRED_DOCUMENTS').first()
        row.status='PASS';db.commit()
    before=db_state(db_factory,cid)
    response=operator_client.post(f'/api/pilot/contracts/{cid}/assistant-preview',json={'revision':detail['workflow']['revision'],'fingerprint':detail['workflow']['fingerprint']})
    assert response.status_code==200
    assert any(d['recorded']['status']=='PASS' and d['preview']['status']=='MISSING' for d in response.json()['recheck_differences'])
    assert db_state(db_factory,cid)==before


def test_preview_rejects_concurrent_change_after_recheck(operator_client,db_factory,monkeypatch):
    cid=create_contract(operator_client)['contract_id'];detail=operator_client.get(f'/api/contracts/{cid}').json()
    original=readonly_review_service.RuleEngine.validate_contract_evidence
    def changed(self,*a,**kw):
        result=original(self,*a,**kw)
        with db_factory() as db:
            db.get(Contract,cid).title='미리보기 중 변경';db.commit()
        return result
    monkeypatch.setattr(readonly_review_service.RuleEngine,'validate_contract_evidence',changed)
    response=operator_client.post(f'/api/pilot/contracts/{cid}/assistant-preview',json={'revision':detail['workflow']['revision'],'fingerprint':detail['workflow']['fingerprint']})
    assert response.status_code==409
