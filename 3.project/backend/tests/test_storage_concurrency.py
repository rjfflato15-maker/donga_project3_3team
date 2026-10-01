import io
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from pypdf import PdfWriter

from backend.app.db.models import AuditEvent, Document, DocumentExtract
from backend.app.services import pipeline_service, storage_service
from test_api import create_contract


def seed_pdf(db_factory, contract_id, pages=1):
    buffer = io.BytesIO()
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=300, height=200)
    writer.write(buffer)
    key, _, _ = storage_service.store_original(contract_id, "미리보기.pdf", buffer.getvalue())
    with db_factory() as db:
        document = Document(contract_id=contract_id, file_name="미리보기.pdf", storage_path=key,
                            document_type="contract", processing_status="COMPLETED")
        db.add(document)
        db.flush()
        db.add(DocumentExtract(document_id=document.document_id, raw_fields="{}"))
        db.commit()
        return document.document_id, buffer.getvalue()


def block_analysis(monkeypatch):
    started, finish = Event(), Event()
    analyze = pipeline_service.analyze_document
    def blocked(*args, **kwargs):
        started.set()
        if not finish.wait(10):
            raise AssertionError("Test did not release analysis worker.")
        return analyze(*args, **kwargs)
    monkeypatch.setattr(pipeline_service, "analyze_document", blocked)
    return started, finish


def test_ocr_upload_does_not_block_other_contract_preview(operator_client, separate_client, db_factory, monkeypatch):
    uploader_contract = create_contract(operator_client)
    visible_contract = create_contract(operator_client, title="대표가 확인할 다른 계약")
    doc_id, content = seed_pdf(db_factory, visible_contract["contract_id"])
    representative = separate_client()
    started, finish = block_analysis(monkeypatch)
    with ThreadPoolExecutor(max_workers=2) as workers:
        upload = workers.submit(operator_client.post,
            f"/api/contracts/{uploader_contract['contract_id']}/documents",
            files=[("files", ("분석중_계약서.txt", "외주 용역 계약서\n계약금액: 1,000원".encode(), "text/plain"))])
        try:
            assert started.wait(2), "OCR worker did not start."
            listing = workers.submit(representative.get, "/api/contracts")
            response = listing.result(timeout=2)
            assert response.status_code == 200, response.text
            read = workers.submit(representative.get, f"/api/documents/{doc_id}/download", params={"masked": False})
            response = read.result(timeout=2)
            assert response.status_code == 200, response.text
            assert response.content == content
            preview = workers.submit(representative.get, f"/api/documents/{doc_id}/preview-image", params={"masked": False})
            response = preview.result(timeout=2)
            assert response.status_code == 200, response.text
            assert response.content.startswith(b"\x89PNG\r\n\x1a\n")
            assert not upload.done(), "Upload should still be waiting in simulated OCR."
        finally:
            finish.set()
        response = upload.result(timeout=10)
        assert response.status_code == 200, response.text


@pytest.mark.parametrize("operation", ["preview-image", "download", "text-preview"])
def test_slow_masking_does_not_block_other_file_requests(operation, operator_client, separate_client, db_factory, monkeypatch):
    from backend.app.ai import visual_masking
    from backend.app.api import documents

    contract = create_contract(operator_client)
    doc_id, pdf_bytes = seed_pdf(db_factory, contract["contract_id"])
    representative = separate_client()
    started, finish = Event(), Event()

    def paused(*args, **kwargs):
        started.set()
        if not finish.wait(10):
            raise AssertionError("Test did not release masking worker.")
        if operation == "preview-image":
            return args[1].copy()
        if operation == "download":
            return pdf_bytes
        return "테스트 원문", "테스트 가린 텍스트"

    if operation == "text-preview":
        monkeypatch.setattr(documents, "read_texts", paused)
    else:
        method = "mask_pdf_page_image" if operation == "preview-image" else "render_masked_pdf_bytes"
        monkeypatch.setattr(visual_masking, method, paused)

    with ThreadPoolExecutor(max_workers=2) as workers:
        masking = workers.submit(operator_client.get, f"/api/documents/{doc_id}/{operation}", params={"masked": True})
        try:
            assert started.wait(2), "Masking worker did not start."
            listing = workers.submit(representative.get, "/api/contracts")
            assert listing.result(timeout=2).status_code == 200
            # This request writes an audit event under STORAGE_LOCK. It must
            # finish while the other request is still rendering/OCRing.
            download = workers.submit(representative.get, f"/api/documents/{doc_id}/download", params={"masked": False})
            response = download.result(timeout=2)
            assert response.status_code == 200, response.text
            assert response.content == pdf_bytes
            assert not masking.done()
        finally:
            finish.set()
        response = masking.result(timeout=10)
        assert response.status_code == 200, response.text


