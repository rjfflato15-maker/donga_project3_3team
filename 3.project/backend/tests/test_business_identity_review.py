"""Source-backed exemption boundaries, using actual native PDF objects."""
import hashlib
import json

import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject as D, NameObject as N, ArrayObject as A, NumberObject as I, TextStringObject as T, DecodedStreamObject

from backend.app.db.models import Document, AuditEvent
from backend.app.services.business_identity_service import native_identity
from test_api import create_contract
from submission_helpers import complete_source_review, submission_body


def native_pdf(lines, *, mode=0, drawing=False, y=770, extra=''):
    writer = PdfWriter()
    page = writer.add_blank_page(595, 842)
    font = D({N('/Type'):N('/Font'), N('/Subtype'):N('/Type0'), N('/BaseFont'):N('/HYSMyeongJo-Medium'),
        N('/Encoding'):N('/UniKS-UCS2-H'), N('/DescendantFonts'):A([D({N('/Type'):N('/Font'),
        N('/Subtype'):N('/CIDFontType0'), N('/BaseFont'):N('/HYSMyeongJo-Medium'),
        N('/CIDSystemInfo'):D({N('/Registry'):T('Adobe'),N('/Ordering'):T('Korea1'),N('/Supplement'):I(0)})})])})
    page[N('/Resources')] = D({N('/Font'):D({N('/F1'):writer._add_object(font)})})
    content = f'BT /F1 12 Tf {mode} Tr 20 TL 50 {y} Td ' + ' '.join('<'+s.encode('utf-16be').hex()+'> Tj T*' for s in lines) + ' ET'
    if drawing: content += ' 1 1 1 rg 40 710 350 70 re f'
    content += extra
    stream = DecodedStreamObject(); stream.set_data(content.encode()); page[N('/Contents')] = writer._add_object(stream)
    import io
    out = io.BytesIO(); writer.write(out); return out.getvalue()


LINES = ['사업자등록증', '상호: Synthetic Vendor', '사업자등록번호: 000-00-00000']


@pytest.mark.parametrize('mode,drawing,y', [(0,False,770),(3,False,770),(0,True,770),(0,False,900)])
def test_only_visible_native_text_without_other_page_content_is_eligible(tmp_path, mode, drawing, y):
    data = native_pdf(LINES,mode=mode,drawing=drawing,y=y); path=tmp_path/'source.pdf';path.write_bytes(data)
    result = native_identity(str(path),hashlib.sha256(data).hexdigest(),'business_registration')
    assert (result is not None and (result['number'],result['name']) == ('0000000000','syntheticvendor')) == (mode==0 and not drawing and y==770)


@pytest.mark.parametrize('lines,extra,eligible', [
    (['시연용 합성 예시 · 상호 / 인명 모두 가상']+LINES, '', True),
    (LINES, ' 0 0 20 20 re S', True),  # unrelated table/decoration is allowed
    (LINES, ' 45 730 m 300 730 l S', False),  # number crossed out
    (LINES, ' BT /F1 12 Tf 50 730 Td <0058005800580058> Tj ET', False),  # another text object covers the number
    (['공급자','상호: Synthetic Vendor','사업자등록번호: 000-00-00000',
      '공급받는자','상호: Buyer','사업자등록번호: 111-11-11111'], '', True),
    (['공급자 공급받는자']+LINES, '', False),
    (LINES+['사업자등록번호: 000-00-0000O'], '', False),
    (['사업자등록증','상호: Synthetic Vendor','사업자등록번호: 000-00-0000O'], '', False),
])
def test_source_roles_layout_and_unreadable_number_boundaries(tmp_path,lines,extra,eligible):
    data=native_pdf(lines,extra=extra);path=tmp_path/'source.pdf';path.write_bytes(data)
    result=native_identity(str(path),hashlib.sha256(data).hexdigest(),'business_registration')
    assert bool(result)==eligible


