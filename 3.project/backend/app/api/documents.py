import hashlib
import io
import json
import mimetypes
from pathlib import Path
from urllib.parse import quote
from typing import List, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..db.models import Document, DocumentFileInfo, ValidationResult
from ..schemas.document import DocumentResponse, AnalysisFields, Correction
from ..schemas.common import DocumentType
from ..services.contract_service import get_document_response
from ..services.document_correction_service import apply_correction, pipeline_service
from ..services.storage_service import read_upload, resolve_path, STORAGE_LOCK, read_texts
from ..services.workflow_service import audit, touch_contract, policy_for
from ..services.document_version_service import require_current, version_history, compare_versions
from ..services.preview_image_cache import cached_preview, invalidate_preview
from ..security import Actor, get_current_user, require_operator

router = APIRouter(tags=["Documents"])
PRIVATE_HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}


def document_and_path(db, document_id):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, "문서를 찾을 수 없습니다.")
    path = resolve_path(doc.storage_path)
    if not path:
        raise HTTPException(404, "공용 서버에 원본 파일이 없습니다. 담당자가 원본을 다시 등록해야 합니다.")
    return doc, path


def sensitive_values(doc, db=None):
    from ..services.preview_masking_service import document_sensitive_values
    return document_sensitive_values(doc, db)


@router.post("/api/contracts/{contract_id}/documents", response_model=List[DocumentResponse])
def upload_contract_documents(contract_id: int, files: List[UploadFile] = File(...),
                              target_document_type: Optional[str] = Form(None), upload_mode: str = Form('ADD'),
                              replaces_document_id: Optional[int] = Form(None), revision: Optional[int] = Form(None),
                              change_note: str = Form(''), db: Session = Depends(get_db),
                              actor: Actor = Depends(require_operator)):
    if upload_mode not in {'ADD', 'REISSUE'}:
        raise HTTPException(400,'upload_mode는 ADD 또는 REISSUE입니다.')
    if upload_mode == 'REISSUE' and (len(files) != 1 or replaces_document_id is None or revision is None or not change_note.strip()):
        raise HTTPException(400,'재발행은 파일 1개·이전 문서 ID·revision·변경 사유가 필요합니다.')
    if upload_mode == 'ADD' and replaces_document_id is not None:
        raise HTTPException(400,'문서 교체에는 REISSUE를 명시하세요.')
    if revision is not None and len(files) != 1:
        raise HTTPException(400,'revision을 검사하는 등록은 파일 1개씩 요청하세요.')
    if len(change_note) > 2000:
        raise HTTPException(400,'변경 사유는 2000자 이하로 입력하세요.')
    if not 1 <= len(files) <= 20:
        raise HTTPException(400, "한 번에 1~20개 파일을 등록하세요.")
    if target_document_type and target_document_type not in [t.value for t in DocumentType]:
        raise HTTPException(400, "문서 유형을 확인하세요.")
    contents = [(file, read_upload(file)) for file in files]
    result = []
    for file, content in contents:
        try:
            doc = pipeline_service.process_document_upload(db, contract_id, file.filename, content, target_document_type or "",
                replaces_document_id=replaces_document_id, expected_contract_revision=revision, change_note=change_note,actor=actor)
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


@router.get('/api/documents/{document_id}/versions')
def get_versions(document_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document,document_id)
    if not doc:
        raise HTTPException(404,'문서를 찾을 수 없습니다.')
    return {'contract_id':doc.contract_id,'revision':policy_for(db,doc.contract_id)['revision'], 'versions':version_history(db,doc)}


@router.get('/api/documents/{document_id}/compare')
def get_version_comparison(document_id: int, previous_document_id: Optional[int] = None, db: Session = Depends(get_db)):
    doc=db.get(Document,document_id)
    if not doc:
        raise HTTPException(404,'문서를 찾을 수 없습니다.')
    return {'contract_id':doc.contract_id,'revision':policy_for(db,doc.contract_id)['revision'],**compare_versions(db,doc,previous_document_id)}


