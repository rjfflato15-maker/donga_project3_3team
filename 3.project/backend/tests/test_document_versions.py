import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from backend.app.db.models import Document, DocumentVersion
from test_api import create_contract
from test_review_workflow_api import configured_contract, upload
from test_storage_concurrency import block_analysis


def reissue(client,cid,did,revision,text=None,**extra):
    text=text or '외주 용역 계약서\n상호: 가상 검증업체\n사업자등록번호: 220-88-12345\n공급가액: 100원\n세액: 10원\n합계금액: 110원\n전액 청구'
    return client.post(f'/api/contracts/{cid}/documents',files=[('files',('reissue.txt',text.encode(),'text/plain'))],
                      data={'upload_mode':'REISSUE','replaces_document_id':did,'revision':revision,'change_note':'원문 재발행본으로 교체',**extra})


def test_complete_review_correction_reissue_reapproval_keeps_old_source_and_invalidates_signoffs(operator_client,separate_client):
    representative,cid,_=configured_contract(operator_client,separate_client)
    detail=operator_client.get(f'/api/contracts/{cid}').json()
    old=detail['documents'][0]; did=old['document_id']
    assert operator_client.get(f'/api/documents/{did}/provenance').json()['fields']['total_amount']['evidence']
    values=old['analysis']['fields']; values['total_amount']=111
    assert operator_client.put(f'/api/documents/{did}/fields',json={'fields':values,'document_type':'contract','revision':detail['workflow']['revision'],'note':'사람 검수 수정 기록'}).status_code == 200
    detail=operator_client.get(f'/api/contracts/{cid}').json()
    body={'decision':'CONFIRMED','note':'국세청 미연동과 금액 차이를 원문에서 직접 확인함','acknowledge_unverified':True,
          'revision':detail['workflow']['revision'],'fingerprint':detail['workflow']['fingerprint']}
    assert operator_client.post(f'/api/pilot/contracts/{cid}/approvals',json={**body,'step':1}).status_code == 200
    assert representative.post(f'/api/contracts/{cid}/reviews',json=body).status_code == 200
    response=reissue(operator_client,cid,did,body['revision'])
    assert response.status_code == 200,response.text
    new=response.json()[0]; new_id=new['document_id']
    assert new_id != did and new['version']['previous_document_id'] == did and new['version']['version_number'] == 2
    current=operator_client.get(f'/api/contracts/{cid}').json()
    assert [d['document_id'] for d in current['documents']] == [new_id]
    assert current['workflow']['approval_status'] == 'STALE'
    assert representative.get(f'/api/pilot/contracts/{cid}/approvals').json()['completed_steps'] == 0
    context=operator_client.get(f'/api/contracts/{cid}/review-context').json()
    assert [d['document_id'] for d in context['documents']] == [new_id]
    assert not any(c['field']==str(did) for c in context['checks'])
    history=operator_client.get(f'/api/documents/{new_id}/versions').json()['versions']
    assert [v['is_current'] for v in history] == [False,True]
    comparison=operator_client.get(f'/api/documents/{new_id}/compare').json()
    assert {'field':'total_amount','previous_value':111,'new_value':110} in comparison['changes']
    assert operator_client.get(f'/api/documents/{did}/download',params={'masked':False}).status_code == 200
    assert operator_client.delete(f'/api/documents/{did}').status_code == 409
    assert operator_client.put(f'/api/documents/{did}/fields',json={'fields':values,'document_type':'contract','revision':current['workflow']['revision'],'note':'이전 값 수정 시도'}).status_code == 409
    body.update(revision=current['workflow']['revision'],fingerprint=current['workflow']['fingerprint'],review_cycle=current['workflow']['reviews'][0]['review_id'] if current['workflow']['reviews'] else 0)
    assert representative.post(f'/api/contracts/{cid}/reviews',json=body).status_code == 400
    from submission_helpers import complete_source_review
    current = complete_source_review(operator_client, cid)
    body.update(revision=current['workflow']['revision'],fingerprint=current['workflow']['fingerprint'],review_cycle=current['workflow']['reviews'][0]['review_id'] if current['workflow']['reviews'] else 0)
    assert operator_client.post(f'/api/pilot/contracts/{cid}/approvals',json={**body,'step':1}).status_code == 200
    assert representative.post(f'/api/contracts/{cid}/reviews',json=body).status_code == 200


