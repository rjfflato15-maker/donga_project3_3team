"""Synthetic coverage/response regressions; never contact a model or use gold data."""
import io
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from PIL import Image

from backend.app.ai import grounding, grounding_v4, llm_supplement, local_vlm, pdf_runtime
from backend.app.services import vlm_reread_service


def pages(text='합계금액: 110원', **extra):
    return [{'page': 1, 'location_kind': 'page', 'text': text, **extra}]


def proposal(state='VALUE'):
    return {'state': state, 'value': '110' if state == 'VALUE' else None,
            'page': 1 if state == 'VALUE' else None,
            'line': 1 if state == 'VALUE' else None,
            'quote': '합계금액: 110원' if state == 'VALUE' else ''}


@pytest.mark.parametrize('policy', [grounding, grounding_v4])
@pytest.mark.parametrize('evidence', [[], pages(''), pages(' \n\t'),
                                     pages(evidence_complete=False),
                                     pages() + [{'page': 2, 'location_kind': 'page', 'text': ''}]])
@pytest.mark.parametrize('state', ['VALUE', 'ABSENT', 'REVIEW'])
def test_unavailable_evidence_never_accepts_a_model_proposal(policy, evidence, state):
    decision = policy.guard_proposal('total_amount', proposal(state), evidence, 'estimate')
    assert not decision['accepted']
    assert 'SOURCE_EVIDENCE_UNAVAILABLE' in decision['reasons']
    assert decision['anchor'] is None and decision['human_confirmed'] is False


@pytest.mark.parametrize('policy', ['v3', 'v4'])
@pytest.mark.parametrize('state', ['ABSENT', 'REVIEW'])
def test_unavailable_evidence_cannot_erase_existing_fields(policy, state):
    fields = {'total_amount': 110, 'amount': 110, 'amount_basis': 'TOTAL'}
    result, review = llm_supplement.apply_proposals(fields,
        {'ok': True, 'proposals': {'total_amount': proposal(state)}}, [],
        'estimate', ['total_amount'], guard_policy=policy)
    assert result == fields
    assert not review['decisions'][0]['applied']
    assert review['unresolved_fields'] == ['total_amount']
    assert review['manual_review_required'] and not review['human_confirmed']


@pytest.mark.parametrize('policy', ['v3', 'v4'])
def test_review_with_complete_ambiguous_evidence_still_clears_effective_value(policy):
    evidence = pages('합계금액: 110원\n합계금액: 120원')
    fields = {'total_amount': 110, 'amount': 110, 'amount_basis': 'TOTAL'}
    result, review = llm_supplement.apply_proposals(fields,
        {'ok': True, 'proposals': {'total_amount': proposal('REVIEW')}}, evidence,
        'estimate', ['total_amount'], guard_policy=policy)
    assert result['total_amount'] is None and result['amount'] is None
    assert result['amount_basis'] == 'UNKNOWN'
    assert fields['total_amount'] == 110  # caller's original remains intact
    assert review['decisions'][0]['accepted'] and review['decisions'][0]['applied']
    assert review['unresolved_fields'] == ['total_amount']
    assert review['manual_review_required'] and not review['human_confirmed']


@pytest.mark.parametrize('evidence', [[], pages(''), pages(evidence_complete=False)])
def test_supplement_skips_model_entirely_for_unavailable_evidence(monkeypatch, evidence):
    monkeypatch.setattr(llm_supplement, 'source_pages', lambda *_: evidence)
    client = SimpleNamespace(extract=lambda *_: pytest.fail('No inference without evidence'))
    fields = {'total_amount': 110, 'amount_scope': 'FULL'}
    result, review = llm_supplement.supplement_document('synthetic.pdf', '', fields, 'estimate', client)
    assert result == fields and review['error'] == 'SOURCE_EVIDENCE_UNAVAILABLE'
    assert review['status'] == 'FAILED' and review['guard_review_required']
    assert review['manual_review_required'] and not review['human_confirmed']


@pytest.mark.parametrize('policy', [grounding, grounding_v4])
@pytest.mark.parametrize('change', [{'state': []}, {'line': True}, {'page': True},
                                    {'quote': None}, {'value': {'number': 110}}])
