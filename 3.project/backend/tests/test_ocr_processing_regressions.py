"""Synthetic extraction/engine-boundary tests, not real Korean OCR benchmarks."""
import math
import sys
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import (ArrayObject, DecodedStreamObject, DictionaryObject,
                           NameObject, NumberObject)

from backend.app.ai import pdf_runtime, preprocessor


def add_pdf_page(writer, text='', raster=False, form=False, size=(300, 500)):
    page = writer.add_blank_page(width=size[0], height=size[1])
    resources = DictionaryObject()
    content = b''
    if raster:
        image = DecodedStreamObject()
        image.set_data(bytes([30, 70, 110]) * 4)
        image.update({NameObject('/Type'): NameObject('/XObject'), NameObject('/Subtype'): NameObject('/Image'),
                      NameObject('/Width'): NumberObject(2), NameObject('/Height'): NumberObject(2),
                      NameObject('/ColorSpace'): NameObject('/DeviceRGB'), NameObject('/BitsPerComponent'): NumberObject(8)})
        xobjects = DictionaryObject({NameObject('/Im0'): writer._add_object(image)})
        content = f'q {size[0]} 0 0 {size[1]} 0 0 cm /Im0 Do Q '.encode()
        if form:
            nested = DecodedStreamObject()
            nested.set_data(content)
            nested.update({NameObject('/Type'): NameObject('/XObject'), NameObject('/Subtype'): NameObject('/Form'),
                           NameObject('/BBox'): ArrayObject([NumberObject(value) for value in (0, 0, *size)]),
                           NameObject('/Resources'): DictionaryObject({NameObject('/XObject'): xobjects})})
            xobjects = DictionaryObject({NameObject('/Fm0'): writer._add_object(nested)})
            content = b'/Fm0 Do '
        resources[NameObject('/XObject')] = xobjects
    if text:
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                                 NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
        resources[NameObject('/Font')] = DictionaryObject({NameObject('/F1'): writer._add_object(font)})
        content += f'BT /F1 12 Tf 20 20 Td ({text}) Tj ET'.encode('ascii')
    page[NameObject('/Resources')] = resources
    stream = DecodedStreamObject()
    stream.set_data(content)
    page[NameObject('/Contents')] = writer._add_object(stream)
    return page


def write_pdf(tmp_path, *specifications):
    writer = PdfWriter()
    for spec in specifications:
        add_pdf_page(writer, **spec)
    path = tmp_path / 'synthetic.pdf'
    writer.write(path)
    return path


@pytest.mark.parametrize('form', [False, True])
def test_pagewise_pdf_keeps_native_and_scanned_pages_with_footer(tmp_path, monkeypatch, form):
    path = write_pdf(tmp_path, {'text': 'Native first'}, {'raster': True},
                     {'text': 'Page 3', 'raster': True, 'form': form}, {'text': 'Native last'})
    calls, rendered, opened = [], [], []
    original_open, original_page, original_render = pdf_runtime.open_pdf, pdf_runtime.open_page, pdf_runtime.render_page_image
    active_pages = []

    @contextmanager
    def tracked_open(path):
        opened.append(path)
        with original_open(path) as pdf:
            yield pdf

    @contextmanager
    def tracked_page(pdf, index):
        with original_page(pdf, index) as page:
            active_pages.append(index)
            try:
                yield page
            finally:
                active_pages.pop()

    def render(page, scale):
        rendered.append(active_pages[-1])
        return original_render(page, scale)

    def recognize(image):
        assert not active_pages  # no page handle held during OCR
        assert not pdf_runtime.PDFIUM_LOCK._is_owned()
        calls.append(image)
        return ['사업자등록번호: 123-45-67890', 'Page   3\n합계금액: 1100원'][len(calls) - 1]

    monkeypatch.setattr(pdf_runtime, 'open_pdf', tracked_open)
    monkeypatch.setattr(pdf_runtime, 'open_page', tracked_page)
    monkeypatch.setattr(pdf_runtime, 'render_page_image', render)
    monkeypatch.setattr(preprocessor, 'run_ocr_on_image', recognize)
    pages = preprocessor.extract_pdf_pages(path)
    assert [page['page'] for page in pages] == [1, 2, 3, 4]
    assert [page['text'] for page in pages] == ['Native first', '사업자등록번호: 123-45-67890',
                                                'Page 3\n\nPage   3\n합계금액: 1100원', 'Native last']
    assert all(page['evidence_complete'] for page in pages)
    assert len(opened) == 1 and rendered == [1, 2] and len(calls) == 2
    for image in calls:
        with pytest.raises(ValueError):
            image.getpixel((0, 0))


