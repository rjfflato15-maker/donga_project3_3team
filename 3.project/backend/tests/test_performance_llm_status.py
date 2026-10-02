import json
from datetime import datetime, timedelta

from backend.app.db.models import Document, Contract, ContractReview
from backend.app.services import llm_status_service as status
from test_api import create_contract
from test_review_workflow_api import upload
from test_document_versions import reissue


def test_status_separates_disabled_configuration_reachable_server_and_actual_execution(monkeypatch,tmp_path):
    home=tmp_path; (home/'.ollama').mkdir();(home/'.ollama/server.json').write_text('{"disable_ollama_cloud":true}')
    monkeypatch.setattr(status.Path,'home',lambda:home)
    status._cache.clear();calls=[]
    class Response:
        def raise_for_status(self):pass
        def json(self):return {'models':[{'name':'qwen3:latest','size':100}]}
    monkeypatch.setattr(status.OllamaClient,'extract',lambda *a: (_ for _ in ()).throw(AssertionError('status must not infer')))
    monkeypatch.setattr('requests.Session.get',lambda *a,**kw: calls.append(kw) or Response())
    assert status.llm_status()['connected'] is None
    off=status.llm_status(probe=True)
    assert off['configured_enabled'] is False and off['connected'] is True and off['ready_for_inference'] is False
    monkeypatch.setenv('APP_LLM_ENABLED','true')
    on=status.llm_status(probe=True)
    assert on['ready_for_inference'] is True and len(calls) == 1
    monkeypatch.setenv('APP_OLLAMA_URL','https://outside.invalid')
    invalid=status.llm_status(probe=True)
    assert invalid['connection_state']=='INVALID_CONFIGURATION' and len(calls)==1
    monkeypatch.delenv('APP_OLLAMA_URL')
    status._cache.clear()
    def unavailable(*a,**kw):raise RuntimeError('private transport detail must not be exposed')
    monkeypatch.setattr('requests.Session.get',unavailable)
    assert status.llm_status(probe=True)['error']=='LOCAL_SERVER_UNAVAILABLE'
    status._cache.clear()


def test_stored_execution_counts_value_adoptions_separately_from_calls_and_rejections():
    stored={'total_amount':110,'tax_amount':None,'ai_review':{'status':'COMPLETED','attempts':1,'decisions':[
        {'field':'total_amount','applied':True,'proposal':{'state':'VALUE','value':'110'}},
        {'field':'tax_amount','applied':True,'proposal':{'state':'ABSENT','value':None}},
        {'field':'company_name','applied':False,'proposal':{'state':'VALUE','value':'blocked'}}]}}
    report=status.document_execution(stored)
    assert report['inference_invoked'] is True and report['invocation_count']==1
    assert report['applied_value_field_count']==1 and report['current_matching_ai_value_field_count']==1
    stored['total_amount']=121
    assert status.document_execution(stored)['current_matching_ai_value_field_count']==0
    assert status.document_execution({})['inference_invoked'] is None


def test_performance_counts_changed_fields_and_current_approval_not_save_events_or_waiting_as_work(operator_client,separate_client,db_factory):
    representative=separate_client()
    representative.put('/api/pilot/settings',json={'company_name':'통계 테스트','required_document_types':['contract']})
    cid=create_contract(operator_client,contract_amount=110,vendor_name='가상 검증업체')['contract_id']
    doc=upload(operator_client,cid); did=doc['document_id']
    with db_factory() as db:
        row=db.get(Document,did);stored=json.loads(row.extract.raw_fields)
        stored['ai_review']={'status':'COMPLETED','attempts':1,'model':'qwen3:latest','decisions':[
            {'field':'total_amount','accepted':True,'applied':True,'proposal':{'state':'VALUE','value':'110'}},
            {'field':'tax_amount','accepted':True,'applied':True,'proposal':{'state':'ABSENT','value':None}}]}
        row.extract.raw_fields=json.dumps(stored,ensure_ascii=False);db.commit()
    fields=doc['analysis']['fields'];fields['total_amount']=111
    for _ in range(2):
        detail=operator_client.get(f'/api/contracts/{cid}').json()
        result=operator_client.put(f'/api/documents/{did}/fields',json={'fields':fields,'document_type':'contract','revision':detail['workflow']['revision'],'note':'통계 검증 저장'})
        assert result.status_code==200,result.text
    detail=operator_client.get(f'/api/contracts/{cid}').json()
    assert detail['llm']['applied_value_field_count']==1 and detail['llm']['current_matching_ai_value_field_count']==0
    assert detail['documents'][0]['llm']['configured_enabled_at_analysis'] is False
    operator_client.post(f'/api/pilot/contracts/{cid}/resubmission-requests',json={'contact_method':'PHONE','memo':'서류 요청 기록'})
    assert representative.post(f'/api/contracts/{cid}/reviews',json={'decision':'CONFIRMED','note':'미연동 항목과 값 차이를 원문에서 확인했음','acknowledge_unverified':True,
        'revision':detail['workflow']['revision'],'fingerprint':detail['workflow']['fingerprint']}).status_code==200
    with db_factory() as db:
        registered=datetime(2026,10,1,10)
        db.get(Contract,cid).created_at=registered
        db.query(ContractReview).filter_by(contract_id=cid).first().created_at=registered+timedelta(minutes=20)
        db.commit()
    row=operator_client.get('/api/pilot/performance',params={'contract_id':cid}).json()['contracts'][0]
    assert row['human_correction_save_count']==2 and row['human_field_edit_count']==1 and row['human_changed_unique_field_count']==1
    assert row['resubmission_request_count']==1 and row['registration_to_current_final_confirmation_elapsed_seconds']==1200
    assert row['active_review_seconds'] is None and row['measured_time_saving_seconds'] is None
    assert reissue(operator_client,cid,did,detail['workflow']['revision']).status_code==200
    row=operator_client.get('/api/pilot/performance',params={'contract_id':cid}).json()['contracts'][0]
    assert row['registration_to_current_final_confirmation_elapsed_seconds'] is None and row['ai_applied_value_field_count']==0
    assert row['human_field_edit_count']==1 and row['document_version_count']==2


def test_llm_list_status_does_not_make_network_probe_and_legacy_is_unknown(operator_client,monkeypatch):
    status._cache.clear()
    def forbidden(*a,**kw):raise AssertionError('list and detail must not probe')
    monkeypatch.setattr('requests.Session.get',forbidden)
    cid=create_contract(operator_client)['contract_id'];doc=upload(operator_client,cid)
    listing=operator_client.get('/api/contracts').json()[0]
    assert listing['llm']['current_state']['connected'] is None
    detail=operator_client.get(f'/api/documents/{doc["document_id"]}').json()
    assert detail['llm']['status']=='DISABLED' and detail['llm']['invocation_count']==0
    assert operator_client.get('/api/pilot/info').json()['llm_connected'] is None
