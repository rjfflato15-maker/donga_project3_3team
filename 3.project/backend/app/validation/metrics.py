from typing import List, Optional, Tuple
from ..schemas.validation import ValidationSummary, ValidationCheck
from ..schemas.common import ValidationStatus


def calculate_validation_metrics(
    required_count: int,
    submitted_count: int,
    checks: List[ValidationCheck],
) -> ValidationSummary:
    """
    Calculates metrics according to Section 7 of 00_공통개발기준서.md:
    - 증빙 충족률 = 제출된 필수 문서 수 / 전체 필수 문서 수 * 100
    - 정보 일치율 = PASS / (PASS + FAIL) * 100
    - 정보 불일치율 = FAIL / (PASS + FAIL) * 100
    - REVIEW, MISSING are excluded from match/mismatch denominators
    - denominator == 0 -> match/mismatch rates are None
    """
    pass_cnt = sum(1 for c in checks if c.status == ValidationStatus.PASS)
    fail_cnt = sum(1 for c in checks if c.status == ValidationStatus.FAIL)
    review_cnt = sum(1 for c in checks if c.status == ValidationStatus.REVIEW)
    missing_cnt = sum(1 for c in checks if c.status == ValidationStatus.MISSING)

    # Completeness rate
    if required_count > 0:
        completeness = round((submitted_count / required_count) * 100.0, 1)
    else:
        completeness = 0.0

    # Match / mismatch rate
    match_denominator = pass_cnt + fail_cnt
    match_rate: Optional[float] = None
    mismatch_rate: Optional[float] = None

    if match_denominator > 0:
        match_rate = round((pass_cnt / match_denominator) * 100.0, 1)
        mismatch_rate = round((fail_cnt / match_denominator) * 100.0, 1)

    return ValidationSummary(
        required_document_count=required_count,
        submitted_document_count=submitted_count,
        completeness_rate=completeness,
        pass_count=pass_cnt,
        fail_count=fail_cnt,
        review_count=review_cnt,
        missing_count=missing_cnt,
        match_rate=match_rate,
        mismatch_rate=mismatch_rate,
    )