@pytest.mark.parametrize("intervening_change", ["revision", "delete"])
def test_restore_cannot_overwrite_concurrent_changes(intervening_change, operator_client, separate_client, db_factory, monkeypatch):
    contract = create_contract(operator_client)
    cid = contract["contract_id"]
    with db_factory() as db:
        missing = Document(contract_id=cid, file_name="계약서.txt", storage_path="raw/unavailable.txt",
                           document_type="contract", processing_status="COMPLETED")
        db.add(missing)
        db.commit()
        doc_id = missing.document_id
    second_operator = separate_client("operator")
    started, finish = block_analysis(monkeypatch)
    with ThreadPoolExecutor(max_workers=2) as workers:
        restoration = workers.submit(operator_client.put, f"/api/documents/{doc_id}/original",
            files={"file": ("계약서.txt", "외주 용역 계약서\n계약금액: 1,000원".encode(), "text/plain")})
        try:
            assert started.wait(2)
            if intervening_change == "revision":
                change = workers.submit(second_operator.put, f"/api/contracts/{cid}", json={
                    "title": "다른 담당자가 수정한 계약", "revision": contract["workflow"]["revision"],
                    "change_note": "복구 중 최신 계약 변경"})
                assert change.result(timeout=2).status_code == 200
            else:
                change = workers.submit(second_operator.delete, f"/api/documents/{doc_id}")
                assert change.result(timeout=2).status_code == 204
        finally:
            finish.set()
        response = restoration.result(timeout=10)
        assert response.status_code == 409, response.text
    if intervening_change == "revision":
        detail = second_operator.get(f"/api/documents/{doc_id}").json()
        assert detail["file_available"] is False
    else:
        assert second_operator.get(f"/api/documents/{doc_id}").status_code == 404


def test_pdf_page_runtime_and_mask_failure_is_closed(operator_client, db_factory, monkeypatch):
    from backend.app.ai import visual_masking
    contract = create_contract(operator_client)
    doc_id, _ = seed_pdf(db_factory, contract["contract_id"], pages=2)
    pages = operator_client.get(f"/api/documents/{doc_id}/pages-info")
    assert pages.status_code == 200, pages.text
    assert pages.json()["total_pages"] == 2
    for page in range(2):
        response = operator_client.get(f"/api/documents/{doc_id}/preview-image", params={"page": page, "masked": False})
        assert response.status_code == 200, response.text
        assert response.content.startswith(b"\x89PNG")
    assert operator_client.get(f"/api/documents/{doc_id}/preview-image", params={"page": 2, "masked": False}).status_code == 404
    def failed_mask(*_, **__):
        raise RuntimeError("simulated privacy mask failure")
    monkeypatch.setattr(visual_masking, "mask_pdf_page_image", failed_mask)
    response = operator_client.get(f"/api/documents/{doc_id}/preview-image")
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/json")
    response = operator_client.get(f"/api/documents/{doc_id}/download", params={"masked": True})
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/json")
    with db_factory() as db:
        events = db.query(AuditEvent).filter(AuditEvent.document_id == doc_id).all()
        assert sum(event.action == "ORIGINAL_PREVIEW_REQUEST" for event in events) == 2
        assert not any(event.action.startswith("MASKED_") for event in events)


def test_masked_pdf_export_closes_bitmap_and_supports_installed_runtime(operator_client, db_factory, monkeypatch):
    from backend.app.ai import visual_masking
    contract = create_contract(operator_client)
    doc_id, _ = seed_pdf(db_factory, contract["contract_id"], pages=2)
    # This checks the installed PDF API/resource path, not OCR or masking quality.
    monkeypatch.setattr(visual_masking, "mask_pdf_page_image", lambda page, image, **_: image.copy())
    response = operator_client.get(f"/api/documents/{doc_id}/download", params={"masked": True})
    assert response.status_code == 200, response.text
    assert response.content.startswith(b"%PDF-")
    assert "masked_" in response.headers["content-disposition"]
