"""Bundle existing checks into manual request records; never re-extract or send."""
import hashlib
import json
from datetime import datetime, timezone

from fastapi import HTTPException

from ..db.models import (Contract, Document, DocumentFileInfo, ResubmissionRequest,
                         RequestBundle, RequestBundleItem, AuditEvent)
from ..schemas.common import DOCUMENT_TYPE_KOREAN, DocumentType
from ..config import NTS_MODE
from .contract_service import ContractService
from .review_context_service import request_response
from .storage_service import STORAGE_LOCK, resolve_path
from .workflow_service import policy_for, fingerprint_for


def require_contract(db, contract_id):
    contract = db.get(Contract, contract_id)
    if not contract:
        raise HTTPException(404, '계약을 찾을 수 없습니다.')
    return contract


def live_guard(db, contract_id, revision, fingerprint):
    contract = require_contract(db, contract_id)
    inputs = ContractService().pipeline_service.validation_inputs(db, contract)
    if policy_for(db, contract_id)['revision'] != revision or fingerprint_for(db, contract, inputs) != fingerprint:
        raise HTTPException(409, '계약 자료가 변경되었습니다. 최신 자료에서 요청 항목을 다시 확인하세요.')


def source_verified(db, document_id):
    row = db.get(Document, document_id)
    info = db.get(DocumentFileInfo, document_id)
    if not row:
        return False
    path = resolve_path(row.storage_path)
    verified = False
    if path and info:
        try:
            with path.open('rb') as stream:
                verified = hashlib.file_digest(stream, 'sha256').hexdigest() == info.sha256
        except OSError:
            pass
    return verified


def source_snapshot(db, doc):
    info = db.get(DocumentFileInfo, doc.document_id)
    return {'document_id': doc.document_id, 'document_type': doc.document_type.value,
            'file_name': doc.original_file_name, 'version': doc.version,
            'source_sha256': info.sha256 if info else None, 'source_version_verified': source_verified(db, doc.document_id),
            'fields': doc.analysis.fields.model_dump(mode='json')}


def pending_items(db, contract_id):
    rows = (db.query(RequestBundleItem, RequestBundle).join(RequestBundle,
        RequestBundle.request_id == RequestBundleItem.request_id)
        .filter(RequestBundle.contract_id == contract_id, RequestBundleItem.status == 'WAITING_RESPONSE')
        .order_by(RequestBundleItem.item_id).all())
    return [{'request_id': item.request_id, 'item_id': item.item_id, 'issue_key': item.issue_key,
             'request_revision': bundle.request_revision, 'document_id': item.document_id,
             'title': item.title, 'status': item.status} for item, bundle in rows]


