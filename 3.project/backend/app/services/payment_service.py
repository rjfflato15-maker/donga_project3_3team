"""Record an already completed whole-contract payment; no external operations."""
import json
import hashlib
import re
from fastapi import HTTPException

from ..db.models import Contract, ContractPayment, ContractReview, PaymentConfirmation, AuditEvent, DocumentFileInfo, PaymentCorrection
from ..schemas.contract import ContractDetailResponse
from .pipeline_service import PipelineService
from .storage_service import STORAGE_LOCK, resolve_path
from .document_version_service import active_documents
from .workflow_service import fingerprint_for, policy_for


class OperationalContractDetailResponse(ContractDetailResponse):
    # Keep the frozen extraction/evaluation schema separate from operational data.
    payment: dict | None = None
    stage: str | None = None
    work_state: dict = {}
    registration: dict | None = None


def latest_review(db, contract_id):
    return db.query(ContractReview).filter_by(contract_id=contract_id).order_by(ContractReview.review_id.desc()).first()


def originals_verified(db, contract_id):
    """Do not mistake an old masked sidecar fallback for the original bytes."""
    contract = db.get(Contract, contract_id)
    for doc in active_documents(contract):
        info = db.get(DocumentFileInfo, doc.document_id)
        path = resolve_path(doc.storage_path)
        if not info or not path:
            return False
        try:
            digest = hashlib.sha256()
            with path.open('rb') as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b''):
                    digest.update(chunk)
            if digest.hexdigest() != info.sha256:
                return False
        except OSError:
            return False
    return True


def effective_payment(db, fact):
    correction = db.query(PaymentCorrection).filter_by(payment_id=fact.payment_id).order_by(
        PaymentCorrection.correction_id.desc()).first()
    data = json.loads(correction.snapshot_json) if correction else {
        'paid_on': fact.paid_on, 'method': fact.method, 'note': fact.note,
        'reference': json.loads(fact.snapshot_json)}
    return data, correction


def payment_state(db, contract_id, revision, fingerprint, *, review=None):
    fact = db.query(ContractPayment).filter_by(contract_id=contract_id).first()
    if not fact:
        return None
    data, correction = effective_payment(db, fact)
    voided = bool(correction and correction.action == 'VOID')
    review = review or latest_review(db, contract_id)
    confirmed = bool(review and review.decision == 'CONFIRMED' and review.revision == revision
                     and json.loads(review.snapshot_json).get('fingerprint') == fingerprint)
    verified = originals_verified(db, contract_id) if confirmed else None
    scope_matches = same_payment_scope(data['reference'],
        reference_snapshot(db.get(Contract, contract_id), policy_for(db, contract_id)))
    link = (db.query(PaymentConfirmation).filter_by(payment_id=fact.payment_id, review_id=review.review_id,
             revision=revision, fingerprint=fingerprint).first()) if confirmed else None
    if link and (not verified or voided or not scope_matches):
        link = None
    return {'payment_id': fact.payment_id, 'scope': 'WHOLE_CONTRACT',
            'status': 'VOIDED' if voided else 'RECORDED' if link else 'RECONFIRMATION_REQUIRED',
            'correction_revision': correction.correction_id if correction else 0,
            'reconfirmation_allowed': bool(not voided and not link and confirmed and verified and scope_matches),
            'blocked_reason': None if link else 'FINAL_REVIEW_REQUIRED' if not confirmed else
                'SOURCE_VERSION_UNVERIFIED' if not verified else 'PAYEE_OR_AMOUNT_CHANGED' if not scope_matches else None,
            # The current UI uses paid_on as its DONE signal. Stale payment facts
            # must remain visible without hiding changed documents from review.
            'paid_on': data['paid_on'] if link else None, 'recorded_paid_on': data['paid_on'],
            'method': data['method'], 'note': data['note'], 'actor_name': correction.actor_name if correction else fact.actor_name,
            'created_at': fact.created_at.isoformat(), 'original_snapshot': json.loads(fact.snapshot_json),
            'current_confirmation': {'review_id': link.review_id, 'revision': link.revision,
                'fingerprint': link.fingerprint, 'actor_name': link.actor_name,
                'created_at': link.created_at.isoformat()} if link else None}


