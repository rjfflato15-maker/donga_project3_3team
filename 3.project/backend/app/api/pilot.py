import json
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from dataclasses import asdict
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from ..config import IS_PILOT, STORAGE_DIR, DATABASE_URL, DEPLOYMENT_MODE, NTS_MODE
from ..db.database import get_db
from ..db.models import (Contract, ContractReview, ContractWorkflow, AuditEvent, CompanySetting,
                         User, UserProfile, AuthSession)
from ..schemas.common import DocumentType
from ..security import Actor, get_current_user, require_representative, hash_password, validate_password
from ..services.workflow_service import audit, required_types, touch_contract, policy_for, fingerprint_for
from ..services.storage_service import STORAGE_LOCK
from ..services.contract_service import ContractService

router = APIRouter(tags=["C Pilot"])


@router.get("/api/pilot/info")
def pilot_info(db: Session = Depends(get_db)):
    name = db.get(CompanySetting, "company_name")
    from ..services.llm_status_service import llm_status
    state=llm_status()
    return {"company_name": json.loads(name.value) if name else "C업체 시범환경",
            "deployment_mode": DEPLOYMENT_MODE, "local_database": DATABASE_URL.startswith("sqlite"),
            "nts_mode": NTS_MODE, "llm_connected": state['connected'], "llm":state,
            "required_document_types": [t.value for t in required_types(db)]}


@router.get('/api/pilot/llm-status')
def current_llm_status():
    from ..services.llm_status_service import llm_status
    return llm_status(probe=True)


class SettingsUpdate(BaseModel):
    company_name: str = Field(min_length=1, max_length=80)
    required_document_types: List[DocumentType]


@router.put("/api/pilot/settings")
def update_settings(req: SettingsUpdate, db: Session = Depends(get_db),
                    actor: Actor = Depends(require_representative)):
    values = list(dict.fromkeys(t.value for t in req.required_document_types))
    if not values or "unknown" in values:
        raise HTTPException(400, "필수 문서를 1종 이상 선택하세요.")
    with STORAGE_LOCK:
        for key, value in (("company_name", req.company_name.strip()), ("required_documents", values)):
            row = db.get(CompanySetting, key)
            if not row:
                row = CompanySetting(key=key)
                db.add(row)
            row.value = json.dumps(value, ensure_ascii=False)
        contract_ids = [row.contract_id for row in db.query(Contract).all()]
        for contract_id in contract_ids:
            touch_contract(db, contract_id)
        db.commit()
        audit(db, actor, "COMPANY_POLICY_UPDATED", details={"required_documents": values})
    from ..services.pipeline_service import PipelineService
    pipeline = PipelineService()
    for contract_id in contract_ids:
        pipeline.revalidate_contract(db, contract_id)
    return pilot_info(db)


class ReviewRequest(BaseModel):
    decision: str
    note: str = Field(min_length=1, max_length=2000)
    revision: int
    fingerprint: str
    acknowledge_unverified: bool = False


