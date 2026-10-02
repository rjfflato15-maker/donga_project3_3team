from typing import List, Optional, Literal
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from .common import DocumentType
from .document import DocumentResponse
from .validation import ValidationSummary, ValidationCheck


class ContractBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    vendor_name: str = Field(min_length=1, max_length=200)
    business_number: str = Field(max_length=50)
    contract_amount: float = Field(ge=0, allow_inf_nan=False)
    amount_basis: Literal["TOTAL", "SUPPLY", "UNKNOWN"] = "UNKNOWN"
    tax_amount: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    payment_mode: Literal["FULL", "INSTALLMENT"] = "FULL"


class ContractCreate(ContractBase):
    pass


class ContractUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    vendor_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    business_number: Optional[str] = Field(default=None, max_length=50)
    contract_amount: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    amount_basis: Optional[Literal["TOTAL", "SUPPLY", "UNKNOWN"]] = None
    tax_amount: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    payment_mode: Optional[Literal["FULL", "INSTALLMENT"]] = None
    revision: Optional[int] = None
    change_note: Optional[str] = Field(default=None, max_length=2000)


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
    submitted_document_types: List[str] = []
    created_at: datetime
    approval_status: str = "PENDING"
    revision: int = 1
    missing_original_count: int = 0

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
    workflow: dict = {}
    llm: dict = {}

    model_config = ConfigDict(from_attributes=True)
