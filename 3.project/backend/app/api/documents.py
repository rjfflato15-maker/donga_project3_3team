import hashlib
import io
import json
import mimetypes
from pathlib import Path
from urllib.parse import quote
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..db.models import Document, DocumentFileInfo, ValidationResult
from ..schemas.document import DocumentResponse, AnalysisFields
from ..schemas.common import DocumentType
from ..services.contract_service import get_document_response
from ..services.pipeline_service import PipelineService
from ..services.storage_service import read_upload, resolve_path, STORAGE_LOCK, read_texts
from ..services.workflow_service import audit, touch_contract, policy_for
from ..security import Actor, get_current_user, require_operator

router = APIRouter(tags=["Documents"])
pipeline_service = PipelineService()
PRIVATE_HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}


def document_and_path(db, document_id):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, "문서를 찾을 수 없습니다.")
    path = resolve_path(doc.storage_path)
    if not path:
        raise HTTPException(404, "공용 서버에 원본 파일이 없습니다. 담당자가 원본을 다시 등록해야 합니다.")
    return doc, path


def sensitive_values(doc):
    fields = json.loads(doc.extract.raw_fields or "{}") if doc.extract else {}
    keys = ("company_name", "business_registration_no", "account_number", "phone", "address", "representative_name")
    values = {k: str(fields[k]) for k in keys if fields.get(k)}
    if doc.contract:
        values.update(vendor_name=doc.contract.vendor_name, business_number=doc.contract.business_number)
    return values


@router.post("/api/contracts/{contract_id}/documents", response_model=List[DocumentResponse])
def upload_contract_documents(contract_id: int, files: List[UploadFile] = File(...),
                              target_document_type: Optional[str] = Form(None), db: Session = Depends(get_db),
                              actor: Actor = Depends(require_operator)):
    if not 1 <= len(files) <= 20:
        raise HTTPException(400, "한 번에 1~20개 파일을 등록하세요.")
    if target_document_type and target_document_type not in [t.value for t in DocumentType]:
        raise HTTPException(400, "문서 유형을 확인하세요.")
    contents = [(file, read_upload(file)) for file in files]
    result = []
    for file, content in contents:
        try:
            doc = pipeline_service.process_document_upload(db, contract_id, file.filename, content, target_document_type or "")
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        audit(db, actor, "DOCUMENT_UPLOAD", contract_id, doc.document_id, {"file_name": doc.file_name})
        result.append(get_document_response(doc))
    return result


@router.get("/api/documents/{document_id}", response_model=DocumentResponse)
def get_document(document_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, "문서를 찾을 수 없습니다.")
    return get_document_response(doc)


@router.delete("/api/documents/{document_id}", status_code=204)
def delete_document(document_id: int, db: Session = Depends(get_db), actor: Actor = Depends(require_operator)):
    with STORAGE_LOCK:
        doc = db.get(Document, document_id)
        if not doc:
            raise HTTPException(404, "문서를 찾을 수 없습니다.")
        contract_id, name = doc.contract_id, doc.file_name
        db.query(ValidationResult).filter(ValidationResult.extract_id == (doc.extract.extract_id if doc.extract else -1)).delete()
        db.query(DocumentFileInfo).filter(DocumentFileInfo.document_id == document_id).delete()
        db.delete(doc)
        touch_contract(db, contract_id)
        db.commit()
        audit(db, actor, "DOCUMENT_DELETE", contract_id, document_id, {"file_name": name})
    pipeline_service.revalidate_contract(db, contract_id)


@router.put("/api/documents/{document_id}/original", response_model=DocumentResponse)
def restore_original(document_id: int, file: UploadFile = File(...), db: Session = Depends(get_db),
                     actor: Actor = Depends(require_operator)):
    content = read_upload(file)
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, "문서를 찾을 수 없습니다.")
    if resolve_path(doc.storage_path):
        raise HTTPException(409, "원본이 이미 보관되어 있습니다. 새 문서는 증빙 업로드로 등록하세요.")
    if Path(file.filename or "").suffix.lower() != Path(doc.file_name).suffix.lower():
        raise HTTPException(400, "기존 원본과 같은 파일 형식으로 등록하세요.")
    info = db.get(DocumentFileInfo, document_id)
    if info and info.sha256 != hashlib.sha256(content).hexdigest():
        raise HTTPException(409, "이전에 저장한 원본과 내용이 다릅니다. 정확한 원본을 등록하거나 새 증빙으로 추가하세요.")
    contract_id, document_type = doc.contract_id, doc.document_type
    revision = policy_for(db, contract_id)["revision"]
    updated = pipeline_service.process_document_upload(db, contract_id, file.filename, content,
                                                        document_type, existing_document_id=document_id,
                                                        restoration_revision=revision)
    with STORAGE_LOCK:
        audit(db, actor, "ORIGINAL_RESTORED", contract_id, document_id, {"reanalysis": True})
    return get_document_response(updated)


