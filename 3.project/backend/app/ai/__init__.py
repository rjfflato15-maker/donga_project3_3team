import os
from typing import Dict, Any, Tuple
from .preprocessor import extract_text_from_file
from .masking import mask_sensitive_information
from .classifier import classify_document
from .extractor import extract_fields, is_generic_title, extract_contract_title
from ..schemas.document import (
    DocumentAnalysisResponse,
    MaskInfo,
    AnalysisFields,
    INCOMPLETE_EXTRACTION_WARNING,
)
from ..schemas.common import DocumentType, MaskStatus


def analyze_document(file_path: str, file_name: str = "", target_document_type: str = "", *, use_llm=None, force_document_type=False) -> Tuple[DocumentAnalysisResponse, str, str]:
    """
    Executes the full local AI processing pipeline:
    1. Local text extraction from file (.txt, .pdf, .png, .jpg, etc.)
    2. Local PII detection & masking (creates masked_text)
    3. Document type classification
    4. Structured field extraction
    5. Returns (DocumentAnalysisResponse, raw_text, masked_text)
    """
    extraction_metadata = {}
    raw_text, ext = extract_text_from_file(file_path, file_name=file_name,
                                          extraction_metadata=extraction_metadata)

    # Step 2: Privacy Preprocessing & Masking
    masked_text, masked_count, categories, token_map = mask_sensitive_information(raw_text)
    mask_status = MaskStatus.MASKED if masked_count > 0 else MaskStatus.NOT_STARTED

    # Step 3: Classification (using raw or masked text)
    doc_type, confidence, breakdown = classify_document(raw_text, target_type=target_document_type)
    selected_warning = None
    if force_document_type and target_document_type:
        selected = DocumentType(target_document_type)
        if selected != doc_type:
            selected_warning = f'자동 분류({doc_type.value})와 등록할 때 선택한 종류({selected.value})가 다릅니다. 서류 종류를 원문과 확인하세요.'
            confidence = 0
        doc_type = selected

    # Step 4: Extraction
    fields = extract_fields(raw_text, doc_type=doc_type)
    from ..validation.billing import extraction_context
    billing_context = extraction_context(raw_text)
    if billing_context['claim_stage'] != 'UNKNOWN' or billing_context['payment_mode'] != 'UNKNOWN' or billing_context['schedule']:
        extraction_metadata['billing_context'] = billing_context
    enabled = os.getenv("APP_LLM_ENABLED", "false").lower() == "true" if use_llm is None else use_llm
    ai_review = None
    if enabled:
        from .llm_supplement import supplement_document
        values, ai_review = supplement_document(file_path, raw_text, fields.model_dump(), doc_type.value)
        fields = AnalysisFields.model_validate(values)

    warnings = [selected_warning] if selected_warning else []
    if extraction_metadata.get("evidence_complete") is False:
        warnings.append(INCOMPLETE_EXTRACTION_WARNING)
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
        ai_review=ai_review,
        extraction_metadata=extraction_metadata or None,
    )

    return response, raw_text, masked_text


__all__ = [
    "extract_text_from_file",
    "mask_sensitive_information",
    "classify_document",
    "extract_fields",
    "is_generic_title",
    "extract_contract_title",
    "analyze_document",
]