def test_same_type_additions_stay_separate_logical_documents_and_legacy_is_version_one(operator_client,db_factory):
    cid=create_contract(operator_client)['contract_id']
    a=upload(operator_client,cid,'tax_invoice'); b=upload(operator_client,cid,'tax_invoice')
    assert a['version']['logical_document_id'] != b['version']['logical_document_id']
    assert len(operator_client.get(f'/api/contracts/{cid}').json()['documents']) == 2
    with db_factory() as db:
        db.delete(db.get(DocumentVersion,a['document_id']));db.commit()
    revision=operator_client.get(f'/api/contracts/{cid}').json()['workflow']['revision']
    text='세금계산서\n상호: 가상 검증업체\n사업자등록번호: 220-88-12345\n합계금액: 110원\n전액 청구'
    result=reissue(operator_client,cid,a['document_id'],revision,text=text)
    assert result.status_code == 200,result.text
    assert len(operator_client.get(f'/api/contracts/{cid}').json()['documents']) == 2
    assert len(operator_client.get(f"/api/documents/{result.json()[0]['document_id']}/versions").json()['versions']) == 2


def test_failed_reissue_keeps_previous_active_values_and_revision(operator_client,db_factory,monkeypatch):
    from backend.app.services import pipeline_service
    cid=create_contract(operator_client)['contract_id']; old=upload(operator_client,cid)
    detail=operator_client.get(f'/api/contracts/{cid}').json()
    def failed(*a,**kw):raise RuntimeError('unit failed OCR')
    monkeypatch.setattr(pipeline_service,'analyze_document',failed)
    result=reissue(operator_client,cid,old['document_id'],detail['workflow']['revision'])
    assert result.status_code == 422,result.text
    current=operator_client.get(f'/api/contracts/{cid}').json()
    assert current['workflow']['revision'] == detail['workflow']['revision']
    assert current['documents'] == detail['documents']
    with db_factory() as db:assert db.query(DocumentVersion).count() == 1


def test_concurrent_edit_during_reissue_rejected_without_second_version(operator_client,separate_client,db_factory,monkeypatch):
    cid=create_contract(operator_client)['contract_id']; old=upload(operator_client,cid)
    revision=operator_client.get(f'/api/contracts/{cid}').json()['workflow']['revision']
    other=separate_client('operator');started,finish=block_analysis(monkeypatch)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending=pool.submit(reissue,operator_client,cid,old['document_id'],revision)
        try:
            assert started.wait(2)
            assert other.put(f'/api/contracts/{cid}',json={'title':'동시 변경 계약','revision':revision,'change_note':'재발행 중 계약 수정'}).status_code == 200
        finally:finish.set()
        assert pending.result(timeout=10).status_code == 409
    with db_factory() as db:assert db.query(DocumentVersion).count() == 1


def test_reissue_requires_explicit_preconditions_and_bound_document(operator_client):
    cid=create_contract(operator_client)['contract_id'];a=upload(operator_client,cid)
    other=create_contract(operator_client)['contract_id']
    revision=operator_client.get(f'/api/contracts/{cid}').json()['workflow']['revision']
    assert reissue(operator_client,cid,a['document_id'],revision,upload_mode='ADD').status_code == 400
    assert reissue(operator_client,other,a['document_id'],1).status_code == 404
    assert reissue(operator_client,cid,a['document_id'],revision,target_document_type='estimate').status_code == 400
    assert reissue(operator_client,cid,a['document_id'],revision+1).status_code == 409