def test_guard_boundary_rejects_malformed_proposals_without_crashing(policy, change):
    decision = policy.guard_proposal('total_amount', {**proposal(), **change}, pages(), 'estimate')
    assert not decision['accepted'] and 'INVALID_FORMAT' in decision['reasons']


def test_source_failure_exposes_targets_that_human_review_can_resolve(monkeypatch):
    from backend.app.services.field_confirmation_service import reviewed_ai
    monkeypatch.setattr(llm_supplement, 'source_pages', lambda *_: [])
    _, review = llm_supplement.supplement_document('synthetic.pdf', '', {}, 'estimate')
    assert set(review['targets']) == set(grounding.LABELS)
    assert review['unresolved_fields'] == review['targets'] and review['attempts'] == 0
    partial = reviewed_ai(review, {'total_amount': {}})
    assert partial['manual_review_required'] and not partial['human_confirmed']
    resolved = reviewed_ai(review, {field: {} for field in review['targets']})
    assert resolved['human_confirmed'] and not resolved['manual_review_required']


def test_source_exception_preserves_expected_field_review_scope(monkeypatch):
    def unavailable(*args):
        raise RuntimeError('Synthetic unreadable file')
    monkeypatch.setattr(llm_supplement, 'source_pages', unavailable)
    _, review = llm_supplement.supplement_document('synthetic.pdf', '', {}, 'bank_account')
    assert set(review['targets']) == {'company_name', 'issue_date'}
    assert review['unresolved_fields'] == review['targets']
    assert review['error'] == 'LOCAL_LLM_OR_SOURCE_UNAVAILABLE'


def test_pdf_source_uses_shared_pagewise_extraction_and_keeps_physical_pages(monkeypatch):
    from backend.app.ai import preprocessor
    extracted = pages() + [{'page': 2, 'location_kind': 'page', 'text': '비고', 'evidence_complete': True}]
    monkeypatch.setattr(preprocessor, 'extract_pdf_pages', lambda *_: extracted)
    result = grounding.source_pages('synthetic.pdf', '[파일명: synthetic.pdf]\n합계금액: 110원\n\n비고')
    assert result is extracted and grounding.source_evidence_complete(result)
    assert [item['page'] for item in result] == [1, 2]


def test_different_second_ocr_pass_is_unavailable_not_fresh_authority(monkeypatch):
    from backend.app.ai import preprocessor
    extracted = pages('합계금액: 120원', evidence_complete=True, extraction_warnings=['OCR_TEXT_MERGED'])
    monkeypatch.setattr(preprocessor, 'extract_pdf_pages', lambda *_: extracted)
    result = grounding.source_pages('synthetic.pdf', '합계금액: 110원')
    assert not grounding.source_evidence_complete(result)
    assert result[0]['text'] == '합계금액: 120원'
    assert result[0]['extraction_warnings'] == ['OCR_TEXT_MERGED', 'SOURCE_TEXT_CHANGED']


def test_pdf_page_limit_is_not_proof_of_absence(tmp_path, monkeypatch):
    from pypdf import PdfWriter
    path = tmp_path / 'too-many-pages.pdf'
    writer = PdfWriter()
    for _ in range(51):
        writer.add_blank_page(width=72, height=72)
    with path.open('wb') as stream:
        writer.write(stream)
    monkeypatch.setattr(pdf_runtime, 'render_page_image', lambda *_: pytest.fail('Page limit must prevent rasterization'))
    evidence = grounding.source_pages(path, '')
    assert len(evidence) == 51
    assert not grounding.source_evidence_complete(evidence)
    assert not grounding.guard_proposal('company_name', proposal('ABSENT'), evidence, 'estimate')['accepted']


class RecordingLock:
    def __init__(self):
        self.depth = 0

    def __enter__(self):
        self.depth += 1

    def __exit__(self, *args):
        self.depth -= 1


