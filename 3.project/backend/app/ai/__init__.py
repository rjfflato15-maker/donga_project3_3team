import os
from typing import Dict, Any, Tuple
from .preprocessor import extract_text_from_file
from .masking import mask_sensitive_information
from .classifier import classify_document
from .extractor import extract_fields
from ..schemas.document import (
    DocumentAnalysisResponse,
    MaskInfo,
    AnalysisFields,
)
from ..schemas.common import DocumentType, MaskStatus


def analyze_document(file_path: str, file_name: str = "", target_document_type: str = "") -> Tuple[DocumentAnalysisResponse, str, str]:
    """
    Executes the full local AI processing pipeline:
    1. Local text extraction from file (.txt, .pdf, .png, .jpg, etc.)
    2. Local PII detection & masking (creates masked_text)
    3. Document type classification
    4. Structured field extraction
    5. Returns (DocumentAnalysisResponse, raw_text, masked_text)
    """
    raw_text, ext = extract_text_from_file(file_path, file_name=file_name)

    # Step 2: Privacy Preprocessing & Masking
    masked_text, masked_count, categories, token_map = mask_sensitive_information(raw_text)
    mask_status = MaskStatus.MASKED if masked_count > 0 else MaskStatus.NOT_STARTED

    # Step 3: Classification (using raw or masked text)
    doc_type, confidence, breakdown = classify_document(raw_text, target_type=target_document_type)

    # Step 4: Extraction
    fields = extract_fields(raw_text)

    warnings = []
    if doc_type == DocumentType.UNKNOWN:
        warnings.append("문서 유형을 자동으로 식별하지 못했습니다. 수동 확인이 필요합니다.")
    if confidence < 0.80 and doc_type != DocumentType.UNKNOWN:
        warnings.append("문서 유형 판별 신뢰도가 다소 낮습니다. (신뢰도: {:.0f}%)".format(confidence * 100))

    mask_info = MaskInfo(
        status=mask_status,
        masked_count=masked_count,
        categories=categories,
    )

    response = DocumentAnalysisResponse(
        document_type=doc_type,
        confidence=confidence,
        mask=mask_info,
        fields=fields,
        warnings=warnings,
    )

    return response, raw_text, masked_text


__all__ = [
    "extract_text_from_file",
    "mask_sensitive_information",
    "classify_document",
    "extract_fields",
    "analyze_document",
]
