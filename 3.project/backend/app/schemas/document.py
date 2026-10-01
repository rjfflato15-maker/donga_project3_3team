from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from .common import DocumentType, ProcessingStatus, MaskStatus


class AnalysisFields(BaseModel):
    title: Optional[str] = None
    company_name: Optional[str] = None
    business_registration_no: Optional[str] = None
    amount: Optional[float] = None
    issue_date: Optional[str] = None
    contract_period_start: Optional[str] = None
    contract_period_end: Optional[str] = None
    account_number: Optional[str] = None
    bank_name: Optional[str] = None
    supply_amount: Optional[float] = None
    tax_amount: Optional[float] = None
    total_amount: Optional[float] = None
    amount_basis: str = "UNKNOWN"
    amount_scope: str = "UNKNOWN"

    model_config = ConfigDict(from_attributes=True, allow_inf_nan=False)


class MaskInfo(BaseModel):
    status: MaskStatus = MaskStatus.NOT_STARTED
    masked_count: int = 0
    categories: List[str] = []


class DocumentAnalysis(BaseModel):
    fields: AnalysisFields = AnalysisFields()
    warnings: List[str] = []


class DocumentAnalysisResponse(BaseModel):
    document_type: DocumentType
    confidence: float
    mask: MaskInfo
    fields: AnalysisFields
    warnings: List[str] = []


class DocumentResponse(BaseModel):
    document_id: int
    contract_id: int
    original_file_name: str
    document_type: DocumentType
    confidence: float
    processing_status: ProcessingStatus
    mask_status: MaskStatus
    analysis: DocumentAnalysis
    raw_text: Optional[str] = None
    masked_text: Optional[str] = None
    business_status: Optional[str] = None
    file_available: bool = False
    file_size: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)
