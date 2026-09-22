from typing import List
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..db.models import Document
from ..schemas.document import DocumentResponse
from ..services.contract_service import get_document_response
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
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
