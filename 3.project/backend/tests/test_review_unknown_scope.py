import json
from backend.app.db.models import Document
from test_api import create_contract
from test_review_workflow_api import upload


def test_unknown_scope_cannot_be_satisfied_by_a_legacy_confirmation(operator_client,separate_client,db_factory):
    rep=separate_client('representative');policy=rep.get('/api/pilot/company-policy/presets').json()[1]
    policy['required_document_types']=['contract','tax_invoice'];assert rep.put('/api/pilot/company-policy',json=policy).status_code==200
    cid=create_contract(operator_client,contract_amount=110)['contract_id'];upload(operator_client,cid)
    text='세금계산서\n상호: 가상 검증업체\n사업자등록번호: 220-88-12345\n공급가액: 100원\n세액: 10원\n합계금액: 110원\n'
    response=operator_client.post(f'/api/contracts/{cid}/documents',files=[('files',('invoice.txt',text.encode(),'text/plain'))],data={'target_document_type':'tax_invoice'})
    assert response.status_code==200,response.text;invoice=response.json()[0]['document_id']
    with db_factory() as db:
        doc=db.get(Document,invoice);raw=json.loads(doc.extract.raw_fields);raw['amount_scope']='UNKNOWN'
        raw['human_review']={'field_confirmations':{'amount_scope':{'value':'UNKNOWN','actor_name':'legacy','at':'old'}}}
        doc.extract.raw_fields=json.dumps(raw,ensure_ascii=False);db.commit()
    detail=operator_client.get(f'/api/contracts/{cid}').json();gate=detail['workflow']['submission']['gate']
    assert any(b['document_id']==invoice and b['field']=='amount_scope' and b['code']=='FIELD_VALUE_REQUIRED' for b in gate['blockers'])
    assert not gate['can_submit'] and not gate['can_submit_exception']
    provenance=operator_client.get(f'/api/documents/{invoice}/provenance').json()
    assert not provenance['fields']['amount_scope'].get('human_confirmation')