def test_file_extraction_contains_scanned_page_after_native_page(tmp_path, monkeypatch):
    path = write_pdf(tmp_path, {'text': 'Native contract'}, {'raster': True})
    monkeypatch.setattr(preprocessor, 'run_ocr_on_image', lambda _: '공급가액: 1000원\n합계금액: 1100원')
    text, extension = preprocessor.extract_text_from_file(path, 'contract.pdf')
    assert extension == 'pdf'
    assert text == '[파일명: contract.pdf]\nNative contract\n\n공급가액: 1000원\n합계금액: 1100원'


@pytest.mark.parametrize('failure', ['blank', 'exception', 'render'])
def test_failed_page_preserves_native_and_later_pages_and_marks_incomplete(tmp_path, monkeypatch, failure):
    path = write_pdf(tmp_path, {'text': 'Native first'}, {'text': 'Page 2', 'raster': True},
                     {'raster': True}, {'text': 'Native last'})
    calls = []
    original_render = pdf_runtime.render_page_image

    def render(page, scale):
        if failure == 'render' and not calls:
            calls.append('failed render')
            raise RuntimeError('private exception must not be logged')
        return original_render(page, scale)

    def recognize(image):
        calls.append('ocr')
        if len(calls) == 1:
            if failure == 'exception':
                raise RuntimeError('private exception must not be logged')
            return ''
        return 'Later scanned text'

    monkeypatch.setattr(pdf_runtime, 'render_page_image', render)
    monkeypatch.setattr(preprocessor, 'run_ocr_on_image', recognize)
    pages = preprocessor.extract_pdf_pages(path)
    assert [p['text'] for p in pages] == ['Native first', 'Page 2', 'Later scanned text', 'Native last']
    assert [p['evidence_complete'] for p in pages] == [True, False, True, True]
    assert pages[1]['extraction_warnings']


def test_verified_blank_separator_is_preserved_without_ocr_and_complete(tmp_path, monkeypatch):
    path = write_pdf(tmp_path, {'text': 'Before'}, {}, {'text': 'After'})
    monkeypatch.setattr(preprocessor, 'run_ocr_on_image', lambda _: pytest.fail('No OCR for positively blank page'))
    pages = preprocessor.extract_pdf_pages(path)
    assert len(pages) == 3 and pages[1]['page'] == 2 and pages[1]['text'] == ''
    assert pages[1]['evidence_complete'] is True and pages[1]['verified_blank'] is True
    assert pages[1]['extraction_warnings'] == []
    metadata = {}
    preprocessor.extract_text_from_file(path, extraction_metadata=metadata)
    assert metadata == {'evidence_complete': True, 'page_count': 3, 'incomplete_pages': [], 'warning_codes': []}


def test_oversized_page_count_preserves_native_but_never_renders(tmp_path, monkeypatch):
    path = write_pdf(tmp_path, *[{'text': f'Page {n}'} for n in range(1, 52)])
    monkeypatch.setattr(pdf_runtime, 'render_page_image', lambda *a: pytest.fail('No OCR render beyond 50 pages'))
    pages = preprocessor.extract_pdf_pages(path)
    assert len(pages) == 51 and pages[-1]['text'] == 'Page 51'
    assert all(not p['evidence_complete'] and 'PDF_PAGE_LIMIT' in p['extraction_warnings'] for p in pages)


@pytest.mark.parametrize('size', [(10000, 10000), (10_000_000, 10), (10, 10_000_000), (300.1, 500.3)])
def test_render_size_is_bounded_before_allocation(size):
    scale = preprocessor._pdf_ocr_scale(*size)
    assert math.ceil(size[0] * scale) <= 2400
    assert math.ceil(size[1] * scale) <= 2400


@pytest.mark.parametrize('size', [(0, 10), (-1, 10), (float('inf'), 10), (10, float('nan'))])
def test_invalid_pdf_dimensions_fail_before_render(size):
    with pytest.raises(ValueError):
        preprocessor._pdf_ocr_scale(*size)


def test_large_pdf_is_rendered_only_at_ocr_useful_size(tmp_path, monkeypatch):
    path = write_pdf(tmp_path, {'raster': True, 'size': (10000, 10000)})
    sizes = []
    monkeypatch.setattr(preprocessor, 'run_ocr_on_image', lambda image: sizes.append(image.size) or 'Recognized text')
    pages = preprocessor.extract_pdf_pages(path)
    assert sizes == [(2400, 2400)] and pages[0]['evidence_complete']