def bundle_context(db, contract_id):
    detail = ContractService().get_contract_detail(db, contract_id)
    if not detail:
        raise HTTPException(404, '계약을 찾을 수 없습니다.')
    required = [kind.value for kind in detail.required_document_types]
    received = {doc.document_type.value for doc in detail.documents}
    missing = [kind for kind in required if kind not in received]
    pending = pending_items(db, contract_id)
    vendors, internal, reading, notices = [], [], [], []
    doc_by_id = {str(doc.document_id): doc for doc in detail.documents}
    checks_by_document = {key: [] for key in doc_by_id}
    for check in detail.checks:
        if check.status.value not in {'FAIL', 'MISSING', 'REVIEW'}:
            continue
        data = check.model_dump(mode='json')
        if check.rule_id == 'BUSINESS_STATUS' and check.status.value == 'REVIEW' and NTS_MODE == 'disabled':
            notices.append({'rule_id': check.rule_id, 'message': check.message, 'requires_action': False})
        elif check.rule_id == 'REQUIRED_DOCUMENTS' and check.field in missing:
            kind = check.field
            label = DOCUMENT_TYPE_KOREAN[DocumentType(kind)]
            item = {'issue_key': f'missing:{kind}', 'title': f'{label} 제출 요청',
                    'document_type': kind, 'document_id': None,
                    'reason': f'{label} 제출이 필요합니다.', 'checks': [data],
                    'requires_original_review': False,
                    'snapshot': {'checks': [data], 'missing_document_type': kind}}
            (internal if kind == 'inspection_confirmation' else vendors).append(item)
        elif check.field in doc_by_id:
            checks_by_document[check.field].append(data)
        else:
            internal.append({'issue_key': f'contract:{check.rule_id}:{check.field}',
                'title': '계약 기준 확인', 'document_type': None, 'document_id': None,
                'reason': check.message, 'checks': [data], 'requires_original_review': False,
                'requires_action': check.rule_id != 'BUSINESS_STATUS', 'snapshot': {'checks': [data]}})
    for key, checks in checks_by_document.items():
        if not checks:
            continue
        doc = doc_by_id[key]
        snapshot = source_snapshot(db, doc)
        label = DOCUMENT_TYPE_KOREAN[doc.document_type]
        issue_key = f'document:{doc.version.get("logical_document_id", doc.document_id)}'
        invalid = (not doc.file_available or not snapshot['source_version_verified'] or
                   doc.processing_status.value == 'FAILED' or doc.document_type in
                   {DocumentType.UNKNOWN, DocumentType.INSPECTION_CONFIRMATION} or
                   any(c['rule_id'] in {'ORIGINAL_FILE', 'DOCUMENT_PROCESSING', 'DOCUMENT_TYPE'} for c in checks))
        if invalid:
            if not snapshot['source_version_verified'] and not any(c['rule_id'] == 'ORIGINAL_FILE' for c in checks):
                checks = [*checks, {'rule_id': 'SOURCE_VERSION', 'status': 'REVIEW', 'field': key,
                    'expected': '등록 당시 원문', 'actual': '원문 해시 확인 불가',
                    'message': '원본과 등록 해시를 확인한 후 거래처 요청 여부를 결정하세요.'}]
            internal.append({'issue_key': issue_key, 'title': f'{label} 내부 확인',
                'document_type': doc.document_type.value, 'document_id': doc.document_id,
                'reason': '\n'.join(c['message'] for c in checks), 'checks': checks,
                'requires_original_review': False, 'snapshot': {'checks': checks, 'document': snapshot}})
            continue
        failures = [c for c in checks if c['status'] == 'FAIL' and c['rule_id'] not in
                    {'ORIGINAL_FILE', 'DOCUMENT_PROCESSING', 'DOCUMENT_TYPE', 'AMOUNT_EXTRACTION', 'BUSINESS_STATUS'}]
        reviews = [c for c in checks if c['status'] == 'REVIEW']
        if failures:
            vendors.append({'issue_key': issue_key, 'title': f'{label} 보완 요청',
                'document_type': doc.document_type.value, 'document_id': doc.document_id,
                'reason': '\n'.join(c['message'] for c in failures), 'checks': failures,
                'requires_original_review': True, 'snapshot': {'checks': failures, 'document': snapshot}})
        if reviews:
            reading.append({'issue_key': issue_key, 'title': f'{label} 원문 확인',
                'document_type': doc.document_type.value, 'document_id': doc.document_id,
                'reason': '\n'.join(c['message'] for c in reviews), 'checks': reviews,
                'requires_original_review': False, 'snapshot': {'checks': reviews, 'document': snapshot}})
    for candidate in vendors:
        candidate['pending_items'] = [item for item in pending if item['issue_key'] == candidate['issue_key']]
        candidate['already_requested'] = bool(candidate['pending_items'])
    legacy_count = db.query(ResubmissionRequest).outerjoin(RequestBundle,
        RequestBundle.request_id == ResubmissionRequest.request_id).filter(
            ResubmissionRequest.contract_id == contract_id, ResubmissionRequest.status == 'WAITING_RESPONSE',
            RequestBundle.request_id.is_(None)).count()
    return {'contract_id': contract_id, 'revision': detail.workflow['revision'],
        'fingerprint': detail.workflow['fingerprint'], 'required_document_types': required,
        'received_document_types': [kind for kind in required if kind in received],
        'document_counts': {'required': len(required), 'received': len(set(required) & received), 'missing': len(missing)},
        'vendor_candidates': vendors, 'internal_items': internal, 'reading_items': reading,
        'notices': notices, 'pending_items': pending, 'legacy_pending_request_count': legacy_count}


def payload_hash(req):
    payload = req.model_dump(mode='json')
    # Omitted requested_on means the server's day of first creation. The same
    # submitted body must replay successfully even after midnight.
    if 'requested_on' not in req.model_fields_set:
        payload['requested_on'] = None
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


def audit_row(actor, action, contract_id, details):
    return AuditEvent(actor_id=actor.user_id, actor_name=actor.display_name, action=action,
        contract_id=contract_id, details=json.dumps(details, ensure_ascii=False),
        created_at=datetime.now(timezone.utc).replace(tzinfo=None))


def replay(db, contract_id, req, actor, digest):
    existing = db.query(RequestBundle).filter_by(contract_id=contract_id, actor_id=actor.user_id,
        idempotency_key=req.idempotency_key).first()
    if not existing:
        return None
    if existing.payload_sha256 != digest:
        raise HTTPException(409, '같은 요청 키에 다른 내용이 있습니다. 새 요청 키를 사용하세요.')
    return request_response(db.get(ResubmissionRequest, existing.request_id))


