"""Synthetic PDFium raster regressions; WinOCR is replaced at its boundary.

No installed Windows OCR/model is assumed. These exercise actual generated PDF,
preview image and flattened export bytes, rather than mocking PDF coordinates.
"""
import io
import math
import zipfile
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from PIL import Image, ImageChops
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (ArrayObject, DecodedStreamObject, DictionaryObject,
                           NameObject, NumberObject)

from backend.app.ai import pdf_runtime, visual_masking
from backend.app.db.models import Document, DocumentExtract
from backend.app.services import preview_masking_service as masking
from backend.app.services import storage_service
from test_api import create_contract

IDENTIFIER = '123-45-67890'
TRANSFORMS = [(0, False), (90, False), (180, False), (270, False),
              (0, True), (90, True), (180, True), (270, True)]


def synthetic_pdf(path, rotation=0, crop=False, raster=None, form=False, text=IDENTIFIER):
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=500)
    font = writer._add_object(DictionaryObject({NameObject('/Type'): NameObject('/Font'),
        NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')}))
    resources = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
    content = f'BT /F1 20 Tf 30 400 Td ({text}) Tj ET'.encode('ascii')
    if raster is not None:
        obj = DecodedStreamObject()
        obj.set_data(raster.convert('RGB').tobytes())
        obj.update({NameObject('/Type'): NameObject('/XObject'), NameObject('/Subtype'): NameObject('/Image'),
            NameObject('/Width'): NumberObject(raster.width), NameObject('/Height'): NumberObject(raster.height),
            NameObject('/ColorSpace'): NameObject('/DeviceRGB'), NameObject('/BitsPerComponent'): NumberObject(8)})
        image_ref = writer._add_object(obj.flate_encode())
        xobjects = DictionaryObject({NameObject('/Im0'): image_ref})
        image_content = b'q 300 0 0 500 0 0 cm /Im0 Do Q'
        if form:
            nested = DecodedStreamObject()
            nested.set_data(image_content)
            nested.update({NameObject('/Type'): NameObject('/XObject'), NameObject('/Subtype'): NameObject('/Form'),
                NameObject('/BBox'): ArrayObject([NumberObject(v) for v in (0, 0, 300, 500)]),
                NameObject('/Resources'): DictionaryObject({NameObject('/XObject'): xobjects})})
            xobjects = DictionaryObject({NameObject('/Fm0'): writer._add_object(nested)})
            image_content = b'/Fm0 Do'
        resources[NameObject('/XObject')] = xobjects
        content = image_content + b' BT /F1 10 Tf 30 20 Td (Page 1) Tj ET'
    page[NameObject('/Resources')] = resources
    stream = DecodedStreamObject()
    stream.set_data(content)
    page[NameObject('/Contents')] = writer._add_object(stream)
    if crop:
        page.cropbox.lower_left = (20, 200)
        page.cropbox.upper_right = (290, 490)
    if rotation:
        page.rotate(rotation)
    writer.write(path)
    return path


def rendered_pdf(path, scale=2):
    with pdf_runtime.open_pdf(path) as pdf, pdf_runtime.open_page(pdf, 0) as page:
        return pdf_runtime.render_page_image(page, scale)


def dark_pixels(image):
    with image.convert('L') as gray:
        return sum(gray.histogram()[:20])


def dark_bounds(image):
    with image.convert('L') as gray:
        with gray.point(lambda value: 255 if value < 20 else 0) as binary:
            return binary.getbbox()


def install_pdf(db_factory, contract_id, path):
    key, _, _ = storage_service.store_original(contract_id, 'synthetic.pdf', path.read_bytes())
    with db_factory() as db:
        document = Document(contract_id=contract_id, file_name='synthetic.pdf', storage_path=key,
                            document_type='contract', processing_status='COMPLETED')
        db.add(document)
        db.flush()
        db.add(DocumentExtract(document_id=document.document_id, raw_fields='{}'))
        db.commit()
        return document.document_id


def response_image(response, route, tmp_path):
    assert response.status_code == 200, response.text
    if route == 'preview-image':
        with Image.open(io.BytesIO(response.content)) as image:
            return image.convert('RGB')
    content = response.content
    if route == 'export':
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = [name for name in archive.namelist() if name.endswith('.pdf')]
            assert len(names) == 1
            content = archive.read(names[0])
    path = tmp_path / f'{route}-protected.pdf'
    path.write_bytes(content)
    # Flattened PDF has no selectable original identifier text.
    assert IDENTIFIER not in ''.join(page.extract_text() or '' for page in PdfReader(path).pages)
    # At export scale 1.5 and resolution 108, render scale 1.5 returns its bitmap.
    return rendered_pdf(path, 1.5)


@pytest.mark.parametrize('rotation,crop', TRANSFORMS)
@pytest.mark.parametrize('route', ['preview-image', 'download', 'export'])
def test_native_pdf_transform_is_masked_in_every_http_output(rotation, crop, route,
        operator_client, db_factory, monkeypatch, tmp_path):
    path = synthetic_pdf(tmp_path / 'native.pdf', rotation, crop)
    with rendered_pdf(path) as original:
        assert dark_pixels(original) > 100
    def unavailable(*_, **__):
        raise AssertionError('Ordinary native text must not require OCR, even when rotated/cropped.')
    monkeypatch.setattr(masking, '_safe_winocr_recognize', unavailable)
    cid = create_contract(operator_client)['contract_id']
    did = install_pdf(db_factory, cid, path)
    url = f'/api/contracts/{cid}/export' if route == 'export' else f'/api/documents/{did}/{route}'
    response = operator_client.get(url, params={'masked': True})
    with response_image(response, route, tmp_path) as protected:
        assert dark_pixels(protected) == 0
        assert protected.convert('L').getextrema()[0] >= 20


def mixed_fixture(tmp_path, rotation=0, crop=False, form=False):
    native = synthetic_pdf(tmp_path / 'number.pdf')
    with rendered_pdf(native) as raster:
        path = synthetic_pdf(tmp_path / 'mixed.pdf', rotation, crop, raster=raster, form=form)
    # A number-only native control supplies independent expected bounds in the
    # same final rotation/CropBox. It is never a production OCR implementation.
    expected = synthetic_pdf(tmp_path / 'expected.pdf', rotation, crop)
    with rendered_pdf(expected) as number_only:
        bounds, size = dark_bounds(number_only), number_only.size
    return path, bounds, size


def positioned_ocr(bounds, size, calls):
    def recognize(image, lang):
        calls.append(image.size)
        x0, y0, x1, y1 = (bounds[0] * image.width / size[0], bounds[1] * image.height / size[1],
                          bounds[2] * image.width / size[0], bounds[3] * image.height / size[1])
        # Split at OCR word boundaries so masking a single-word regex is not enough.
        words = []
        for index, value in enumerate(['123-', '45-', '67890']):
            left = x0 + (x1 - x0) * index / 3
            words.append({'text': value, 'bounding_rect': {'x': left, 'y': y0,
                'width': (x1 - x0) / 3, 'height': y1 - y0}})
        return {'lines': [{'text': '123- 45- 67890', 'words': words}]}
    return recognize


@pytest.mark.parametrize('rotation,crop', TRANSFORMS)
@pytest.mark.parametrize('route', ['preview-image', 'download', 'export'])
def test_mixed_raster_and_native_footer_uses_ocr_in_every_http_output(rotation, crop, route,
        operator_client, db_factory, monkeypatch, tmp_path):
    path, bounds, size = mixed_fixture(tmp_path, rotation, crop)
    calls = []
    monkeypatch.setattr(masking, '_safe_winocr_recognize', positioned_ocr(bounds, size, calls))
    cid = create_contract(operator_client)['contract_id']
    did = install_pdf(db_factory, cid, path)
    url = f'/api/contracts/{cid}/export' if route == 'export' else f'/api/documents/{did}/{route}'
    response = operator_client.get(url, params={'masked': True})
    with response_image(response, route, tmp_path) as protected:
        target = (math.floor(bounds[0] * protected.width / size[0]),
                  math.floor(bounds[1] * protected.height / size[1]),
                  math.ceil(bounds[2] * protected.width / size[0]),
                  math.ceil(bounds[3] * protected.height / size[1]))
        with protected.crop(target) as number_region:
            assert dark_pixels(number_region) == 0
            assert number_region.convert('L').getextrema()[0] >= 20
        if not crop:
            assert dark_pixels(protected) > 10  # Native footer remains readable.
    assert len(calls) == 1


@pytest.mark.parametrize('route', ['preview-image', 'download', 'export'])
@pytest.mark.parametrize('failure', [None, {'lines': []}, {'lines': [{'text': IDENTIFIER, 'words': []}]},
                                    'unavailable'])
def test_required_ocr_failure_never_returns_original_or_partial_output(route, failure,
        operator_client, db_factory, monkeypatch, tmp_path):
    path, _, _ = mixed_fixture(tmp_path)
    def recognize(*_, **__):
        if failure == 'unavailable':
            raise ImportError('Controlled missing Windows OCR boundary')
        return failure
    monkeypatch.setattr(masking, '_safe_winocr_recognize', recognize)
    cid = create_contract(operator_client)['contract_id']
    did = install_pdf(db_factory, cid, path)
    url = f'/api/contracts/{cid}/export' if route == 'export' else f'/api/documents/{did}/{route}'
    response = operator_client.get(url, params={'masked': True})
    assert response.status_code == 503, response.text
    assert response.headers['content-type'].startswith('application/json')
    original = operator_client.get(f'/api/documents/{did}/download', params={'masked': False})
    assert original.status_code == 200 and original.content == path.read_bytes()


def test_form_xobject_with_native_footer_requires_ocr(monkeypatch, tmp_path):
    path, bounds, size = mixed_fixture(tmp_path, form=True)
    calls = []
    monkeypatch.setattr(masking, '_safe_winocr_recognize', positioned_ocr(bounds, size, calls))
    with pdf_runtime.open_pdf(path) as pdf, pdf_runtime.open_page(pdf, 0) as page:
        assert pdf_runtime.page_requires_raster_masking(page)
        with pdf_runtime.render_page_image(page, 2) as original:
            with visual_masking.mask_pdf_page_image(page, original) as protected:
                with protected.crop(bounds) as target:
                    assert dark_pixels(target) == 0
    assert len(calls) == 1


def test_native_non_sensitive_text_is_unchanged_and_known_list_values_are_masked(monkeypatch, tmp_path):
    path = synthetic_pdf(tmp_path / 'ordinary.pdf', text='2026-09-01 Total 110')
    monkeypatch.setattr(masking, '_safe_winocr_recognize', lambda *a, **k: pytest.fail('Unexpected OCR'))
    with pdf_runtime.open_pdf(path) as pdf, pdf_runtime.open_page(pdf, 0) as page:
        with pdf_runtime.render_page_image(page, 2) as original:
            with visual_masking.mask_pdf_page_image(page, original) as protected:
                assert ImageChops.difference(original, protected).getbbox() is None
            with visual_masking.mask_pdf_page_image(page, original, sensitive_dict={'vendor_name': ['Total']}) as protected:
                assert ImageChops.difference(original, protected).getbbox() is not None
                assert dark_pixels(protected) > 100  # Date and amount are retained.


@pytest.mark.parametrize('field,value', [('x', math.nan), ('y', math.inf), ('width', -1),
    ('height', 0), ('x', 300), ('y', -10), ('width', 'invalid')])
def test_invalid_ocr_rectangles_fail_closed(monkeypatch, field, value):
    rect = {'x': 10, 'y': 10, 'width': 80, 'height': 20}
    rect[field] = value
    monkeypatch.setattr(masking, '_safe_winocr_recognize', lambda *a, **k: {
        'lines': [{'text': IDENTIFIER, 'words': [{'text': IDENTIFIER, 'bounding_rect': rect}]}]})
    with Image.new('RGB', (200, 100), 'white') as image:
        with pytest.raises(RuntimeError):
            masking.mask_image_with_ocr(image)


def test_partially_positioned_ocr_line_fails_closed(monkeypatch):
    monkeypatch.setattr(masking, '_safe_winocr_recognize', lambda *a, **k: {'lines': [{
        'text': 'Page 1 ' + IDENTIFIER,
        'words': [{'text': 'Page 1', 'bounding_rect': {'x': 10, 'y': 10, 'width': 40, 'height': 20}}]}]})
    with Image.new('RGB', (200, 100), 'white') as image:
        with pytest.raises(RuntimeError):
            masking.mask_image_with_ocr(image)


@pytest.mark.parametrize('width,height,scale', [(0, 10, 2), (10, -1, 2), (10, 10, 0),
    (math.inf, 100, 2), (100, math.nan, 2), (10, 10, math.inf)])
def test_invalid_render_geometry_is_rejected(width, height, scale):
    with pytest.raises(RuntimeError):
        visual_masking._render_scale(width, height, scale)


@pytest.mark.parametrize('size', [(10000, 10000), (10000000, 10), (10, 10000000), (300.1, 500.3)])
def test_rounded_render_budget_is_finite(size):
    scale, pixels = visual_masking._render_scale(*size, 2)
    assert 0 < scale <= 2 and math.isfinite(scale)
    assert pixels == math.ceil(size[0] * scale) * math.ceil(size[1] * scale)
    assert pixels <= visual_masking.MAX_PAGE_PIXELS
    assert max(math.ceil(edge * scale) for edge in size) <= visual_masking.MAX_PAGE_EDGE


def test_native_helpers_obey_shared_lock_and_ocr_runs_outside_it(monkeypatch, tmp_path):
    path, bounds, size = mixed_fixture(tmp_path)
    original_ocr = positioned_ocr(bounds, size, [])
    def recognize(image, lang):
        with ThreadPoolExecutor(max_workers=1) as executor:
            def acquire():
                acquired = pdf_runtime.PDFIUM_LOCK.acquire(timeout=1)
                if acquired:
                    pdf_runtime.PDFIUM_LOCK.release()
                return acquired
            assert executor.submit(acquire).result(timeout=2), 'OCR must not hold PDFium mutex.'
        return original_ocr(image, lang)
    monkeypatch.setattr(masking, '_safe_winocr_recognize', recognize)
    with pdf_runtime.open_pdf(path) as pdf, pdf_runtime.open_page(pdf, 0) as page:
        started, done = Event(), Event()
        def inspect():
            started.set()
            pdf_runtime.page_requires_raster_masking(page)
            done.set()
        with ThreadPoolExecutor(max_workers=1) as executor:
            with pdf_runtime.PDFIUM_LOCK:
                future = executor.submit(inspect)
                assert started.wait(1)
                assert not done.wait(0.1)
            future.result(timeout=2)
        with pdf_runtime.render_page_image(page, 2) as image:
            with visual_masking.mask_pdf_page_image(page, image):
                pass


def test_second_page_failure_discards_export_and_closes_images(monkeypatch, tmp_path):
    first = synthetic_pdf(tmp_path / 'first.pdf')
    writer = PdfWriter()
    writer.append(first)
    writer.append(first)
    path = tmp_path / 'two.pdf'
    writer.write(path)
    images, calls = [], []
    original_render = pdf_runtime.render_page_image
    original_mask = visual_masking.mask_pdf_page_image
    def render(*args):
        image = original_render(*args)
        images.append(image)
        return image
    def mask(*args, **kwargs):
        calls.append(True)
        if len(calls) == 2:
            raise RuntimeError('Controlled second-page failure')
        image = original_mask(*args, **kwargs)
        images.append(image)
        return image
    monkeypatch.setattr(pdf_runtime, 'render_page_image', render)
    monkeypatch.setattr(visual_masking, 'mask_pdf_page_image', mask)
    with pytest.raises(RuntimeError, match='second-page'):
        visual_masking.render_masked_pdf_bytes(path)
    for image in images:
        with pytest.raises(ValueError):
            image.getpixel((0, 0))


def test_page_limit_blocks_before_render(monkeypatch, tmp_path):
    writer = PdfWriter()
    for _ in range(51):
        writer.add_blank_page(width=1, height=1)
    path = tmp_path / '51.pdf'
    writer.write(path)
    monkeypatch.setattr(pdf_runtime, 'render_page_image', lambda *a: pytest.fail('No oversized document rendering'))
    with pytest.raises(RuntimeError, match='1~50'):
        visual_masking.render_masked_pdf_bytes(path)


def test_document_pixel_limit_blocks_before_next_bitmap(monkeypatch, tmp_path):
    writer = PdfWriter()
    for _ in range(4):
        writer.add_blank_page(width=10000, height=10000)
    path = tmp_path / 'budget.pdf'
    writer.write(path)
    calls = []
    def render(page, scale):
        calls.append(scale)
        return Image.new('RGB', (1, 1), 'white')
    monkeypatch.setattr(pdf_runtime, 'render_page_image', render)
    monkeypatch.setattr(visual_masking, 'mask_pdf_page_image', lambda page, image, **kw: image.copy())
    with pytest.raises(RuntimeError, match='전체 크기'):
        visual_masking.render_masked_pdf_bytes(path)
    assert len(calls) == 3  # Never allocate actual 16M bitmaps in this budget test.


def decorated_pdf(path, kind):
    """Native footer plus annotation appearance or vector-path identifier."""
    synthetic_pdf(path, text='Page 1')
    writer = PdfWriter(clone_from=path)
    page = writer.pages[0]
    footer = b'BT /F1 10 Tf 30 20 Td (Page 1) Tj ET'
    if kind == 'annotation':
        appearance = DecodedStreamObject()
        appearance.set_data(b'BT /F1 20 Tf 0 10 Td (123-45-67890) Tj ET')
        appearance.update({NameObject('/Type'): NameObject('/XObject'), NameObject('/Subtype'): NameObject('/Form'),
            NameObject('/BBox'): ArrayObject([NumberObject(v) for v in (0, 0, 220, 50)]),
            NameObject('/Resources'): page['/Resources']})
        annotation = DictionaryObject({NameObject('/Type'): NameObject('/Annot'), NameObject('/Subtype'): NameObject('/Stamp'),
            NameObject('/Rect'): ArrayObject([NumberObject(v) for v in (30, 350, 250, 400)]),
            NameObject('/AP'): DictionaryObject({NameObject('/N'): writer._add_object(appearance)}),
            NameObject('/F'): NumberObject(4)})
        page[NameObject('/Annots')] = ArrayObject([writer._add_object(annotation)])
        body = b''
    else:
        segments = {'a': (0, 20, 10, 20), 'b': (10, 20, 10, 10), 'c': (10, 10, 10, 0),
                    'd': (0, 0, 10, 0), 'e': (0, 10, 0, 0), 'f': (0, 20, 0, 10), 'g': (0, 10, 10, 10)}
        digits = {'0': 'abcdef', '1': 'bc', '2': 'abdeg', '3': 'abcdg', '4': 'bcfg',
                  '5': 'acdfg', '6': 'acdefg', '7': 'abc', '8': 'abcdefg', '9': 'abcdfg', '-': 'g'}
        body = b'2 w '
        for index, digit in enumerate(IDENTIFIER):
            for segment in digits[digit]:
                x0, y0, x1, y1 = segments[segment]
                body += f'{30+index*16+x0} {350+y0} m {30+index*16+x1} {350+y1} l S '.encode()
    stream = DecodedStreamObject()
    stream.set_data(body + footer)
    page[NameObject('/Contents')] = writer._add_object(stream)
    writer.write(path)
    with rendered_pdf(path) as original, original.crop((0, 0, 600, 900)) as top:
        bounds = dark_bounds(top)
        assert bounds is not None
        return path, bounds, original.size


@pytest.mark.parametrize('kind', ['annotation', 'vector'])
@pytest.mark.parametrize('route', ['preview-image', 'download', 'export'])
@pytest.mark.parametrize('ocr_available', [True, False])
def test_content_outside_native_text_requires_ocr_and_is_never_silently_exposed(kind, route,
        ocr_available, operator_client, db_factory, monkeypatch, tmp_path):
    path, bounds, size = decorated_pdf(tmp_path / f'{kind}.pdf', kind)
    calls = []
    recognize = positioned_ocr(bounds, size, calls) if ocr_available else lambda *a, **k: None
    monkeypatch.setattr(masking, '_safe_winocr_recognize', recognize)
    with pdf_runtime.open_pdf(path) as pdf, pdf_runtime.open_page(pdf, 0) as page:
        assert pdf_runtime.page_requires_raster_masking(page)
        with pdf_runtime.open_textpage(page) as textpage:
            assert IDENTIFIER not in pdf_runtime.page_text(textpage)
    cid = create_contract(operator_client)['contract_id']
    did = install_pdf(db_factory, cid, path)
    url = f'/api/contracts/{cid}/export' if route == 'export' else f'/api/documents/{did}/{route}'
    response = operator_client.get(url, params={'masked': True})
    if not ocr_available:
        assert response.status_code == 503, response.text
        return
    with response_image(response, route, tmp_path) as protected:
        target = (math.floor(bounds[0] * protected.width / size[0]),
                  math.floor(bounds[1] * protected.height / size[1]),
                  math.ceil(bounds[2] * protected.width / size[0]),
                  math.ceil(bounds[3] * protected.height / size[1]))
        with protected.crop(target) as identifier:
            assert dark_pixels(identifier) == 0
        assert dark_pixels(protected) > 10  # The native footer is still visible.
    assert len(calls) == 1


def test_whole_ocr_result_cannot_contain_unpositioned_text(monkeypatch):
    monkeypatch.setattr(masking, '_safe_winocr_recognize', lambda *a, **k: {
        'text': 'Page 1 ' + IDENTIFIER,
        'lines': [{'text': 'Page 1', 'words': [{'text': 'Page 1',
            'bounding_rect': {'x': 1, 'y': 1, 'width': 30, 'height': 12}}]}]})
    with Image.new('RGB', (200, 100), 'white') as image:
        with pytest.raises(RuntimeError):
            masking.mask_image_with_ocr(image)


def test_unresolved_native_sensitive_geometry_fails_closed(monkeypatch, tmp_path):
    path = synthetic_pdf(tmp_path / 'native.pdf')
    monkeypatch.setattr(pdf_runtime, 'matching_text_rectangles', lambda *a: [])
    with pdf_runtime.open_pdf(path) as pdf, pdf_runtime.open_page(pdf, 0) as page:
        with pdf_runtime.render_page_image(page, 2) as original:
            with pytest.raises(RuntimeError, match='위치'):
                visual_masking.mask_pdf_page_image(page, original)


@pytest.mark.parametrize('helper', ['matching_text_rectangles', 'page_rect_to_bitmap'])
def test_native_search_and_coordinate_helpers_wait_for_pdfium_mutex(helper, tmp_path):
    path = synthetic_pdf(tmp_path / 'native.pdf')
    with pdf_runtime.open_pdf(path) as pdf, pdf_runtime.open_page(pdf, 0) as page:
        with pdf_runtime.open_textpage(page) as textpage:
            operation = (lambda: pdf_runtime.matching_text_rectangles(textpage, IDENTIFIER)) if helper == 'matching_text_rectangles' else (
                lambda: pdf_runtime.page_rect_to_bitmap(page, (30, 400, 140, 420), (600, 1000)))
            started, done = Event(), Event()
            def invoke():
                started.set()
                result = operation()
                done.set()
                return result
            with ThreadPoolExecutor(max_workers=1) as executor:
                with pdf_runtime.PDFIUM_LOCK:
                    pending = executor.submit(invoke)
                    assert started.wait(1)
                    assert not done.wait(0.1)
                assert pending.result(timeout=2)


@pytest.mark.parametrize('ocr_fails', [False, True])
def test_resized_ocr_uses_actual_axis_scale_and_closes_temporary_image(monkeypatch, ocr_fails):
    targets = []
    def recognize(target, lang):
        targets.append(target)
        assert max(target.size) <= 2400
        if ocr_fails:
            raise RuntimeError('Controlled OCR failure')
        return {'text': IDENTIFIER, 'lines': [{'text': IDENTIFIER, 'words': [{
            'text': IDENTIFIER, 'bounding_rect': {'x': 400 * target.width / 3001,
                'y': 99 * target.height / 301, 'width': 80 * target.width / 3001,
                'height': 20 * target.height / 301}}]}]}
    monkeypatch.setattr(masking, '_safe_winocr_recognize', recognize)
    with Image.new('RGB', (3001, 301), 'white') as image:
        from PIL import ImageDraw
        ImageDraw.Draw(image).rectangle((400, 99, 480, 119), fill='black')
        if ocr_fails:
            with pytest.raises(RuntimeError):
                masking.mask_image_with_ocr(image)
        else:
            with masking.mask_image_with_ocr(image) as protected:
                assert dark_pixels(protected) == 0
    assert len(targets) == 1
    with pytest.raises(ValueError):
        targets[0].getpixel((0, 0))
