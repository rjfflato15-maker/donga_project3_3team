"""Claim stage, contract amount and actual payment must stay independent."""
from decimal import Decimal

import pytest

from backend.app.validation.billing import extraction_context, scope_in_document, contract_terms
from backend.app.validation.engine import RuleEngine


def document(kind, text, total=38500000, scope='UNKNOWN', document_id=1):
    return {'document_id': document_id, 'document_type': kind, 'sha256': str(document_id),
            'fields': {'total_amount': total, 'amount_scope': scope,
                       'business_registration_no': '123-45-67890',
                       'extraction_metadata': {'billing_context': extraction_context(text)}}}


def checks(docs, mode='FULL'):
    return RuleEngine().validate_contract_evidence(1, '합성 계약', '합성 거래처', '123-45-67890',
        38500000, docs, required_document_types=[],
        amount_policy={'amount_basis': 'TOTAL', 'payment_mode': mode})[1]


@pytest.mark.parametrize('text,expected', [
    ('프로젝트 최종 검수 완료 잔금 정산 청구분', 'UNKNOWN'),
    ('잔금 청구\n외상미수금 38,500,000원\n영수', 'UNKNOWN'),
    ('선금 청구', 'UNKNOWN'), ('잔금 70% 청구', 'PARTIAL'),
    ('잔금(70%) 정산 청구', 'PARTIAL'), ('계약금액의 30% 청구', 'PARTIAL'),
    ('잔금 70%\n별도 청구 내역 확인', 'UNKNOWN'),
    ('최종 검수 완료 후 계약 전액 청구', 'FULL'),
    ('계약 전액 청구 / 부분 청구', 'UNKNOWN'),
])
def test_only_explicit_claim_extent_is_extracted(text, expected):
    assert scope_in_document(text, 'tax_invoice', True) == expected


def test_contract_terms_keep_stage_ratio_and_amount_together():
    doc = document('contract', '착수금(30%): 계약 후 지급 11,550,000원 / 잔금(70%): 최종 검수 후 지급 26,950,000원')
    terms = contract_terms([doc], Decimal('38500000'))
    assert terms == {'mode': 'INSTALLMENT', 'stage_amounts': {
        'ADVANCE': Decimal('11550000'), 'FINAL': Decimal('26950000')}, 'ambiguous': False}


def test_full_invoice_with_remainder_word_checks_contract_terms_not_only_keyword():
    docs = [document('contract', '착수금(30%): 11,550,000원\n잔금(70%): 26,950,000원'),
            document('tax_invoice', '최종 검수 완료 잔금 정산 청구분', document_id=2)]
    result = checks(docs, 'INSTALLMENT')
    assert any(c.rule_id == 'AMOUNT_MATCH_TAX_INVOICE' and c.status == 'PASS' for c in result)
    review = [c for c in result if c.rule_id == 'PAYMENT_SCOPE']
    assert len(review) == 1 and review[0].status == 'REVIEW'
    assert '26,950,000' in review[0].expected
    assert '38,500,000' in review[0].actual


def test_genuine_final_seventy_percent_is_compared_to_contract_stage():
    docs = [document('contract', '선금(30%): 11,550,000원\n잔금(70%): 26,950,000원'),
            document('tax_invoice', '잔금 정산 청구분', total=26950000, document_id=2)]
    result = checks(docs, 'INSTALLMENT')
    assert not any(c.rule_id == 'PAYMENT_SCOPE' for c in result)
    assert any(c.rule_id == 'INSTALLMENT_TOTAL' and c.status == 'REVIEW' for c in result)


def test_no_advance_full_final_settlement_is_not_partial_or_paid():
    docs = [document('contract', '선금 없음. 최종 검수 완료 후 전액 일괄 지급.'),
            document('tax_invoice', '최종 검수 완료 후 계약 전액 청구\n외상미수금 38,500,000원', scope='FULL', document_id=2)]
    result = checks(docs)
    assert any(c.rule_id == 'AMOUNT_MATCH_TAX_INVOICE' and c.status == 'PASS' for c in result)
    assert not any(c.rule_id in {'PAYMENT_SCOPE', 'CONTRACT_PAYMENT_TERMS'} for c in result)
    assert all('지급 완료' not in (c.actual or '') for c in result)


@pytest.mark.parametrize('module', ['grounding', 'grounding_v4'])
@pytest.mark.parametrize('quote,value,accepted', [
    ('잔금 청구', 'PARTIAL', False),
    ('잔금 70% 청구', 'PARTIAL', True),
    ('계약 전액 청구', 'FULL', True),
])
def test_llm_guards_require_explicit_scope(module, quote, value, accepted):
    from importlib import import_module
    guard = import_module('backend.app.ai.' + module).guard_proposal
    answer = {'state': 'VALUE', 'value': value, 'quote': quote, 'line': 1, 'page': 1}
    pages = [{'page': 1, 'location_kind': 'page', 'text': quote}]
    assert guard('amount_scope', answer, pages, 'tax_invoice')['accepted'] == accepted


def test_full_claim_does_not_force_single_payment_plan():
    docs = [document('contract', '선금 30% 11,550,000원 / 잔금 70% 26,950,000원'),
            document('tax_invoice', '계약 전액 청구', scope='FULL', document_id=2)]
    assert not any(c.rule_id == 'PAYMENT_SCOPE' for c in checks(docs, 'INSTALLMENT'))


def test_reference_policy_and_original_terms_disagree():
    docs = [document('contract', '선금 30% 11,550,000원 / 잔금 70% 26,950,000원')]
    assert any(c.rule_id == 'CONTRACT_PAYMENT_TERMS' and c.status == 'REVIEW' for c in checks(docs))


def test_conflicting_source_terms_and_malformed_metadata_do_not_pass():
    docs = [document('contract', '잔금 70% 20,000,000원')]
    assert contract_terms(docs, Decimal('38500000'))['ambiguous']
    docs[0]['fields']['extraction_metadata']['billing_context']['schedule'] = {'FINAL': {'amount': 'NaN'}}
    assert contract_terms(docs, Decimal('38500000'))['ambiguous']


def test_unlabelled_amount_or_date_is_not_a_payment_schedule():
    context = extraction_context('최종 검수 2026년 12월 15일\n합계 38,500,000원\n잔금 정산 청구')
    assert context['schedule'] == {} and context['payment_mode'] == 'UNKNOWN'


def test_no_advance_sentence_does_not_bind_later_total_to_advance():
    context = extraction_context('선금 없음. 최종 검수 완료 후 공급가액 35,000,000원과 부가세 3,500,000원을 합한 38,500,000원 전액을 한 번에 정산하며 일괄 지급한다.')
    assert context['payment_mode'] == 'FULL' and context['schedule'] == {}