class Correction(BaseModel):
    fields: AnalysisFields
    document_type: DocumentType
    revision: int
    note: str


@router.put("/api/documents/{document_id}/fields", response_model=DocumentResponse)
def correct_fields(document_id: int, req: Correction, db: Session = Depends(get_db),
                   actor: Actor = Depends(require_operator)):
    with STORAGE_LOCK:
        doc = db.get(Document, document_id)
        if not doc or not doc.extract:
            raise HTTPException(404, "추출 결과를 찾을 수 없습니다.")
        if req.revision != policy_for(db, doc.contract_id)["revision"]:
            raise HTTPException(409, "자료가 변경되었습니다. 새로고침 후 다시 수정하세요.")
        if not req.note.strip():
            raise HTTPException(400, "추출값 수정 사유를 입력하세요.")
        if req.fields.amount_basis not in {"TOTAL", "SUPPLY", "UNKNOWN"} or req.fields.amount_scope not in {"FULL", "PARTIAL", "UNKNOWN"}:
            raise HTTPException(400, "금액 기준과 청구 범위를 확인하세요.")
        from ..validation.financial import money
        for key in ("amount", "supply_amount", "tax_amount", "total_amount"):
            value = getattr(req.fields, key)
            if value is not None and money(value) is None:
                raise HTTPException(400, "금액은 0 이상의 유효한 숫자로 입력하세요.")
        before = json.loads(doc.extract.raw_fields or "{}")
        doc.document_type = req.document_type.value
        after = req.fields.model_dump()
        if before.get("ai_review"):
            after["ai_review"] = {**before["ai_review"], "human_confirmed": True, "manual_review_required": False}
        doc.extract.raw_fields = json.dumps(after, ensure_ascii=False)
        doc.extract.extracted_vendor_name = req.fields.company_name
        doc.extract.extracted_vendor_reg_no = req.fields.business_registration_no
        doc.extract.extracted_amount = req.fields.total_amount if req.fields.total_amount is not None else req.fields.amount
        doc.extract.extracted_date = req.fields.issue_date
        doc.extract.extracted_status = "MANUALLY_CONFIRMED"
        touch_contract(db, doc.contract_id)
        contract_id = doc.contract_id
        db.commit()
        audit(db, actor, "EXTRACT_CORRECTED", contract_id, document_id,
              {"note": req.note.strip()[:1000], "before": before, "after": req.fields.model_dump()})
    pipeline_service.revalidate_contract(db, contract_id)
    return get_document_response(doc)


def record_file_request(db, actor, action, contract_id, document_id, details=None):
    # Record only after preparing a response. This is still a request record,
    # not proof that the browser received every byte of a streamed response.
    # Rendering/OCR finishes before taking this short publication lock.
    with STORAGE_LOCK:
        audit(db, actor, action + "_REQUEST", contract_id, document_id, details)