def install_pdfium_spy(monkeypatch, *, size=(612, 792), render_error=False):
    import pypdfium2
    lock = RecordingLock()
    calls = []

    def record(operation):
        assert lock.depth, f'Native PDFium operation outside shared lock: {operation}'
        calls.append(operation)

    class Bitmap:
        def to_pil(self):
            record('bitmap.to_pil')
            return Image.new('RGB', (12, 12), 'red')

        def close(self):
            record('bitmap.close')

    class Page:
        def get_size(self):
            record('page.get_size')
            return size

        def render(self, scale):
            record('page.render')
            assert max(size) * scale <= 1600
            if render_error:
                raise RuntimeError('Synthetic render failure')
            return Bitmap()

        def close(self):
            record('page.close')

    class Document:
        def __init__(self, content):
            record('document.open')
            assert content == b'snapshotted-pdf'

        def __len__(self):
            record('document.count')
            return 1

        def __getitem__(self, index):
            record('document.page')
            assert index == 0
            return Page()

        def close(self):
            record('document.close')

    monkeypatch.setattr(pdf_runtime, 'PDFIUM_LOCK', lock)
    monkeypatch.setattr(pypdfium2, 'PdfDocument', Document)
    return lock, calls


@pytest.mark.parametrize('size', [(612, 792), (100_000_000, 200_000_000)])
def test_vlm_uses_shared_pdfium_lock_and_detached_bitmap(monkeypatch, size):
    lock, calls = install_pdfium_spy(monkeypatch, size=size)
    data = vlm_reread_service.page_image({'suffix': '.pdf', 'content': b'snapshotted-pdf'}, 1)
    assert lock.depth == 0
    assert calls[-3:] == ['bitmap.close', 'page.close', 'document.close']
    with Image.open(io.BytesIO(data)) as image:
        assert image.size == (12, 12) and image.getpixel((0, 0))[0] > 240


@pytest.mark.parametrize('size', [(0, 792), (float('nan'), 792), (float('inf'), 792)])
def test_vlm_invalid_page_sizes_fail_with_all_handles_closed(monkeypatch, size):
    lock, calls = install_pdfium_spy(monkeypatch, size=size)
    with pytest.raises(HTTPException) as error:
        vlm_reread_service.page_image({'suffix': '.pdf', 'content': b'snapshotted-pdf'}, 1)
    assert error.value.status_code == 422 and lock.depth == 0
    assert 'page.render' not in calls
    assert calls[-2:] == ['page.close', 'document.close']


def test_vlm_render_failure_closes_document_and_page(monkeypatch):
    lock, calls = install_pdfium_spy(monkeypatch, render_error=True)
    with pytest.raises(HTTPException):
        vlm_reread_service.page_image({'suffix': '.pdf', 'content': b'snapshotted-pdf'}, 1)
    assert lock.depth == 0 and calls[-2:] == ['page.close', 'document.close']


@pytest.mark.parametrize('page', [0, -1, True, '1', None])
def test_vlm_rejects_invalid_page_before_opening_pdf(monkeypatch, page):
    _, calls = install_pdfium_spy(monkeypatch)
    with pytest.raises(HTTPException) as error:
        vlm_reread_service.page_image({'suffix': '.pdf', 'content': b'snapshotted-pdf'}, page)
    assert error.value.status_code == 422 and not calls


def test_real_pdf_vlm_render_is_readable_jpeg():
    from pypdf import PdfWriter
    stream = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(stream)
    result = vlm_reread_service.page_image({'suffix': '.pdf', 'content': stream.getvalue()}, 1)
    with Image.open(io.BytesIO(result)) as image:
        assert image.format == 'JPEG' and max(image.size) <= 1600


@pytest.mark.parametrize('envelope', [[], {'message': {'content': json.dumps({'fields': ['total_amount']})}},
                                     {'message': {'content': json.dumps({'fields': None})}}])
def test_vlm_invalid_outer_response_becomes_actionable_error(monkeypatch, envelope):
    monkeypatch.setattr(local_vlm.LocalVlmClient, 'metadata', lambda _: {'name': 'synthetic'})
    session = SimpleNamespace(post=lambda *a, **kw: SimpleNamespace(raise_for_status=lambda: None, json=lambda: envelope))
    with pytest.raises(local_vlm.VlmError, match='INVALID_RESPONSE'):
        local_vlm.LocalVlmClient(session).read(b'synthetic-image', ['total_amount'], 'estimate')


@pytest.mark.parametrize('key,value', [('state', []), ('party', {}), ('state', None), ('party', 1)])
def test_vlm_malformed_candidate_enums_never_crash(key, value):
    answer = {'state': 'VALUE', 'value': '110', 'quote': '합계금액: 110원', 'party': 'SUPPLIER', key: value}
    result = vlm_reread_service.candidate('total_amount', answer)
    assert not result['usable'] and result['value'] is None
