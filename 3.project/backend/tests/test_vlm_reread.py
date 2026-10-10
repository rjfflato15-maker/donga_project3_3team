import base64
import json
import pytest

from backend.app.ai.local_vlm import LocalVlmClient, VlmError
from backend.app.db.models import Document, AuditEvent
from backend.app.services import vlm_reread_service as service
from test_api import create_contract
from test_review_workflow_api import upload
from test_contract_export import install_raster

MODEL = {'name': 'qwen2.5vl:7b', 'digest': 'test-only-model-digest', 'vision': True}


def answer(value='100', quote='합계금액: 100원', party='SUPPLIER'):
    return {'state': 'VALUE', 'value': value, 'quote': quote, 'party': party}


def visual_doc(client, db_factory):
    cid = create_contract(client)['contract_id']
    did = upload(client, cid)['document_id']
    path = install_raster(db_factory, did)
    detail = client.get(f'/api/contracts/{cid}').json()
    return cid, did, path, detail['workflow']['revision']


def read(client, did, revision, fields=None, masked=False):
    return client.post(f'/api/documents/{did}/vlm-reread?masked={str(masked).lower()}',
        json={'revision': revision, 'page': 1, 'fields': fields or ['total_amount', 'tax_amount']})


def fake_read(monkeypatch):
    monkeypatch.setattr(LocalVlmClient, 'read', lambda self, image, fields, kind: (
        {field: answer('0', '세액: 0원') if field == 'tax_amount' else answer() for field in fields}, MODEL))


def test_reread_proposes_values_without_changing_saved_fields_or_review(operator_client, db_factory, monkeypatch):
    cid, did, _, revision = visual_doc(operator_client, db_factory)
    before = operator_client.get(f'/api/contracts/{cid}').json()
    fake_read(monkeypatch)
    result = read(operator_client, did, revision)
    assert result.status_code == 200, result.text
    data = result.json()
    assert data['automatically_applied'] is False and data['evidence_verified'] is False
    assert [item['value'] for item in data['candidates']] == [100, 0]
    assert all(item['usable'] for item in data['candidates'])
    after = operator_client.get(f'/api/contracts/{cid}').json()
    assert after['workflow'] == before['workflow']
    assert after['documents'][0]['analysis']['fields'] == before['documents'][0]['analysis']['fields']
    latest = operator_client.get(f'/api/documents/{did}/vlm-reread', params={'revision': revision}).json()
    assert latest['run_id'] == data['run_id']


def test_only_selected_original_confirmed_values_are_saved_and_invalidate_revision(operator_client, db_factory, monkeypatch):
    cid, did, _, revision = visual_doc(operator_client, db_factory)
    fake_read(monkeypatch)
    with db_factory() as db:
        doc = db.get(Document, did)
        doc.processing_status = 'FAILED'
        db.commit()
    data = read(operator_client, did, revision).json()
    body = {'run_id': data['run_id'], 'revision': revision, 'fields': ['tax_amount'],
        'note': '이미지 원문 세액 0원을 직접 확인', 'acknowledge_original': False}
    assert operator_client.post(f'/api/documents/{did}/vlm-confirm', json=body).status_code == 422
    body['acknowledge_original'] = True
    saved = operator_client.post(f'/api/documents/{did}/vlm-confirm', json=body)
    assert saved.status_code == 200, saved.text
    assert saved.json()['analysis']['fields']['tax_amount'] == 0
    assert saved.json()['analysis']['fields']['total_amount'] == 110
    assert saved.json()['processing_status'] == 'REVIEW'
    with db_factory() as db:
        stored = json.loads(db.get(Document, did).extract.raw_fields)
        assert stored['human_review']['field_confirmations']['tax_amount']['method'] == 'VLM_ORIGINAL_CONFIRMED'
        assert stored['vlm_review']['run_id'] == data['run_id']
        assert db.query(AuditEvent).filter_by(action='EXTRACT_CORRECTED').count() == 1
    assert operator_client.get(f'/api/contracts/{cid}').json()['workflow']['revision'] == revision + 1
    assert operator_client.post(f'/api/documents/{did}/vlm-confirm', json=body).status_code == 409


