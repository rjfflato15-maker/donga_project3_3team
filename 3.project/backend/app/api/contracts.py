import os
import tempfile
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..schemas.contract import (
    ContractCreate,
    ContractUpdate,
    ParsedContractResponse,
)
from ..services.contract_service import ContractService
from ..services.review_summary_service import ContractDashboardListItem
from ..services.payment_service import OperationalContractDetailResponse as ContractDetailResponse
from ..ai.preprocessor import extract_text_from_file
from ..ai.extractor import extract_fields
from ..ai.classifier import classify_document
from ..security import Actor, get_current_user
from ..services.workflow_service import audit
from ..services.storage_service import read_upload, clean_name
from ..config import IS_PILOT
from ..db.models import Contract, ContractExclusion
from pydantic import BaseModel, Field
from ..services.storage_service import STORAGE_LOCK

router = APIRouter(prefix="/api/contracts", tags=["Contracts"])
contract_service = ContractService()


@router.post("/parse-file", response_model=ParsedContractResponse)
def parse_contract_file(file: UploadFile = File(...)):
    """Parse contract PDF/text/image file and auto-extract title, vendor, business number, amount, date"""
    suffix = os.path.splitext(clean_name(file.filename))[1]
    fd, temp_path = tempfile.mkstemp(prefix="contract-parse-", suffix=suffix)
    os.close(fd)

    try:
        content = read_upload(file)
        with open(temp_path, "wb") as f:
            f.write(content)

        raw_text, _ = extract_text_from_file(temp_path, file.filename)
        doc_type, confidence, _ = classify_document(raw_text)
        fields = extract_fields(raw_text, doc_type=doc_type)

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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="계약 파일을 읽지 못했습니다. 파일 형식과 내용을 확인한 뒤 다시 시도하세요.",
        ) from e
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass



@router.get("", response_model=List[ContractDashboardListItem])
def list_contracts(db: Session = Depends(get_db)):
    """List all registered contracts with evidence summary"""
    return contract_service.list_contracts(db)


@router.post("", response_model=ContractDetailResponse, status_code=status.HTTP_201_CREATED)
def create_contract(req: ContractCreate, db: Session = Depends(get_db), actor: Actor = Depends(get_current_user)):
    """Register a new contract and initialize verification checklist"""
    contract = contract_service.create_contract(db, req, user_id=actor.user_id)
    audit(db, actor, "CONTRACT_CREATED", contract.contract_id, details={"title": req.title})
    detail = contract_service.get_contract_detail(db, contract.contract_id)
    return detail


@router.get('/excluded')
def excluded_contracts(db: Session = Depends(get_db)):
    return [{'contract_id': contract.contract_id, 'title': contract.title,
             'vendor_name': contract.vendor_name, 'excluded_at': excluded.created_at,
             'excluded_by': excluded.actor_name}
            for contract, excluded in db.query(Contract, ContractExclusion).join(
                ContractExclusion, Contract.contract_id == ContractExclusion.contract_id).order_by(
                    ContractExclusion.created_at.desc()).all()]


class RestoreContract(BaseModel):
    note: str = Field(min_length=3, max_length=500)


@router.post('/{contract_id}/restore', response_model=ContractDetailResponse)
def restore_contract(contract_id: int, req: RestoreContract, db: Session = Depends(get_db),
                     actor: Actor = Depends(get_current_user)):
    with STORAGE_LOCK:
        excluded = db.get(ContractExclusion, contract_id)
        if not db.get(Contract, contract_id):
            raise HTTPException(404, '계약을 찾을 수 없습니다.')
        if excluded:
            db.delete(excluded)
            audit(db, actor, 'CONTRACT_RESTORED', contract_id, details={'note': req.note.strip()})
            db.commit()
    return contract_service.get_contract_detail(db, contract_id)


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
def update_contract(contract_id: int, req: ContractUpdate, db: Session = Depends(get_db), actor: Actor = Depends(get_current_user)):
    """Update contract information and re-evaluate validation rules"""
    detail = contract_service.update_contract(db, contract_id, req)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with ID {contract_id} not found",
        )
    audit(db, actor, "CONTRACT_UPDATED", contract_id, details={"note": req.change_note or "", "changes": req.model_dump(exclude_unset=True)})
    return detail


@router.delete("/{contract_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contract(contract_id: int, db: Session = Depends(get_db), actor: Actor = Depends(get_current_user)):
    """Exclude from the inbox without deleting documents, reviews or payment facts."""
    success = contract_service.delete_contract(db, contract_id, actor.display_name)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with ID {contract_id} not found",
        )
    audit(db, actor, "CONTRACT_EXCLUDED", contract_id)
    return None


@router.post("/seed-demo", response_model=ContractDetailResponse)
def seed_demo_contract(db: Session = Depends(get_db)):
    """Seeds or resets the demo contract matching the presentation slides"""
    if IS_PILOT:
        raise HTTPException(403, "시범 운영 모드에서는 자동 데모 초기화를 사용하지 않습니다.")
    contract = contract_service.seed_demo_contract(db)
    return contract_service.get_contract_detail(db, contract.contract_id)