def test_supported_native_fields_are_distinct_from_unverified_text_and_people(operator_client,separate_client,db_factory):
    cid,anchor,did=setup_source(operator_client,separate_client,native_pdf(LINES))
    identity='상호: Synthetic Vendor\n사업자등록번호: 000-00-00000\n'
    sources=[('estimate','estimate.pdf',native_pdf(['견적서']+LINES[1:]+['합계금액: 110원']),'application/pdf'),
      ('tax_invoice','invoice.pdf',native_pdf(['세금계산서']+LINES[1:]+['공급가액: 100원','세액: 10원','합계금액: 110원','전액 청구']),'application/pdf'),
      ('bank_account','bank.txt',('통장사본\n'+identity+'은행: 국민은행\n계좌번호: 000-000-000000\n').encode(),'text/plain'),
      ('inspection_confirmation','inspection.txt',('검수확인서\n'+identity+'검수 완료\n').encode(),'text/plain')]
    for kind,name,data,mime in sources:
        result=operator_client.post(f'/api/contracts/{cid}/documents',files=[('files',(name,data,mime))],data={'target_document_type':kind})
        assert result.status_code==200,result.text
    before=operator_client.get(f'/api/contracts/{cid}').json()
    assert len(before['workflow']['submission']['gate']['blockers'])==10
    reviewed=confirm_anchor(operator_client,cid,anchor);gate=reviewed['workflow']['submission']['gate']
    assert len(gate['automatic_review'])==10
    assert len([b for b in gate['blockers'] if b['code']=='HUMAN_REVIEW_REQUIRED'])==7  # contract checked; TXT sources retain their obligations
    assert {b['document_type'] for b in gate['automatic_review']}=={'estimate','business_registration','tax_invoice'}
    ready=complete_source_review(operator_client,cid)
    result=operator_client.post(f'/api/pilot/contracts/{cid}/submission',json=submission_body(ready))
    assert result.status_code==200,result.text
    from test_submission_flow import decision
    representative=separate_client('representative')
    approved=representative.post(f'/api/contracts/{cid}/reviews',json=decision(result.json()))
    assert approved.status_code==200,approved.text
    assert approved.json()['stage']=='PAYMENT'
    with db_factory() as db:
        for item in gate['automatic_review']:
            stored=json.loads(db.get(Document,item['document_id']).extract.raw_fields)
            assert 'business_registration_no' not in (stored.get('human_review') or {}).get('field_confirmations',{})
        event=db.query(AuditEvent).filter_by(contract_id=cid,action='CONTRACT_SUBMITTED').one()
        assert len(json.loads(event.details)['automatic_review'])==10


def setup_source(operator, separate, data):
    rep = separate('representative'); policy = rep.get('/api/pilot/company-policy/presets').json()[1]
    policy['required_document_types']=['contract','business_registration'];assert rep.put('/api/pilot/company-policy',json=policy).status_code==200
    cid=create_contract(operator,vendor_name='Synthetic Vendor',business_number='000-00-00000',contract_amount=110)['contract_id']
    text='계약서\n상호: Synthetic Vendor\n사업자등록번호: 000-00-00000\n공급가액: 100원\n세액: 10원\n합계금액: 110원\n'
    result=operator.post(f'/api/contracts/{cid}/documents',files=[('files',('contract.txt',text.encode(),'text/plain'))],data={'target_document_type':'contract'})
    assert result.status_code==200,result.text;anchor=result.json()[0]['document_id']
    result=operator.post(f'/api/contracts/{cid}/documents',files=[('files',('registration.pdf',data,'application/pdf'))],data={'target_document_type':'business_registration'})
    assert result.status_code==200,result.text;did=result.json()[0]['document_id']
    return cid,anchor,did


def confirm_anchor(client,cid,anchor):
    detail=client.get(f'/api/contracts/{cid}').json()
    response=client.post(f'/api/documents/{anchor}/confirm-fields',json={'revision':detail['workflow']['revision'],'fields':['company_name','business_registration_no','total_amount']})
    assert response.status_code==200,response.text
    return client.get(f'/api/contracts/{cid}').json()


