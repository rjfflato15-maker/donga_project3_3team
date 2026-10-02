from PIL import Image
import pytest

from backend.app.services.evidence_geometry_service import attach_coordinates, normalized_box, ocr_boxes


def test_ocr_boxes_follow_resized_image_axes_and_do_not_pick_duplicate_quotes(monkeypatch):
    from backend.app.ai import preprocessor
    def recognize(image, **kwargs):
        assert image.size == (1600, 1200)
        return {"lines": [{"text": "합계금액: 1100원", "words": [
            {"text": "합계금액:", "bounding_rect": {"x": 160, "y": 240, "width": 160, "height": 60}},
            {"text": "1100원", "bounding_rect": {"x": 360, "y": 240, "width": 160, "height": 60}}]}]}
    monkeypatch.setattr(preprocessor, "_safe_winocr_recognize", recognize)
    with Image.new("RGB", (800, 600)) as image:
        result = ocr_boxes(image, ["합계금액: 1100원"], 2)["합계금액: 1100원"]
    assert result["bbox"] == pytest.approx({"page": 2, "x": .1, "y": .2, "width": .225, "height": .05})
    assert len(result["bboxes"]) == 2
    monkeypatch.setattr(preprocessor, "_safe_winocr_recognize", lambda *a, **kw: {"lines": [
        {"text": "same", "words": []}, {"text": "same", "words": []}]})
    with Image.new("RGB", (1400, 1600)) as image:
        assert ocr_boxes(image, ["same"], 1)["same"]["bbox"] is None


@pytest.mark.parametrize("rectangle", [(0, 0, -1, 2), (-1, 0, 2, 2), (1, 1, 120, 2), (float("nan"), 0, 2, 2)])
def test_invalid_or_unverified_geometry_is_never_clamped_into_a_fake_box(rectangle):
    assert normalized_box(1, rectangle, 100, 100) is None


def test_text_and_docx_have_no_physical_boxes(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("합계금액: 1100원", encoding="utf-8")
    anchor = {"page": None, "line": 1, "quote": "합계금액: 1100원"}
    assert attach_coordinates(source, [anchor], "sha")[0]["bbox"] is None
    assert anchor["source_sha256"] == "sha"


def test_native_pdf_real_rectangles_and_rotated_pages_fail_closed(tmp_path):
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    from backend.app.services.evidence_geometry_service import pdf_boxes
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=200)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(b'BT /F1 12 Tf 30 140 Td (TOTAL 1100) Tj ET')
    page[NameObject('/Contents')] = writer._add_object(stream)
    path = tmp_path/'native.pdf'
    writer.write(path)
    result = pdf_boxes(path, 1, ['TOTAL 1100', 'NOT ON PAGE'])
    box = result['TOTAL 1100']['bbox']
    assert .09 < box['x'] < .11 and .20 < box['y'] < .35
    assert box['page'] == 1 and result['NOT ON PAGE']['bbox'] is None
    page.rotate(90)
    writer.write(path)
    assert pdf_boxes(path, 1, ['TOTAL 1100']) == {}


def test_provenance_api_attaches_actual_boxes_and_preview_checks_source_and_revision(operator_client, db_factory, monkeypatch):
    import io, json
    from test_api import create_contract
    from backend.app.db.models import Document, DocumentExtract, DocumentFileInfo
    from backend.app.services import storage_service, review_context_service
    from backend.app.ai import preprocessor
    cid = create_contract(operator_client)['contract_id']
    buffer = io.BytesIO()
    with Image.new('RGB', (1400, 1600)) as image:
        image.save(buffer, format='PNG')
    key, _, sha = storage_service.store_original(cid, 'coordinate.png', buffer.getvalue())
    storage_service.store_text(key, '견적서\n합계금액: 1100원', '견적서\n합계금액: 1100원')
    with db_factory() as db:
        doc = Document(contract_id=cid, file_name='coordinate.png', storage_path=key, document_type='estimate', processing_status='COMPLETED')
        db.add(doc); db.flush()
        db.add(DocumentExtract(document_id=doc.document_id, raw_fields=json.dumps({'total_amount':1100})))
        db.add(DocumentFileInfo(document_id=doc.document_id, sha256=sha, byte_size=len(buffer.getvalue())))
        db.commit(); did=doc.document_id
    monkeypatch.setattr(review_context_service, 'source_pages', lambda *a: [{'page':1, 'text':'견적서\n합계금액: 1100원', 'location_kind':'page'}])
    monkeypatch.setattr(preprocessor, '_safe_winocr_recognize', lambda *a, **kw: {'lines':[{'text':'합계금액: 1100원', 'words':[{'bounding_rect':{'x':140,'y':320,'width':420,'height':80}}]}]})
    provenance = operator_client.get(f'/api/documents/{did}/provenance').json()
    evidence = provenance['fields']['total_amount']['evidence'][0]
    assert evidence['source_sha256'] == sha and evidence['bbox']['x'] == .1
    revision = operator_client.get(f'/api/contracts/{cid}').json()['workflow']['revision']
    url = f'/api/documents/{did}/preview-image'
    assert operator_client.get(url, params={'masked':False,'revision':revision,'source_sha256':sha}).status_code == 200
    assert operator_client.get(url, params={'masked':False,'revision':revision+1}).status_code == 409
    assert operator_client.get(url, params={'masked':False,'source_sha256':'bad'}).status_code == 409


def test_preview_exif_orientation_matches_coordinate_image(operator_client, db_factory):
    import io
    from test_api import create_contract
    from backend.app.db.models import Document
    from backend.app.services.storage_service import store_original
    cid = create_contract(operator_client)['contract_id']
    buffer = io.BytesIO()
    with Image.new('RGB', (80, 40)) as image:
        exif = image.getexif(); exif[274] = 6
        image.save(buffer, format='JPEG', exif=exif)
    key, _, _ = store_original(cid, 'oriented.jpg', buffer.getvalue())
    with db_factory() as db:
        doc=Document(contract_id=cid,file_name='oriented.jpg',storage_path=key,document_type='estimate')
        db.add(doc); db.commit(); did=doc.document_id
    response=operator_client.get(f'/api/documents/{did}/preview-image',params={'masked':False})
    assert response.status_code == 200
    with Image.open(io.BytesIO(response.content)) as image:
        assert image.size == (40, 80)