def approved_snapshot(db, contract_id, revision):
    contract = db.get(Contract, contract_id)
    if not contract:
        raise HTTPException(404, '계약을 찾을 수 없습니다.')
    policy = policy_for(db, contract_id)
    if policy['revision'] != revision:
        raise HTTPException(409, '계약 자료가 변경되었습니다. 최신 자료를 다시 확인하세요.')
    inputs = PipelineService().validation_inputs(db, contract)
    fingerprint = fingerprint_for(db, contract, inputs)
    review = latest_review(db, contract_id)
    if not (review and review.decision == 'CONFIRMED' and review.revision == revision
            and json.loads(review.snapshot_json).get('fingerprint') == fingerprint):
        raise HTTPException(409, '현재 자료의 대표 최종 결재 후 지급 사실을 기록하세요.')
    if not originals_verified(db, contract_id):
        raise HTTPException(409, '현재 원본을 등록 당시 해시로 확인할 수 없습니다. 원본을 복구·재등록하고 다시 결재하세요.')
    return contract, policy, fingerprint, review


def reference_snapshot(contract, policy):
    return {'vendor_name': contract.vendor_name, 'business_number': contract.business_number,
            'contract_amount': contract.contract_amount, 'amount_basis': policy['amount_basis'],
            'tax_amount': policy['tax_amount'], 'payment_mode': policy['payment_mode']}


def same_payment_scope(original, current):
    if any(original[key] != current[key] for key in ('contract_amount', 'amount_basis', 'tax_amount', 'payment_mode')):
        return False
    original_party = re.sub(r'[-\s]', '', original['business_number'])
    current_party = re.sub(r'[-\s]', '', current['business_number'])
    return original_party == current_party and bool(original_party or original['vendor_name'] == current['vendor_name'])


def add_confirmation(db, fact, revision, fingerprint, review, actor, note, action):
    data, _ = effective_payment(db, fact)
    if not db.query(PaymentConfirmation).filter_by(payment_id=fact.payment_id, review_id=review.review_id).first():
        db.add(PaymentConfirmation(payment_id=fact.payment_id, contract_id=fact.contract_id,
            review_id=review.review_id, revision=revision, fingerprint=fingerprint,
            actor_id=actor.user_id, actor_name=actor.display_name, note=note))
    # Audit and record are committed atomically; a lost response can be retried.
    db.add(AuditEvent(actor_id=actor.user_id, actor_name=actor.display_name, action=action,
        contract_id=fact.contract_id, details=json.dumps({'payment_id': fact.payment_id,
            'review_id': review.review_id, 'revision': revision, 'scope': 'WHOLE_CONTRACT',
            'paid_on': data['paid_on'], 'method': data['method'], 'note': note}, ensure_ascii=False)))


def payment_request_receipt(req):
    payload = req.model_dump()
    return {'key': req.idempotency_key, 'sha256': hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()}


def recorded_request(db, fact, key):
    """Find an immutable receipt, including requests since superseded or voided.

    JSON metadata keeps existing databases compatible without rewriting facts
    or corrections. Legacy facts without a receipt remain readable.
    """
    receipt = json.loads(fact.snapshot_json).get('record_request')
    if receipt and receipt['key'] == key:
        return receipt
    for correction in db.query(PaymentCorrection).filter_by(payment_id=fact.payment_id):
        receipt = json.loads(correction.snapshot_json).get('reference', {}).get('record_request')
        if receipt and receipt['key'] == key:
            return receipt
    return None


def record_payment(db, contract_id, req, actor):
    db.rollback()
    with STORAGE_LOCK:
        db.expire_all()
        contract, policy, fingerprint, review = approved_snapshot(db, contract_id, req.revision)
        receipt = payment_request_receipt(req)
        fact = db.query(ContractPayment).filter_by(contract_id=contract_id).first()
        if fact:
            state = payment_state(db, contract_id, req.revision, fingerprint, review=review)
            previous_request = recorded_request(db, fact, req.idempotency_key)
            if previous_request:
                if previous_request != receipt:
                    raise HTTPException(409, '같은 지급 요청 키를 다른 내용에 재사용할 수 없습니다.')
                # Return today's state, not a historical success that would
                # mislead a retrying browser after a correction or VOID.
                return state, False
            if req.payment_revision != state['correction_revision']:
                raise HTTPException(409, '지급 기록이 변경되었습니다. 최신 기록을 다시 확인하세요.')
            if state['status'] == 'VOIDED':
                if not req.acknowledge_new_payment:
                    raise HTTPException(409, '취소 이후 실제 지급 사실을 새로 확인했음을 명시하세요.')
                snapshot = {**reference_snapshot(contract, policy), 'revision': req.revision,
                            'fingerprint': fingerprint, 'review_id': review.review_id,
                            'record_request': receipt}
                db.add(PaymentCorrection(payment_id=fact.payment_id, action='RECORD', reason='취소한 지급 기록을 새 사실로 등록',
                    actor_name=actor.display_name, snapshot_json=json.dumps({'paid_on': req.paid_on,
                        'method': req.method, 'note': req.note, 'reference': snapshot}, ensure_ascii=False)))
                db.flush()
                add_confirmation(db, fact, req.revision, fingerprint, review, actor, req.note, 'PAYMENT_RECORDED')
                db.commit()
                return payment_state(db, contract_id, req.revision, fingerprint, review=review), True
            raise HTTPException(409, '이미 지급 사실이 기록되어 있습니다. 재결재 후에는 기존 지급 사실 재확인을 사용하세요.')
        if req.payment_revision != 0:
            raise HTTPException(409, '지급 기록이 변경되었습니다. 최신 기록을 다시 확인하세요.')
        snapshot = {**reference_snapshot(contract, policy), 'revision': req.revision,
                    'fingerprint': fingerprint, 'review_id': review.review_id,
                    'record_request': receipt}
        fact = ContractPayment(contract_id=contract_id, paid_on=req.paid_on, method=req.method,
            note=req.note, actor_id=actor.user_id, actor_name=actor.display_name,
            snapshot_json=json.dumps(snapshot, ensure_ascii=False))
        db.add(fact)
        db.flush()
        add_confirmation(db, fact, req.revision, fingerprint, review, actor, req.note, 'PAYMENT_RECORDED')
        db.commit()
        return payment_state(db, contract_id, req.revision, fingerprint, review=review), True


