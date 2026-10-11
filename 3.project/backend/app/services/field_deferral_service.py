"""Review follow-up notes, bound to one version/value; never approve or change values.

kind=DEFER is "decide later"; kind=NO_ISSUE records a person's judgement that the remaining
automatic check is not an error. Neither changes the check result or the approval requirement."""
import json
from datetime import timezone

from ..db.models import AuditEvent, DocumentFileInfo
from ..schemas.document import AnalysisFields

ACTIONS = ('FIELD_DEFERRED', 'FIELD_DEFERRAL_CLEARED', 'EXTRACT_CORRECTED')
DOCUMENT_SCOPE = '__document__'


def current_deferrals(db, document_id, stored=None):
    values = AnalysisFields(**(stored or {})).model_dump()
    info = db.get(DocumentFileInfo, document_id)
    source_hash = info.sha256 if info else None
    decisions = {}
    events = db.query(AuditEvent).filter(AuditEvent.document_id == document_id,
        AuditEvent.action.in_(ACTIONS)).order_by(AuditEvent.event_id.desc()).all()
    for event in events:
        try:
            data = json.loads(event.details)
        except (ValueError, TypeError):
            continue
        if not isinstance(data, dict):
            continue
        if event.action == 'EXTRACT_CORRECTED':
            named = data.get('confirmed_fields') or data.get('changed_fields') or []
            for key in named:
                decisions.setdefault(key, None)
            # A changed document type invalidates document-level follow-up too.
            if data.get('changed_fields') or data.get('previous_document_type') != data.get('new_document_type'):
                decisions.setdefault(DOCUMENT_SCOPE, None)
            continue
        key = data.get('field')
        if key not in values and key != DOCUMENT_SCOPE:
            continue
        if key in decisions:
            continue
        decisions[key] = None if event.action == 'FIELD_DEFERRAL_CLEARED' else {
            **data, 'actor_id': event.actor_id, 'actor_name': event.actor_name,
            'at': event.created_at.replace(tzinfo=timezone.utc).isoformat(),
        }
    result = {}
    from .field_confirmation_service import contract_basis
    basis=contract_basis(db,document_id)
    for key, item in decisions.items():
        if not item or item.get('source_sha256') != source_hash:
            continue
        if item.get('kind')=='NO_ISSUE' and item.get('basis')!=basis:
            continue
        expected = values if key == DOCUMENT_SCOPE else values.get(key)
        if item.get('value') != expected:
            continue
        result[key] = {**{name: item[name] for name in ('note', 'actor_id', 'actor_name', 'at')},
                       'kind': item.get('kind') or 'DEFER'}
    return result


def deferral_details(db, doc, field, note, kind='DEFER'):
    values = AnalysisFields(**json.loads(doc.extract.raw_fields or '{}') if doc.extract else {}).model_dump()
    info = db.get(DocumentFileInfo, doc.document_id)
    from .field_confirmation_service import contract_basis
    return {'field': field, 'note': note, 'value': values if field == DOCUMENT_SCOPE else values[field],
        'source_sha256': info.sha256 if info else None, 'kind': kind,'basis':contract_basis(db,doc.document_id)}


# 검사 규칙별로 사람이 원문에서 판단하는 항목. 화면의 확인 항목 연결과 같은 기준이다.
CHECK_FIELDS = {
    'BUSINESS_NO_MATCH': ['business_registration_no'], 'ACCOUNT_HOLDER_MATCH': ['company_name'],
    'AMOUNT_COMPONENTS': ['supply_amount', 'tax_amount', 'total_amount'],
    'AMOUNT_EXTRACTION': ['supply_amount', 'tax_amount', 'total_amount', 'amount'],
    'AMOUNT_MATCH_ESTIMATE': ['total_amount', 'amount'], 'AMOUNT_MATCH_TAX_INVOICE': ['total_amount', 'amount_scope'],
    'PAYMENT_SCOPE': ['amount_scope', 'total_amount'], 'INSTALLMENT_TOTAL': ['total_amount', 'amount_scope'],
}


def unsettled_checks(db, documents, checks):
    """Checks still needing work after a person recorded "no issue" for the item.

    Only used for to-do counts and stage. The automatic results, the approval summary and the
    representative's acknowledgement of unverified checks are unchanged."""
    marked = {}
    for doc in documents:
        stored = json.loads(doc.extract.raw_fields or '{}') if doc.extract else {}
        notes = {k for k, v in current_deferrals(db, doc.document_id, stored).items() if v.get('kind') == 'NO_ISSUE'}
        if notes:
            marked[doc.document_id] = notes
    if not marked:
        return list(checks)
    result = []
    for check in checks:
        fields = CHECK_FIELDS.get(check.rule_id)
        targets = [d for d in documents if str(d.document_id) == check.field] or (
            [d for d in documents if getattr(d.document_type, 'value', d.document_type) == 'tax_invoice'] if check.rule_id in {'INSTALLMENT_TOTAL', 'PAYMENT_SCOPE'} else [])
        settled = (getattr(check.status, 'value', check.status) != 'PASS' and fields and targets
                   and all(marked.get(d.document_id, set()) & set(fields) for d in targets))
        if not settled:
            result.append(check)
    return result