def test_native_repeat_number_reduces_obligation_without_forging_a_human_proof(operator_client,separate_client,db_factory):
    cid,anchor,did=setup_source(operator_client,separate_client,native_pdf(LINES))
    before=operator_client.get(f'/api/contracts/{cid}').json();assert len(before['workflow']['submission']['gate']['automatic_review'])==2
    assert not before['workflow']['submission']['gate']['can_submit']
    reviewed=confirm_anchor(operator_client,cid,anchor);gate=reviewed['workflow']['submission']['gate']
    assert len(gate['automatic_review'])==2
    assert gate['automatic_review'][0]['document_id']==did and gate['automatic_review'][0]['field']=='business_registration_no'
    assert not [b for b in gate['blockers'] if b['code']=='HUMAN_REVIEW_REQUIRED']
    with db_factory() as db:
        raw=json.loads(db.get(Document,did).extract.raw_fields)
        assert 'business_registration_no' not in (raw.get('human_review') or {}).get('field_confirmations',{})
    detail=complete_source_review(operator_client,cid)
    response=operator_client.post(f'/api/pilot/contracts/{cid}/submission',json=submission_body(detail));assert response.status_code==200,response.text
    with db_factory() as db:
        event=db.query(AuditEvent).filter_by(contract_id=cid,action='CONTRACT_SUBMITTED').one()
        assert json.loads(event.details)['automatic_review'][0]['anchor_document_id']==anchor


def test_only_source_verified_fields_are_excluded_in_a_mixed_format_contract(operator_client,separate_client):
    cid,anchor,did=setup_source(operator_client,separate_client,native_pdf(LINES))
    text='상호: Synthetic Vendor\n사업자등록번호: 000-00-00000\n'
    sources=[('estimate','estimate.pdf',native_pdf(['견적서']+LINES[1:]+['합계금액: 110원']),'application/pdf'),
        ('bank_account','bank.txt',('통장사본\n'+text+'은행: 국민은행\n계좌번호: 000-000-000000\n').encode(),'text/plain'),
        ('tax_invoice','invoice.txt',('세금계산서\n'+text+'공급가액: 100원\n세액: 10원\n합계금액: 110원\n전액 청구\n').encode(),'text/plain'),
        ('inspection_confirmation','inspection.txt',('검수확인서\n'+text+'검수 완료\n').encode(),'text/plain')]
    for kind,name,data,mime in sources:
        result=operator_client.post(f'/api/contracts/{cid}/documents',files=[('files',(name,data,mime))],data={'target_document_type':kind})
        assert result.status_code==200,result.text
    before=operator_client.get(f'/api/contracts/{cid}').json();gate=before['workflow']['submission']['gate']
    assert len([b for b in gate['blockers'] if b['code']=='HUMAN_REVIEW_REQUIRED'])==15
    after=confirm_anchor(operator_client,cid,anchor);gate=after['workflow']['submission']['gate']
    assert len(gate['automatic_review'])==5
    # Only estimate/registration are native here; other TXT inputs stay manual.
    assert len([b for b in gate['blockers'] if b['code']=='HUMAN_REVIEW_REQUIRED'])==12
    assert {b['document_type'] for b in gate['automatic_review']}=={'estimate','business_registration'}


def test_unknown_scope_remains_a_value_entry_block_even_with_a_legacy_confirmation(operator_client,separate_client,db_factory):
    cid,anchor,did=setup_source(operator_client,separate_client,native_pdf(LINES))
    text='세금계산서\n상호: Synthetic Vendor\n사업자등록번호: 000-00-00000\n합계금액: 110원\n'
    response=operator_client.post(f'/api/contracts/{cid}/documents',files=[('files',('invoice.txt',text.encode(),'text/plain'))],data={'target_document_type':'tax_invoice'})
    assert response.status_code==200,response.text;invoice=response.json()[0]['document_id']
    with db_factory() as db:
        row=db.get(Document,invoice);raw=json.loads(row.extract.raw_fields);raw['amount_scope']='UNKNOWN'
        raw['human_review']={'field_confirmations':{'amount_scope':{'value':'UNKNOWN','actor_name':'legacy','at':'old'}}}
        row.extract.raw_fields=json.dumps(raw,ensure_ascii=False);db.commit()
    detail=operator_client.get(f'/api/contracts/{cid}').json();gate=detail['workflow']['submission']['gate']
    assert any(b['document_id']==invoice and b['field']=='amount_scope' and b['code']=='FIELD_VALUE_REQUIRED' for b in gate['blockers'])
    assert not gate['can_submit'] and not gate['can_submit_exception']


