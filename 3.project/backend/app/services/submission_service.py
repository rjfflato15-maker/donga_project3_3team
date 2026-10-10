"""Operator review and submission, separate from inference and final approval.

Persist in the existing append-only audit log so upgrading does not rewrite
customer data, policy, schema, or completed approvals. Each submission binds to
the saved revision, evidence fingerprint, and the final-review cycle.
"""
import hashlib
import json

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..db.models import AuditEvent, ApprovalSignoff, DocumentFileInfo, ResubmissionRequest
from ..schemas.document import AnalysisFields
from .company_policy_service import company_policy, current_cycle, first_signoff
from .document_version_service import active_documents
from .field_confirmation_service import current_confirmations
from .field_deferral_service import current_deferrals, unsettled_checks
from .storage_service import STORAGE_LOCK, resolve_path

FIELD_LABELS = {'company_name': '업체명', 'business_registration_no': '사업자번호',
                'account_number': '계좌번호', 'bank_name': '은행명', 'amount': '금액',
                'total_amount': '합계금액', 'supply_amount': '공급가액',
                'tax_amount': '세액', 'amount_scope': '청구 범위'}
DOC_LABELS = {'contract': '계약서', 'estimate': '견적서', 'business_registration': '사업자등록증',
              'bank_account': '통장사본', 'tax_invoice': '세금계산서',
              'inspection_confirmation': '검수확인서', 'unknown': '종류 미확인 서류'}


class SubmissionRequest(BaseModel):
    review_cycle: int = Field(default=0, ge=0, strict=True)
    revision: int = Field(ge=1, strict=True)
    fingerprint: str = Field(min_length=64, max_length=64)
    idempotency_key: str = Field(min_length=8, max_length=100)
    note: str = Field(min_length=3, max_length=2000)
    exception_reason: str = Field(default='', max_length=2000)
    acknowledge_exception: bool = False
    exception_items: list[str] = Field(default_factory=list, max_length=100)
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


def check_key(check):
    return f'{check.rule_id}:{check.field}'


def latest_submission(db, contract_id, key=None):
    query = db.query(AuditEvent).filter_by(contract_id=contract_id, action='CONTRACT_SUBMITTED')
    if key:
        query = query.filter(AuditEvent.details.contains('"idempotency_key": ' + json.dumps(key)))
    return query.order_by(AuditEvent.event_id.desc()).first()


def submission_state(db, contract_id, workflow, gate=None):
    row = latest_submission(db, contract_id)
    data = json.loads(row.details) if row else {}
    current = bool(row and data.get('revision') == workflow['revision']
                   and data.get('fingerprint') == workflow['fingerprint']
                   and data.get('cycle_review_id') == current_cycle(db, contract_id))
    if gate is not None:
        current = current and data.get('gate_fingerprint') == gate['fingerprint'] and not gate['blockers']
    status = ('APPROVED' if workflow['approval_status'] == 'CONFIRMED' else
              'SUBMITTED' if current else 'RETURNED' if workflow['approval_status'] == 'RETURNED'
              else 'STALE' if row else 'NOT_SUBMITTED')
    return {'status': status, 'current': current, 'event_id': row.event_id if row else None,
            'actor_name': row.actor_name if row else None,
            'submitted_at': row.created_at.isoformat() if row else None,
            'note': data.get('note'), 'exception_reason': data.get('exception_reason'),
            'exception_items': data.get('exception_items') or [],
            'gate': gate, 'next_owner': 'representative' if current else 'operator',
            'legacy_completed_approval': status == 'APPROVED' and not row}