def test_renderer_failure_preserves_native_but_marks_unknown_raster_coverage(tmp_path, monkeypatch):
    path = write_pdf(tmp_path, {'text': 'Native only'}, {'text': 'Footer', 'raster': True})
    monkeypatch.setattr(pdf_runtime, 'open_pdf', lambda *a: (_ for _ in ()).throw(RuntimeError('unavailable')))
    pages = preprocessor.extract_pdf_pages(path)
    assert [p['text'] for p in pages] == ['Native only', 'Footer']
    assert all(not p['evidence_complete'] and 'PDF_RENDERER_UNAVAILABLE' in p['extraction_warnings'] for p in pages)


def test_native_reader_one_page_failure_does_not_discard_other_pages(tmp_path, monkeypatch):
    from pypdf import PageObject
    path = write_pdf(tmp_path, {'text': 'Before'}, {'text': 'Recoverable native'}, {'text': 'After'})
    original = PageObject.extract_text

    def extract(page, *a, **kw):
        text = original(page, *a, **kw)
        if 'Recoverable' in text:
            raise RuntimeError('pypdf-only failure')
        return text

    monkeypatch.setattr(PageObject, 'extract_text', extract)
    monkeypatch.setattr(preprocessor, 'run_ocr_on_image', lambda *a: pytest.fail('Recovered native page needs no OCR'))
    pages = preprocessor.extract_pdf_pages(path)
    assert [p['text'] for p in pages] == ['Before', 'Recoverable native', 'After']
    assert all(p['evidence_complete'] for p in pages)


def test_native_and_ocr_conflicting_lines_are_not_invented_or_deduplicated():
    assert preprocessor._merge_pdf_text('Footer', 'Footer\nTotal 100\nTotal 110\nTotal 110') == (
        'Footer\n\nFooter\nTotal 100\nTotal 110\nTotal 110')


@pytest.mark.parametrize('original,expected', [((400, 1200), (800, 2400)), ((800, 600), (1600, 1200)),
                                               ((1, 10000), (1, 2400)), ((3000, 1500), (2400, 1200))])
def test_ocr_resize_preserves_shape_without_zero_dimensions(monkeypatch, original, expected):
    captured = []

    def recognize(image, lang):
        captured.append(image)
        assert image.size == expected and lang == 'ko'
        return {'lines': [{'text': ' 확인된 문자 '}]}

    monkeypatch.setattr(preprocessor, '_safe_winocr_recognize', recognize)
    with Image.new('RGB', original, 'white') as image:
        assert preprocessor.run_ocr_on_image(image) == '확인된 문자'
        assert image.size == original and image.getpixel((0, 0)) == (255, 255, 255)
    with pytest.raises(ValueError):
        captured[0].getpixel((0, 0))


def test_path_image_is_oriented_detached_and_transparency_is_white(tmp_path):
    path = tmp_path / 'transparent.png'
    with Image.new('RGBA', (10, 20), (0, 0, 0, 0)) as source:
        source.putpixel((1, 1), (0, 0, 0, 255))
        exif = source.getexif()
        exif[274] = 6
        source.save(path, exif=exif)
    with preprocessor._to_pil_image(path) as image:
        assert image.size == (20, 10) and image.mode == 'RGB'
        assert image.getpixel((0, 0)) == (255, 255, 255)
        assert image.getpixel((18, 1)) == (0, 0, 0)
        path.unlink()  # the decoder/file handle is no longer needed
        assert image.getpixel((18, 1)) == (0, 0, 0)


def test_invalid_image_returns_empty_without_attempting_engine(monkeypatch):
    monkeypatch.setattr(preprocessor, '_safe_winocr_recognize', lambda *a: pytest.fail('invalid image'))
    assert preprocessor.run_ocr_on_image(b'not an image') == ''


def test_tesseract_fallback_uses_owned_image_and_closes_it(monkeypatch):
    captured = []
    monkeypatch.setattr(preprocessor, '_safe_winocr_recognize', lambda *a, **kw: {})
    monkeypatch.setitem(sys.modules, 'pytesseract', SimpleNamespace(
        image_to_string=lambda image, **kw: captured.append(image) or 'fallback'))
    with Image.new('RGB', (100, 100), 'white') as source:
        assert preprocessor.run_ocr_on_image(source) == 'fallback'
        assert source.getpixel((0, 0)) == (255, 255, 255)
    with pytest.raises(ValueError):
        captured[0].getpixel((0, 0))


