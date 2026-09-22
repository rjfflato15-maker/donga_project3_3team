import re
from typing import Dict, List, Tuple
from ..schemas.common import DocumentType


# Signature rules and keyword weights for the 6 core document types
SIGNATURES: Dict[DocumentType, Dict[str, float]] = {
    DocumentType.CONTRACT: {
        "계약서": 3.0,
        "외주용역계약서": 4.0,
        "표준계약서": 3.0,
        "용역계약서": 3.0,
        "계약기간": 1.5,
        "계약금액": 1.5,
        "발주사": 1.0,
        "수주사": 1.0,
        "제 1 조": 1.5,
        "제 2 조": 1.5,
        "이하 \"갑\"": 2.0,
        "이하 \"을\"": 2.0,
        "(갑)": 1.0,
        "(을)": 1.0,
    },
    DocumentType.ESTIMATE: {
        "견적서": 4.0,
        "견 적 서": 4.0,
        "견적 번호": 2.5,
        "견적 일자": 2.0,
        "견적 금액": 2.5,
        "견적금액": 2.5,
        "아래와 같이 견적합니다": 3.0,
        "견적합니다": 2.0,
        "귀하": 1.0,
        "공급가액": 1.0,
    },
    DocumentType.BUSINESS_REGISTRATION: {
        "사업자등록증": 4.0,
        "사 업 자 등 록 증": 4.0,
        "개업연월일": 3.0,
        "법인등록번호": 2.0,
        "사업장소재지": 2.5,
        "본점소재지": 1.5,
        "사업의 종류": 2.5,
        "세무서장": 2.5,
        "일반과세자": 2.0,
        "간이과세자": 2.0,
    },
    DocumentType.BANK_ACCOUNT: {
        "통장사본": 4.0,
        "통 장 사 본": 4.0,
        "계좌개설확인서": 4.0,
        "거래은행": 3.0,
        "예금주": 2.5,
        "예금주명": 2.5,
        "예금종류": 2.0,
        "신규일자": 1.5,
        "관리점": 2.0,
        "당행에 개설되어": 3.0,
    },
    DocumentType.TAX_INVOICE: {
        "전자세금계산서": 4.0,
        "전 자 세 금 계 산 서": 4.0,
        "세금계산서": 3.5,
        "공급받는자": 3.0,
        "공급자": 1.5,
        "승인번호": 3.0,
        "총 합계금액": 2.0,
        "영수(청구)": 3.0,
        "영수 함": 2.0,
        "청구 함": 2.0,
        "세액": 1.5,
    },
    DocumentType.INSPECTION_CONFIRMATION: {
        "검수확인서": 4.0,
        "검 수 확 인 서": 4.0,
        "납품확인서": 3.5,
        "납품 및 검수 확인서": 4.5,
        "납품 및 검수확인서": 4.5,
        "검수 내용": 3.0,
        "검수일자": 2.5,
        "검수자": 2.5,
        "완료되었음을 확인": 3.0,
        "과업지시서": 2.0,
        "계약 상대자": 1.5,
    },
}

FILENAME_SIGNATURES: Dict[DocumentType, List[str]] = {
    DocumentType.CONTRACT: ["계약서", "계약", "contract", "외주계약", "용역계약", "표준계약"],
    DocumentType.ESTIMATE: ["견적서", "견적", "estimate", "quotation", "내역서"],
    DocumentType.BUSINESS_REGISTRATION: ["사업자등록증", "사업자등록", "사업자", "business_registration", "bizreg", "biz", "등록증"],
    DocumentType.BANK_ACCOUNT: ["통장사본", "통장", "계좌", "bank_account", "bank", "passbook", "계좌사본"],
    DocumentType.TAX_INVOICE: ["세금계산서", "전자세금계산서", "tax_invoice", "tax", "invoice", "계산서"],
    DocumentType.INSPECTION_CONFIRMATION: ["검수확인서", "납품확인서", "검수", "납품", "inspection_confirmation", "inspection", "확인서", "완료확인서", "검수서", "납품서"],
}


def classify_document(text: str, target_type: str = "") -> Tuple[DocumentType, float, Dict[str, float]]:
    """
    Classifies document text into one of the 6 core document types or unknown.
    Optionally accepts a target_type hint from user selection.
    Returns:
        (predicted_document_type, confidence_score, score_breakdown)
    """
    scores: Dict[DocumentType, float] = {doc_type: 0.0 for doc_type in SIGNATURES}

    norm_text = re.sub(r"\s+", "", text).lower()

    # 1. Target Type Hint Boost
    if target_type:
        try:
            enum_target = DocumentType(target_type)
            if enum_target in scores:
                scores[enum_target] += 10.0
        except ValueError:
            pass

    # 2. Signature Keyword Matching (Original + Space-normalized)
    for doc_type, keywords in SIGNATURES.items():
        for kw, weight in keywords.items():
            norm_kw = re.sub(r"\s+", "", kw).lower()
            if kw in text or norm_kw in norm_text:
                scores[doc_type] += weight

    # 3. Filename Signature Matching
    for doc_type, fn_keywords in FILENAME_SIGNATURES.items():
        for fn_kw in fn_keywords:
            if fn_kw.lower() in norm_text:
                scores[doc_type] += 5.0
                break

    best_type = DocumentType.UNKNOWN
    best_score = 0.0

    for doc_type, score in scores.items():
        if score > best_score:
            best_score = score
            best_type = doc_type

    # Fallback to target_type if provided
    if best_score < 3.0:
        if target_type:
            try:
                forced_enum = DocumentType(target_type)
                if forced_enum != DocumentType.UNKNOWN:
                    return forced_enum, 0.85, {k.value: v for k, v in scores.items()}
            except ValueError:
                pass
        return DocumentType.UNKNOWN, 0.40, {k.value: v for k, v in scores.items()}

    # Normalize confidence into [0.70, 0.99]
    confidence = min(0.99, 0.70 + (best_score / 25.0) * 0.29)
    confidence = round(confidence, 2)

    return best_type, confidence, {k.value: round(v, 2) for k, v in scores.items()}