def test_new_candidate_sensitive_values_are_masked(operator_client, db_factory, monkeypatch):
    _, did, _, revision = visual_doc(operator_client, db_factory)
    monkeypatch.setattr(LocalVlmClient, 'read', lambda *args: ({'company_name': answer('새 거래처 비밀', '공급자 상호: 새 거래처 비밀')}, MODEL))
    response = read(operator_client, did, revision, ['company_name'], masked=True)
    assert response.status_code == 200, response.text
    assert '새 거래처 비밀' not in response.text


@pytest.mark.parametrize('value,changed', [('123-45-11111', False), ('123-45-22222', True)])
def test_candidate_difference_is_compared_before_masking(operator_client, db_factory, monkeypatch, value, changed):
    _, did, _, revision = visual_doc(operator_client, db_factory)
    with db_factory() as db:
        doc = db.get(Document, did)
        stored = json.loads(doc.extract.raw_fields)
        stored['business_registration_no'] = '123-45-11111'
        doc.extract.raw_fields = json.dumps(stored, ensure_ascii=False)
        db.commit()
    monkeypatch.setattr(LocalVlmClient, 'read', lambda *args: (
        {'business_registration_no': answer(value, f'공급자 사업자번호: {value}')}, MODEL))
    data = read(operator_client, did, revision, ['business_registration_no'], masked=True).json()
    assert data['candidates'][0]['changed'] is changed
    assert value not in json.dumps(data, ensure_ascii=False)
    latest = operator_client.get(f'/api/documents/{did}/vlm-reread', params={'revision': revision, 'masked': True}).json()
    assert latest['candidates'][0]['changed'] is changed


def test_changed_source_or_revision_and_foreign_run_are_rejected(operator_client, db_factory, monkeypatch):
    _, did, path, revision = visual_doc(operator_client, db_factory)
    fake_read(monkeypatch)
    assert read(operator_client, did, revision + 1).status_code == 409
    data = read(operator_client, did, revision).json()
    _, other, _, other_revision = visual_doc(operator_client, db_factory)
    body = {'run_id': data['run_id'], 'revision': other_revision, 'fields': ['tax_amount'],
        'note': '다른 문서 후보 사용 시도', 'acknowledge_original': True}
    assert operator_client.post(f'/api/documents/{other}/vlm-confirm', json=body).status_code == 404
    path.write_bytes(path.read_bytes() + b'changed')
    assert read(operator_client, did, revision).status_code == 409


def test_changes_during_inference_are_discarded(operator_client, db_factory, monkeypatch):
    _, did, _, revision = visual_doc(operator_client, db_factory)
    def concurrent(*args):
        with db_factory() as db:
            doc = db.get(Document, did)
            doc.extract.raw_fields = json.dumps({'total_amount': 999})
            db.commit()
        return {'total_amount': answer(), 'tax_amount': answer('0', '세액: 0원')}, MODEL
    monkeypatch.setattr(LocalVlmClient, 'read', concurrent)
    assert read(operator_client, did, revision).status_code == 409
    with db_factory() as db:
        assert db.query(AuditEvent).filter_by(action='VLM_REREAD_COMPLETED').count() == 0


def test_unavailable_model_and_nonvisual_files_keep_saved_values(operator_client, db_factory, monkeypatch):
    _, did, _, revision = visual_doc(operator_client, db_factory)
    def unavailable(*args):
        raise VlmError('TIMEOUT')
    monkeypatch.setattr(LocalVlmClient, 'read', unavailable)
    assert read(operator_client, did, revision).status_code == 503
    cid = create_contract(operator_client)['contract_id']
    text_doc = upload(operator_client, cid)['document_id']
    rev = operator_client.get(f'/api/contracts/{cid}').json()['workflow']['revision']
    assert read(operator_client, text_doc, rev).status_code == 422


def test_reread_and_confirmation_permissions(operator_client, separate_client, db_factory):
    _, did, _, revision = visual_doc(operator_client, db_factory)
    representative = separate_client('representative')
    assert read(representative, did, revision).status_code == 403
    assert representative.post(f'/api/documents/{did}/vlm-confirm', json={'run_id': 1, 'revision': revision,
        'fields': ['total_amount'], 'note': '권한 확인', 'acknowledge_original': True}).status_code == 403
    operator_client.post('/api/auth/logout')
    assert operator_client.get('/api/vlm/status').status_code == 401


