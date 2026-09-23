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

    model_config = ConfigDict(from_attributes=True)


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

    model_config = ConfigDict(from_attributes=True)
