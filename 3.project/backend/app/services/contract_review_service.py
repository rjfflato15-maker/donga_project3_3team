"""Publish a contract review using the same checks for each review entry point.

Route dependencies authorize callers. This service owns the existing snapshot,
revision recheck, storage lock, review commit and audit sequence.
"""
import json

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..db.models import Contract, ContractReview
from ..schemas.review import ReviewRequest
from ..security import Actor
from .contract_service import ContractService
from .storage_service import STORAGE_LOCK
from .workflow_service import audit, policy_for, fingerprint_for


def submit_review(contract_id: int, req: ReviewRequest, db: Session, actor: Actor):
    if req.decision not in {"CONFIRMED", "RETURNED"}:
        raise HTTPException(400, "확인 완료 또는 보완 요청을 선택하세요.")
    if len(req.note.strip()) < 3:
        raise HTTPException(400, "승인·반려 사유를 3자 이상 입력하세요.")
    service = ContractService()
    # Rule evaluation can perform an enabled NTS lookup. Do it outside the
    # storage lock, then publish only if the reviewed inputs are still current.
    detail = service.get_contract_detail(db, contract_id)
    if not detail:
        raise HTTPException(404, "계약을 찾을 수 없습니다.")
    if detail.workflow["revision"] != req.revision or detail.workflow["fingerprint"] != req.fingerprint:
        raise HTTPException(409, "계약 자료가 변경되었습니다. 최신 자료를 다시 확인하세요.")
    from .company_policy_service import current_cycle
    from .submission_service import latest_submission
    live_cycle = current_cycle(db, contract_id)
    if (req.review_cycle is None and live_cycle) or (req.review_cycle is not None and req.review_cycle != live_cycle):
        raise HTTPException(409, '결재·반려 상태가 바뀌었습니다. 최신 검토 차수와 상신 내용을 확인하세요.')
    latest = latest_submission(db, contract_id)
    if req.submission_event_id is not None and (not latest or latest.event_id != req.submission_event_id):
        raise HTTPException(409, '상신 내용이 바뀌었습니다. 최신 상신 자료를 다시 확인하세요.')
    if req.decision == "RETURNED" and detail.workflow["approval_status"] != "CONFIRMED":
        from .submission_service import require_current_submission
        require_current_submission(db, contract_id, detail.workflow)
    if req.decision == "CONFIRMED":
        from .submission_service import require_current_submission
        if detail.workflow["submission"]["gate"]["blockers"]:
            raise HTTPException(400, "필수 원문 검토·검사 실패를 먼저 해결하세요.")
        require_current_submission(db, contract_id, detail.workflow)
        if any(not doc.file_available for doc in detail.documents) or detail.summary.missing_count:
            raise HTTPException(400, "누락된 필수 문서와 원본을 보완한 후 최종 확인하세요.")
        if any(check.status.value in {"FAIL", "REVIEW"} for check in detail.checks):
            if not req.acknowledge_unverified or len(req.note.strip()) < 10:
                raise HTTPException(400, "불일치·미확인 항목을 직접 검토했음을 선택하고 확인 근거를 10자 이상 남기세요.")
    snapshot = {"fingerprint": detail.workflow["fingerprint"],
                    "submission": {k: v for k, v in detail.workflow["submission"].items() if k != "gate"},
                    "contract": {"title": detail.title, "vendor_name": detail.vendor_name,
                                 "business_number": detail.business_number, "contract_amount": detail.contract_amount},
                    "policy": {key: detail.workflow[key] for key in ("revision", "amount_basis", "tax_amount", "payment_mode")}, "summary": detail.summary.model_dump(),
                    "checks": [c.model_dump(mode="json") for c in detail.checks],
                    "documents": [{"document_id": d.document_id, "file_name": d.original_file_name,
                                   "file_available": d.file_available, "fields": d.analysis.fields.model_dump()}
                                  for d in detail.documents]}
    db.rollback()
    with STORAGE_LOCK:
        db.expire_all()
        contract = db.get(Contract, contract_id)
        if not contract:
            raise HTTPException(404, "계약을 찾을 수 없습니다.")
        inputs = service.pipeline_service.validation_inputs(db, contract)
        if policy_for(db, contract_id)["revision"] != req.revision or fingerprint_for(db, contract, inputs) != req.fingerprint:
            raise HTTPException(409, "확인 처리 중 계약 자료가 변경되었습니다. 최신 자료를 다시 확인하세요.")
        from .workflow_service import review_state
        if current_cycle(db, contract_id) != live_cycle:
            raise HTTPException(409, '처리 중 결재 상태가 바뀌었습니다. 최신 상태를 확인하세요.')
        live_workflow = review_state(db, contract_id, req.fingerprint)
        if live_workflow["approval_status"] == req.decision:
            raise HTTPException(409, "현재 자료는 이미 같은 결정으로 처리되었습니다. 최신 상태를 확인하세요.")
        if req.decision == "RETURNED" and live_workflow["approval_status"] != "CONFIRMED":
            from .submission_service import require_current_submission
            require_current_submission(db, contract_id, {**live_workflow, "submission": detail.workflow["submission"]})
        if req.decision == "CONFIRMED":
            require_current_submission(db, contract_id, {**live_workflow, "submission": detail.workflow["submission"]})
            from .company_policy_service import require_prior_approval
            require_prior_approval(db, contract_id, req.revision, req.fingerprint, actor)
        review = ContractReview(contract_id=contract_id, revision=req.revision, actor_id=actor.user_id,
                                actor_name=actor.display_name, decision=req.decision, note=req.note.strip(),
                                snapshot_json=json.dumps(snapshot, ensure_ascii=False, default=str))
        db.add(review)
        db.commit()
        audit(db, actor, "REPRESENTATIVE_" + req.decision, contract_id, details={"revision": req.revision, "fingerprint": req.fingerprint, "review_id": review.review_id, "note": req.note.strip()})
    return service.get_contract_detail(db, contract_id)