@router.delete("/api/documents/{document_id}", status_code=204)
def delete_document(document_id: int, db: Session = Depends(get_db), actor: Actor = Depends(require_operator)):
    with STORAGE_LOCK:
        doc = db.get(Document, document_id)
        if not doc:
            raise HTTPException(404, "문서를 찾을 수 없습니다.")
        if doc.version:
            from ..db.models import DocumentVersion
            if db.query(DocumentVersion).filter_by(logical_document_id=doc.version.logical_document_id).count() > 1:
                raise HTTPException(409,'재발행 이력이 있는 문서는 삭제할 수 없습니다. 버전 이력을 보관합니다.')
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
    require_current(doc)
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


@router.put("/api/documents/{document_id}/fields", response_model=DocumentResponse)
def correct_fields(document_id: int, req: Correction, db: Session = Depends(get_db),
                   actor: Actor = Depends(require_operator)):
    return apply_correction(document_id, req, db, actor)


class FieldConfirmation(BaseModel):
    field: str
    revision: int = Field(ge=1)


class UndoFieldConfirmation(FieldConfirmation):
    confirmed_at: str


class FieldDeferral(FieldConfirmation):
    note: str = Field(min_length=1, max_length=1000)
    kind: Literal['DEFER', 'NO_ISSUE'] = 'DEFER'


class ClearFieldDeferral(FieldConfirmation):
    deferred_at: str


@router.post('/api/documents/{document_id}/defer-field')
def defer_field(document_id: int, req: FieldDeferral, db: Session = Depends(get_db),
                actor: Actor = Depends(require_operator)):
    from ..services.field_deferral_service import DOCUMENT_SCOPE, current_deferrals, deferral_details
    with STORAGE_LOCK:
        doc = db.get(Document, document_id)
        if not doc:
            raise HTTPException(404, '문서를 찾을 수 없습니다.')
        require_current(doc)
        if req.revision != policy_for(db, doc.contract_id)['revision']:
            raise HTTPException(409, '자료가 변경되었습니다. 최신 항목을 다시 확인하세요.')
        if req.field not in AnalysisFields.model_fields and req.field != DOCUMENT_SCOPE:
            raise HTTPException(422, '보류할 항목이 올바르지 않습니다.')
        if not req.note.strip():
            raise HTTPException(422, '문제가 아니라고 판단한 이유를 입력하세요.' if req.kind == 'NO_ISSUE' else '다음에 확인할 내용을 입력하세요.')
        audit(db, actor, 'FIELD_DEFERRED', doc.contract_id, document_id,
            deferral_details(db, doc, req.field, req.note.strip(), req.kind))
        stored = json.loads(doc.extract.raw_fields or '{}') if doc.extract else {}
        return {'field': req.field, 'deferral': current_deferrals(db, document_id, stored)[req.field]}


@router.post('/api/documents/{document_id}/clear-field-deferral')
def clear_field_deferral(document_id: int, req: ClearFieldDeferral, db: Session = Depends(get_db),
                         actor: Actor = Depends(require_operator)):
    from ..services.field_deferral_service import current_deferrals
    with STORAGE_LOCK:
        doc = db.get(Document, document_id)
        if not doc:
            raise HTTPException(404, '문서를 찾을 수 없습니다.')
        require_current(doc)
        if req.revision != policy_for(db, doc.contract_id)['revision']:
            raise HTTPException(409, '자료가 변경되었습니다. 최신 보류 기록을 확인하세요.')
        stored = json.loads(doc.extract.raw_fields or '{}') if doc.extract else {}
        pending = current_deferrals(db, document_id, stored).get(req.field)
        if not pending or pending['at'] != req.deferred_at:
            raise HTTPException(409, '보류 기록이 변경되었습니다. 최신 기록을 확인하세요.')
        audit(db, actor, 'FIELD_DEFERRAL_CLEARED', doc.contract_id, document_id,
            {'field': req.field, 'deferral': pending})
        return {'field': req.field, 'deferral': None}