@pytest.mark.parametrize('lines,mode,drawing', [
    (LINES[:2]+['사업자등록번호: 111-11-11111'],0,False),
    (['사업자등록증','상호: Other Vendor','사업자등록번호: 000-00-00000'],0,False),
    (LINES+['다른 사업자등록번호: 111-11-11111'],0,False),
    (['공급받는자']+LINES,0,False),
    (LINES,3,False), (LINES,0,True),
])
def test_false_pass_in_saved_values_cannot_exempt_different_or_ambiguous_original(operator_client,separate_client,db_factory,monkeypatch,lines,mode,drawing):
    monkeypatch.setattr('backend.app.ai.preprocessor.run_ocr_on_image',lambda image:'')
    cid,anchor,did=setup_source(operator_client,separate_client,native_pdf(lines,mode=mode,drawing=drawing))
    # Deliberately make stored predictions agree with the contract. The real
    # source stays wrong/ambiguous; repeating saved predictions is not evidence.
    with db_factory() as db:
        doc=db.get(Document,did);raw=json.loads(doc.extract.raw_fields);raw.update(company_name='Synthetic Vendor',business_registration_no='000-00-00000',ai_review={})
        raw.pop('human_review',None);doc.extract.raw_fields=json.dumps(raw,ensure_ascii=False);db.commit()
    detail=confirm_anchor(operator_client,cid,anchor);gate=detail['workflow']['submission']['gate']
    assert any(c['rule_id']=='BUSINESS_NO_MATCH' and c['status']=='PASS' and c['field']==str(did) for c in detail['checks'])
    assert gate['automatic_review']==[]
    assert any(b['document_id']==did and (b['field']=='business_registration_no' or b['code'] in {'READING_INCOMPLETE','READING_FAILED'}) for b in gate['blockers'])
    assert operator_client.post(f'/api/pilot/contracts/{cid}/submission',json=submission_body(detail)).status_code==400


@pytest.mark.parametrize('variant',['ai_target','deferred','incomplete','tamper','anchor_undo'])
def test_exemption_is_recomputed_when_current_evidence_or_review_changes(operator_client,separate_client,db_factory,variant):
    from backend.app.services.storage_service import resolve_path
    cid,anchor,did=setup_source(operator_client,separate_client,native_pdf(LINES));detail=confirm_anchor(operator_client,cid,anchor)
    assert len(detail['workflow']['submission']['gate']['automatic_review'])==2
    if variant=='deferred':
        response=operator_client.post(f'/api/documents/{did}/defer-field',json={'field':'business_registration_no','kind':'DEFER','note':'추가 원문 확인 필요','revision':detail['workflow']['revision']})
        assert response.status_code==200,response.text
    with db_factory() as db:
        doc=db.get(Document,anchor if variant=='anchor_undo' else did);raw=json.loads(doc.extract.raw_fields)
        if variant=='ai_target':raw['ai_review']={'targets':['business_registration_no'],'manual_review_required':True}
        if variant=='incomplete':raw['extraction_metadata']={'evidence_complete':False}
        if variant=='anchor_undo':raw['human_review']['field_confirmations'].pop('business_registration_no')
        if variant=='tamper':resolve_path(doc.storage_path).write_bytes(native_pdf(LINES+['changed']))
        doc.extract.raw_fields=json.dumps(raw,ensure_ascii=False);db.commit()
    latest=operator_client.get(f'/api/contracts/{cid}').json();gate=latest['workflow']['submission']['gate']
    if variant=='anchor_undo':
        assert not gate['can_submit'] and all(not item['anchor_confirmed'] for item in gate['automatic_review'])
        assert gate['fingerprint']!=detail['workflow']['submission']['gate']['fingerprint']
    elif variant=='ai_target':
        assert not any(item['field']=='business_registration_no' for item in gate['automatic_review'])
        assert any(b['field']=='business_registration_no' for b in gate['blockers'])
        assert any(item['field']=='company_name' for item in gate['automatic_review'])
    else:assert gate['automatic_review']==[]

