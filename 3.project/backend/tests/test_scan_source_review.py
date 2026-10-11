"""Policy/false-PASS tests. Real Windows OCR is exercised separately on raster fixtures."""
from types import SimpleNamespace as NS
import hashlib,json
import pytest
from PIL import Image
from backend.app.services.business_identity_service import POLICY,_scan_identity,automatic_field_review,build_scan_review
from backend.app.validation.engine import RuleEngine

def proof():
    loc={f:{'page':1,'line':i,'bbox':{'page':1,'x':.1,'y':.1,'width':.3,'height':.03}} for i,f in enumerate(['company_name','business_registration_no','total_amount','supply_amount','tax_amount'],1)}
    return {'policy':POLICY,'kind':'tax_invoice','method':'RASTER_OCR_ROW_CROP','identity':{'name':'syntheticvendor','number':'0000000000','financial':{'total_amount':110,'supply_amount':100,'tax_amount':10},'locations':loc},'verified_fields':list(loc)}

def context(tmp_path):
    path=tmp_path/'scan.png'
    with Image.new('RGB',(1400,1800),'white') as im:im.save(path)
    sha=hashlib.sha256(path.read_bytes()).hexdigest();source=proof();source['source_sha256']=sha
    values={'company_name':'Synthetic Vendor','business_registration_no':'000-00-00000','total_amount':110,'supply_amount':100,'tax_amount':10,'amount_scope':'FULL'}
    doc=NS(document_id=1,document_type='tax_invoice');checks=[NS(field='1',rule_id=r,status='PASS') for r in ['BUSINESS_NO_MATCH','AMOUNT_MATCH_TAX_INVOICE']]
    anchor={'name':'syntheticvendor','number':'0000000000','total':110,'payment_mode':'FULL','document_id':2,'confirmed':True}
    return doc,values,checks,path,sha,anchor,source

def test_scan_metadata_is_not_model_confidence_or_a_human_confirmation(tmp_path):
    doc,values,checks,path,sha,anchor,source=context(tmp_path)
    assert automatic_field_review(doc,'total_amount',values,{'confidence':1},checks,path,sha,anchor,{}) is None
    stored={'extraction_metadata':{'automatic_source_review':source}}
    r=automatic_field_review(doc,'total_amount',values,stored,checks,path,sha,anchor,{})
    assert r['source_method']=='RASTER_OCR_ROW_CROP' and 'human_confirmation' not in r
    assert 'human_review' not in stored

@pytest.mark.parametrize('fault',['source_hash','crop_disagreement','old_policy','unknown_scope','correlated_amount','correlated_number'])
def test_scan_false_pass_cannot_remove_source_work(tmp_path,fault):
    doc,values,checks,path,sha,anchor,source=context(tmp_path)
    field='business_registration_no' if fault=='correlated_number' else 'amount_scope' if fault=='unknown_scope' else 'total_amount'
    if fault=='source_hash':source['source_sha256']='different'
    elif fault=='crop_disagreement':source['verified_fields'].remove('tax_amount')
    elif fault=='old_policy':source['policy']='old'
    elif fault=='unknown_scope':values['amount_scope']='UNKNOWN'
    elif fault=='correlated_amount':values.update(total_amount=220,supply_amount=200,tax_amount=20);anchor['total']=220
    elif fault=='correlated_number':values['business_registration_no']='111-11-11111';anchor['number']='1111111111'
    assert automatic_field_review(doc,field,values,{'extraction_metadata':{'automatic_source_review':source}},checks,path,sha,anchor,{}) is None

def test_source_mismatch_is_visible_even_when_stored_amount_matches_wrong_basis(tmp_path):
    doc,values,checks,path,sha,anchor,source=context(tmp_path)
    values.update(total_amount=220,supply_amount=200,tax_amount=20,extraction_metadata={'automatic_source_review':source})
    _,results=RuleEngine().validate_contract_evidence(1,'synthetic','Synthetic Vendor','000-00-00000',220,
        [{'document_id':1,'document_type':'tax_invoice','fields':values,'sha256':sha}],required_document_types=[],amount_policy={'amount_basis':'TOTAL','payment_mode':'FULL'})
    assert any(c.rule_id=='AMOUNT_MATCH_TAX_INVOICE' and c.status=='PASS' for c in results)
    assert any(c.rule_id=='SOURCE_VALUE_MATCH_TOTAL_AMOUNT' and c.status=='REVIEW' and c.expected=='110원' for c in results)

def test_current_human_identity_fix_reuses_other_verified_scan_rows(tmp_path):
    doc,values,checks,path,sha,anchor,source=context(tmp_path)
    source['identity']['name']='ocrtypo';source['verified_fields'].remove('company_name')
    stored={'extraction_metadata':{'automatic_source_review':source}}
    assert automatic_field_review(doc,'total_amount',values,stored,checks,path,sha,anchor,{}) is None
    assert automatic_field_review(doc,'total_amount',values,stored,checks,path,sha,anchor,{},human_fields={'company_name'})
    assert not stored.get('human_review')

