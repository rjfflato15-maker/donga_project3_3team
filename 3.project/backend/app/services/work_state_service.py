"""One operational projection for every screen; never mutate inference or reviews."""
from collections import defaultdict

from ..config import NTS_MODE
from ..db.models import RequestBundle, RequestBundleItem, ResubmissionRequest
from .review_summary_service import display_issue_counts, issue_card_groups
from .document_version_service import active_documents, metadata

STAGE_LABELS = {'RECEIVING': '서류 받기', 'CHECK': '확인', 'WAITING': '보완',
                'APPROVAL': '결재', 'PAYMENT': '지급', 'DONE': '끝'}


def operational_documents(contract):
    # Keep version metadata OUT of validation/fingerprint inputs. Merely adding
    # display metadata must never invalidate existing reviews or payments.
    return [{'document_id': d.document_id, 'document_type': d.document_type,
             'logical_document_id': metadata(d)['logical_document_id']}
            for d in active_documents(contract)]


def pending_keys_by_contract(db):
    rows = db.query(RequestBundle.contract_id, RequestBundleItem.issue_key).join(
        ResubmissionRequest, ResubmissionRequest.request_id == RequestBundle.request_id).join(
        RequestBundleItem, RequestBundleItem.request_id == RequestBundle.request_id).filter(
        ResubmissionRequest.status == 'WAITING_RESPONSE',
        RequestBundleItem.status == 'WAITING_RESPONSE').all()
    result = defaultdict(set)
    for cid, key in rows:
        result[cid].add(key)
    return result


def build_work_state(checks, documents, workflow, approval, waiting_count, payment=None,
                     ai_pending=0, pending_keys=()):
    """Facts remain separate: waiting, rule results, human approval and payment."""
    counts = display_issue_counts(checks)
    groups = issue_card_groups(checks, documents, nts_mode=NTS_MODE)
    by_id = {str(d['document_id']): d for d in documents}
    missing = [c.field for c in checks if c.rule_id == 'REQUIRED_DOCUMENTS'
               and c.status == 'MISSING']
    external_missing = [kind for kind in missing if kind != 'inspection_confirmation']
    immediate = []
    for c in checks:
        if c.status not in {'FAIL', 'MISSING', 'REVIEW'}:
            continue
        if NTS_MODE == 'disabled' and c.rule_id == 'BUSINESS_STATUS' and c.status == 'REVIEW':
            continue
        doc = by_id.get(str(c.field))
        key = f'missing:{c.field}' if c.rule_id == 'REQUIRED_DOCUMENTS' else (
            f'document:{doc.get("logical_document_id", doc["document_id"])}' if doc else None)
        external = c.field != 'inspection_confirmation' if c.rule_id == 'REQUIRED_DOCUMENTS' else (
            doc is not None and doc.get('document_type') not in {'inspection_confirmation', 'unknown'})
        # A mixed document's REVIEW remains internal work even when its FAIL
        # has already been requested. Legacy requests have no item linkage.
        if key in pending_keys and external and c.status in {'MISSING', 'FAIL'}:
            continue
        immediate.append(c)
    approval_status = workflow['approval_status']
    if payment and payment.get('status') == 'RECORDED' and approval_status == 'CONFIRMED':
        stage = 'DONE'
    elif approval_status == 'CONFIRMED':
        stage = 'PAYMENT'
    elif waiting_count:
        stage = 'WAITING'
    elif external_missing:
        stage = 'RECEIVING'
    elif sum(counts.values()) or ai_pending or approval_status == 'RETURNED':
        stage = 'CHECK'
    else:
        stage = 'APPROVAL'
    actions = []
    if stage not in {'PAYMENT', 'DONE'} and (immediate or ai_pending or approval_status == 'RETURNED'):
        actions.append({'role': 'operator', 'code': 'REVIEW_CURRENT_EVIDENCE',
                        'label': '현재 서류와 남은 확인 항목 처리'})
    if stage == 'APPROVAL':
        step = approval.get('next_step')
        steps = approval.get('steps') or []
        role = steps[step - 1]['role'] if step and step <= len(steps) else 'representative'
        actions.append({'role': role, 'code': 'APPROVE_CURRENT_REVISION',
                        'label': '현재 자료 검토 후 이번 단계 결재'})
    if stage == 'PAYMENT':
        reconfirm = payment and payment.get('status') == 'RECONFIRMATION_REQUIRED'
        blocked = payment.get('blocked_reason') if reconfirm else None
        if blocked == 'SOURCE_VERSION_UNVERIFIED':
            actions.append({'role': 'operator', 'code': 'RESTORE_ORIGINAL',
                            'label': '원본 복구·재등록 후 다시 결재'})
        elif blocked == 'PAYEE_OR_AMOUNT_CHANGED':
            actions.append({'role': 'operator', 'code': 'REVIEW_CHANGED_PAYMENT_SCOPE',
                            'label': '거래처·금액 변경과 기존 지급 이력 확인 · 다시 지급하지 마세요'})
        else:
            actions.append({'role': 'operator', 'code': 'RECONFIRM_PAYMENT' if reconfirm else 'RECORD_PAYMENT',
                            'label': '기존 지급 사실 재확인' if reconfirm else '전체 지급 완료 사실 기록'})
    return {'schema_version': 1, 'stage': stage, 'stage_label': STAGE_LABELS[stage],
            'revision': workflow['revision'], 'fingerprint': workflow['fingerprint'],
            'approval_status': approval_status, 'approval_next_step': approval.get('next_step'),
            'counts': {'check_items': sum(counts.values()), 'issue_cards': len(groups),
                       'missing_document_types': len(missing),
                       'missing_external_document_types': len(external_missing),
                       'waiting_requests': waiting_count, 'pending_ai_documents': ai_pending,
                       'immediate_check_items': len(immediate)},
            'next_actions': actions, 'waiting_for': ['VENDOR'] if waiting_count else [],
            'payment_already_recorded': bool(payment and payment.get('recorded_paid_on')),
            'payment_blocked_reason': payment.get('blocked_reason') if payment else None,
            'rule_results_are_human_confirmation': False,
            'basis': 'CURRENT_SAVED_FIELDS_AND_CURRENT_REVIEW'}