@pytest.mark.parametrize('field,item,usable', [
    ('tax_amount', answer('0', '세액: 0원'), True),
    ('total_amount', answer('100', '합계: 999원'), False),
    ('business_registration_no', answer('001-23-45678', '사업자번호 001-23-45678'), True),
    ('company_name', answer('발주회사', '상호: 발주회사', 'BUYER'), False),
    ('account_number', answer('001234567890', '계좌: 001234567890', 'UNKNOWN'), False),
    ('issue_date', answer('2026-10-07', '발행일: 2026년 10월 7일'), True),
    ('amount_scope', answer('FULL', '합계금액: 1,100,000원'), False),
    ('amount_scope', answer('FULL', '계약 전액 청구'), True),
    ('amount_scope', answer('PARTIAL', '잔금 청구'), False),
    ('amount_scope', answer('PARTIAL', '잔금 70% 정산 청구'), True),
    ('amount_scope', answer('FULL', '최종 검수 완료 후 계약 전액 청구'), True),
    ('amount_scope', answer('FULL', '잔금 청구'), False),
    ('amount_scope', answer('FULL', '전액 계약 중 잔금 청구'), False),
])
def test_candidate_guards_do_not_treat_model_quotes_as_verified_evidence(field, item, usable):
    assert service.candidate(field, item)['usable'] is usable


def test_local_vlm_payload_uses_image_and_refuses_cloud_or_text_models(monkeypatch, tmp_path):
    monkeypatch.setenv('APP_VLM_MODEL', 'qwen2.5vl:7b')
    monkeypatch.setenv('APP_VLM_ENABLED', 'true')
    monkeypatch.setenv('APP_OLLAMA_URL', 'http://127.0.0.1:11434')
    monkeypatch.setattr('backend.app.ai.local_vlm.Path.home', lambda: tmp_path)
    (tmp_path / '.ollama').mkdir()
    (tmp_path / '.ollama/server.json').write_text('{"disable_ollama_cloud":true}')
    calls = []
    class Response:
        def __init__(self, data): self.data = data
        def raise_for_status(self): pass
        def json(self): return self.data
    class Session:
        trust_env = True
        def get(self, url, **kw): return Response({'models': [{'name': 'qwen2.5vl:7b', 'digest': 'unit', 'size': 1}]})
        def post(self, url, **kw):
            calls.append((url, kw))
            if url.endswith('/api/show'): return Response({'capabilities': ['vision']})
            return Response({'message': {'content': json.dumps({'fields': {'total_amount': answer()}})}})
    session = Session()
    client = LocalVlmClient(session)
    client.read(b'unit-image', ['total_amount'], 'tax_invoice')
    assert session.trust_env is False
    assert base64.b64decode(calls[-1][1]['json']['messages'][0]['images'][0]) == b'unit-image'
    assert calls[-1][1]['allow_redirects'] is False
    monkeypatch.setenv('APP_OLLAMA_URL', 'https://outside.invalid')
    with pytest.raises(VlmError): LocalVlmClient(session)


def test_local_vlm_truncated_output_and_invalid_settings_are_actionable(monkeypatch):
    monkeypatch.setenv('APP_VLM_MODEL', 'qwen2.5vl:7b')
    monkeypatch.setenv('APP_OLLAMA_URL', 'http://127.0.0.1:11434')
    monkeypatch.setenv('APP_VLM_TIMEOUT', '90')
    monkeypatch.setattr(LocalVlmClient, 'metadata', lambda self: MODEL)
    class Response:
        def raise_for_status(self): pass
        def json(self): return {'done_reason': 'length', 'message': {'content': '{'}}
    class Session:
        def post(self, *args, **kwargs): return Response()
    with pytest.raises(VlmError, match='OUTPUT_LIMIT'):
        LocalVlmClient(Session()).read(b'image', ['total_amount'], 'tax_invoice')
    monkeypatch.setenv('APP_VLM_TIMEOUT', 'invalid')
    with pytest.raises(VlmError, match='INVALID_LOCAL_CONFIGURATION'):
        LocalVlmClient(Session())