def test_scoped_ai_problem_does_not_force_other_verified_fields_back_to_full_review(tmp_path):
    doc,values,checks,path,sha,anchor,source=context(tmp_path)
    stored={'ai_review':{'manual_review_required':True,'targets':['amount_scope']},'extraction_metadata':{'automatic_source_review':source}}
    assert automatic_field_review(doc,'total_amount',values,stored,checks,path,sha,anchor,{})
    assert automatic_field_review(doc,'amount_scope',values,stored,checks,path,sha,anchor,{}) is None

def test_blank_raster_has_no_verified_source_even_with_existing_extracted_values(tmp_path):
    _,_,_,path,sha,_,_=context(tmp_path)
    assert build_scan_review(path,sha,'tax_invoice')['identity'] is None

def test_internal_scan_identity_never_leaks_into_public_response_or_export(operator_client,db_factory):
    from test_api import create_contract
    from test_review_workflow_api import upload
    from backend.app.db.models import Document
    from backend.app.services.contract_export_service import public_data
    cid=create_contract(operator_client)['contract_id'];did=upload(operator_client,cid,'estimate')['document_id']
    metadata={'evidence_complete':True,'automatic_source_review':{'identity':{'name':'private-normalized-marker','number':'1111111111'}}}
    with db_factory() as db:
        doc=db.get(Document,did);raw=json.loads(doc.extract.raw_fields);raw['extraction_metadata']=metadata;doc.extract.raw_fields=json.dumps(raw);db.commit()
    exposed=operator_client.get(f'/api/contracts/{cid}').json()['documents'][0]['analysis']['extraction_metadata']
    assert exposed=={'evidence_complete':True}
    for masked in [False,True]:
        output=public_data({'extraction_metadata':metadata},masked,{})
        assert output=={'extraction_metadata':{'evidence_complete':True}}

def test_scan_role_ambiguity_and_missing_won_are_not_monetary_evidence():
    ambiguous=[{'page':1,'text':'공급자 공급받는자\n상호: Synthetic Vendor\n사업자등록번호: 000-00-00000\n합계금액: 110원'}]
    assert _scan_identity(ambiguous,'tax_invoice') is None
    plain=[{'page':1,'text':'공급자\n상호: Synthetic Vendor\n사업자등록번호: 000-00-00000\n합계금액: 110 USD'}]
    parsed,_=_scan_identity(plain,'tax_invoice');assert parsed['financial']=={}

def test_vendor_name_difference_is_a_problem_even_if_business_number_matches():
    _,checks=RuleEngine().validate_contract_evidence(1,'synthetic','Synthetic Vendor','000-00-00000',110,
        [{'document_id':1,'document_type':'estimate','fields':{'company_name':'Other Vendor','business_registration_no':'000-00-00000','total_amount':110,'amount_basis':'TOTAL'}}],required_document_types=[],amount_policy={'amount_basis':'TOTAL','payment_mode':'FULL'})
    assert any(c.rule_id=='BUSINESS_NO_MATCH' and c.status=='PASS' for c in checks)
    assert any(c.rule_id=='VENDOR_NAME_MATCH' and c.status=='REVIEW' for c in checks)

@pytest.mark.parametrize('initial_name',[None,'Wrong Vendor'])
def test_ingestion_supplements_only_missing_crop_verified_fields_without_human_proofs(operator_client,db_factory,monkeypatch,initial_name):
    from test_api import create_contract
    from backend.app.db.models import Document
    from backend.app.schemas.document import DocumentAnalysisResponse,AnalysisFields,MaskInfo
    from backend.app.schemas.common import DocumentType
    from backend.app.services import pipeline_service,business_identity_service
    cid=create_contract(operator_client,vendor_name='Synthetic Vendor',business_number='000-00-00000')['contract_id']
    monkeypatch.setattr(pipeline_service,'analyze_document',lambda *a,**kw:(DocumentAnalysisResponse(document_type=DocumentType.BANK_ACCOUNT,confidence=1,mask=MaskInfo(),fields=AnalysisFields(company_name=initial_name,business_registration_no='000-00-00000',bank_name='국민은행',account_number='000-000-000000')),'통장사본\n예금주: Synthetic Vendor','통장사본'))
    def source(path,sha,kind):
        p=proof();p.update(kind=kind,source_sha256=sha);p['identity']['values']={'company_name':'Synthetic Vendor'};p['verified_fields']=['company_name','business_registration_no'];return p
    monkeypatch.setattr(business_identity_service,'build_scan_review',source)
    import io
    buf=io.BytesIO()
    with Image.new('RGB',(1400,1800),'white') as im:im.save(buf,format='PNG')
    result=operator_client.post(f'/api/contracts/{cid}/documents',files=[('files',('bank.png',buf.getvalue(),'image/png'))],data={'target_document_type':'bank_account'})
    assert result.status_code==200,result.text
    with db_factory() as db:
        raw=json.loads(db.get(Document,result.json()[0]['document_id']).extract.raw_fields)
        assert raw['company_name']==('Synthetic Vendor' if initial_name is None else initial_name)
        assert not raw.get('human_review')
        if initial_name is None:assert raw['extraction_metadata']['automatic_source_review']['completed_missing_fields']==['company_name']
