import os
import io
import mimetypes
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..db.models import Document
from ..schemas.document import DocumentResponse
from ..services.contract_service import get_document_response
from ..services.pipeline_service import PipelineService

router = APIRouter(tags=["Documents"])
pipeline_service = PipelineService()


@router.post("/api/contracts/{contract_id}/documents", response_model=List[DocumentResponse])
def upload_contract_documents(
    contract_id: int,
    files: List[UploadFile] = File(...),
    target_document_type: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Batch upload contract evidence documents:
    - Stores raw files safely
    - Executes local privacy pre-processing & masking
    - Classifies into 6 core types
    - Extracts structured fields
    - Updates contract validation checks
    """
    results = []
    for file in files:
        content = file.file.read()
        try:
            doc_record = pipeline_service.process_document_upload(
                db=db,
                contract_id=contract_id,
                file_name=file.filename or "uploaded_file.txt",
                file_bytes=content,
                target_document_type=target_document_type or "",
            )
            results.append(get_document_response(doc_record))
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process {file.filename}: {str(e)}",
            )
    return results


@router.get("/api/documents/{document_id}", response_model=DocumentResponse)
def get_document(document_id: int, db: Session = Depends(get_db)):
    """Retrieve document metadata, masking status, extracted fields, and raw/masked text"""
    doc = db.query(Document).filter(Document.document_id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found",
        )
    return get_document_response(doc)


@router.delete("/api/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, db: Session = Depends(get_db)):
    """Delete a document and revalidate the contract"""
    doc = db.query(Document).filter(Document.document_id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found",
        )
    contract_id = doc.contract_id
    db.delete(doc)
    db.commit()

    pipeline_service.revalidate_contract(db, contract_id)
    return None


def resolve_document_path(storage_path: str) -> Optional[str]:
    """Resolve storage path with fallback to workspace storage directories"""
    if not storage_path:
        return None
    if os.path.exists(storage_path):
        return storage_path
    base_name = os.path.basename(storage_path)
    candidate_dirs = [
        os.path.join(os.getcwd(), "storage", "raw"),
        os.path.join(os.getcwd(), "storage"),
        "c:/project/storage/raw",
        "c:/project/storage",
        "c:/project/sample-data",
    ]
    for d in candidate_dirs:
        p = os.path.join(d, base_name)
        if os.path.exists(p):
            return p
    return None


def _extract_sensitive_dict(doc: Document) -> dict:
    """Extracts known sensitive information terms for visual masking."""
    import json
    sensitive: dict = {}
    if doc.contract:
        if doc.contract.vendor_name:
            sensitive["vendor_name"] = doc.contract.vendor_name
        if doc.contract.business_number:
            sensitive["business_number"] = doc.contract.business_number
    if doc.extract:
        if doc.extract.extracted_vendor_name:
            sensitive["extracted_vendor_name"] = doc.extract.extracted_vendor_name
        if doc.extract.extracted_vendor_reg_no:
            sensitive["extracted_vendor_reg_no"] = doc.extract.extracted_vendor_reg_no
        if doc.extract.raw_fields:
            try:
                rf = json.loads(doc.extract.raw_fields)
                if isinstance(rf, dict):
                    for k, v in rf.items():
                        if v is not None and isinstance(v, (str, int, float)):
                            sensitive[k] = str(v)
            except Exception:
                pass
    return sensitive


@router.get("/api/documents/{document_id}/file")
def get_document_file(document_id: int, masked: bool = False, db: Session = Depends(get_db)):
    """Serve the original or visually masked file inline for browser viewing."""
    doc = db.query(Document).filter(Document.document_id == document_id).first()
    resolved_path = resolve_document_path(doc.storage_path) if doc else None
    if not doc or not resolved_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document file with ID {document_id} not found",
        )

    lower_p = resolved_path.lower()
    sensitive_dict = _extract_sensitive_dict(doc) if masked else {}

    # If visual masking is requested on PDF or Image
    if masked:
        if lower_p.endswith(".pdf"):
            try:
                from backend.app.ai.visual_masking import render_masked_pdf_bytes
                pdf_bytes = render_masked_pdf_bytes(resolved_path, sensitive_dict=sensitive_dict, scale=2)
                return Response(
                    content=pdf_bytes,
                    media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="masked_{doc.file_name}"'},
                )
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"[get_document_file] Masking error: {e}")
        elif any(lower_p.endswith(im_ext) for im_ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff"]):
            try:
                from PIL import Image
                from backend.app.ai.visual_masking import mask_image_with_ocr
                pil_image = Image.open(resolved_path).convert("RGB")
                masked_image = mask_image_with_ocr(pil_image, sensitive_dict=sensitive_dict)
                buf = io.BytesIO()
                masked_image.save(buf, format="PNG")
                return Response(
                    content=buf.getvalue(),
                    media_type="image/png",
                    headers={"Content-Disposition": f'inline; filename="masked_{doc.file_name}"'},
                )
            except Exception:
                pass

    media_type, _ = mimetypes.guess_type(resolved_path)
    if lower_p.endswith(".pdf"):
        media_type = "application/pdf"
    elif lower_p.endswith(".docx"):
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif lower_p.endswith(".doc"):
        media_type = "application/msword"
    elif lower_p.endswith(".xlsx"):
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif lower_p.endswith(".xls"):
        media_type = "application/vnd.ms-excel"
    elif lower_p.endswith(".csv"):
        media_type = "text/csv; charset=utf-8"
    elif lower_p.endswith(".hwp"):
        media_type = "application/x-hwp"
    elif lower_p.endswith(".hwpx"):
        media_type = "application/hwp+zip"

    return FileResponse(
        resolved_path,
        media_type=media_type or "application/octet-stream",
        filename=doc.file_name,
        content_disposition_type="inline",
    )


@router.get("/api/documents/{document_id}/pages-info")
def get_document_pages_info(document_id: int, db: Session = Depends(get_db)):
    """Get page count and file type info for all document types (PDF, Image, Word, Hancom, Excel, Text)"""
    doc = db.query(Document).filter(Document.document_id == document_id).first()
    resolved_path = resolve_document_path(doc.storage_path) if doc else None
    if not doc or not resolved_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document file with ID {document_id} not found",
        )
    
    ext = os.path.splitext(resolved_path)[1].lower()
    is_pdf = ext == ".pdf"
    is_image = ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".tif"]
    is_word = ext in [".docx", ".doc"]
    is_hwp = ext in [".hwp", ".hwpx"]
    is_excel = ext in [".xlsx", ".xlsm", ".xls", ".csv"]
    is_text = ext in [".txt", ".json", ".md"]
    total_pages = 1

    if is_pdf:
        try:
            import pypdfium2 as pdfium
            pdf = pdfium.PdfDocument(resolved_path)
            total_pages = len(pdf)
        except Exception:
            total_pages = 1

    format_category = "other"
    if is_pdf:
        format_category = "pdf"
    elif is_image:
        format_category = "image"
    elif is_word:
        format_category = "word"
    elif is_hwp:
        format_category = "hwp"
    elif is_excel:
        format_category = "excel"
    elif is_text:
        format_category = "text"

    return {
        "document_id": document_id,
        "is_pdf": is_pdf,
        "is_image": is_image,
        "is_word": is_word,
        "is_hwp": is_hwp,
        "is_excel": is_excel,
        "is_text": is_text,
        "format_category": format_category,
        "extension": ext.replace(".", "").upper(),
        "total_pages": total_pages,
        "file_name": doc.file_name,
    }


@router.get("/api/documents/{document_id}/preview-image")
def get_document_preview_image(document_id: int, page: int = 0, masked: bool = False, db: Session = Depends(get_db)):
    """
    Render a PDF page or return an image file as a high-resolution PNG image.
    When masked=True, automatically detects and applies visual redaction badges to sensitive personal/business information.
    """
    doc = db.query(Document).filter(Document.document_id == document_id).first()
    resolved_path = resolve_document_path(doc.storage_path) if doc else None
    if not doc or not resolved_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document file with ID {document_id} not found",
        )
    
    ext = os.path.splitext(resolved_path)[1].lower()
    is_image = ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".tif"]
    sensitive_dict = _extract_sensitive_dict(doc) if masked else {}

    if is_image:
        if masked:
            try:
                from PIL import Image
                from backend.app.ai.visual_masking import mask_image_with_ocr
                pil_image = Image.open(resolved_path).convert("RGB")
                masked_img = mask_image_with_ocr(pil_image, sensitive_dict=sensitive_dict)
                buf = io.BytesIO()
                masked_img.save(buf, format="PNG")
                return Response(content=buf.getvalue(), media_type="image/png")
            except Exception:
                pass
        media_type, _ = mimetypes.guess_type(resolved_path)
        return FileResponse(
            resolved_path,
            media_type=media_type or "image/png",
            content_disposition_type="inline",
        )
    
    if ext == ".pdf":
        try:
            import pypdfium2 as pdfium
            pdf = pdfium.PdfDocument(resolved_path)
            total_pages = len(pdf)
            if page < 0 or page >= total_pages:
                page = 0
            page_obj = pdf[page]
            pil_image = page_obj.render(scale=2).to_pil()
            if masked:
                from backend.app.ai.visual_masking import mask_pdf_page_image
                pil_image = mask_pdf_page_image(page_obj, pil_image, scale=2, sensitive_dict=sensitive_dict)
            buf = io.BytesIO()
            pil_image.save(buf, format="PNG")
            return Response(content=buf.getvalue(), media_type="image/png")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to render PDF page as image: {str(e)}",
            )
    
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Preview image not supported for extension '{ext}'",
    )


