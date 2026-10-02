"""Observed workflow timing; elapsed time is not active work or measured savings."""
from statistics import median
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..db.models import ContractReview, Document, AuditEvent
from ..services.contract_service import ContractService

router = APIRouter(tags=["C Pilot Measurements"])


@router.get('/api/pilot/performance')
def measured_performance(contract_id: int = None, db: Session = Depends(get_db)):
    from ..services.performance_service import performance
    report=performance(db,contract_id)
    if contract_id is not None and not report['contracts']:
        raise HTTPException(404,'계약을 찾을 수 없습니다.')
    return report


@router.get("/api/pilot/metrics")
def workflow_metrics(db: Session = Depends(get_db)):
    contracts = ContractService().list_contracts(db)
    ids = [row.contract_id for row in contracts]
    base = {
        "scope": "현재 업무 목록의 계약",
        "contract_count": len(ids),
        "confirmed_count": sum(row.approval_status == "CONFIRMED" for row in contracts),
        "awaiting_confirmation_count": sum(row.approval_status != "CONFIRMED" for row in contracts),
        "timed_contract_count": 0,
        "mean_elapsed_seconds": None,
        "median_elapsed_seconds": None,
        "document_registration_count": 0,
        "field_correction_count": 0,
        "measurement": "첫 원본 등록 완료부터 첫 대표 확인까지의 경과시간",
        "limitation": "대기시간을 포함합니다. 실제 검수 작업시간·오경고 수·원본 찾는 시간·도입 전후 절감시간은 별도 측정해야 합니다.",
    }
    if not ids:
        return base
    first_document = {}
    documents = db.query(Document).filter(Document.contract_id.in_(ids)).all()
    for document in documents:
        if document.uploaded_at:
            old = first_document.get(document.contract_id)
            first_document[document.contract_id] = min(old, document.uploaded_at) if old else document.uploaded_at
    first_confirmation = {}
    reviews = db.query(ContractReview).filter(ContractReview.contract_id.in_(ids),
        ContractReview.decision == "CONFIRMED").order_by(ContractReview.created_at).all()
    for review in reviews:
        first_confirmation.setdefault(review.contract_id, review.created_at)
    elapsed = [(stamp - first_document[key]).total_seconds() for key, stamp in first_confirmation.items()
        if key in first_document and stamp >= first_document[key]]
    corrections = db.query(AuditEvent).filter(AuditEvent.contract_id.in_(ids),
        AuditEvent.action == "EXTRACT_CORRECTED").count()
    base.update(document_registration_count=len(documents), field_correction_count=corrections,
        timed_contract_count=len(elapsed),
        mean_elapsed_seconds=round(sum(elapsed) / len(elapsed), 2) if elapsed else None,
        median_elapsed_seconds=round(median(elapsed), 2) if elapsed else None)
    return base
