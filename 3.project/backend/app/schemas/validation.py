from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from .common import ValidationStatus, DocumentType


class ValidationCheck(BaseModel):
    rule_id: str
    status: ValidationStatus
    field: str
    expected: Optional[str] = None
    actual: Optional[str] = None
    message: str

    model_config = ConfigDict(from_attributes=True)


class ValidationSummary(BaseModel):
    required_document_count: int = 6
    submitted_document_count: int = 0
    completeness_rate: float = 0.0
    pass_count: int = 0
    fail_count: int = 0
    review_count: int = 0
    missing_count: int = 0
    match_rate: Optional[float] = None
    mismatch_rate: Optional[float] = None


class ValidationReportResponse(BaseModel):
    contract_id: int
    summary: ValidationSummary
    checks: List[ValidationCheck]

    model_config = ConfigDict(from_attributes=True)


class ValidationDocumentInput(BaseModel):
    document_id: int
    document_type: DocumentType
    fields: dict = {}


class ValidationInput(BaseModel):
    contract_id: int
    required_document_types: List[DocumentType] = []
    documents: List[ValidationDocumentInput] = []
