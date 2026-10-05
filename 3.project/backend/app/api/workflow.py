"""Frontend-facing review context, request records and configurable approvals."""
import json
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..db.models import Contract, CompanySetting, ResubmissionRequest, ApprovalSignoff
from ..security import Actor, get_current_user, require_representative
from ..services.storage_service import STORAGE_LOCK
from ..services.workflow_service import audit, touch_contract, policy_for, fingerprint_for
from ..services.company_policy_service import CompanyPolicy, company_policy, presets, approval_state, first_signoff, current_cycle
from ..services.review_context_service import document_provenance, review_context, request_response
from ..services.contract_service import ContractService
from .pilot import ReviewRequest, submit_review
router = APIRouter(tags=['Review workflow'])

def require_contract(db, cid):
    row = db.get(Contract, cid)
    if not row:
        raise HTTPException(404, '계약을 찾을 수 없습니다.')
    return row

@router.get('/api/contracts/{contract_id}/review-context')
def get_context(contract_id: int, db: Session=Depends(get_db)):
    result = review_context(db, contract_id)
    if result is None:
        raise HTTPException(404, '계약을 찾을 수 없습니다.')
    return result

@router.get('/api/documents/{document_id}/provenance')
def get_provenance(document_id: int, db: Session=Depends(get_db)):
    from ..db.models import Document
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, '문서를 찾을 수 없습니다.')
    return document_provenance(db, doc)

class RequestCreate(BaseModel):
    contact_method: Literal['KAKAO', 'SMS', 'EMAIL', 'PHONE', 'OTHER']
    requested_on: date = Field(default_factory=lambda: datetime.now(timezone(timedelta(hours=9))).date())
    due_on: date | None = None
    memo: str = Field(min_length=1, max_length=2000)
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    @model_validator(mode='after')
    def dates(self):
        if self.due_on and self.due_on < self.requested_on:
            raise ValueError('기한은 요청일보다 빠를 수 없습니다.')
        return self

class RequestResolve(BaseModel):
    status: Literal['RECEIVED', 'CANCELLED']
    note: str = Field(min_length=1, max_length=2000)
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

@router.get('/api/pilot/contracts/{contract_id}/resubmission-requests')
def list_requests(contract_id: int, db: Session=Depends(get_db)):
    require_contract(db, contract_id)
    return [request_response(r) for r in db.query(ResubmissionRequest).filter_by(contract_id=contract_id).order_by(ResubmissionRequest.request_id.desc()).all()]

@router.post('/api/pilot/contracts/{contract_id}/resubmission-requests', status_code=201)
def add_request(contract_id: int, req: RequestCreate, db: Session=Depends(get_db), actor: Actor=Depends(get_current_user)):
    with STORAGE_LOCK:
        require_contract(db, contract_id)
        row = ResubmissionRequest(contract_id=contract_id, contact_method=req.contact_method, requested_on=req.requested_on.isoformat(), due_on=req.due_on.isoformat() if req.due_on else None, memo=req.memo, status='WAITING_RESPONSE', actor_id=actor.user_id, actor_name=actor.display_name)
        db.add(row)
        db.commit()
        db.refresh(row)
        audit(db, actor, 'RESUBMISSION_REQUEST_RECORDED', contract_id, details={'request_id': row.request_id, 'contact_method': row.contact_method})
        return request_response(row)

@router.patch('/api/pilot/contracts/{contract_id}/resubmission-requests/{request_id}')
def resolve_request(contract_id: int, request_id: int, req: RequestResolve, db: Session=Depends(get_db), actor: Actor=Depends(get_current_user)):
    with STORAGE_LOCK:
        require_contract(db, contract_id)
        row = db.get(ResubmissionRequest, request_id)
        if not row or row.contract_id != contract_id:
            raise HTTPException(404, '요청 기록이 없습니다.')
        if row.bundle is not None:
            raise HTTPException(409, '묶음 요청은 항목별 회신 API로 처리하세요. 요청 전체를 한 번에 닫을 수 없습니다.')
        if row.status != 'WAITING_RESPONSE':
            raise HTTPException(409, '이미 회신 처리하거나 취소한 요청입니다.')
        row.status = req.status
        row.resolved_at = datetime.now(timezone.utc).replace(tzinfo=None)
        row.resolution_note = req.note
        db.commit()
        audit(db, actor, 'RESUBMISSION_REQUEST_RESOLVED', contract_id, details={'request_id': request_id, 'status': req.status})
        return request_response(row)

