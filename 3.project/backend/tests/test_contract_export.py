import hashlib
import io
import json
import zipfile
from pathlib import Path

from PIL import Image

from backend.app.db.models import (AuditEvent, Document, DocumentFileInfo,
    ResubmissionRequest, WorkAssignment, ContractReview, ApprovalSignoff, ContractWorkflow)
from backend.app.services import contract_export_service as exports
from backend.app.services.storage_service import resolve_path
from test_api import create_contract
from test_review_workflow_api import upload
from test_document_versions import reissue
from test_preview_masking import words_line


def bundle(response):
    assert response.status_code == 200, response.text
    return zipfile.ZipFile(io.BytesIO(response.content))


def test_one_contract_bundle_keeps_previous_originals_history_and_current_checks(operator_client,db_factory,separate_client):
    cid=create_contract(operator_client)['contract_id']
    old=upload(operator_client,cid,'estimate')['document_id']
    unrelated=create_contract(operator_client,title='OTHER-CONTRACT-SECRET')['contract_id']
    upload(operator_client,unrelated)
    detail=operator_client.get(f'/api/contracts/{cid}').json()
    old_bytes=operator_client.get(f'/api/documents/{old}/download',params={'masked':False}).content
    response=reissue(operator_client,cid,old,detail['workflow']['revision'],
        text='견적서\n상호: 가상 검증업체\n사업자등록번호: 220-88-12345\n합계금액: 110원\n전액 청구',target_document_type='estimate')
    assert response.status_code==200,response.text
    new=response.json()[0]['document_id']
    with db_factory() as db:
        db.add(ResubmissionRequest(contract_id=cid,contact_method='EMAIL',requested_on='2026-10-03',
            due_on='2026-10-06',memo='unit request',actor_id=1,actor_name='unit reviewer'))
        db.add(WorkAssignment(contract_id=cid,contract_revision=1,contract_fingerprint='unit',
            assigner_id=1,assigner_name='unit reviewer',assignee_id=1,assignee_name='unit assignee',title='unit assignment'))
        db.add(ContractReview(contract_id=cid,revision=1,actor_id=1,actor_name='unit reviewer',
            decision='RETURNED',note='unit note',snapshot_json='{}'))
        db.add(ApprovalSignoff(contract_id=cid,revision=1,fingerprint='unit',actor_id=1,
            actor_name='unit reviewer',note='unit approval'))
        db.commit()
    revision=operator_client.get(f'/api/contracts/{cid}').json()['workflow']['revision']
    response=separate_client().get(f'/api/contracts/{cid}/export',params={'masked':False,'revision':revision})
    with bundle(response) as archive:
        manifest=json.loads(archive.read('manifest.json'))
        documents=manifest['documents']
        assert len(documents)==2
        previous=next(d for d in documents if d['document_id']==old)
        current=next(d for d in documents if d['document_id']==new)
        assert previous['is_current'] is False and current['is_current'] is True
        assert archive.read(previous['entry'])==old_bytes
        assert all(d['source_sha256']==d['export_sha256'] for d in documents)
        history=json.loads(archive.read('history.json'))
        assert history['requests'] and history['assignments'] and history['approvals'] and history['final_reviews']
        assert any(event['action']=='DOCUMENT_UPLOAD' for event in history['edits_and_events'])
        assert json.loads(archive.read('validation_results.json'))
        assert b'OTHER-CONTRACT-SECRET' not in b''.join(archive.read(name) for name in archive.namelist())
        assert all(not name.startswith('/') and '..' not in name.split('/') for name in archive.namelist())
    assert response.headers['cache-control']=='no-store'
    assert 'filename*=' in response.headers['content-disposition']
    assert operator_client.get(f'/api/contracts/{cid}').json()['workflow']['revision']==revision
    with db_factory() as db:
        events=db.query(AuditEvent).filter_by(contract_id=cid,action='CONTRACT_BUNDLE_EXPORT_REQUEST').all()
        assert len(events)==1 and json.loads(events[0].details)['masked'] is False