@router.post('/api/documents/{document_id}/confirm-field')
def confirm_field(document_id: int, req: FieldConfirmation, db: Session = Depends(get_db),
                  actor: Actor = Depends(require_operator)):
    """A single explicit button press attests to this field, never other fields."""
    from ..services.field_confirmation_service import current_confirmations
    with STORAGE_LOCK:
        doc = db.get(Document, document_id)
        if not doc or not doc.extract:
            raise HTTPException(404, '추출 결과를 찾을 수 없습니다.')
        require_current(doc)
        if req.revision != policy_for(db, doc.contract_id)['revision']:
            raise HTTPException(409, '자료가 변경되었습니다. 현재 원문을 다시 확인하세요.')
        stored = json.loads(doc.extract.raw_fields or '{}')
        values = AnalysisFields(**stored).model_dump()
        if req.field not in values or values[req.field] in (None, '', 'UNKNOWN'):
            raise HTTPException(422, '읽은 값이 있는 항목만 원문 확인할 수 있습니다.')
        if req.field in current_confirmations(db, document_id, stored):
            raise HTTPException(409, '이미 원문 확인한 항목입니다. 최신 기록을 불러오세요.')
        if not resolve_path(doc.storage_path):
            raise HTTPException(409, '원본 파일이 없어 원문 확인할 수 없습니다.')
        apply_correction(document_id, Correction(fields=AnalysisFields(), document_type=doc.document_type,
            revision=req.revision, note=f'원문과 같은 {req.field} 확인', confirmed_fields=[req.field]), db, actor)
        proof = json.loads(doc.extract.raw_fields)['human_review']['field_confirmations'][req.field]
        return {'field': req.field, 'revision': policy_for(db, doc.contract_id)['revision'], 'confirmed_at': proof['at']}


@router.post('/api/documents/{document_id}/undo-field-confirmation')
def undo_field_confirmation(document_id: int, req: UndoFieldConfirmation, db: Session = Depends(get_db),
                            actor: Actor = Depends(require_operator)):
    """Undo only this actor's recent, unchanged explicit confirmation; keep values/history."""
    from ..services.field_confirmation_service import current_confirmations, reviewed_ai
    with STORAGE_LOCK:
        db.expire_all()
        doc = db.get(Document, document_id)
        if not doc or not doc.extract:
            raise HTTPException(404, '추출 결과를 찾을 수 없습니다.')
        require_current(doc)
        if req.revision != policy_for(db, doc.contract_id)['revision']:
            raise HTTPException(409, '자료가 변경되어 이 확인을 되돌릴 수 없습니다. 최신 기록을 확인하세요.')
        stored = json.loads(doc.extract.raw_fields or '{}')
        proofs = current_confirmations(db, document_id, stored)
        proof = proofs.get(req.field)
        if not proof or proof.get('actor_id') != actor.user_id or proof.get('at') != req.confirmed_at or proof.get('method') != 'EXPLICIT_CONFIRMATION':
            raise HTTPException(409, '방금 본인이 기록한 원문 확인만 되돌릴 수 있습니다.')
        try:
            at = datetime.fromisoformat(proof['at'])
            age = (datetime.now(timezone.utc) - at).total_seconds()
        except (ValueError, TypeError):
            age = 61
        if not 0 <= age <= 60:
            raise HTTPException(409, '확인 되돌리기 시간이 지났습니다.')
        del proofs[req.field]
        stored['human_review'] = {'field_confirmations': proofs, 'confirmed_fields': sorted(proofs)}
        if stored.get('ai_review'):
            stored['ai_review'] = reviewed_ai(stored['ai_review'], proofs)
        doc.extract.raw_fields = json.dumps(stored, ensure_ascii=False)
        # Do not rewind revisions or restore an earlier approval after an undo.
        touch_contract(db, doc.contract_id)
        contract_id = doc.contract_id
        audit(db, actor, 'FIELD_CONFIRMATION_UNDONE', contract_id, document_id,
            {'field': req.field, 'confirmation': proof, 'revision': policy_for(db, contract_id)['revision']})
    pipeline_service.revalidate_contract(db, contract_id)
    return {'field': req.field, 'revision': policy_for(db, contract_id)['revision']}


def record_file_request(db, actor, action, contract_id, document_id, details=None):
    # Record only after preparing a response. This is still a request record,
    # not proof that the browser received every byte of a streamed response.
    # Rendering/OCR finishes before taking this short publication lock.
    with STORAGE_LOCK:
        audit(db, actor, action + "_REQUEST", contract_id, document_id, details)


