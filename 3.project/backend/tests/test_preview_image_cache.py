import io,json
from collections import OrderedDict
from PIL import Image
from test_api import create_contract
from backend.app.db.models import Document,DocumentExtract,DocumentFileInfo
from backend.app.services import storage_service, preview_masking_service, preview_image_cache
from backend.app.services.workflow_service import touch_contract


def image_document(client,db_factory):
    cid=create_contract(client)['contract_id']
    stream=io.BytesIO()
    with Image.new('RGB',(120,80),'white') as image:
        image.save(stream,format='PNG')
    key,path,sha=storage_service.store_original(cid,'preview.png',stream.getvalue())
    with db_factory() as db:
        doc=Document(contract_id=cid,file_name='preview.png',storage_path=key,document_type='estimate',processing_status='COMPLETED')
        db.add(doc);db.flush();did=doc.document_id
        db.add(DocumentExtract(document_id=did,raw_fields=json.dumps({'company_name':'가상업체'})))
        db.add(DocumentFileInfo(document_id=did,sha256=sha,byte_size=len(stream.getvalue())))
        db.commit()
    return cid,did,path,sha


def test_mask_modes_sensitive_changes_and_revision_never_reuse_wrong_image(operator_client,db_factory,monkeypatch):
    cid,did,_,sha=image_document(operator_client,db_factory)
    calls=[]
    def mask(image,sensitive_dict):
        calls.append(sensitive_dict)
        return Image.new('RGB',image.size,'black')
    monkeypatch.setattr(preview_masking_service,'mask_image_with_ocr',mask)
    revision=operator_client.get(f'/api/contracts/{cid}').json()['workflow']['revision']
    url=f'/api/documents/{did}/preview-image'
    first=operator_client.get(url,params={'masked':True,'revision':revision,'source_sha256':sha})
    second=operator_client.get(url,params={'masked':True,'revision':revision,'source_sha256':sha})
    assert first.status_code==second.status_code==200 and first.content==second.content
    assert len(calls)==1
    original=operator_client.get(url,params={'masked':False,'revision':revision})
    assert original.status_code==200 and original.content!=first.content
    assert operator_client.get(url,params={'masked':True,'revision':revision}).content==first.content
    assert first.headers['cache-control']=='no-store'
    with db_factory() as db:
        db.get(Document,did).extract.raw_fields=json.dumps({'company_name':'다른 가상업체'})
        db.commit()
    assert operator_client.get(url,params={'masked':True,'revision':revision}).status_code==200
    assert len(calls)==2  # Sensitive values matter even if revision was not touched.
    with db_factory() as db:
        touch_contract(db,cid);db.commit()
    assert operator_client.get(url,params={'masked':True,'revision':revision}).status_code==409
    latest=operator_client.get(f'/api/contracts/{cid}').json()['workflow']['revision']
    assert operator_client.get(url,params={'masked':True,'revision':latest}).status_code==200
    assert len(calls)==3


def test_warm_cache_checks_auth_and_actual_source_bytes(operator_client,db_factory,separate_client):
    _,did,path,sha=image_document(operator_client,db_factory)
    url=f'/api/documents/{did}/preview-image'
    old=operator_client.get(url,params={'masked':False,'source_sha256':sha})
    with Image.new('RGB',(120,80),'red') as image:
        image.save(path,format='PNG')
    assert operator_client.get(url,params={'masked':False,'source_sha256':sha}).status_code==409
    changed=operator_client.get(url,params={'masked':False})
    assert changed.status_code==200 and changed.content!=old.content
    unauth=separate_client('representative')
    unauth.cookies.clear()
    assert unauth.get(url,params={'masked':False}).status_code==401


def test_mask_failure_is_retryable_and_never_returns_warm_original(operator_client,db_factory,monkeypatch):
    _,did,_,_=image_document(operator_client,db_factory)
    url=f'/api/documents/{did}/preview-image'
    assert operator_client.get(url,params={'masked':False}).status_code==200
    calls=[]
    def fail(*args,**kwargs):
        calls.append(1);raise RuntimeError('synthetic OCR failure')
    monkeypatch.setattr(preview_masking_service,'mask_image_with_ocr',fail)
    for _ in range(2):
        assert operator_client.get(url,params={'masked':True}).status_code==503
    assert len(calls)==2


def test_cache_expires_and_is_bounded(monkeypatch):
    monkeypatch.setattr(preview_image_cache,'_entries',OrderedDict())
    monkeypatch.setattr(preview_image_cache,'_bytes',0)
    monkeypatch.setattr(preview_image_cache,'MAX_ENTRIES',2)
    monkeypatch.setattr(preview_image_cache,'MAX_BYTES',30)
    clock=[0];monkeypatch.setattr(preview_image_cache,'monotonic',lambda:clock[0])
    calls=[]
    def render():
        calls.append(1);return b'\x89PNG\r\n\x1a\n'+b'abcdef'
    for key in ('a','a','b','c'):
        preview_image_cache.cached_preview(key,render)
    assert len(calls)==3 and len(preview_image_cache._entries)==2
    assert preview_image_cache._bytes<=30
    clock[0]=121
    preview_image_cache.cached_preview('c',render)
    assert len(calls)==4
