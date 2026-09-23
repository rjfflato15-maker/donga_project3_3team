import os
import tempfile
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..schemas.contract import (
    ContractCreate,
    ContractUpdate,
    ContractListItem,
    ContractDetailResponse,
    ParsedContractResponse,
)
from ..services.contract_service import ContractService
from ..ai.preprocessor import extract_text_from_file
from ..ai.extractor import extract_fields
from ..ai.classifier import classify_document

router = APIRouter(prefix="/api/contracts", tags=["Contracts"])
contract_service = ContractService()


@router.post("/parse-file", response_model=ParsedContractResponse)
async def parse_contract_file(file: UploadFile = File(...)):
    """Parse contract PDF/text/image file and auto-extract title, vendor, business number, amount, date"""
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, file.filename)

    try:
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)

        raw_text, _ = extract_text_from_file(temp_path, file.filename)
        fields = extract_fields(raw_text)
        doc_type, confidence = classify_document(raw_text, file.filename)

        title = fields.title
        if not title:
            base_name = os.path.splitext(file.filename)[0]
            base_name = base_name.replace("_", " ").replace("-", " ").strip()
            title = base_name if base_name else "신규 계약"

        return ParsedContractResponse(
            title=title,
            vendor_name=fields.company_name,
            business_number=fields.business_registration_no,
            contract_amount=fields.amount,
            issue_date=fields.issue_date,
            document_type=doc_type.value,
            raw_text_snippet=raw_text[:500] if raw_text else "",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse contract file: {str(e)}",
        )
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass



@router.get("", response_model=List[ContractListItem])
def list_contracts(db: Session = Depends(get_db)):
    """List all registered contracts with evidence summary"""
    return contract_service.list_contracts(db)


@router.post("", response_model=ContractDetailResponse, status_code=status.HTTP_201_CREATED)
def create_contract(req: ContractCreate, db: Session = Depends(get_db)):
    """Register a new contract and initialize verification checklist"""
    contract = contract_service.create_contract(db, req)
    detail = contract_service.get_contract_detail(db, contract.contract_id)
    return detail


@router.get("/{contract_id}", response_model=ContractDetailResponse)
def get_contract(contract_id: int, db: Session = Depends(get_db)):
    """Get contract details, submitted documents, and validation results"""
    detail = contract_service.get_contract_detail(db, contract_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with ID {contract_id} not found",
        )
    return detail


@router.put("/{contract_id}", response_model=ContractDetailResponse)
def update_contract(contract_id: int, req: ContractUpdate, db: Session = Depends(get_db)):
    """Update contract information and re-evaluate validation rules"""
    detail = contract_service.update_contract(db, contract_id, req)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with ID {contract_id} not found",
        )
    return detail


@router.delete("/{contract_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contract(contract_id: int, db: Session = Depends(get_db)):
    """Delete a contract and clean up all associated documents and validation records"""
    success = contract_service.delete_contract(db, contract_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with ID {contract_id} not found",
        )
    return None


@router.post("/seed-demo", response_model=ContractDetailResponse)
def seed_demo_contract(db: Session = Depends(get_db)):
    """Seeds or resets the demo contract matching the presentation slides"""
    contract = contract_service.seed_demo_contract(db)
    return contract_service.get_contract_detail(db, contract.contract_id)


