from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from .common import DocumentType
from .document import DocumentResponse
from .validation import ValidationSummary, ValidationCheck


class ContractBase(BaseModel):
    title: str
    vendor_name: str
    business_number: str
    contract_amount: float


class ContractCreate(ContractBase):
    pass


class ContractListItem(BaseModel):
    contract_id: int
    title: str
    vendor_name: str
    business_number: str
    contract_amount: float
    review_status: str
    completeness_rate: float
    submitted_docs_count: int
    total_docs_count: int = 6
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContractDetailResponse(BaseModel):
    contract_id: int
    title: str
    vendor_name: str
    business_number: str
    contract_amount: float
    review_status: str
    required_document_types: List[DocumentType]
    documents: List[DocumentResponse]
    summary: ValidationSummary
    checks: List[ValidationCheck]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