def review_gate(db, contract, checks, document_responses=()):
    """No raw customer values in the gate; expose target, reason and action only."""
    blockers = []
    responses = {d.document_id: d for d in document_responses}
    def block(code, reason, action, doc=None, field=None):
        kind = getattr(doc.document_type, 'value', doc.document_type) if doc else None
        blockers.append({'code': code, 'document_id': doc.document_id if doc else None,
                         'document_type': kind, 'field': field,
                         'label': f'{DOC_LABELS.get(kind, "계약")} · {FIELD_LABELS.get(field, "원문")}',
                         'reason': reason, 'action': action, 'owner': 'operator'})
    for check in checks:
        if check.rule_id == 'REQUIRED_DOCUMENTS' and check.status == 'MISSING':
            block('MISSING_DOCUMENT', f'{DOC_LABELS.get(check.field, check.field)} 미등록 상태입니다.', '서류 받기·보완 요청')
            blockers[-1].update(document_type=check.field, label=DOC_LABELS.get(check.field, check.field))
    documents = active_documents(contract)
    if not documents and not blockers:
        block('MISSING_DOCUMENT', '검토할 서류가 없습니다.', '서류 등록')
    bindings = []
    for doc in documents:
        response = responses.get(doc.document_id)
        path = resolve_path(doc.storage_path)
        info = db.get(DocumentFileInfo, doc.document_id)
        verified = False
        try:
            if path and info:
                with path.open('rb') as stream:
                    verified = hashlib.file_digest(stream, 'sha256').hexdigest() == info.sha256
        except OSError:
            pass
        if (response and not response.file_available) or not verified:
            block('SOURCE_UNVERIFIED', '원본이 없거나 등록한 원본과 다릅니다.', '원본 복구·재등록', doc)
            continue
        if str(getattr(doc.processing_status, 'value', doc.processing_status)) in {'FAILED', 'UPLOADED', 'PREPROCESSING', 'ANALYZING'} or not doc.extract or doc.extract.extracted_status == 'FAILED':
            block('READING_FAILED', '서류를 읽지 못했거나 처리가 끝나지 않았습니다.', '판독 상태 확인·읽을 수 있는 수정본 등록', doc)
            continue
        if getattr(doc.document_type, 'value', doc.document_type) == 'unknown':
            block('DOCUMENT_TYPE_UNKNOWN', '서류 종류를 확인하지 못했습니다.', '원문 확인 후 서류 종류 정정', doc)
        stored = json.loads(doc.extract.raw_fields or '{}')
        extraction = stored.get('extraction_metadata') or {}
        if extraction.get('evidence_complete') is False:
            block('READING_INCOMPLETE', 'PDF 일부 페이지를 읽지 못해 전체 근거를 확인할 수 없습니다.', '읽을 수 있는 수정본 등록·전체 재판독', doc)
            continue
        values = AnalysisFields(**stored).model_dump()
        proofs = current_confirmations(db, doc.document_id, stored)
        decisions = current_deferrals(db, doc.document_id, stored)
        bindings.append({'document_id': doc.document_id, 'confirmations': proofs, 'decisions': decisions})
        for field, decision in decisions.items():
            if decision.get('kind') != 'NO_ISSUE':
                block('DECISION_DEFERRED', '담당자 판단을 보류한 항목입니다.', '판단·보완 조치 완료 후 보류 해제', doc, field)
        fields = {'company_name', 'business_registration_no'}
        kind = getattr(doc.document_type, 'value', doc.document_type)
        if kind == 'bank_account':
            fields |= {'account_number', 'bank_name'}
        if kind in {'contract', 'estimate', 'tax_invoice'}:
            fields |= {'total_amount' if values.get('total_amount') is not None else 'amount'}
        if kind == 'tax_invoice':
            fields |= {'supply_amount', 'tax_amount', 'amount_scope'}
        ai = stored.get('ai_review') or {}
        fields |= set(ai.get('targets') or []) & set(FIELD_LABELS)
        for field in sorted(fields):
            if field not in values or values[field] is None or values[field] == '':
                continue  # Missing/unusable values stay in the rule results below.
            if field not in proofs:
                block('HUMAN_REVIEW_REQUIRED', '자동으로 읽은 값을 담당자가 아직 원문과 대조하지 않았습니다.', '원문 대조·값 확인 또는 오독 정정', doc, field)
    waiting = db.query(ResubmissionRequest).filter_by(contract_id=contract.contract_id, status='WAITING_RESPONSE').count()
    if waiting:
        block('WAITING_VENDOR', f'거래처 회신 대기 요청이 {waiting}건 남았습니다.', '받은 항목만 수령 기록·재검사, 미회신은 계속 대기')
    unsettled = unsettled_checks(db, documents, checks)
    from ..config import NTS_MODE
    exceptions = [{'key': check_key(c), 'rule_id': c.rule_id, 'document_id': int(c.field) if c.field.isdigit() else None,
                   'reason': c.message, 'status': getattr(c.status, 'value', c.status)}
                  for c in unsettled if c.status in {'FAIL', 'REVIEW'}
                  and not (c.rule_id == 'BUSINESS_STATUS' and NTS_MODE == 'disabled')]
    exceptions = list({item['key']: item for item in exceptions}.values())
    binding = {'cycle': current_cycle(db, contract.contract_id), 'review': bindings, 'blockers': blockers, 'exceptions': exceptions}
    digest = hashlib.sha256(json.dumps(binding, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()
    return {'blockers': blockers, 'exception_items': exceptions, 'fingerprint': digest,
            'can_submit': not blockers and not exceptions,
            'can_submit_exception': not blockers and bool(exceptions),
            'completion': '필수 원본·담당자 원문 대조·회신 처리를 끝내고 검토 의견을 기록하면 대표에게 상신합니다.'}


def require_current_submission(db, contract_id, workflow):
    state = submission_state(db, contract_id, workflow, (workflow.get('submission') or {}).get('gate'))
    if not state['current']:
        raise HTTPException(409, '담당자가 현재 자료의 검토를 완료하고 결재 상신해야 합니다. 반려·자료 변경 후에는 재상신하세요.')
    return state


def submit_contract(contract_id, req, db, actor):
    from .contract_service import ContractService
    from .workflow_service import fingerprint_for, policy_for
    from ..db.models import Contract
    if actor.role not in {'operator', 'admin'}:
        raise HTTPException(403, '담당자 권한으로 검토 완료·결재 상신하세요.')
    service = ContractService()
    # Enabled external rule lookups run outside the publication lock. The
    # evaluated inputs and local gate are rechecked before the durable event.
    detail = service.get_contract_detail(db, contract_id)
    if not detail:
        raise HTTPException(404, '계약을 찾을 수 없습니다.')
    db.rollback()
    with STORAGE_LOCK:
        db.expire_all()
        row = latest_submission(db, contract_id, req.idempotency_key)
        previous = json.loads(row.details) if row else {}
        if previous.get('idempotency_key') == req.idempotency_key:
            if row.actor_id != actor.user_id or any(previous.get(k) != getattr(req, k) for k in ('revision', 'fingerprint', 'review_cycle', 'note', 'exception_reason', 'exception_items', 'acknowledge_exception')):
                raise HTTPException(409, '같은 상신 요청 키에 다른 내용을 보낼 수 없습니다.')
        else:
            from ..db.models import ContractExclusion
            from .workflow_service import review_state
            contract = db.get(Contract, contract_id)
            if not contract or db.get(ContractExclusion, contract_id):
                raise HTTPException(404, '계약을 찾을 수 없습니다.')
            inputs = service.pipeline_service.validation_inputs(db, contract)
            if policy_for(db, contract_id)['revision'] != req.revision or fingerprint_for(db, contract, inputs) != req.fingerprint:
                raise HTTPException(409, '자료가 바뀌었습니다. 최신 원문과 검토 항목을 확인한 뒤 상신하세요.')
            if req.review_cycle != current_cycle(db, contract_id):
                raise HTTPException(409, '결재·반려 상태가 바뀌었습니다. 최신 사유를 확인한 뒤 재상신하세요.')
            gate = review_gate(db, contract, detail.checks)
            if gate['fingerprint'] != detail.workflow['submission']['gate']['fingerprint']:
                raise HTTPException(409, '검토·회신 상태가 바뀌었습니다. 최신 항목을 확인한 뒤 상신하세요.')
            wf = review_state(db, contract_id, req.fingerprint)
            if wf['approval_status'] == 'CONFIRMED' or submission_state(db, contract_id, wf, gate)['current']:
                raise HTTPException(409, '현재 자료는 이미 상신하거나 승인했습니다. 최신 상태를 확인하세요.')
            if gate['blockers']:
                raise HTTPException(400, '상신 전에 필수 검토를 완료하세요. ' + ' · '.join(i['label'] + ': ' + i['reason'] for i in gate['blockers'][:3]))
            expected = sorted(i['key'] for i in gate['exception_items'])
            if expected:
                if not req.acknowledge_exception or len(req.exception_reason) < 10 or sorted(set(req.exception_items)) != expected:
                    raise HTTPException(400, '남은 불일치·미확인 항목 전체와 예외 상신 사유(10자 이상)를 확인하세요.')
            elif req.exception_items or req.acknowledge_exception or req.exception_reason:
                raise HTTPException(409, '예외 항목이 바뀌었습니다. 최신 검토 결과를 확인하세요.')
            data = req.model_dump()
            data['gate_fingerprint'] = gate['fingerprint']
            data['cycle_review_id'] = current_cycle(db, contract_id)
            db.add(AuditEvent(actor_id=actor.user_id, actor_name=actor.display_name, action='CONTRACT_SUBMITTED',
                              contract_id=contract_id, details=json.dumps(data, ensure_ascii=False)))
            steps = company_policy(db).approval_steps
            if len(steps) == 2 and steps[0].role == 'operator' and not first_signoff(db, contract_id, req.revision, req.fingerprint):
                db.add(ApprovalSignoff(contract_id=contract_id, revision=req.revision, fingerprint=req.fingerprint,
                                      cycle_review_id=data['cycle_review_id'], actor_id=actor.user_id,
                                      actor_name=actor.display_name, note=req.note))
            db.commit()
    return service.get_contract_detail(db, contract_id)
