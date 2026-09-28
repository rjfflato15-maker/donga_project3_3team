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
async def upload_contract_documents(
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
        content = await file.read()
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


@router.get("/api/documents/{document_id}/file")
def get_document_file(document_id: int, db: Session = Depends(get_db)):
    """Serve the original file (e.g. for image or PDF preview) inline for browser viewing"""
    doc = db.query(Document).filter(Document.document_id == document_id).first()
    resolved_path = resolve_document_path(doc.storage_path) if doc else None
    if not doc or not resolved_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document file with ID {document_id} not found",
        )
    media_type, _ = mimetypes.guess_type(resolved_path)
    if resolved_path.lower().endswith(".pdf"):
        media_type = "application/pdf"

    return FileResponse(
        resolved_path,
        media_type=media_type or "application/octet-stream",
        filename=doc.file_name,
        content_disposition_type="inline",
    )


@router.get("/api/documents/{document_id}/pages-info")
def get_document_pages_info(document_id: int, db: Session = Depends(get_db)):
    """Get page count and file type info for PDF / Image documents"""
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
    total_pages = 1

    if is_pdf:
        try:
            import pypdfium2 as pdfium
            pdf = pdfium.PdfDocument(resolved_path)
            total_pages = len(pdf)
        except Exception:
            total_pages = 1

    return {
        "document_id": document_id,
        "is_pdf": is_pdf,
        "is_image": is_image,
        "total_pages": total_pages,
        "file_name": doc.file_name,
    }


@router.get("/api/documents/{document_id}/preview-image")
def get_document_preview_image(document_id: int, page: int = 0, db: Session = Depends(get_db)):
    """
    Render a PDF page or return an image file as a high-resolution PNG image.
    Allows PDF documents to be viewed directly as crisp images just like PNG/JPG files.
    """
    doc = db.query(Document).filter(Document.document_id == document_id).first()
    resolved_path = resolve_document_path(doc.storage_path) if doc else None
    if not doc or not resolved_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document file with ID {document_id} not found",
        )
    
    ext = os.path.splitext(resolved_path)[1].lower()
    if ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".tif"]:
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
            pil_image = pdf[page].render(scale=2).to_pil()
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


