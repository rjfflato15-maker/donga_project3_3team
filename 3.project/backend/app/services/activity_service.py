"""Readable, paginated stored activity. Missing historical evidence stays missing."""
import json
from datetime import timezone

from fastapi import HTTPException

from ..db.models import AuditEvent, Contract, ContractReview, Document, RequestBundle, RequestBundleItem
from .contract_export_service import collect_sensitive, public_data
from .workflow_service import policy_for, fingerprint_for
from .pipeline_service import PipelineService
from .readonly_review_service import require_unchanged

TITLES = {
    'CONTRACT_CREATED': '계약 등록', 'CONTRACT_UPDATED': '계약 기준 수정',
    'DOCUMENT_UPLOAD': '서류 등록', 'DOCUMENT_REISSUED': '고친 본 등록',
    'DOCUMENT_DELETE': '현재 서류 삭제', 'ORIGINAL_RESTORED': '원본 복구',
    'EXTRACT_CORRECTED': '원문 확인·읽은 값 수정', 'RULE_VALIDATION': '자동 검사 결과 기록',
    'RESUBMISSION_REQUEST_RECORDED': '거래처 요청 기록',
    'RESUBMISSION_REQUEST_RESOLVED': '거래처 회신·취소 기록',
    'RESUBMISSION_BUNDLE_RECORDED': '묶음 요청 기록',
    'RESUBMISSION_BUNDLE_ITEMS_RESOLVED': '요청 항목 회신·취소 기록',
    'APPROVAL_FIRST_STAGE': '담당 검토 결재',
    'REPRESENTATIVE_CONFIRMED': '대표 최종 결재',
    'REPRESENTATIVE_RETURNED': '대표 반려',
    'PAYMENT_RECORDED': '전체 지급 사실 기록', 'PAYMENT_RECONFIRMED': '기존 지급 재확인',
    'ASSIGNMENT_CREATED': '사내 담당자에게 맡김', 'ASSIGNMENT_CHANGED': '맡기기 변경',
}


def current_basis(db, cid, revision=None, fingerprint=None):
    contract = db.get(Contract, cid)
    if not contract:
        raise HTTPException(404, '계약을 찾을 수 없습니다.')
    live_revision = policy_for(db, cid)['revision']
    digest = fingerprint_for(db, contract, PipelineService().validation_inputs(db, contract))
    if revision is not None and revision != live_revision or fingerprint is not None and fingerprint != digest:
        raise HTTPException(409, '계약 자료가 변경되었습니다. 최신 자료를 다시 불러오세요.')
    return {'contract_id': cid, 'revision': live_revision, 'fingerprint': digest}


def activity(db, cid, *, limit=50, before_event_id=None, masked=True, revision=None, fingerprint=None):
    basis = current_basis(db, cid, revision, fingerprint)
    contract = db.get(Contract, cid)
    # Include all this contract's historical values for free-text masking,
    # even if the sensitive value is found on a different pagination page.
    all_events = db.query(AuditEvent).filter_by(contract_id=cid)
    sensitive = {'vendor_name': contract.vendor_name, 'business_number': contract.business_number}
    for (raw,) in db.query(AuditEvent.details).filter_by(contract_id=cid):
        try:
            collect_sensitive(json.loads(raw or '{}'), sensitive)
        except (ValueError, TypeError):
            pass
    for doc in db.query(Document).filter_by(contract_id=cid):
        for raw in [doc.extract.raw_fields if doc.extract else '{}',
                    doc.version.initial_fields_json if doc.version else '{}']:
            try:
                collect_sensitive(json.loads(raw or '{}'), sensitive)
            except (ValueError, TypeError):
                pass
    historical_snapshots = [raw for (raw,) in db.query(ContractReview.snapshot_json).filter_by(contract_id=cid)]
    historical_snapshots += [raw for (raw,) in db.query(RequestBundleItem.snapshot_json).join(
        RequestBundle, RequestBundle.request_id == RequestBundleItem.request_id).filter(
        RequestBundle.contract_id == cid)]
    for raw in historical_snapshots:
        try:
            collect_sensitive(json.loads(raw or '{}'), sensitive)
        except (ValueError, TypeError):
            pass
    query = all_events.filter(AuditEvent.action.in_(TITLES))
    if before_event_id is not None:
        query = query.filter(AuditEvent.event_id < before_event_id)
    rows = query.order_by(AuditEvent.event_id.desc()).limit(limit + 1).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = []
    for row in rows:
        try:
            data = json.loads(row.details or '{}')
            available = isinstance(data, dict)
        except (ValueError, TypeError):
            data, available = {}, False
        if not available:
            data = {}
        items.append({'event_id': row.event_id, 'type': row.action, 'title': TITLES[row.action],
            'occurred_at': row.created_at.replace(tzinfo=timezone.utc).isoformat(),
            'actor_id': row.actor_id, 'actor_name': row.actor_name,
            'document_id': row.document_id, 'revision': data.get('revision'),
            'request_id': data.get('request_id'), 'review_id': data.get('review_id'),
            'details_available': available, 'data': data})
    result = {**basis, 'order': 'EVENT_ID_DESC', 'masked': masked, 'items': items,
              'has_more': has_more, 'next_before_event_id': rows[-1].event_id if has_more else None,
              'recorded_facts_only': True,
              'limitations': ['과거에 기록되지 않은 사실은 추정해서 채우지 않습니다.',
                              '자동 검사 기록은 원문 사람 확인이나 국세청 진위 조회를 뜻하지 않습니다.']}
    protected = public_data(result, masked, sensitive)
    # This authenticated company timeline must identify who performed an action.
    # Restore only the stored actor column, never actor-like keys in free text or
    # event details. Export masking keeps its separate, unchanged privacy policy.
    for item, row in zip(protected['items'], rows):
        item['actor_name'] = row.actor_name
    require_unchanged(db, basis)
    return protected
