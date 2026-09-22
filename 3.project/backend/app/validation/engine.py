from typing import List, Dict, Any, Tuple
from ..schemas.common import (
    DocumentType,
    ValidationStatus,
    CORE_6_DOCUMENT_TYPES,
    DOCUMENT_TYPE_KOREAN,
)
from ..schemas.validation import (
    ValidationCheck,
    ValidationSummary,
    ValidationReportResponse,
)
from .metrics import calculate_validation_metrics
from ..integrations.nts_client import get_nts_client


class RuleEngine:
    """
    Deterministic rule engine for contract evidence cross-validation
    """

    def __init__(self):
        self.nts_client = get_nts_client()

    def validate_contract_evidence(
        self,
        contract_id: int,
        contract_title: str,
        expected_vendor_name: str,
        expected_biz_no: str,
        contract_amount: float,
        documents_data: List[Dict[str, Any]],
    ) -> Tuple[ValidationSummary, List[ValidationCheck]]:
        """
        Runs the 4 deterministic rule checks:
        1. REQUIRED_DOCUMENTS (Missing document rule)
        2. BUSINESS_NO_MATCH (Cross-document business registration number matching)
        3. AMOUNT_MATCH (Cross-document amount matching with difference calculation)
        4. BUSINESS_STATUS (NTS public agency status verification)
        """
        checks: List[ValidationCheck] = []

        # Map documents by document_type
        submitted_types = set()
        docs_by_type: Dict[str, List[Dict[str, Any]]] = {}

        for doc in documents_data:
            dtype = doc.get("document_type")
            if dtype:
                submitted_types.add(dtype)
                docs_by_type.setdefault(dtype, []).append(doc)

        # ----------------------------------------------------
        # Rule 1: REQUIRED_DOCUMENTS (Check 6 core documents)
        # ----------------------------------------------------
        missing_types = []
        for required_type in CORE_6_DOCUMENT_TYPES:
            r_val = required_type.value
            korean_name = DOCUMENT_TYPE_KOREAN.get(required_type, r_val)
            if r_val not in submitted_types:
                missing_types.append(required_type)
                checks.append(
                    ValidationCheck(
                        rule_id="REQUIRED_DOCUMENTS",
                        status=ValidationStatus.MISSING,
                        field=r_val,
                        expected="제출",
                        actual="누락",
                        message=f"{korean_name}이(가) 제출되지 않았습니다.",
                    )
                )

        # ----------------------------------------------------
        # Rule 2: BUSINESS_NO_MATCH (Cross-validation)
        # ----------------------------------------------------
        # Check against business_registration, estimate, and tax_invoice
        found_biz_nos: Dict[str, str] = {}
        for dtype in ["business_registration", "estimate", "tax_invoice", "contract"]:
            if dtype in docs_by_type:
                for doc in docs_by_type[dtype]:
                    fields = doc.get("fields", {})
                    b_no = fields.get("business_registration_no")
                    if b_no:
                        found_biz_nos[dtype] = b_no

        if not found_biz_nos:
            checks.append(
                ValidationCheck(
                    rule_id="BUSINESS_NO_MATCH",
                    status=ValidationStatus.REVIEW,
                    field="business_registration_no",
                    expected=expected_biz_no,
                    actual="미추출",
                    message="문서에서 사업자등록번호를 추출하지 못하여 수동 확인이 필요합니다.",
                )
            )
        else:
            all_match = True
            mismatch_details = []
            clean_expected = expected_biz_no.replace("-", "").strip()

            for dtype, found_no in found_biz_nos.items():
                clean_found = found_no.replace("-", "").strip()
                if clean_found != clean_expected:
                    all_match = False
                    d_korean = DOCUMENT_TYPE_KOREAN.get(DocumentType(dtype), dtype)
                    mismatch_details.append(f"{d_korean}: {found_no}")

            if all_match:
                checks.append(
                    ValidationCheck(
                        rule_id="BUSINESS_NO_MATCH",
                        status=ValidationStatus.PASS,
                        field="business_registration_no",
                        expected=expected_biz_no,
                        actual=expected_biz_no,
                        message="계약서와 제출 증빙(사업자등록증/견적서/세금계산서)의 사업자등록번호가 일치합니다.",
                    )
                )
            else:
                checks.append(
                    ValidationCheck(
                        rule_id="BUSINESS_NO_MATCH",
                        status=ValidationStatus.FAIL,
                        field="business_registration_no",
                        expected=expected_biz_no,
                        actual=", ".join(mismatch_details),
                        message=f"사업자등록번호 불일치: 계약서 기준({expected_biz_no})과 증빙 문서가 다릅니다.",
                    )
                )

        # ----------------------------------------------------
        # Rule 3: BUSINESS_STATUS (NTS Status)
        # ----------------------------------------------------
        nts_result = self.nts_client.check_business_status(expected_biz_no)
        b_status = nts_result.get("status", "계속사업자")
        is_active = nts_result.get("is_active", True)

        if is_active:
            checks.append(
                ValidationCheck(
                    rule_id="BUSINESS_STATUS",
                    status=ValidationStatus.PASS,
                    field="business_status",
                    expected="정상영업 (계속사업자)",
                    actual=b_status,
                    message="국세청 확인 결과 정상 계속사업자입니다.",
                )
            )
        else:
            checks.append(
                ValidationCheck(
                    rule_id="BUSINESS_STATUS",
                    status=ValidationStatus.FAIL,
                    field="business_status",
                    expected="정상영업 (계속사업자)",
                    actual=b_status,
                    message=f"국세청 확인 결과 계속사업자가 아닙니다 ({b_status}). 주의가 필요합니다.",
                )
            )

        # ----------------------------------------------------
        # Rule 4: AMOUNT_MATCH (Cross-document amount matching)
        # ----------------------------------------------------
        # Compare contract amount with estimate amount and tax invoice amount
        estimate_amounts = []
        if "estimate" in docs_by_type:
            for doc in docs_by_type["estimate"]:
                amt = doc.get("fields", {}).get("amount")
                if amt is not None:
                    estimate_amounts.append(float(amt))

        tax_invoice_amounts = []
        if "tax_invoice" in docs_by_type:
            for doc in docs_by_type["tax_invoice"]:
                amt = doc.get("fields", {}).get("amount")
                if amt is not None:
                    tax_invoice_amounts.append(float(amt))

        # 4-A. Estimate amount vs Contract amount
        if estimate_amounts:
            est_amt = estimate_amounts[0]
            if abs(est_amt - contract_amount) < 1.0:
                checks.append(
                    ValidationCheck(
                        rule_id="AMOUNT_MATCH_ESTIMATE",
                        status=ValidationStatus.PASS,
                        field="amount_estimate",
                        expected=f"{int(contract_amount):,}원",
                        actual=f"{int(est_amt):,}원",
                        message="계약금액과 견적서 금액이 일치합니다.",
                    )
                )
            else:
                diff = abs(contract_amount - est_amt)
                checks.append(
                    ValidationCheck(
                        rule_id="AMOUNT_MATCH_ESTIMATE",
                        status=ValidationStatus.FAIL,
                        field="amount_estimate",
                        expected=f"{int(contract_amount):,}원",
                        actual=f"{int(est_amt):,}원",
                        message=f"계약금액과 견적금액이 {int(diff):,}원 차이납니다.",
                    )
                )

        # 4-B. Tax Invoice amount vs Contract amount
        if tax_invoice_amounts:
            tax_amt = tax_invoice_amounts[0]
            if abs(tax_amt - contract_amount) < 1.0:
                checks.append(
                    ValidationCheck(
                        rule_id="AMOUNT_MATCH_TAX_INVOICE",
                        status=ValidationStatus.PASS,
                        field="amount_tax_invoice",
                        expected=f"{int(contract_amount):,}원",
                        actual=f"{int(tax_amt):,}원",
                        message="계약금액과 세금계산서 청구 금액이 일치합니다.",
                    )
                )
            else:
                diff = abs(contract_amount - tax_amt)
                checks.append(
                    ValidationCheck(
                        rule_id="AMOUNT_MATCH_TAX_INVOICE",
                        status=ValidationStatus.FAIL,
                        field="amount_tax_invoice",
                        expected=f"{int(contract_amount):,}원",
                        actual=f"{int(tax_amt):,}원",
                        message=f"금액 {int(diff):,}원 불일치 (계약서: {int(contract_amount):,}원 ↔ 세금계산서: {int(tax_amt):,}원)",
                    )
                )

        # Calculate metrics
        required_count = len(CORE_6_DOCUMENT_TYPES)
        submitted_count = len([t for t in CORE_6_DOCUMENT_TYPES if t.value in submitted_types])

        summary = calculate_validation_metrics(
            required_count=required_count,
            submitted_count=submitted_count,
            checks=checks,
        )

        return summary, checks