def serve_document(document_id, masked, disposition, db, actor):
    doc, path = document_and_path(db, document_id)
    suffix, name, contract_id = path.suffix.lower(), doc.file_name, doc.contract_id
    sensitive = sensitive_values(doc) if masked else {}
    text = read_texts(doc)[1] if masked and suffix not in {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif", ".tif", ".tiff"} else None
    action = ("MASKED_" if masked else "ORIGINAL_") + ("DOWNLOAD" if disposition == "attachment" else "VIEW")
    # All ORM values needed below have been copied; release the read transaction
    # while rendering immutable original files or running privacy masking.
    db.rollback()
    if not masked:
        response = FileResponse(path, filename=name, content_disposition_type=disposition,
                                media_type=mimetypes.guess_type(name)[0] or "application/octet-stream", headers=PRIVATE_HEADERS)
        record_file_request(db, actor, action, contract_id, document_id)
        return response
    try:
        if suffix == ".pdf":
            from ..ai.visual_masking import render_masked_pdf_bytes
            from ..ai.pdf_runtime import open_pdf, page_count
            with open_pdf(path) as pdf:
                if page_count(pdf) > 50:
                    raise HTTPException(413, "마스킹 PDF 다운로드는 50페이지까지 지원합니다. 페이지 미리보기 또는 권한이 있는 원본 다운로드를 사용하세요.")
            content = render_masked_pdf_bytes(str(path), sensitive_dict=sensitive, scale=1.5)
            media, name = "application/pdf", "masked_" + name
        elif suffix in {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif", ".tif", ".tiff"}:
            from PIL import Image
            from ..ai.visual_masking import mask_image_with_ocr
            with Image.open(path) as original:
                image = original.convert("RGB")
            result = None
            try:
                result = mask_image_with_ocr(image, sensitive_dict=sensitive)
                buffer = io.BytesIO()
                result.save(buffer, format="PNG")
                content, media, name = buffer.getvalue(), "image/png", "masked_" + Path(name).stem + ".png"
            finally:
                image.close()
                if result is not None:
                    result.close()
        else:
            if not text:
                raise RuntimeError("No masked text")
            content, media, name = text.encode(), "text/plain; charset=utf-8", "masked_" + Path(name).stem + ".txt"
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, "마스킹 결과를 생성하지 못했습니다. 원본을 자동으로 대신 표시하지 않습니다.") from exc
    headers = {**PRIVATE_HEADERS, "Content-Disposition": disposition + "; filename*=UTF-8\'\'" + quote(name)}
    response = Response(content, media_type=media, headers=headers)
    record_file_request(db, actor, action, contract_id, document_id)
    return response


@router.get("/api/documents/{document_id}/file")
def get_document_file(document_id: int, masked: bool = True, db: Session = Depends(get_db),
                      actor: Actor = Depends(get_current_user)):
    return serve_document(document_id, masked, "inline", db, actor)


@router.get("/api/documents/{document_id}/download")
def download_document(document_id: int, masked: bool = False, db: Session = Depends(get_db),
                      actor: Actor = Depends(get_current_user)):
    return serve_document(document_id, masked, "attachment", db, actor)


@router.get("/api/documents/{document_id}/text-preview")
def get_text_preview(document_id: int, masked: bool = True, db: Session = Depends(get_db),
                     actor: Actor = Depends(get_current_user)):
    doc, _ = document_and_path(db, document_id)
    contract_id = doc.contract_id
    raw, protected = read_texts(doc)
    text = protected if masked else raw
    if not text:
        raise HTTPException(422, "추출 텍스트가 없습니다. 원본을 내려받아 확인하세요.")
    record_file_request(db, actor, "MASKED_TEXT_PREVIEW" if masked else "ORIGINAL_TEXT_PREVIEW", contract_id, document_id)
    return {"text": text}


@router.get("/api/documents/{document_id}/pages-info")
def get_document_pages_info(document_id: int, db: Session = Depends(get_db)):
    doc, path = document_and_path(db, document_id)
    name, count = doc.file_name, 1
    db.rollback()
    if path.suffix.lower() == ".pdf":
        try:
            from ..ai.pdf_runtime import open_pdf, page_count
            with open_pdf(path) as pdf:
                count = page_count(pdf)
        except Exception as exc:
            raise HTTPException(422, "PDF 페이지 정보를 읽지 못했습니다. 파일 손상 또는 암호 설정을 확인하세요.") from exc
    return {"total_pages": count, "file_available": True, "file_name": name}


@router.get("/api/documents/{document_id}/preview-image")
def get_document_preview_image(document_id: int, page: int = Query(0, ge=0), masked: bool = True,
                               db: Session = Depends(get_db), actor: Actor = Depends(get_current_user)):
    doc, path = document_and_path(db, document_id)
    contract_id = doc.contract_id
    sensitive = sensitive_values(doc) if masked else {}
    db.rollback()
    image = None
    try:
        from PIL import Image
        from ..ai.visual_masking import mask_pdf_page_image, mask_image_with_ocr
        if path.suffix.lower() == ".pdf":
            from ..ai.pdf_runtime import open_pdf, open_page, page_count, page_size, render_page_image
            with open_pdf(path) as pdf:
                if page >= page_count(pdf):
                    raise HTTPException(404, "해당 페이지가 없습니다.")
                with open_page(pdf, page) as pdf_page:
                    w, h = page_size(pdf_page)
                    scale = min(2.0, (16_000_000 / max(w * h, 1)) ** 0.5)
                    image = render_page_image(pdf_page, scale)
                    if masked:
                        protected = mask_pdf_page_image(pdf_page, image, scale=scale, sensitive_dict=sensitive)
                        image.close()
                        image = protected
        else:
            with Image.open(path) as original:
                image = original.convert("RGB")
            if masked:
                protected = mask_image_with_ocr(image, sensitive_dict=sensitive)
                image.close()
                image = protected
        output = io.BytesIO()
        image.save(output, format="PNG")
        content = output.getvalue()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, "미리보기를 생성하지 못했습니다. 마스킹에 실패하면 원본으로 대체하지 않습니다.") from exc
    finally:
        if image is not None:
            image.close()
    response = Response(content, media_type="image/png", headers=PRIVATE_HEADERS)
    record_file_request(db, actor, "MASKED_PREVIEW" if masked else "ORIGINAL_PREVIEW", contract_id, document_id, {"page": page + 1})
    return response