def test_native_ocr_merge_preserves_buyer_boundary_before_company():
    from backend.app.ai.grounding import candidates
    merged = preprocessor._merge_pdf_text('공급받는자', '공급자\n공급받는자\n상호: 북쪽회사')
    assert merged == '공급받는자\n\n공급자\n공급받는자\n상호: 북쪽회사'
    found = candidates([{'page': 1, 'text': merged}], 'company_name', 'tax_invoice')
    assert len(found) == 1 and found[0]['party'] == 'buyer'


def test_only_whole_matching_native_ocr_blocks_are_deduplicated():
    assert preprocessor._merge_pdf_text('Page 1\nTotal 110', 'Page 1\nTotal 110') == 'Page 1\nTotal 110'
    assert preprocessor._merge_pdf_text('Page 1', 'Page   1') == 'Page 1\n\nPage   1'


def test_text_budget_is_explicitly_incomplete_and_preserves_page_slots(tmp_path, monkeypatch):
    path = write_pdf(tmp_path, {'text': 'Page one'}, {'text': 'Page two'})
    monkeypatch.setattr(preprocessor, 'MAX_PDF_TEXT_CHARS', 10)
    pages = preprocessor.extract_pdf_pages(path)
    assert [p['text'] for p in pages] == ['Page one', 'Pa']
    assert not pages[1]['evidence_complete'] and 'PDF_TEXT_LIMIT' in pages[1]['extraction_warnings']


def test_native_page_safety_limit_fails_closed(tmp_path, monkeypatch):
    path = write_pdf(tmp_path, {'text': 'One'}, {'text': 'Two'}, {'text': 'Three'})
    monkeypatch.setattr(preprocessor, 'MAX_PDF_NATIVE_PAGES', 2)
    assert preprocessor.extract_pdf_pages(path) == []


def test_pdfplumber_fallback_reads_each_missing_page_once_and_is_incomplete(tmp_path, monkeypatch):
    path = write_pdf(tmp_path, {})
    monkeypatch.setattr(pdf_runtime, 'open_pdf', lambda *a: (_ for _ in ()).throw(RuntimeError('unavailable')))
    calls = []

    @contextmanager
    def plumber_open(path):
        yield SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: calls.append(1) or 'Fallback native')])

    monkeypatch.setitem(sys.modules, 'pdfplumber', SimpleNamespace(open=plumber_open))
    pages = preprocessor.extract_pdf_pages(path)
    assert calls == [1] and pages[0]['text'] == 'Fallback native'
    assert not pages[0]['evidence_complete']


def test_reader_page_count_disagreement_marks_whole_document_incomplete(tmp_path, monkeypatch):
    import pypdf
    path = write_pdf(tmp_path, {'text': 'One'}, {'text': 'Two'})
    monkeypatch.setattr(pypdf, 'PdfReader', lambda *a: SimpleNamespace(
        pages=[SimpleNamespace(extract_text=lambda: 'One')]))
    pages = preprocessor.extract_pdf_pages(path)
    assert [p['text'] for p in pages] == ['One', 'Two']
    assert all(not p['evidence_complete'] and 'PDF_PAGE_COUNT_MISMATCH' in p['extraction_warnings'] for p in pages)


@pytest.mark.parametrize('policy_name', ['grounding', 'grounding_v4'])
@pytest.mark.parametrize('field,label,value', [('company_name', '상호', '북쪽회사'),
                                              ('business_registration_no', '사업자등록번호', '123-45-67891')])
def test_preserved_ocr_party_boundary_rejects_buyer_identity(policy_name, field, label, value):
    import importlib
    policy = importlib.import_module('backend.app.ai.' + policy_name)
    quote = f'{label}: {value}'
    merged = preprocessor._merge_pdf_text('공급받는자', f'공급자\n공급받는자\n{quote}')
    pages = [{'page': 1, 'location_kind': 'page', 'text': merged, 'evidence_complete': True}]
    options = policy.candidates(pages, field, 'tax_invoice')
    assert len(options) == 1 and options[0]['party'] == 'buyer'
    proposal = {'state': 'VALUE', 'value': value, 'page': 1, 'line': 5, 'quote': quote}
    decision = policy.guard_proposal(field, proposal, pages, 'tax_invoice')
    assert not decision['accepted'] and 'WRONG_PARTY' in decision['reasons']