def create_bundle(db, contract_id, req, actor):
    digest = payload_hash(req)
    db.rollback()
    with STORAGE_LOCK:
        db.expire_all()
        require_contract(db, contract_id)
        existing = replay(db, contract_id, req, actor, digest)
        if existing is not None:
            return existing, False
        if req.due_on and req.due_on < req.requested_on:
            raise HTTPException(422, '기한은 요청일보다 빠를 수 없습니다.')
    # Calculate current checks outside the publication lock; mutation below
    # checks that this snapshot and the submitted revision are still current.
    context = bundle_context(db, contract_id)
    if context['revision'] != req.revision or context['fingerprint'] != req.fingerprint:
        raise HTTPException(409, '계약 자료가 변경되었습니다. 최신 요청 항목을 다시 확인하세요.')
    candidates = {item['issue_key']: item for item in context['vendor_candidates']}
    selected = []
    for requested in req.items:
        candidate = candidates.get(requested.issue_key)
        if candidate is None:
            raise HTTPException(400, '현재 거래처 요청 후보에 없는 항목입니다. 사내 확인·판독 항목은 요청에 포함할 수 없습니다.')
        if candidate['requires_original_review'] and not requested.reviewed_original:
            raise HTTPException(400, '번호·금액 불일치는 원문을 직접 대조했음을 확인한 후 요청하세요.')
        selected.append(candidate)
    db.rollback()
    with STORAGE_LOCK:
        db.expire_all()
        existing = replay(db, contract_id, req, actor, digest)
        if existing is not None:
            return existing, False
        live_guard(db, contract_id, req.revision, req.fingerprint)
        # Original bytes are immutable, but an external deletion/change does
        # not always change the saved-field fingerprint. Recheck SHA here.
        for candidate in selected:
            if candidate['document_id'] is not None:
                if not source_verified(db, candidate['document_id']):
                    raise HTTPException(409, '원본이 변경되거나 없어졌습니다. 원문을 다시 확인하세요.')
        waiting_keys = {item['issue_key'] for item in pending_items(db, contract_id)}
        if waiting_keys & {item['issue_key'] for item in selected}:
            raise HTTPException(409, '이미 답을 기다리는 요청 항목이 있습니다. 기존 요청의 회신·취소를 먼저 기록하세요.')
        try:
            row = ResubmissionRequest(contract_id=contract_id, contact_method=req.contact_method,
                requested_on=req.requested_on.isoformat(), due_on=req.due_on.isoformat() if req.due_on else None,
                memo=req.memo, status='WAITING_RESPONSE', actor_id=actor.user_id, actor_name=actor.display_name)
            db.add(row)
            db.flush()
            bundle = RequestBundle(request_id=row.request_id, contract_id=contract_id, actor_id=actor.user_id,
                contract_revision=req.revision, contract_fingerprint=req.fingerprint, request_revision=1,
                idempotency_key=req.idempotency_key, payload_sha256=digest)
            bundle.items = [RequestBundleItem(issue_key=item['issue_key'], title=item['title'],
                document_type=item['document_type'], document_id=item['document_id'], reason=item['reason'],
                snapshot_json=json.dumps(item['snapshot'], ensure_ascii=False), status='WAITING_RESPONSE') for item in selected]
            row.bundle = bundle
            db.add(audit_row(actor, 'RESUBMISSION_BUNDLE_RECORDED', contract_id,
                {'request_id': row.request_id, 'issue_keys': [item['issue_key'] for item in selected],
                 'revision': req.revision, 'contact_method': req.contact_method}))
            db.commit()
            return request_response(row), True
        except Exception:
            db.rollback()
            raise


def resolve_items(db, contract_id, request_id, req, actor):
    db.rollback()
    with STORAGE_LOCK:
        db.expire_all()
        live_guard(db, contract_id, req.revision, req.fingerprint)
        row = db.get(ResubmissionRequest, request_id)
        if not row or row.contract_id != contract_id or row.bundle is None:
            raise HTTPException(404, '이 계약의 묶음 요청 기록을 찾을 수 없습니다.')
        bundle = row.bundle
        if bundle.request_revision != req.request_revision:
            raise HTTPException(409, '다른 사용자가 회신 기록을 변경했습니다. 최신 요청을 다시 확인하세요.')
        items = {item.item_id: item for item in bundle.items}
        for change in req.items:
            if change.item_id not in items:
                raise HTTPException(404, '이 요청에 속한 항목을 찾을 수 없습니다.')
            if items[change.item_id].status != 'WAITING_RESPONSE':
                raise HTTPException(409, '이미 회신 처리하거나 취소한 항목은 변경할 수 없습니다.')
        try:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            for change in req.items:
                item = items[change.item_id]
                item.status, item.resolution_note, item.resolved_at = change.status, change.note, now
            bundle.request_revision += 1
            if not any(item.status == 'WAITING_RESPONSE' for item in bundle.items):
                row.status = 'RECEIVED' if any(item.status == 'RECEIVED' for item in bundle.items) else 'CANCELLED'
                row.resolved_at = now
                row.resolution_note = '\n'.join(f'{item.title}: {item.resolution_note}' for item in bundle.items)
            db.add(audit_row(actor, 'RESUBMISSION_BUNDLE_ITEMS_RESOLVED', contract_id,
                {'request_id': request_id, 'request_revision': bundle.request_revision,
                 'items': [change.model_dump(mode='json') for change in req.items]}))
            db.commit()
            return request_response(row)
        except Exception:
            db.rollback()
            raise
