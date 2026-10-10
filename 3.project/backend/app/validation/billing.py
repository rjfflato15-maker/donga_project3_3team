"""Document statements and contract comparisons; never infer an actual payment."""
import re
from decimal import Decimal, InvalidOperation

CONTEXT_VERSION = 'claim-context-20261010'
STAGES = r'착수금|선급금|선금|중도금|잔금|계약금(?!액)'
AGGREGATE_TYPES = {'contract', 'estimate', 'inspection_confirmation'}


def scope_in_document(text, document_type=None, has_total=False):
    kind = getattr(document_type, 'value', document_type)
    if kind in AGGREGATE_TYPES and has_total:
        return 'FULL'
    compact = '\n'.join(re.sub(r'\s+', '', line) for line in text.splitlines())
    whole = bool(re.search(r'전액청구|전체(?:계약)?금액|계약(?:금액|대금|총액)(?:의)?(?:전액|전체)청구', compact))
    part = bool(re.search(r'부분청구|분할청구', compact))
    fractions = re.findall(r'(?:착수금|선급금|선금|중도금|잔금|계약금액의)[(:：]?([0-9]+(?:\.[0-9]+)?)%[^\n]{0,24}청구', compact)
    part = part or any(Decimal(value) > 0 and Decimal(value) < 100 for value in fractions)
    if whole and part:
        return 'UNKNOWN'
    return 'FULL' if whole else 'PARTIAL' if part else 'UNKNOWN'


def extraction_context(text):
    """Keep conservative, labeled contract terms beside extraction metadata.

    No bare amount, inferred VAT, actual transfer or registered reference enters
    this pass. Legacy documents without this metadata remain explicitly unknown.
    """
    schedule = {}
    conflicts = False
    compact = re.sub(r'\s+', '', text)
    for line in text.splitlines():
        labels = list(re.finditer(STAGES, re.sub(r'\s+', '', line)))
        clean = re.sub(r'\s+', '', line)
        for index, label in enumerate(labels):
            tail = clean[label.end():labels[index+1].start() if index+1 < len(labels) else len(clean)]
            if re.match(r'[:：]?(?:없음|없이|없다|없으며|은없|을청구하지)', tail):
                continue
            ratio_match = re.search(r'([0-9]+(?:\.[0-9]+)?)%', tail)
            amounts = re.findall(r'(?<![0-9])([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)원', tail)
            # A date or a statement merely mentioning a stage is not a plan.
            if not ratio_match and not amounts:
                continue
            ratio = Decimal(ratio_match[1]) if ratio_match else None
            amount_values = {Decimal(value.replace(',', '')) for value in amounts}
            if ratio is not None and not 0 < ratio <= 100 or len(amount_values) > 1:
                conflicts = True
                continue
            stage = 'FINAL' if label[0] == '잔금' else 'INTERIM' if label[0] == '중도금' else 'ADVANCE'
            value = {'ratio': float(ratio) if ratio is not None else None,
                     'amount': float(next(iter(amount_values))) if amount_values else None}
            if stage in schedule and schedule[stage] != value:
                conflicts = True
            schedule[stage] = value
    partial_terms = any(value['ratio'] is not None and value['ratio'] < 100 for value in schedule.values())
    whole_terms = bool(re.search(r'일시지급|일괄지급|선금(?:없이|없음)|전액(?:을)?한번에(?:정산|지급)', compact))
    mode = 'CONFLICT' if conflicts or partial_terms and whole_terms else 'INSTALLMENT' if partial_terms else 'FULL' if whole_terms else 'UNKNOWN'
    stage = 'FINAL' if re.search(r'잔금|최종검수.*(?:정산|청구)', compact) else 'INTERIM' if '중도금' in compact else 'ADVANCE' if re.search(r'착수금|선급금|선금(?!없이|없음)', compact) else 'UNKNOWN'
    return {'version': CONTEXT_VERSION, 'claim_stage': stage, 'payment_mode': mode, 'schedule': schedule}


def context_for(doc):
    metadata = doc.get('fields', {}).get('extraction_metadata')
    value = metadata.get('billing_context') if isinstance(metadata, dict) else None
    return value if isinstance(value, dict) and value.get('version') == CONTEXT_VERSION else {}