@router.get('/api/pilot/company-policy')
def get_policy(db: Session=Depends(get_db)):
    return company_policy(db).model_dump(mode='json')

@router.get('/api/pilot/company-policy/presets')
def get_presets():
    return presets()

@router.put('/api/pilot/company-policy')
def set_policy(req: CompanyPolicy, db: Session=Depends(get_db), actor: Actor=Depends(require_representative)):
    with STORAGE_LOCK:
        for key, value in (('organization_policy', req.model_dump(mode='json')), ('required_documents', [t.value for t in req.required_document_types])):
            row = db.get(CompanySetting, key)
            if not row:
                row = CompanySetting(key=key)
                db.add(row)
            row.value = json.dumps(value, ensure_ascii=False)
        ids = [c.contract_id for c in db.query(Contract).all()]
        for cid in ids:
            touch_contract(db, cid)
        db.commit()
        audit(db, actor, 'COMPANY_APPROVAL_POLICY_UPDATED', details={'company_type': req.company_type, 'stage_count': len(req.approval_steps)})
    pipeline = ContractService().pipeline_service
    for cid in ids:
        pipeline.revalidate_contract(db, cid)
    return get_policy(db)

class SignoffRequest(ReviewRequest):
    step: int = Field(ge=1, le=2, strict=True)

@router.get('/api/pilot/contracts/{contract_id}/approvals')
def get_approvals(contract_id: int, db: Session=Depends(get_db)):
    detail = ContractService().get_contract_detail(db, contract_id)
    if not detail:
        raise HTTPException(404, '계약을 찾을 수 없습니다.')
    return approval_state(db, contract_id, detail.workflow['revision'], detail.workflow['fingerprint'])

@router.post('/api/pilot/contracts/{contract_id}/approvals')
def signoff(contract_id: int, req: SignoffRequest, db: Session=Depends(get_db), actor: Actor=Depends(get_current_user)):
    if not req.note.strip():
        raise HTTPException(400, '검토 근거를 입력하세요.')
    if req.decision != 'CONFIRMED':
        raise HTTPException(400, '반려는 기존 reviews API의 RETURNED를 사용하세요.')
    steps = company_policy(db).approval_steps
    if req.step > len(steps):
        raise HTTPException(400, '설정에 없는 결재 단계입니다.')
    if actor.role not in {steps[req.step - 1].role, 'admin'}:
        raise HTTPException(403, '현재 단계의 결재 권한이 없습니다.')
    if req.step == len(steps):
        return submit_review(contract_id, ReviewRequest(**req.model_dump(exclude={'step'})), db, actor)
    service = ContractService()
    detail = service.get_contract_detail(db, contract_id)
    if not detail:
        raise HTTPException(404, '계약을 찾을 수 없습니다.')
    if any((not d.file_available for d in detail.documents)) or detail.summary.missing_count:
        raise HTTPException(400, '누락 서류와 원본을 먼저 보완하세요.')
    if (detail.summary.fail_count or detail.summary.review_count) and (not req.acknowledge_unverified or len(req.note.strip()) < 10):
        raise HTTPException(400, '불일치·미확인 항목의 검토 근거를 10자 이상 남기세요.')
    db.rollback()
    with STORAGE_LOCK:
        db.expire_all()
        contract = require_contract(db, contract_id)
        inputs = service.pipeline_service.validation_inputs(db, contract)
        if policy_for(db, contract_id)['revision'] != req.revision or fingerprint_for(db, contract, inputs) != req.fingerprint:
            raise HTTPException(409, '자료가 변경되었습니다. 최신 자료로 검토하세요.')
        if first_signoff(db, contract_id, req.revision, req.fingerprint):
            raise HTTPException(409, '현재 단계는 이미 검토 완료되었습니다.')
        db.add(ApprovalSignoff(contract_id=contract_id, revision=req.revision, fingerprint=req.fingerprint, cycle_review_id=current_cycle(db, contract_id), actor_id=actor.user_id, actor_name=actor.display_name, note=req.note.strip()))
        db.commit()
        audit(db, actor, 'APPROVAL_FIRST_STAGE', contract_id, details={'revision': req.revision})
    return get_approvals(contract_id, db)