@pytest.mark.parametrize('original,expected', [((400, 1200), (800, 2400)), ((1400, 1600), (1400, 1600))])
def test_coordinate_ocr_uses_shared_size_and_closes_only_owned_resize(monkeypatch, original, expected):
    from backend.app.services.evidence_geometry_service import ocr_boxes
    targets = []

    def recognize(image, lang):
        assert image.size == expected
        targets.append(image)
        width, height = image.size
        return {'lines': [{'text': 'Total 110', 'words': [
            {'text': 'Total 110', 'bounding_rect': {'x': width * .1, 'y': height * .2,
                                                   'width': width * .3, 'height': height * .1}}]}]}

    monkeypatch.setattr(preprocessor, '_safe_winocr_recognize', recognize)
    with Image.new('RGB', original, 'white') as image:
        output = ocr_boxes(image, ['Total 110'], 2)['Total 110']
        assert output['bbox'] == pytest.approx({'page': 2, 'x': .1, 'y': .2, 'width': .3, 'height': .1})
        assert image.getpixel((0, 0)) == (255, 255, 255)
        if original != expected:
            with pytest.raises(ValueError):
                targets[0].getpixel((0, 0))
        else:
            assert targets[0] is image


def test_preprocessing_does_not_close_borrowed_input_stream():
    import io
    with io.BytesIO() as stream:
        with Image.new('RGB', (10, 20), 'white') as source:
            source.save(stream, format='PNG')
        stream.seek(0)
        with preprocessor._to_pil_image(stream) as image:
            assert image.size == (10, 20)
        assert not stream.closed
        stream.seek(0)
        assert stream.read(4) == b'\x89PNG'


def test_empty_ocr_on_raster_page_is_never_verified_blank(tmp_path, monkeypatch):
    path = write_pdf(tmp_path, {'text': 'Before'}, {'raster': True})
    monkeypatch.setattr(preprocessor, 'run_ocr_on_image', lambda _: '')
    pages = preprocessor.extract_pdf_pages(path)
    assert pages[1]['verified_blank'] is False and pages[1]['evidence_complete'] is False
    metadata = {}
    text, extension = preprocessor.extract_text_from_file(path, extraction_metadata=metadata)
    assert 'Before' in text and extension == 'pdf'
    assert metadata == {'evidence_complete': False, 'page_count': 2, 'incomplete_pages': [2],
                        'warning_codes': ['PDF_OCR_EMPTY']}


def test_blank_only_pdf_is_incomplete_at_document_level(tmp_path, monkeypatch):
    path = write_pdf(tmp_path, {})
    monkeypatch.setattr(preprocessor, 'run_ocr_on_image', lambda _: pytest.fail('No OCR for positively blank page'))
    metadata = {}
    preprocessor.extract_text_from_file(path, extraction_metadata=metadata)
    assert metadata == {'evidence_complete': False, 'page_count': 1, 'incomplete_pages': [],
                        'warning_codes': ['PDF_NO_READABLE_TEXT']}


def test_unreadable_pdf_metadata_is_incomplete_without_source_text(tmp_path):
    path = tmp_path / 'invalid.pdf'
    path.write_bytes(b'invalid')
    metadata = {}
    text, extension = preprocessor.extract_text_from_file(path, extraction_metadata=metadata)
    assert text == '[파일명: invalid.pdf]' and extension == 'pdf'
    assert metadata == {'evidence_complete': False, 'page_count': 0, 'incomplete_pages': [],
                        'warning_codes': ['PDF_SOURCE_UNAVAILABLE']}


def test_annotation_only_page_is_not_misclassified_as_verified_blank(tmp_path, monkeypatch):
    writer = PdfWriter()
    page = add_pdf_page(writer)
    annotation = DictionaryObject({NameObject('/Type'): NameObject('/Annot'),
                                   NameObject('/Subtype'): NameObject('/Text'),
                                   NameObject('/Rect'): ArrayObject([NumberObject(v) for v in (20, 20, 80, 80)])})
    page[NameObject('/Annots')] = ArrayObject([writer._add_object(annotation)])
    path = tmp_path / 'annotation.pdf'
    writer.write(path)
    calls = []
    monkeypatch.setattr(preprocessor, 'run_ocr_on_image', lambda _: calls.append(1) or '')
    pages = preprocessor.extract_pdf_pages(path)
    assert calls == [1]
    assert not pages[0]['verified_blank'] and not pages[0]['evidence_complete']
    assert pages[0]['extraction_warnings'] == ['PDF_OCR_EMPTY']
