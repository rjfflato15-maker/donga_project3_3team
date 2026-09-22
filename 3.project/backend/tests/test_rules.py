import pytest
from backend.app.validation.engine import RuleEngine
from backend.app.validation.metrics import calculate_validation_metrics
from backend.app.schemas.common import ValidationStatus, DocumentType
from backend.app.schemas.validation import ValidationCheck


def test_calculate_validation_metrics():
    # 5 out of 6 docs submitted -> 83.3%
    # 2 PASS, 1 FAIL, 1 REVIEW, 1 MISSING
    # Match rate: 2 / (2 + 1) * 100 = 66.7%
    # Mismatch rate: 1 / (2 + 1) * 100 = 33.3%
    checks = [
        ValidationCheck(rule_id="R1", status=ValidationStatus.PASS, field="f1", message="m1"),
        ValidationCheck(rule_id="R2", status=ValidationStatus.PASS, field="f2", message="m2"),
        ValidationCheck(rule_id="R3", status=ValidationStatus.FAIL, field="f3", message="m3"),
        ValidationCheck(rule_id="R4", status=ValidationStatus.REVIEW, field="f4", message="m4"),
        ValidationCheck(rule_id="R5", status=ValidationStatus.MISSING, field="f5", message="m5"),
    ]

    summary = calculate_validation_metrics(
        required_count=6,
        submitted_count=5,
        checks=checks,
    )

    assert summary.required_document_count == 6
    assert summary.submitted_document_count == 5
    assert summary.completeness_rate == 83.3
    assert summary.pass_count == 2
    assert summary.fail_count == 1
    assert summary.review_count == 1
    assert summary.missing_count == 1
    assert summary.match_rate == 66.7
    assert summary.mismatch_rate == 33.3


def test_rule_engine_mismatch_and_missing():
    engine = RuleEngine()

    docs_data = [
        {
            "document_id": 1,
            "document_type": "contract",
            "fields": {"business_registration_no": "123-45-67890", "amount": 11000000.0},
        },
        {
            "document_id": 2,
            "document_type": "estimate",
            "fields": {"business_registration_no": "123-45-67890", "amount": 11000000.0},
        },
        {
            "document_id": 3,
            "document_type": "business_registration",
            "fields": {"business_registration_no": "123-45-67890"},
        },
        {
            "document_id": 4,
            "document_type": "bank_account",
            "fields": {},
        },
        {
            "document_id": 5,
            "document_type": "tax_invoice",
            "fields": {"business_registration_no": "123-45-67890", "amount": 10450000.0},
        },
        # inspection_confirmation is missing!
    ]

    summary, checks = engine.validate_contract_evidence(
        contract_id=1,
        contract_title="ABC 홈페이지 구축 외주 계약",
        expected_vendor_name="ABC 주식회사",
        expected_biz_no="123-45-67890",
        contract_amount=11000000.0,
        documents_data=docs_data,
    )

    # 1. Inspection confirmation should be MISSING
    missing_checks = [c for c in checks if c.status == ValidationStatus.MISSING]
    assert len(missing_checks) == 1
    assert missing_checks[0].field == "inspection_confirmation"

    # 2. Tax invoice amount should be FAIL due to 550,000 difference
    tax_checks = [c for c in checks if c.rule_id == "AMOUNT_MATCH_TAX_INVOICE"]
    assert len(tax_checks) == 1
    assert tax_checks[0].status == ValidationStatus.FAIL
    assert "550,000원" in tax_checks[0].message

    # 3. Biz no match should PASS
    biz_checks = [c for c in checks if c.rule_id == "BUSINESS_NO_MATCH"]
    assert len(biz_checks) == 1
    assert biz_checks[0].status == ValidationStatus.PASS

    # 4. Check summary rate
    assert summary.completeness_rate == 83.3
