from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..schemas.contract import (
    ContractCreate,
    ContractListItem,
    ContractDetailResponse,
)
from ..services.contract_service import ContractService

router = APIRouter(prefix="/api/contracts", tags=["Contracts"])
contract_service = ContractService()


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


@router.post("/seed-demo", response_model=ContractDetailResponse)
def seed_demo_contract(db: Session = Depends(get_db)):
    """Seeds or resets the demo contract matching the presentation slides"""
    contract = contract_service.seed_demo_contract(db)
    return contract_service.get_contract_detail(db, contract.contract_id)
