"""Verified code-owned facts and placeholders; free-form model claims are excluded."""
from decimal import Decimal
from string import Formatter
from collections import Counter
from .readonly_review_service import snapshot, require_unchanged
from .review_summary_service import display_issue_counts

TEMPLATES={
    'brief':"{vendor_name}의 ‘{title}’ 계약입니다. 등록 기준금액은 {contract_amount}원({amount_basis})입니다. 필수 서류 {required_document_count}종 중 {submitted_document_count}종이 있고, 확인할 항목은 {open_issue_count}건입니다. 결재 상태: {approval_status}.",
    'detail':"‘{title}’의 계약 상대자는 {vendor_name}입니다. 계약에 등록한 금액은 {contract_amount}원이며 기준은 {amount_basis}입니다. 서류 현황은 {submitted_document_count}/{required_document_count}종, 확인할 항목은 {open_issue_count}건, 결재 상태는 {approval_status}입니다."
}


def amount_display(value):
    result=format(Decimal(str(value)),',f')
    return result.rstrip('0').rstrip('.') if '.' in result else result


def render_template(template,facts):
    if template not in TEMPLATES.values():raise ValueError('UNVERIFIED_SUMMARY_TEMPLATE')
    tokens=[]
    for literal,field,format_spec,conversion in Formatter().parse(template):
        if field is not None:
            if format_spec or conversion or field not in facts:raise ValueError('INVALID_SUMMARY_PLACEHOLDER')
            tokens.append(field)
        if any(char.isdigit() for char in literal):raise ValueError('MODEL_LITERAL_NUMBERS_FORBIDDEN')
    if Counter(tokens)!=Counter(facts.keys()):raise ValueError('MISSING_OR_DUPLICATE_SUMMARY_PLACEHOLDER')
    return template.format_map(facts)


def contract_summary(db,cid,style='brief',revision=None):
    data=snapshot(db,cid,revision)
    summary=data['summary'];reference=data['reference']
    facts={'vendor_name':reference['vendor_name'],'title':reference['title'],
           'contract_amount':amount_display(reference['contract_amount']),
           'amount_basis':{'TOTAL':'부가세 포함 합계','SUPPLY':'공급가액','UNKNOWN':'부가세 포함 여부 확인 필요'}[data['policy']['amount_basis']],
           'required_document_count':str(summary.required_document_count),'submitted_document_count':str(summary.submitted_document_count),
           'open_issue_count':str(sum(display_issue_counts(data['checks']).values())),
           'approval_status':{'CONFIRMED':'최종 확인 완료','RETURNED':'보완 요청','STALE':'자료 변경으로 재확인 필요','PENDING':'최종 확인 대기'}.get(data['workflow']['approval_status'],'확인 필요')}
    template=TEMPLATES[style]
    text=render_template(template,facts)
    require_unchanged(db,data)
    return {'contract_id':cid,'revision':data['revision'],'fingerprint':data['fingerprint'],'text':text,'style':style,
            'facts':facts,'template':template,'numeric_placeholders_verified':True,'llm_used':False,
            'sources':{'contract_amount':'등록한 계약 기준금액','document_counts':'현재 활성 문서의 종류 수','open_issue_count':'현재 규칙 결과, 국세청 disabled 항목 제외','approval_status':'현재 revision/fingerprint의 대표 확인 기록'}}