def contract_terms(documents, expected):
    modes = set()
    stages = {}
    ambiguous = False
    for doc in documents:
        if doc.get('document_type') not in {'contract', 'estimate'}:
            continue
        context = context_for(doc)
        mode = context.get('payment_mode', 'UNKNOWN')
        if mode != 'UNKNOWN':
            modes.add(mode)
        schedule = context.get('schedule', {})
        if not isinstance(schedule, dict):
            ambiguous = True
            continue
        for stage, terms in schedule.items():
            try:
                if stage not in {'ADVANCE', 'INTERIM', 'FINAL'} or not isinstance(terms, dict):
                    raise ValueError('invalid stage')
                amount = Decimal(str(terms['amount'])) if terms.get('amount') is not None else None
                ratio = Decimal(str(terms['ratio'])) if terms.get('ratio') is not None else None
                if amount is not None and (not amount.is_finite() or amount < 0) or ratio is not None and (not ratio.is_finite() or not 0 < ratio <= 100):
                    raise ValueError('invalid amount or ratio')
                ratio_amount = expected * ratio / 100 if expected is not None and ratio is not None else None
                if amount is not None and ratio_amount is not None and amount != ratio_amount:
                    ambiguous = True
                value = amount if amount is not None else ratio_amount
                if value is not None:
                    stages.setdefault(stage, set()).add(value)
            except (TypeError, ValueError, InvalidOperation):
                ambiguous = True
    ambiguous = ambiguous or 'CONFLICT' in modes or len(modes) > 1 or any(len(values) > 1 for values in stages.values())
    return {'mode': next(iter(modes)) if len(modes) == 1 and not ambiguous else 'UNKNOWN',
            'stage_amounts': {stage: next(iter(values)) for stage, values in stages.items() if len(values) == 1},
            'ambiguous': ambiguous}


def invoice_scope_checks(engine, invoices, expected, documents, policy):
    checks = []
    terms = contract_terms(documents, expected)
    if terms['ambiguous'] or terms['mode'] not in {'UNKNOWN', policy.get('payment_mode', 'FULL')}:
        checks.append(engine.check('CONTRACT_PAYMENT_TERMS', 'REVIEW', 'payment_mode',
            '원문 계약 조건과 등록 지급 방식 일치', '지급 조건 확인 필요',
            '계약서·견적서의 지급 조건과 등록한 지급 방식이 다릅니다. 원문 조건과 실제 합의 내용을 확인하세요. 지급 완료 여부는 별도 기록입니다.'))
    for doc, total in invoices:
        scope = doc.get('fields', {}).get('amount_scope', 'UNKNOWN')
        stage = context_for(doc).get('claim_stage', 'UNKNOWN')
        stage_amount = terms['stage_amounts'].get(stage)
        if stage_amount is not None and total != stage_amount:
            checks.append(engine.check('PAYMENT_SCOPE', 'REVIEW', str(doc['document_id']),
                f'계약 조건의 {"잔금" if stage == "FINAL" else "중도금" if stage == "INTERIM" else "선금"} {engine.fmt(stage_amount)}',
                f'계산서 {engine.fmt(total)}',
                f'계산서는 {engine.fmt(total)}인데 계약 조건의 해당 회차는 {engine.fmt(stage_amount)}입니다. '
                '기존 청구·선금 지급 여부와 전체 금액을 합산 발행한 계산서인지 확인하세요. 잔금 문구만으로 일부 청구나 완납을 확정하지 않습니다.'))
        elif scope == 'PARTIAL' and total >= expected:
            checks.append(engine.check('PAYMENT_SCOPE', 'REVIEW', str(doc['document_id']),
                f'계약 총액 {engine.fmt(expected)}', f'계산서 {engine.fmt(total)} · 일부 청구 표시',
                '청구액이 계약 전액 이상인데 일부 청구로 표시되어 있습니다. 청구 문구와 금액 관계를 확인하세요. 지급 여부는 별도입니다.'))
        elif scope == 'FULL' and total < expected:
            checks.append(engine.check('PAYMENT_SCOPE', 'REVIEW', str(doc['document_id']),
                f'계약 총액 {engine.fmt(expected)}', f'계산서 {engine.fmt(total)} · 전액 청구 표시',
                '전액 청구 표시와 계약 총액보다 작은 청구액이 함께 있습니다. 계약 조건과 청구 금액을 확인하세요.'))
    return checks