def test_masked_bundle_hides_files_metadata_and_old_correction_values(operator_client,db_factory):
    cid=create_contract(operator_client,vendor_name='가상 검증업체')['contract_id']
    did=upload(operator_client,cid,'estimate')['document_id']
    with db_factory() as db:
        doc=db.get(Document,did)
        doc.file_name='가상 검증업체_220-88-12345.txt'
        db.add(AuditEvent(contract_id=cid,document_id=did,actor_name='unit reviewer',action='EXTRACT_CORRECTED',
            details=json.dumps({'before':{'company_name':'과거 공급업체'},'note':'과거 공급업체에게 연락 010-1234-5678'})))
        db.commit()
    response=operator_client.get(f'/api/contracts/{cid}/export')  # masked defaults ON
    with bundle(response) as archive:
        texts='\n'.join(archive.read(name).decode('utf-8') for name in archive.namelist())
        assert '가상 검증업체' not in texts and '과거 공급업체' not in texts
        assert '220-88-12345' not in texts and '010-1234-5678' not in texts
        assert 'unit reviewer' not in texts and 'storage_path' not in texts
        entry=json.loads(archive.read('manifest.json'))['documents'][0]
        assert entry['mode']=='MASKED_TEXT_LAYOUT_NOT_PRESERVED'
        assert entry['entry']==f'documents/current/doc_{did}_v1.txt'
        assert '합계금액' in archive.read(entry['entry']).decode()
        assert entry['export_sha256']==hashlib.sha256(archive.read(entry['entry'])).hexdigest()


def install_raster(db_factory,did):
    with db_factory() as db:
        doc=db.get(Document,did)
        path=resolve_path(doc.storage_path).with_suffix('.png')
        with Image.new('RGB',(450,160),'white') as image:
            image.save(path)
        doc.storage_path=str(path)
        doc.file_name='unit.png'
        info=db.get(DocumentFileInfo,did)
        info.sha256=hashlib.sha256(path.read_bytes()).hexdigest()
        info.byte_size=path.stat().st_size
        db.commit()
    return path


def test_png_preview_download_and_zip_share_masking_policy(operator_client,db_factory,monkeypatch):
    cid=create_contract(operator_client)['contract_id']
    did=upload(operator_client,cid)['document_id']
    install_raster(db_factory,did)
    monkeypatch.setattr('backend.app.services.preview_masking_service._safe_winocr_recognize',lambda *a,**k:{
        'lines':[words_line(['상호:','가상','검증업체']),words_line(['발행일:','2026-09-01'],50)]})
    preview=operator_client.get(f'/api/documents/{did}/preview-image',params={'masked':True})
    download=operator_client.get(f'/api/documents/{did}/download',params={'masked':True})
    with bundle(operator_client.get(f'/api/contracts/{cid}/export')) as archive:
        manifest=json.loads(archive.read('manifest.json'))
        contents=[preview.content,download.content,archive.read(manifest['documents'][0]['entry'])]
    assert preview.status_code==download.status_code==200
    for content in contents:
        with Image.open(io.BytesIO(content)) as image:
            assert image.getpixel((120,15))==(45,45,45)
            assert image.getpixel((120,55))==(255,255,255)


def test_masking_failure_returns_no_raw_zip_and_cleans_temporary_files(operator_client,db_factory,monkeypatch,tmp_path):
    cid=create_contract(operator_client)['contract_id']
    did=upload(operator_client,cid)['document_id']
    install_raster(db_factory,did)
    monkeypatch.setattr('backend.app.services.preview_masking_service._safe_winocr_recognize',lambda *a,**k:None)
    original=exports.tempfile.TemporaryDirectory
    created=[]
    def workspace(**kw):
        folder=original(dir=tmp_path,**kw)
        created.append(Path(folder.name))
        return folder
    monkeypatch.setattr(exports.tempfile,'TemporaryDirectory',workspace)
    response=operator_client.get(f'/api/contracts/{cid}/export')
    assert response.status_code==503 and 'application/zip' not in response.headers['content-type']
    assert all(not path.exists() for path in created)
    with db_factory() as db:
        assert db.query(AuditEvent).filter_by(contract_id=cid,action='CONTRACT_BUNDLE_EXPORT_REQUEST').count()==0
    assert operator_client.get(f'/api/contracts/{cid}/export',params={'masked':False}).status_code==200
    assert all(not path.exists() for path in created)


