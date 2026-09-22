from enum import Enum


class DocumentType(str, Enum):
    CONTRACT = "contract"
    ESTIMATE = "estimate"
    BUSINESS_REGISTRATION = "business_registration"
    BANK_ACCOUNT = "bank_account"
    TAX_INVOICE = "tax_invoice"
    INSPECTION_CONFIRMATION = "inspection_confirmation"
    UNKNOWN = "unknown"


class ProcessingStatus(str, Enum):
    UPLOADED = "UPLOADED"
    PREPROCESSING = "PREPROCESSING"
    ANALYZING = "ANALYZING"
    COMPLETED = "COMPLETED"
    REVIEW = "REVIEW"
    FAILED = "FAILED"


class MaskStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    MASKED = "MASKED"
    REVIEW_NEEDED = "REVIEW_NEEDED"
    FAILED = "FAILED"


class ValidationStatus(str, Enum):
    PASS = "PASS"
    REVIEW = "REVIEW"
    MISSING = "MISSING"
    FAIL = "FAIL"


CORE_6_DOCUMENT_TYPES = [
    DocumentType.CONTRACT,
    DocumentType.ESTIMATE,
    DocumentType.BUSINESS_REGISTRATION,
    DocumentType.BANK_ACCOUNT,
    DocumentType.TAX_INVOICE,
    DocumentType.INSPECTION_CONFIRMATION,
]

DOCUMENT_TYPE_KOREAN = {
    DocumentType.CONTRACT: "계약서",
    DocumentType.ESTIMATE: "견적서",
    DocumentType.BUSINESS_REGISTRATION: "사업자등록증",
    DocumentType.BANK_ACCOUNT: "통장사본",
    DocumentType.TAX_INVOICE: "세금계산서",
    DocumentType.INSPECTION_CONFIRMATION: "검수확인서",
    DocumentType.UNKNOWN: "기타/미분류",
}