@router.post("/api/contracts/{contract_id}/reviews")
def submit_review(contract_id: int, req: ReviewRequest, db: Session = Depends(get_db),
                  actor: Actor = Depends(require_representative)):
    if req.decision not in {"CONFIRMED", "RETURNED"}:
        raise HTTPException(400, "확인 완료 또는 보완 요청을 선택하세요.")
    service = ContractService()
    # Rule evaluation can perform an enabled NTS lookup. Do it outside the
    # storage lock, then publish only if the reviewed inputs are still current.
    detail = service.get_contract_detail(db, contract_id)
    if not detail:
        raise HTTPException(404, "계약을 찾을 수 없습니다.")
    if detail.workflow["revision"] != req.revision or detail.workflow["fingerprint"] != req.fingerprint:
        raise HTTPException(409, "계약 자료가 변경되었습니다. 최신 자료를 다시 확인하세요.")
    if req.decision == "CONFIRMED":
        if any(not doc.file_available for doc in detail.documents) or detail.summary.missing_count:
            raise HTTPException(400, "누락된 필수 문서와 원본을 보완한 후 최종 확인하세요.")
        if any(check.status.value in {"FAIL", "REVIEW"} for check in detail.checks):
            if not req.acknowledge_unverified or len(req.note.strip()) < 10:
                raise HTTPException(400, "불일치·미확인 항목을 직접 검토했음을 선택하고 확인 근거를 10자 이상 남기세요.")
    snapshot = {"fingerprint": detail.workflow["fingerprint"],
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
        if req.decision == "CONFIRMED":
            from ..services.company_policy_service import require_prior_approval
            require_prior_approval(db, contract_id, req.revision, req.fingerprint, actor)
        review = ContractReview(contract_id=contract_id, revision=req.revision, actor_id=actor.user_id,
                                actor_name=actor.display_name, decision=req.decision, note=req.note.strip(),
                                snapshot_json=json.dumps(snapshot, ensure_ascii=False, default=str))
        db.add(review)
        db.commit()
        audit(db, actor, "REPRESENTATIVE_" + req.decision, contract_id, details={"revision": req.revision, "note": req.note.strip()})
    return service.get_contract_detail(db, contract_id)


@router.get("/api/pilot/reviews/{review_id}")
def get_review_snapshot(review_id: int, db: Session = Depends(get_db)):
    review = db.get(ContractReview, review_id)
    if not review:
        raise HTTPException(404, "확인 기록이 없습니다.")
    return {"review_id": review.review_id, "actor_name": review.actor_name, "note": review.note,
            "created_at": review.created_at.isoformat(), "snapshot": json.loads(review.snapshot_json)}


@router.get("/api/pilot/audit")
def list_audit(contract_id: int = None, db: Session = Depends(get_db)):
    query = db.query(AuditEvent)
    if contract_id is not None:
        query = query.filter(AuditEvent.contract_id == contract_id)
    return [{"event_id": e.event_id, "actor_name": e.actor_name, "action": e.action,
             "contract_id": e.contract_id, "document_id": e.document_id,
             "details": json.loads(e.details), "created_at": e.created_at.isoformat()}
            for e in query.order_by(AuditEvent.event_id.desc()).limit(100)]


@router.get("/api/pilot/users")
def list_users(db: Session = Depends(get_db), actor: Actor = Depends(require_representative)):
    return [{"user_id": u.user_id, "email": u.email, "display_name": p.display_name,
             "role": p.role, "active": p.active, "must_change_password": p.must_change_password}
            for u, p in db.query(User, UserProfile).join(UserProfile, User.user_id == UserProfile.user_id).all()]


class NewUser(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    display_name: str = Field(min_length=1, max_length=80)
    role: str
    temporary_password: str


@router.post("/api/pilot/users", status_code=201)
def add_user(req: NewUser, db: Session = Depends(get_db), actor: Actor = Depends(require_representative)):
    email = req.email.strip().lower()
    if req.role not in {"operator", "representative"} or "@" not in email or " " in email:
        raise HTTPException(400, "계정 주소와 권한을 확인하세요.")
    validate_password(req.temporary_password)
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(409, "이미 등록된 계정입니다.")
    user = User(email=email, password=hash_password(req.temporary_password))
    db.add(user)
    db.flush()
    db.add(UserProfile(user_id=user.user_id, role=req.role, display_name=req.display_name.strip(), must_change_password=True))
    db.commit()
    audit(db, actor, "ACCOUNT_CREATED", details={"email": email, "role": req.role})
    return {"success": True}


class ActiveUpdate(BaseModel):
    active: bool


@router.patch("/api/pilot/users/{user_id}")
def set_user_active(user_id: int, req: ActiveUpdate, db: Session = Depends(get_db),
                    actor: Actor = Depends(require_representative)):
    profile = db.get(UserProfile, user_id)
    if not profile:
        raise HTTPException(404, "계정이 없습니다.")
    if user_id == actor.user_id and not req.active:
        raise HTTPException(400, "사용 중인 본인 계정은 비활성화할 수 없습니다.")
    profile.active = req.active
    db.query(AuthSession).filter_by(user_id=user_id).delete()
    db.commit()
    audit(db, actor, "ACCOUNT_ACTIVE_CHANGED", details={"user_id": user_id, "active": req.active})
    return {"success": True}


class PasswordReset(BaseModel):
    temporary_password: str


@router.post("/api/pilot/users/{user_id}/reset-password")
def reset_user_password(user_id: int, req: PasswordReset, db: Session = Depends(get_db),
                        actor: Actor = Depends(require_representative)):
    if user_id == actor.user_id:
        raise HTTPException(400, "본인 비밀번호는 계정 설정에서 변경하세요.")
    user, profile = db.get(User, user_id), db.get(UserProfile, user_id)
    if not user or not profile:
        raise HTTPException(404, "계정이 없습니다.")
    validate_password(req.temporary_password)
    user.password = hash_password(req.temporary_password)
    profile.must_change_password = True
    db.query(AuthSession).filter_by(user_id=user_id).delete()
    db.commit()
    audit(db, actor, "ACCOUNT_PASSWORD_RESET", details={"user_id": user_id})
    return {"success": True}


@router.get("/api/pilot/backup")
def export_backup(db: Session = Depends(get_db), actor: Actor = Depends(require_representative)):
    if not IS_PILOT or not DATABASE_URL.startswith("sqlite"):
        raise HTTPException(400, "이 백업 기능은 SQLite 사내망 시범 환경에서 제공됩니다.")
    work = Path(tempfile.mkdtemp(prefix="c-pilot-backup-"))
    archive = work / "backup.zip"
    with STORAGE_LOCK:
        audit(db, actor, "BACKUP_EXPORT")
        from ..services.backup_service import create_backup
        create_backup(archive)
    def cleanup():
        import shutil
        if work.resolve().parent == Path(tempfile.gettempdir()).resolve() and work.name.startswith("c-pilot-backup-"):
            shutil.rmtree(work)
    return FileResponse(archive, media_type="application/zip", filename="C업체_업무백업_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".zip",
                        headers={"Cache-Control": "no-store"}, background=BackgroundTask(cleanup))
