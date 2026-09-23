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


class ContractUpdate(BaseModel):
    title: Optional[str] = None
    vendor_name: Optional[str] = None
    business_number: Optional[str] = None
    contract_amount: Optional[float] = None


class ParsedContractResponse(BaseModel):
    title: Optional[str] = None
    vendor_name: Optional[str] = None
    business_number: Optional[str] = None
    contract_amount: Optional[float] = None
    issue_date: Optional[str] = None
    document_type: Optional[str] = None
    raw_text_snippet: Optional[str] = None


class AutoContractParseItem(BaseModel):
    file_name: str
    document_type: str
    confidence: float
    title: Optional[str] = None
    company_name: Optional[str] = None
    business_registration_no: Optional[str] = None
    amount: Optional[float] = None
    issue_date: Optional[str] = None


class AutoContractSynthesisResponse(BaseModel):
    title: str
    vendor_name: str
    business_number: str
    contract_amount: float
    issue_date: Optional[str] = None
    documents: List[AutoContractParseItem]




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
