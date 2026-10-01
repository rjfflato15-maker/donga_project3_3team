import pytest

from backend.app.ai.extractor import extract_fields
from backend.app.schemas.common import DocumentType
from backend.app.validation.financial import extract_financial_fields, extract_reference_amount


def test_flattened_invoice_summary_does_not_read_date_as_money():
    text = ("전자세금계산서\n작성일자 공 급 가 액 세 액\n"
            "2026 년 12 월 15 일 ₩35,000,000 ₩3,500,000\n"
            "총 합 계 금 액 현 금 수 표 어 음 외 상 미 수 금\n"
            "₩38,500,000 0 0 0 38,500,000\n")
    fields = extract_financial_fields(text, DocumentType.TAX_INVOICE)
    assert fields["supply_amount"] == 35000000
    assert fields["tax_amount"] == 3500000
    assert fields["total_amount"] == 38500000
    assert fields["amount_basis"] == "TOTAL"
    assert fields["supply_amount"] != 12
    assert fields["tax_amount"] != 2026


def test_estimate_subtotal_columns_define_money_not_item_quantity():
    text = ("견적서\n견적금액 : 금 38,500,000원 (부가세 포함)\n"
            "품목 수량 단가 공급가액 세액\n웹 개발 1 35,000,000 35,000,000 3,500,000\n"
            "소 계 35,000,000 3,500,000\n")
    fields = extract_financial_fields(text, DocumentType.ESTIMATE)
    assert fields["supply_amount"] == 35000000
    assert fields["tax_amount"] == 3500000
    assert fields["total_amount"] == 38500000
    assert fields["tax_amount"] != 1


@pytest.mark.parametrize("kind,label", [
    (DocumentType.CONTRACT, "총 계약금액"),
    (DocumentType.ESTIMATE, "견적금액"),
    (DocumentType.INSPECTION_CONFIRMATION, "검수금액"),
])
def test_whole_document_is_not_partial_just_because_it_mentions_payment_schedule(kind, label):
    text = f"{label} : 금 38,500,000 원 (부가가치세 포함)\n착수금 30% / 잔금 70%\n"
    fields = extract_fields(text, doc_type=kind)
    assert fields.amount == 38500000
    assert fields.total_amount == 38500000
    assert fields.amount_basis == "TOTAL"
    assert fields.amount_scope == "FULL"


def test_invoice_explicit_remainder_claim_remains_partial():
    fields = extract_financial_fields("전자세금계산서\n잔금 정산 청구분\n합계금액: 26,950,000원\n", DocumentType.TAX_INVOICE)
    assert fields["total_amount"] == 26950000
    assert fields["amount_scope"] == "PARTIAL"


def test_supply_only_never_invents_ten_percent_tax():
    fields = extract_financial_fields("견적서\n공급가액: 35,000,000원\n부가세 별도\n", DocumentType.ESTIMATE)
    assert fields["supply_amount"] == 35000000
    assert fields["tax_amount"] is None
    assert fields["total_amount"] is None
    assert fields["amount_basis"] == "SUPPLY"


def test_vat_exclusive_reference_label_is_supply_amount():
    fields = extract_financial_fields("계약서\n총계약금액: 금 35,000,000원 (부가세 별도)\n", DocumentType.CONTRACT)
    assert fields["supply_amount"] == 35000000
    assert fields["tax_amount"] is None
    assert fields["total_amount"] is None
    assert fields["amount_basis"] == "SUPPLY"


def test_inline_contract_components_are_read_from_their_own_labels():
    fields = extract_financial_fields("계약서\n공급가액: 금 35,000,000원 / 부가세: 3,500,000원 / 합계금액: 38,500,000원\n", DocumentType.CONTRACT)
    assert fields["supply_amount"] == 35000000
    assert fields["tax_amount"] == 3500000
    assert fields["total_amount"] == 38500000


def test_unlabelled_years_quantities_and_business_number_are_not_amounts():
    text = "작성일: 2026년 12월 15일\n사업자등록번호: 123-45-67890\n수량: 1\n공급가액 세액\n"
    assert extract_reference_amount(text) is None
    fields = extract_financial_fields(text, DocumentType.TAX_INVOICE)
    assert fields["supply_amount"] is None
    assert fields["tax_amount"] is None
    assert fields["total_amount"] is None


def test_conflicting_explicit_totals_require_confirmation():
    text = "합계금액: 38,500,000원\n합계금액: 40,000,000원\n"
    assert extract_reference_amount(text) is None
    assert extract_financial_fields(text)["total_amount"] is None