def reconfirm_payment(db, contract_id, payment_id, req, actor):
    db.rollback()
    with STORAGE_LOCK:
        db.expire_all()
        contract, policy, fingerprint, review = approved_snapshot(db, contract_id, req.revision)
        fact = db.query(ContractPayment).filter_by(contract_id=contract_id, payment_id=payment_id).first()
        if not fact:
            raise HTTPException(404, '이 계약의 지급 기록을 찾을 수 없습니다.')
        original, correction = effective_payment(db, fact)
        if correction and correction.action == 'VOID':
            raise HTTPException(409, '취소한 지급 기록입니다. 실제 지급 사실을 새로 기록하세요.')
        original = original['reference']
        if not same_payment_scope(original, reference_snapshot(contract, policy)):
            raise HTTPException(409, '거래처 식별자·계약 금액·금액 기준·세액·지급 방식이 변경되어 기존 전체 지급 사실을 연결할 수 없습니다.')
        state = payment_state(db, contract_id, req.revision, fingerprint, review=review)
        if state['paid_on']:
            return state, False
        add_confirmation(db, fact, req.revision, fingerprint, review, actor, req.note, 'PAYMENT_RECONFIRMED')
        db.commit()
        return payment_state(db, contract_id, req.revision, fingerprint, review=review), True


def correct_payment(db, contract_id, payment_id, req, actor):
    db.rollback()
    with STORAGE_LOCK:
        db.expire_all()
        contract = db.get(Contract, contract_id)
        if not contract:
            raise HTTPException(404, '계약을 찾을 수 없습니다.')
        policy = policy_for(db, contract_id)
        fingerprint = fingerprint_for(db, contract, PipelineService().validation_inputs(db, contract))
        if policy['revision'] != req.revision or fingerprint != req.fingerprint:
            raise HTTPException(409, '계약 자료가 변경되었습니다. 최신 자료를 확인하세요.')
        fact = db.query(ContractPayment).filter_by(contract_id=contract_id, payment_id=payment_id).first()
        if not fact:
            raise HTTPException(404, '이 계약의 지급 기록을 찾을 수 없습니다.')
        before, previous = effective_payment(db, fact)
        if (previous.correction_id if previous else 0) != req.payment_revision:
            raise HTTPException(409, '다른 사용자가 지급 기록을 정정했습니다. 다시 불러오세요.')
        if previous and previous.action == 'VOID':
            raise HTTPException(409, '이미 취소한 지급 기록입니다.')
        after = dict(before)
        if req.action == 'CORRECT':
            after.update(paid_on=req.paid_on, method=req.method, note=req.note)
        correction = PaymentCorrection(payment_id=fact.payment_id, action=req.action,
            snapshot_json=json.dumps(after, ensure_ascii=False), reason=req.reason,
            actor_name=actor.display_name)
        db.add(correction)
        db.add(AuditEvent(actor_id=actor.user_id, actor_name=actor.display_name,
            action='PAYMENT_VOIDED' if req.action == 'VOID' else 'PAYMENT_CORRECTED', contract_id=contract_id,
            details=json.dumps({'payment_id': payment_id, 'before': before, 'after': after,
                'note': req.reason}, ensure_ascii=False)))
        db.commit()
        return payment_state(db, contract_id, req.revision, fingerprint)
