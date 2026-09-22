from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..schemas.validation import ValidationReportResponse
from ..services.contract_service import ContractService
from ..services.pipeline_service import PipelineService

router = APIRouter(prefix="/api/contracts", tags=["Validations"])
contract_service = ContractService()
pipeline_service = PipelineService()


@router.post("/{contract_id}/validate", response_model=ValidationReportResponse)
def trigger_validation(contract_id: int, db: Session = Depends(get_db)):
    """Triggers deterministic Rule Engine evaluation for a contract's evidence bundle"""
    detail = contract_service.get_contract_detail(db, contract_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with ID {contract_id} not found",
        )
    pipeline_service.revalidate_contract(db, contract_id)
    updated_detail = contract_service.get_contract_detail(db, contract_id)
    return ValidationReportResponse(
        contract_id=contract_id,
        summary=updated_detail.summary,
        checks=updated_detail.checks,
    )


@router.get("/{contract_id}/report", response_model=ValidationReportResponse)
def get_validation_report(contract_id: int, db: Session = Depends(get_db)):
    """Get structured validation summary and check details (PASS/REVIEW/MISSING/FAIL)"""
    detail = contract_service.get_contract_detail(db, contract_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract with ID {contract_id} not found",
        )
    return ValidationReportResponse(
        contract_id=contract_id,
        summary=detail.summary,
        checks=detail.checks,
    )