def serve_document(document_id, masked, disposition, db, actor):
    doc, path = document_and_path(db, document_id)
    suffix, name, contract_id = path.suffix.lower(), doc.file_name, doc.contract_id
    sensitive = sensitive_values(doc, db) if masked else {}
    texts = read_texts(doc) if masked and suffix not in {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif", ".tif", ".tiff"} else None
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
            media, name = "application/pdf", f"masked_document_{document_id}.pdf"
        elif suffix in {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif", ".tif", ".tiff"}:
            from PIL import Image, ImageOps
            from ..services.preview_masking_service import mask_image_with_ocr
            with Image.open(path) as original:
                image = ImageOps.exif_transpose(original).convert("RGB")
            result = None
            try:
                result = mask_image_with_ocr(image, sensitive_dict=sensitive)
                buffer = io.BytesIO()
                result.save(buffer, format="PNG")
                content, media, name = buffer.getvalue(), "image/png", f"masked_document_{document_id}.png"
            finally:
                image.close()
                if result is not None:
                    result.close()
        else:
            from ..services.preview_masking_service import mask_export_text
            text = mask_export_text(texts[0] or texts[1], sensitive) if texts else ""
            if not text:
                raise RuntimeError("No masked text")
            content, media, name = text.encode(), "text/plain; charset=utf-8", f"masked_document_{document_id}.txt"
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
    if masked:
        from ..services.preview_masking_service import mask_export_text
        try:
            # Use the same known-value policy as images/PDFs and contract ZIPs.
            # A generic regex-only sidecar is not an equivalent protected view.
            text = mask_export_text(raw or protected, sensitive_values(doc, db))
        except Exception as exc:
            raise HTTPException(503, "마스킹 결과를 생성하지 못했습니다. 원본을 자동으로 대신 표시하지 않습니다.") from exc
    else:
        text = raw
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
                               revision: Optional[int] = Query(None, ge=1), source_sha256: Optional[str] = None,
                               db: Session = Depends(get_db), actor: Actor = Depends(get_current_user)):
    doc, path = document_and_path(db, document_id)
    contract_id = doc.contract_id
    live_revision = policy_for(db, contract_id)['revision']
    if revision is not None and revision != live_revision:
        raise HTTPException(409, "계약 자료가 변경되었습니다. 근거와 미리보기를 새로 불러오세요.")
    if source_sha256 is not None:
        info = db.get(DocumentFileInfo, document_id)
        if not info or info.sha256 != source_sha256:
            raise HTTPException(409, "원본 버전이 다릅니다. 근거와 미리보기를 새로 불러오세요.")
    sensitive = sensitive_values(doc, db) if masked else {}
    db.rollback()
    try:
        with path.open('rb') as stream:
            actual_sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    except OSError as exc:
        raise HTTPException(409, "원본을 읽을 수 없습니다. 최신 자료를 다시 불러오세요.") from exc
    if source_sha256 is not None and actual_sha != source_sha256:
        raise HTTPException(409, "원본 내용이 변경되었습니다. 근거를 다시 확인하세요.")
    cache_key = (str(path.resolve()), actual_sha, live_revision, page, masked,
                 json.dumps(sensitive, sort_keys=True, ensure_ascii=False))

    def render():
        image = None
        try:
            from PIL import Image, ImageOps
            from ..ai.visual_masking import mask_pdf_page_image
            from ..services.preview_masking_service import mask_image_with_ocr
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
                    image = ImageOps.exif_transpose(original).convert("RGB")
                if masked:
                    protected = mask_image_with_ocr(image, sensitive_dict=sensitive)
                    image.close()
                    image = protected
            output = io.BytesIO()
            image.save(output, format="PNG")
            return output.getvalue()
        finally:
            if image is not None:
                image.close()
    try:
        content = cached_preview(cache_key, render)
        with path.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != actual_sha:
                invalidate_preview(cache_key)
                raise HTTPException(409, "미리보기 생성 중 원본이 변경되었습니다. 다시 불러오세요.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, "미리보기를 생성하지 못했습니다. 마스킹에 실패하면 원본으로 대체하지 않습니다.") from exc
    response = Response(content, media_type="image/png", headers=PRIVATE_HEADERS)
    with STORAGE_LOCK:
        db.expire_all()
        if live_revision != policy_for(db, contract_id)['revision']:
            invalidate_preview(cache_key)
            raise HTTPException(409, "미리보기 생성 중 계약 자료가 변경되었습니다. 새로 불러오세요.")
        record_file_request(db, actor, "MASKED_PREVIEW" if masked else "ORIGINAL_PREVIEW", contract_id, document_id, {"page": page + 1})
    return response
