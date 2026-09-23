import os
import tempfile
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..schemas.contract import (
    AutoContractSynthesisResponse,
    AutoContractParseItem,
    ContractDetailResponse,
    ContractCreate,
)
from ..schemas.common import DocumentType
from ..ai import analyze_document
from ..services.contract_service import ContractService
from ..services.pipeline_service import PipelineService

router = APIRouter(prefix="/api/contracts", tags=["AutoContract"])
contract_service = ContractService()
pipeline_service = PipelineService()


def synthesize_extracted_fields(items: List[AutoContractParseItem]) -> AutoContractSynthesisResponse:
    """
    Synthesizes extracted information across 6 core document types to determine the optimal:
    - title
    - vendor_name
    - business_number
    - contract_amount
    - issue_date
    """
    title: Optional[str] = None
    vendor_name: Optional[str] = None
    business_number: Optional[str] = None
    contract_amount: Optional[float] = None
    issue_date: Optional[str] = None

    # Priority maps for each field based on document reliability
    # 1. Title priority: CONTRACT > ESTIMATE > TAX_INVOICE > others
    title_priority = [DocumentType.CONTRACT.value, DocumentType.ESTIMATE.value, DocumentType.TAX_INVOICE.value]
    for doc_type in title_priority:
        for item in items:
            if item.document_type == doc_type and item.title:
                title = item.title
                break
        if title:
            break
    if not title:
        for item in items:
            if item.title:
                title = item.title
                break

    if not title and items:
        # Fallback based on first file name
        base_name = os.path.splitext(items[0].file_name)[0]
        clean_base = base_name.replace("_", " ").replace("-", " ").strip()
        title = f"{clean_base} 외주 계약" if clean_base else "AI 자동 생성 계약"

    # 2. Vendor Name priority: BUSINESS_REGISTRATION > TAX_INVOICE > BANK_ACCOUNT > CONTRACT > others
    vendor_priority = [
        DocumentType.BUSINESS_REGISTRATION.value,
        DocumentType.TAX_INVOICE.value,
        DocumentType.BANK_ACCOUNT.value,
        DocumentType.CONTRACT.value,
    ]
    for doc_type in vendor_priority:
        for item in items:
            if item.document_type == doc_type and item.company_name:
                vendor_name = item.company_name
                break
        if vendor_name:
            break
    if not vendor_name:
        for item in items:
            if item.company_name:
                vendor_name = item.company_name
                break
    if not vendor_name:
        vendor_name = "(주)미지정 거래처"

    # 3. Business Number priority: BUSINESS_REGISTRATION > TAX_INVOICE > BANK_ACCOUNT > CONTRACT > others
    biz_priority = [
        DocumentType.BUSINESS_REGISTRATION.value,
        DocumentType.TAX_INVOICE.value,
        DocumentType.BANK_ACCOUNT.value,
        DocumentType.CONTRACT.value,
    ]
    for doc_type in biz_priority:
        for item in items:
            if item.document_type == doc_type and item.business_registration_no:
                business_number = item.business_registration_no
                break
        if business_number:
            break
    if not business_number:
        for item in items:
            if item.business_registration_no:
                business_number = item.business_registration_no
                break
    if not business_number:
        business_number = "123-45-67890"

    # 4. Contract Amount priority: CONTRACT > TAX_INVOICE > ESTIMATE > others (or max plausible amount)
    amount_priority = [
        DocumentType.CONTRACT.value,
        DocumentType.TAX_INVOICE.value,
        DocumentType.ESTIMATE.value,
    ]
    for doc_type in amount_priority:
        for item in items:
            if item.document_type == doc_type and item.amount and item.amount > 0:
                contract_amount = item.amount
                break
        if contract_amount is not None:
            break

    if contract_amount is None:
        amounts = [item.amount for item in items if item.amount and item.amount > 0]
        if amounts:
            contract_amount = max(amounts)
        else:
            contract_amount = 10000000.0  # Default fallback amount

    # 5. Date priority: CONTRACT > TAX_INVOICE > ESTIMATE > INSPECTION_CONFIRMATION > others
    date_priority = [
        DocumentType.CONTRACT.value,
        DocumentType.TAX_INVOICE.value,
        DocumentType.ESTIMATE.value,
        DocumentType.INSPECTION_CONFIRMATION.value,
    ]
    for doc_type in date_priority:
        for item in items:
            if item.document_type == doc_type and item.issue_date:
                issue_date = item.issue_date
                break
        if issue_date:
            break
    if not issue_date:
        for item in items:
            if item.issue_date:
                issue_date = item.issue_date
                break
    if not issue_date:
        issue_date = datetime.now().strftime("%Y-%m-%d")

    return AutoContractSynthesisResponse(
        title=title,
        vendor_name=vendor_name,
        business_number=business_number,
        contract_amount=contract_amount,
        issue_date=issue_date,
        documents=items,
    )


@router.post("/auto-parse-batch", response_model=AutoContractSynthesisResponse)
async def auto_parse_batch_documents(files: List[UploadFile] = File(...)):
    """
    Parses multiple evidence documents (up to 6 core types), classifies them,
    extracts key metadata, and synthesizes title, amount, business number, vendor, and date.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one document file must be uploaded",
        )

    parsed_items: List[AutoContractParseItem] = []
    temp_dir = tempfile.gettempdir()

    for file in files:
        temp_path = os.path.join(temp_dir, f"auto_parse_{int(datetime.utcnow().timestamp())}_{file.filename}")
        try:
            content = await file.read()
            with open(temp_path, "wb") as f:
                f.write(content)

            analysis_res, _, _ = analyze_document(temp_path, file_name=file.filename)
            parsed_items.append(
                AutoContractParseItem(
                    file_name=file.filename,
                    document_type=analysis_res.document_type.value,
                    confidence=analysis_res.confidence,
                    title=analysis_res.fields.title,
                    company_name=analysis_res.fields.company_name,
                    business_registration_no=analysis_res.fields.business_registration_no,
                    amount=analysis_res.fields.amount,
                    issue_date=analysis_res.fields.issue_date,
                )
            )
        except Exception as e:
            # Fallback for failed parse
            parsed_items.append(
                AutoContractParseItem(
                    file_name=file.filename,
                    document_type=DocumentType.UNKNOWN.value,
                    confidence=0.5,
                )
            )
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    return synthesize_extracted_fields(parsed_items)


@router.post("/auto-create-batch", response_model=ContractDetailResponse, status_code=status.HTTP_201_CREATED)
async def auto_create_batch_contract(
    title: str = Form(...),
    vendor_name: str = Form(...),
    business_number: str = Form(...),
    contract_amount: float = Form(...),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """
    Creates a new contract record using synthesized/user-confirmed metadata,
    and automatically uploads, masks, classifies, and validates all attached evidence documents.
    """
    # 1. Create Contract
    contract_data = ContractCreate(
        title=title,
        vendor_name=vendor_name,
        business_number=business_number,
        contract_amount=contract_amount,
    )
    contract = contract_service.create_contract(db, contract_data)

    # 2. Upload and process all evidence documents
    for file in files:
        content = await file.read()
        try:
            pipeline_service.process_document_upload(
                db=db,
                contract_id=contract.contract_id,
                file_name=file.filename,
                file_bytes=content,
            )
        except Exception as e:
            print(f"Warning: Error processing uploaded document {file.filename}: {e}")

    # 3. Return full contract detail with evidence validation
    detail = contract_service.get_contract_detail(db, contract.contract_id)
    return detail
