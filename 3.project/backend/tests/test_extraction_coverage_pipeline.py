"""Persist incomplete PDF coverage independently of optional LLM inference."""
import json

import pytest
from fastapi import HTTPException

from backend.app.ai import analyze_document, grounding, preprocessor
from backend.app.db.models import Document
from backend.app.schemas.document import INCOMPLETE_EXTRACTION_WARNING
from backend.app.services.pipeline_service import PipelineService
from backend.app.services.storage_service import resolve_path
from test_api import create_contract
from test_ocr_processing_regressions import write_pdf


def test_partial_pdf_remains_failed_with_llm_disabled_and_preserves_evidence(
        operator_client, db_factory, tmp_path, monkeypatch):
    monkeypatch.setenv('APP_LLM_ENABLED', 'false')
    monkeypatch.setattr('backend.app.ai.local_llm.OllamaClient.extract',
                        lambda *_: pytest.fail('No model call in disabled path'))
    monkeypatch.setattr(preprocessor, 'run_ocr_on_image', lambda _: '')
    source = write_pdf(tmp_path, {'text': 'Native footer', 'raster': True})
    original = source.read_bytes()
    cid = create_contract(operator_client)['contract_id']
    response = operator_client.post(f'/api/contracts/{cid}/documents',
        files=[('files', ('견적서.pdf', original, 'application/pdf'))])
    assert response.status_code == 200, response.text
    document = response.json()[0]
    did = document['document_id']
    assert document['processing_status'] == 'FAILED'
    assert 'Native footer' in document['raw_text']
    metadata = document['analysis']['extraction_metadata']
    assert metadata['evidence_complete'] is False and metadata['incomplete_pages'] == [1]
    assert INCOMPLETE_EXTRACTION_WARNING in document['analysis']['warnings']
    assert document['llm']['status'] == 'DISABLED'
    assert document['llm']['inference_invoked'] is False
    with db_factory() as db:
        stored = db.get(Document, did)
        assert resolve_path(stored.storage_path).read_bytes() == original
        assert json.loads(stored.extract.raw_fields)['extraction_metadata'] == metadata
        assert stored.extract.extracted_status == 'FAILED'
        assert 'Native footer' not in json.dumps(metadata)
    detail = operator_client.get(f'/api/contracts/{cid}').json()
    assert any(item['rule_id'] == 'DOCUMENT_PROCESSING' and item['status'] == 'REVIEW'
               and item['field'] == str(did) for item in detail['checks'])
    reread = operator_client.get(f'/api/documents/{did}').json()
    assert reread['analysis']['extraction_metadata'] == metadata
    assert INCOMPLETE_EXTRACTION_WARNING in reread['analysis']['warnings']
    # Field corrections must retain extraction provenance from the original.
    corrected = operator_client.put(f'/api/documents/{did}/fields', json={
        'fields': document['analysis']['fields'], 'document_type': document['document_type'],
        'revision': detail['workflow']['revision'], 'note': '원문 확인 후 누락 항목 보완',
        'confirmed_fields': ['total_amount']})
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()['analysis']['extraction_metadata'] == metadata


def test_require_readable_rejects_partial_pdf_then_retries_original(
        operator_client, db_factory, tmp_path, monkeypatch):
    monkeypatch.setenv('APP_LLM_ENABLED', 'false')
    monkeypatch.setattr(preprocessor, 'run_ocr_on_image', lambda _: '')
    source = write_pdf(tmp_path, {'text': 'Native footer', 'raster': True})
    original = source.read_bytes()
    cid = create_contract(operator_client)['contract_id']
    with db_factory() as db:
        with pytest.raises(HTTPException) as error:
            PipelineService().process_document_upload(db, cid, '견적서.pdf', original, require_readable=True)
        assert error.value.status_code == 422
        assert db.query(Document).count() == 0
    from backend.app.services import storage_service
    retained = list((storage_service.STORAGE_DIR / 'raw' / str(cid)).glob('*'))
    assert any(path.read_bytes() == original for path in retained if path.is_file())
    monkeypatch.setattr(preprocessor, 'run_ocr_on_image', lambda _: '견적서\n합계금액: 110원')
    with db_factory() as db:
        document = PipelineService().process_document_upload(db, cid, '견적서.pdf', original, require_readable=True)
        assert document.processing_status == 'COMPLETED' and db.query(Document).count() == 1
        assert resolve_path(document.storage_path).read_bytes() == original
        metadata = json.loads(document.extract.raw_fields)['extraction_metadata']
        assert metadata['evidence_complete'] is True and metadata['incomplete_pages'] == []


def test_verified_blank_separator_preserves_complete_readable_document(
        operator_client, db_factory, tmp_path, monkeypatch):
    monkeypatch.setattr(preprocessor, 'run_ocr_on_image', lambda _: pytest.fail('Verified blank needs no OCR'))
    source = write_pdf(tmp_path, {'text': 'Native contract'}, {}, {'text': 'Native terms'})
    analysis, raw, _ = analyze_document(source, '계약서.pdf', use_llm=False)
    assert analysis.extraction_metadata['evidence_complete'] is True
    assert analysis.extraction_metadata['incomplete_pages'] == []
    assert INCOMPLETE_EXTRACTION_WARNING not in analysis.warnings
    evidence = grounding.source_pages(source, raw)
    assert grounding.source_evidence_complete(evidence)
    assert evidence[1]['verified_blank'] is True and evidence[1]['text'] == ''
    cid = create_contract(operator_client)['contract_id']
    with db_factory() as db:
        document = PipelineService().process_document_upload(db, cid, '계약서.pdf', source.read_bytes(), require_readable=True)
        assert document.processing_status == 'COMPLETED'


def test_blank_only_document_is_not_readable_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(preprocessor, 'run_ocr_on_image', lambda _: pytest.fail('Verified blank needs no OCR'))
    source = write_pdf(tmp_path, {})
    analysis, raw, _ = analyze_document(source, 'blank.pdf', use_llm=False)
    assert analysis.extraction_metadata['evidence_complete'] is False
    assert not grounding.source_evidence_complete(grounding.source_pages(source, raw))
    assert INCOMPLETE_EXTRACTION_WARNING in analysis.warnings


def test_legacy_text_analysis_has_no_fabricated_pdf_coverage(tmp_path):
    source = tmp_path / 'plain.txt'
    source.write_text('견적서\n합계금액: 110원')
    analysis, _, _ = analyze_document(source, use_llm=False)
    assert analysis.extraction_metadata is None
