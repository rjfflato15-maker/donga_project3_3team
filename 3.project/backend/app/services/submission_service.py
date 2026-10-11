"""Operator review and submission, separate from inference and final approval.

Persist in the existing append-only audit log without rewriting customer data,
the DB schema, or completed approvals. Each submission binds to
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
from .business_identity_service import automatic_field_review, number, POLICY
from ..validation.engine import normalize_party_name
from ..validation.financial import money
from .workflow_service import policy_for, required_types

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
    acknowledge_work_completed: bool = Field(default=False, strict=True)
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
    def block(code, reason, action, doc=None, field=None, category=None):
        kind = getattr(doc.document_type, 'value', doc.document_type) if doc else None
        blockers.append({'code': code, 'document_id': doc.document_id if doc else None,
                         'document_type': kind, 'field': field,
                         'label': f'{DOC_LABELS.get(kind, "계약")} · {FIELD_LABELS.get(field, "원문")}',
                         'reason': reason, 'action': action, 'owner': 'operator', 'category': category})
    for check in checks:
        if check.rule_id == 'REQUIRED_DOCUMENTS' and check.status == 'MISSING':
            block('MISSING_DOCUMENT', f'{DOC_LABELS.get(check.field, check.field)} 미등록 상태입니다.', '서류 받기·보완 요청')
            blockers[-1].update(document_type=check.field, label=DOC_LABELS.get(check.field, check.field))
    documents = active_documents(contract)
    policy = policy_for(db, contract.contract_id)
    requires_work = any(t.value == 'inspection_confirmation' for t in required_types(db))
    if not documents and not blockers:
        block('MISSING_DOCUMENT', '검토할 서류가 없습니다.', '서류 등록')
    bindings = []
    automatic = []
    anchor = None
    verified_files = {}
    def source_verified(doc):
        if doc.document_id not in verified_files:
            path, info = resolve_path(doc.storage_path), db.get(DocumentFileInfo, doc.document_id)
            verified = False
            try:
                if path and info:
                    with path.open('rb') as stream:
                        verified = hashlib.file_digest(stream, 'sha256').hexdigest() == info.sha256
            except OSError:
                pass
            verified_files[doc.document_id] = (path, info, verified)
        return verified_files[doc.document_id]
    # Source-backed comparison can be shown before the operator checks the
    # contract basis. That basis remains mandatory; it cannot be auto-exempted.
    for doc in documents:
        if getattr(doc.document_type, 'value', doc.document_type) != 'contract' or not doc.extract:
            continue
        _, _, verified = source_verified(doc)
        stored = json.loads(doc.extract.raw_fields or '{}')
        proofs = current_confirmations(db, doc.document_id, stored)
        ai = stored.get('ai_review') or {}
        if (not verified or str(getattr(doc.processing_status, 'value', doc.processing_status)) not in {'COMPLETED','REVIEW'}
                or doc.extract.extracted_status == 'FAILED'
                or (stored.get('extraction_metadata') or {}).get('evidence_complete') is False
                or ai.get('manual_review_required') and not ai.get('targets') or current_deferrals(db, doc.document_id, stored)):
            continue
        if (number(stored.get('business_registration_no')) == number(contract.business_number)
                and normalize_party_name(stored.get('company_name')) == normalize_party_name(contract.vendor_name)):
            anchor = {'document_id': doc.document_id, 'number': number(contract.business_number),
                      'name': normalize_party_name(contract.vendor_name), 'total': None,
                      'payment_mode': policy['payment_mode'],
                      'confirmed': all(key in proofs for key in ('company_name','business_registration_no'))}
            amount_field = 'total_amount' if stored.get('total_amount') is not None else 'amount'
            expected = money(contract.contract_amount)
            if policy['amount_basis'] == 'SUPPLY':
                tax = money(policy['tax_amount'])
                expected = expected + tax if expected is not None and tax is not None else None
            elif policy['amount_basis'] != 'TOTAL':
                expected = None
            if money(stored.get(amount_field)) == expected:
                anchor['total'] = expected
            break
    for doc in documents:
        response = responses.get(doc.document_id)
        path, info, verified = source_verified(doc)
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
        critical = ({'company_name','business_registration_no','total_amount' if values.get('total_amount') is not None else 'amount'} if kind=='contract'
                    else {'company_name','account_number','bank_name'} if kind=='bank_account'
                    else {'amount_scope'} if kind=='tax_invoice' else set())
        for field in sorted(fields):
            if field not in values or values[field] is None or values[field] == '':
                if field in critical:
                    block('FIELD_VALUE_REQUIRED', '필수 지급·계약 정보를 읽지 못했습니다. 원문을 확인하고 값을 입력하세요.', '원문 확인·값 입력', doc, field, 'RISK')
                continue  # Missing/unusable values stay in the rule results below.
            if field == 'amount_scope' and values[field] == 'UNKNOWN':
                block('FIELD_VALUE_REQUIRED', '청구 범위를 확정하지 못했습니다. 계약 조건과 청구액을 확인해 전액·일부를 입력하세요.', '청구 범위 정정', doc, field,'RISK')
                continue
            if field not in proofs:
                if field not in critical:
                    basis = automatic_field_review(doc, field, values, stored, checks, path, info.sha256, anchor, decisions,human_fields=proofs)
                    if basis:
                        automatic.append(basis)
                        continue
                reason = ('계약 거래처·금액과 지급 기준은 담당자가 직접 확인합니다.' if kind=='contract'
                          else '송금 은행·계좌·예금주는 지급 사고 위험 때문에 직접 확인합니다.' if kind=='bank_account' and field in critical
                          else '청구 범위와 계약 지급 조건은 담당자가 직접 판단합니다.' if field=='amount_scope'
                          else '원본 근거로 자동 확인하지 못했습니다. 해당 값만 원문과 확인하거나 정정하세요.')
                scan=(stored.get('extraction_metadata') or {}).get('automatic_source_review')
                if field not in critical and isinstance(scan,dict):
                    reason={'SCAN_PARTY_OR_LAYOUT_AMBIGUOUS':'스캔에서 공급자·필드 위치를 구분하지 못했습니다. 이 항목의 원문을 확인하세요.',
                            'SCAN_PARTY_CROP_DISAGREES':'스캔의 공급자 표기를 다시 읽은 결과가 달라 귀속을 확인해야 합니다.',
                            'SCAN_FIELD_CROP_DISAGREES':'원문 행 재판독이 일부 값과 일치하지 않습니다. 확인하지 못한 이 항목을 대조하세요.',
                            'SCAN_SOURCE_UNVERIFIED':'스캔 원문의 읽을 수 있는 위치·재판독 근거가 없습니다. 이 항목을 확인하세요.'}.get(scan.get('reason'),
                            '스캔 원문 재판독·저장값·계약 기준이 일치하는지 확인하거나 오독을 정정하세요.')
                block('HUMAN_REVIEW_REQUIRED', reason, '필수 확인' if field in critical else '근거 확인·오독 정정', doc, field,
                      'RISK' if field in critical else 'EVIDENCE')
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
    binding = {'cycle': current_cycle(db, contract.contract_id), 'review': bindings, 'blockers': blockers, 'exceptions': exceptions,
               'review_policy': POLICY, 'requires_work_confirmation': requires_work}
    if automatic:
        binding['automatic_review'] = automatic
        binding['review_policy'] = POLICY
    digest = hashlib.sha256(json.dumps(binding, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()
    return {'blockers': blockers, 'exception_items': exceptions, 'fingerprint': digest, 'automatic_review': automatic,
            'review_policy': POLICY, 'requires_work_confirmation': requires_work,
            'can_submit': not blockers and not exceptions,
            'can_submit_exception': not blockers and bool(exceptions),
            'completion': '계약 기준·송금 정보·청구 범위의 필수 확인과 미해결 문제를 정리한 후, 실제 용역 완료 여부와 검토 의견을 기록해 상신합니다.'}


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
            if row.actor_id != actor.user_id or any(previous.get(k) != getattr(req, k) for k in ('revision', 'fingerprint', 'review_cycle', 'note', 'exception_reason', 'exception_items', 'acknowledge_exception','acknowledge_work_completed')):
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
            if gate['requires_work_confirmation'] and not req.acknowledge_work_completed:
                raise HTTPException(400, '검수확인서 존재만으로 실제 용역 완료를 판단하지 않습니다. 납품·용역 검수 완료 사실을 확인하고 상신하세요.')
            if any(not item['anchor_confirmed'] for item in gate['automatic_review']):
                raise HTTPException(400, '자동 대조의 기준인 계약 거래처 정보를 먼저 직접 확인하세요.')
            expected = sorted(i['key'] for i in gate['exception_items'])
            if expected:
                if not req.acknowledge_exception or len(req.exception_reason) < 10 or sorted(set(req.exception_items)) != expected:
                    raise HTTPException(400, '남은 불일치·미확인 항목 전체와 예외 상신 사유(10자 이상)를 확인하세요.')
            elif req.exception_items or req.acknowledge_exception or req.exception_reason:
                raise HTTPException(409, '예외 항목이 바뀌었습니다. 최신 검토 결과를 확인하세요.')
            data = req.model_dump()
            data['gate_fingerprint'] = gate['fingerprint']
            if gate['automatic_review']:
                data['automatic_review'] = gate['automatic_review']
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
