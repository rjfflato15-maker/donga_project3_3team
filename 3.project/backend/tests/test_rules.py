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
            "fields": {"business_registration_no": "123-45-67890", "total_amount": 11000000.0},
        },
        {
            "document_id": 2,
            "document_type": "estimate",
            "fields": {"business_registration_no": "123-45-67890", "total_amount": 11000000.0},
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
            "fields": {"business_registration_no": "123-45-67890", "total_amount": 10450000.0, "amount_scope": "FULL"},
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
        amount_policy={"amount_basis": "TOTAL", "payment_mode": "FULL"},
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
    assert len(biz_checks) == 4
    assert all(check.status == ValidationStatus.PASS for check in biz_checks)

    # 4. Check summary rate
    assert summary.completeness_rate == 83.3


def validate_amounts(documents, policy=None):
    return RuleEngine().validate_contract_evidence(
        contract_id=1, contract_title="금액 검수 테스트", expected_vendor_name="테스트 업체",
        expected_biz_no="123-45-67890", contract_amount=11000000,
        documents_data=documents, required_document_types=[], amount_policy=policy,
    )[1]


def invoice(document_id, total, scope="FULL", digest=None):
    return {"document_id": document_id, "document_type": "tax_invoice", "sha256": digest,
            "fields": {"total_amount": total, "amount_scope": scope, "business_registration_no": "123-45-67890"}}


def test_unknown_basis_does_not_guess_vat_or_pass_amount():
    checks = validate_amounts([invoice(1, 11000000)])
    assert any(check.rule_id == "AMOUNT_BASIS" and check.status == ValidationStatus.REVIEW for check in checks)
    assert not any(check.rule_id.startswith("AMOUNT_MATCH_") for check in checks)


def test_supply_basis_requires_explicit_tax():
    checks = validate_amounts([invoice(1, 12100000)], {"amount_basis": "SUPPLY", "payment_mode": "FULL"})
    assert any(check.rule_id == "AMOUNT_BASIS" for check in checks)
    assert not any(check.rule_id.startswith("AMOUNT_MATCH_") for check in checks)
    checks = validate_amounts([invoice(1, 12100000)], {"amount_basis": "SUPPLY", "tax_amount": 1100000, "payment_mode": "FULL"})
    assert any(check.rule_id == "AMOUNT_MATCH_TAX_INVOICE" and check.status == ValidationStatus.PASS for check in checks)


def test_every_invoice_is_checked_and_components_must_balance():
    docs = [invoice(1, 11000000), invoice(2, 10000000)]
    docs[0]["fields"].update(supply_amount=9000000, tax_amount=1000000)
    checks = validate_amounts(docs, {"amount_basis": "TOTAL", "payment_mode": "FULL"})
    amount_checks = [check for check in checks if check.rule_id == "AMOUNT_MATCH_TAX_INVOICE"]
    assert len(amount_checks) == 2
    assert {check.status for check in amount_checks} == {ValidationStatus.PASS, ValidationStatus.FAIL}
    assert any(check.rule_id == "AMOUNT_COMPONENTS" and check.status == ValidationStatus.FAIL for check in checks)


@pytest.mark.parametrize("total,status", [(11000000, ValidationStatus.PASS), (10000000, ValidationStatus.REVIEW), (12000000, ValidationStatus.FAIL)])
def test_installment_known_parts_are_added(total, status):
    docs = [invoice(1, 5000000, "PARTIAL", "hash-a"), invoice(2, total - 5000000, "PARTIAL", "hash-b")]
    checks = validate_amounts(docs, {"amount_basis": "TOTAL", "payment_mode": "INSTALLMENT"})
    assert any(check.rule_id == "INSTALLMENT_TOTAL" and check.status == status for check in checks)


def test_duplicate_invoice_not_double_counted():
    docs = [invoice(1, 5500000, "PARTIAL", "same-hash"), invoice(2, 5500000, "PARTIAL", "same-hash")]
    checks = validate_amounts(docs, {"amount_basis": "TOTAL", "payment_mode": "INSTALLMENT"})
    assert any(check.rule_id == "DUPLICATE_INVOICE" and check.status == ValidationStatus.REVIEW for check in checks)
    assert not any(check.rule_id == "INSTALLMENT_TOTAL" for check in checks)


@pytest.mark.parametrize("invoice_total,numeric_status", [
    (11000000, ValidationStatus.PASS), (12000000, ValidationStatus.FAIL),
])
def test_single_partial_invoice_for_whole_contract_requires_scope_review(invoice_total, numeric_status):
    checks = validate_amounts([invoice(1, invoice_total, "PARTIAL", "single-invoice")],
                             {"amount_basis": "TOTAL", "payment_mode": "INSTALLMENT"})
    assert any(check.rule_id == "INSTALLMENT_TOTAL" and check.status == numeric_status for check in checks)
    assert any(check.rule_id == "PAYMENT_SCOPE" and check.status == ValidationStatus.REVIEW for check in checks)


def test_thirty_seventy_installment_parts_sum_without_scope_warning():
    docs = [invoice(1, 3300000, "PARTIAL", "first-thirty-percent"),
            invoice(2, 7700000, "PARTIAL", "remaining-seventy-percent")]
    checks = validate_amounts(docs, {"amount_basis": "TOTAL", "payment_mode": "INSTALLMENT"})
    assert any(check.rule_id == "INSTALLMENT_TOTAL" and check.status == ValidationStatus.PASS for check in checks)
    assert not any(check.rule_id == "PAYMENT_SCOPE" for check in checks)


def test_missing_original_and_disabled_nts_never_pass():
    doc = invoice(1, 11000000)
    doc["file_available"] = False
    checks = validate_amounts([doc], {"amount_basis": "TOTAL", "payment_mode": "FULL"})
    assert any(check.rule_id == "ORIGINAL_FILE" and check.status == ValidationStatus.REVIEW for check in checks)
    assert any(check.rule_id == "BUSINESS_STATUS" and check.status == ValidationStatus.REVIEW for check in checks)