def test_export_rejects_stale_revision_and_missing_or_modified_original(operator_client,db_factory):
    cid=create_contract(operator_client)['contract_id']
    did=upload(operator_client,cid)['document_id']
    url=f'/api/contracts/{cid}/export'
    assert operator_client.get(url,params={'revision':999}).status_code==409
    assert operator_client.get('/api/contracts/999999/export').status_code==404
    with db_factory() as db:
        path=resolve_path(db.get(Document,did).storage_path)
        saved=path.read_bytes()
        path.write_bytes(saved+b' changed')
    assert operator_client.get(url,params={'masked':False}).status_code==409
    path.unlink()
    assert operator_client.get(url).status_code==409


def test_export_rejects_contract_changes_during_render(operator_client,db_factory,monkeypatch):
    cid=create_contract(operator_client)['contract_id']
    upload(operator_client,cid)
    original=exports.masked_document
    def changed(doc):
        content=original(doc)
        with db_factory() as db:
            row=db.get(ContractWorkflow,cid)
            row.revision+=1
            db.commit()
        return content
    monkeypatch.setattr(exports,'masked_document',changed)
    assert operator_client.get(f'/api/contracts/{cid}/export').status_code==409


def test_export_requires_login(client):
    assert client.get('/api/contracts/1/export').status_code==401


def test_masked_metadata_preserves_opaque_checksums_with_ten_digit_runs():
    digest='a2208812345b'+('f'*52)
    data=exports.public_data({'fingerprint':digest,'source_sha256':digest,
        'export_sha256':digest,'note':'사업자번호 2208812345'},True,{'business_number':'2208812345'})
    assert data['fingerprint']==data['source_sha256']==data['export_sha256']==digest
    assert '2208812345' not in data['note']


def test_export_size_limits_fail_without_partial_archive(operator_client,monkeypatch):
    cid=create_contract(operator_client)['contract_id']
    upload(operator_client,cid)
    monkeypatch.setattr(exports,'MAX_EXPORT_BYTES',1)
    assert operator_client.get(f'/api/contracts/{cid}/export').status_code==413
    assert operator_client.get(f'/api/contracts/{cid}/export',params={'masked':False}).status_code==413


def test_docx_bundle_delivers_masked_text_instead_of_original_binary(operator_client):
    from docx import Document as WordDocument
    cid=create_contract(operator_client,vendor_name='가상 검증업체')['contract_id']
    word=WordDocument()
    for line in ('견적서','상호: 가상 검증업체','사업자등록번호: 220-88-12345','합계금액: 110원','전액 청구'):
        word.add_paragraph(line)
    source=io.BytesIO()
    word.save(source)
    result=operator_client.post(f'/api/contracts/{cid}/documents',
        files=[('files',('estimate.docx',source.getvalue(),'application/vnd.openxmlformats-officedocument.wordprocessingml.document'))],
        data={'target_document_type':'estimate'})
    assert result.status_code==200,result.text
    with bundle(operator_client.get(f'/api/contracts/{cid}/export')) as archive:
        entry=json.loads(archive.read('manifest.json'))['documents'][0]
        assert entry['entry'].endswith('.txt') and entry['mode']=='MASKED_TEXT_LAYOUT_NOT_PRESERVED'
        text=archive.read(entry['entry']).decode()
        assert '견적서' in text and '가상 검증업체' not in text and '220-88-12345' not in text
        assert not any(name.endswith('.docx') for name in archive.namelist())


def test_scanned_pdf_bundle_is_flattened_and_uses_presentation_ocr_mask(operator_client,db_factory,monkeypatch):
    from pypdf import PdfReader
    from test_storage_concurrency import seed_pdf
    cid=create_contract(operator_client)['contract_id']
    seed_pdf(db_factory,cid,pages=2)
    calls=[]
    def recognize(*a,**k):
        calls.append(1)
        return {'lines':[words_line(['사업자번호:', '220-88-12345'])]}
    monkeypatch.setattr('backend.app.services.preview_masking_service._safe_winocr_recognize',recognize)
    with bundle(operator_client.get(f'/api/contracts/{cid}/export')) as archive:
        entry=json.loads(archive.read('manifest.json'))['documents'][0]
        content=archive.read(entry['entry'])
        assert entry['mode']=='MASKED_PDF' and content.startswith(b'%PDF-')
        pdf=PdfReader(io.BytesIO(content))
        assert len(pdf.pages)==2 and all(not page.extract_text() for page in pdf.pages)
        assert len(calls)==2
