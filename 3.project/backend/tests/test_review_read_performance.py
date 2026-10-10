"""Read paths stay cheap without weakening source checks or historical masks."""
import json
from backend.app.db.models import Document
from backend.app.services import review_context_service as service
from backend.app.services.contract_export_service import public_data
from backend.app.services import preview_masking_service as masking
from test_api import create_contract
from test_review_workflow_api import upload


def test_overview_keeps_confirmations_and_detects_changed_original_without_extraction(operator_client, db_factory, monkeypatch):
    cid = create_contract(operator_client)['contract_id']
    did = upload(operator_client, cid, 'estimate')['document_id']
    full = operator_client.get(f'/api/contracts/{cid}/review-context').json()
    def forbidden(*args):
        raise AssertionError('A list/history read must not extract source pages')
    monkeypatch.setattr(service, 'source_pages', forbidden)
    brief = operator_client.get(f'/api/contracts/{cid}/review-context?include_evidence=false').json()
    assert brief['revision'] == full['revision'] and brief['fingerprint'] == full['fingerprint']
    assert brief['summary'] == full['summary'] and brief['workflow'] == full['workflow']
    assert brief['documents'][0]['source_version_verified'] is True
    assert brief['documents'][0]['human_confirmed_fields'] == full['documents'][0]['human_confirmed_fields']
    assert brief['documents'][0]['fields']['total_amount']['evidence'] == []
    with db_factory() as db:
        from backend.app.services.storage_service import resolve_path
        resolve_path(db.get(Document, did).storage_path).write_text('changed original', encoding='utf-8')
    changed = operator_client.get(f'/api/contracts/{cid}/review-context?include_evidence=false').json()
    assert changed['documents'][0]['source_version_verified'] is False
    assert changed['documents'][0]['fields']['total_amount']['evidence_error'] == 'ORIGINAL_VERSION_CHANGED'


def test_selected_document_only_and_cache_preserve_flags_without_stale_values(operator_client, db_factory, monkeypatch):
    cid = create_contract(operator_client)['contract_id']
    did = upload(operator_client, cid, 'estimate')['document_id']
    other = upload(operator_client, cid, 'contract')['document_id']
    calls = []
    def locate(path, raw):
        calls.append(str(path))
        return [{'page': None, 'location_kind': 'document_block', 'text': raw.partition('\n')[2],
                 'evidence_complete': False, 'extraction_warnings': ['SOURCE_TEXT_CHANGED']}]
    monkeypatch.setattr(service, 'source_pages', locate)
    url = f'/api/contracts/{cid}/review-context?evidence_document_id={did}'
    first = operator_client.get(url).json()
    second = operator_client.get(url).json()
    assert len(calls) == 1
    assert first['documents'] == second['documents']
    assert next(d for d in first['documents'] if d['document_id'] == other)['fields']['total_amount']['evidence'] == []
    with db_factory() as db:
        doc = db.get(Document, did)
        fields = json.loads(doc.extract.raw_fields)
        fields['total_amount'] = 121
        doc.extract.raw_fields = json.dumps(fields)
        db.commit()
    fresh = operator_client.get(url).json()
    assert next(d for d in fresh['documents'] if d['document_id'] == did)['fields']['total_amount']['value'] == 121
    assert len(calls) == 1  # Only immutable source locations are reused.


def test_source_location_cache_separates_versions_text_and_callers(tmp_path):
    from backend.app.services.source_location_cache import cached_source_pages
    path = tmp_path/'source.pdf'
    calls = []
    def load(path, text):
        calls.append(text)
        return [{'text': text, 'page':1}]
    first = cached_source_pages(path, 'old', 'sha1', load)
    first[0]['text'] = 'mutated response'
    assert cached_source_pages(path, 'old', 'sha1', load)[0]['text'] == 'old'
    assert cached_source_pages(path, 'new', 'sha1', load)[0]['text'] == 'new'
    cached_source_pages(path, 'new', 'sha2', load)
    cached_source_pages(tmp_path/'different.pdf', 'old', 'sha1', load)
    assert len(calls) == 4


def test_failed_extraction_is_not_cached(tmp_path):
    from backend.app.services.source_location_cache import cached_source_pages
    calls = []
    def load(*args):
        calls.append(1)
        return [{'text':'partial', 'evidence_complete':False, 'extraction_warnings':['PDF_OCR_EMPTY']}]
    for _ in range(2):
        cached_source_pages(tmp_path/'failed.pdf', 'text', 'sha', load)
    assert len(calls) == 2


def test_source_changed_during_read_does_not_poison_cache(operator_client, db_factory, monkeypatch):
    from backend.app.services.storage_service import resolve_path
    cid = create_contract(operator_client)['contract_id']
    did = upload(operator_client, cid, 'estimate')['document_id']
    with db_factory() as db:
        path = resolve_path(db.get(Document, did).storage_path)
    original = path.read_bytes()
    calls = []
    def locate(path, raw):
        calls.append(1)
        if len(calls) == 1:
            path.write_bytes(b'changed during extraction')
        return [{'page':None, 'text':raw.partition('\n')[2], 'location_kind':'document_block'}]
    monkeypatch.setattr(service, 'source_pages', locate)
    url = f'/api/documents/{did}/provenance'
    changed = operator_client.get(url).json()
    assert changed['source_version_verified'] is False
    assert changed['fields']['total_amount']['evidence'] == []
    path.write_bytes(original)
    restored = operator_client.get(url).json()
    assert restored['source_version_verified'] is True
    assert len(calls) == 2


def test_historical_mask_terms_compile_once_per_response(monkeypatch):
    original = masking.term_pattern
    calls = []
    def compile_term(value):
        calls.append(value)
        return original(value)
    monkeypatch.setattr(masking, 'term_pattern', compile_term)
    data = [{'note':'Old Vendor → New Vendor', 'account_number':'123-456-7890'} for _ in range(50)]
    sensitive = {'vendor_name':['Old Vendor','New Vendor'], 'account_number':['123-456-7890']}
    result = public_data(data, True, sensitive)
    assert len(calls) == 3
    assert 'Old Vendor' not in json.dumps(result) and 'New Vendor' not in json.dumps(result)
    assert '123-456-7890' not in json.dumps(result)
    assert public_data(data, False, sensitive) == data
