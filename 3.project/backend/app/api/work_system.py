"""Shared state, stored activity and recovery search for the local company."""
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Session

from ..db.database import get_db
from ..db.models import Contract, WorkAssignment
from ..services.activity_service import activity, current_basis
from ..services.contract_service import ContractService
from ..services.readonly_review_service import require_unchanged

router = APIRouter(tags=['Contract work system'])
STAGES = {'RECEIVING', 'CHECK', 'WAITING', 'APPROVAL', 'PAYMENT', 'DONE'}
SEOUL = timezone(timedelta(hours=9))  # Match existing server KST, including Windows without tzdata.


@router.get('/api/contracts/search')
def search_contracts(q: str = Query('', max_length=200), stage: str | None = None,
                     completion: Literal['ALL', 'OPEN', 'DONE'] = 'ALL',
                     registered_by_user_id: int | None = Query(None, ge=1),
                     assignee_id: int | None = Query(None, ge=1),
                     date_from: date | None = None, date_to: date | None = None,
                     limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                     db: Session = Depends(get_db)):
    if stage is not None and stage not in STAGES:
        raise HTTPException(422, '단계는 RECEIVING/CHECK/WAITING/APPROVAL/PAYMENT/DONE입니다.')
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, '검색 시작일은 종료일보다 늦을 수 없습니다.')
    query = db.query(Contract)
    text = q.strip().casefold()
    if text:
        predicates = [func.lower(Contract.title).contains(text, autoescape=True),
                      func.lower(Contract.vendor_name).contains(text, autoescape=True),
                      cast(Contract.contract_id, String).contains(text, autoescape=True)]
        digits = ''.join(c for c in text if c.isdigit())
        if digits and all(c.isdigit() or c in ',원 ' for c in text):
            predicates.append(cast(Contract.contract_amount, String).contains(digits, autoescape=True))
        query = query.filter(or_(*predicates))
    if registered_by_user_id is not None:
        query = query.filter(Contract.user_id == registered_by_user_id)
    if assignee_id is not None:
        query = query.filter(Contract.contract_id.in_(db.query(WorkAssignment.contract_id).filter(
            WorkAssignment.assignee_id == assignee_id,
            WorkAssignment.status.in_(['OPEN', 'IN_PROGRESS']))))
    for day, end in [(date_from, False), (date_to, True)]:
        if day is not None:
            try:
                boundary = datetime.combine(day, time.min, SEOUL)
                if end:
                    boundary += timedelta(days=1)
                utc = boundary.astimezone(timezone.utc).replace(tzinfo=None)
            except (ValueError, OverflowError):
                raise HTTPException(422, '검색 날짜 범위를 확인하세요.')
            query = query.filter(Contract.created_at < utc if end else Contract.created_at >= utc)
    rows = ContractService().list_contracts(db, query=query)
    if stage is not None:
        rows = [row for row in rows if row.stage == stage]
    if completion != 'ALL':
        rows = [row for row in rows if (row.stage == 'DONE') == (completion == 'DONE')]
    return {'items': rows[offset:offset + limit], 'total': len(rows), 'limit': limit, 'offset': offset,
            'date_basis': 'CONTRACT_CREATED_AT_ASIA_SEOUL',
            'id_search_basis': 'INTERNAL_CONTRACT_ID',
            'assignee_filter_basis': 'ACTIVE_WORK_ASSIGNMENT',
            'registered_by_filter_basis': 'CONTRACT_REGISTRANT'}


@router.get('/api/contracts/{contract_id}/work-state')
def get_work_state(contract_id: int, revision: int | None = Query(None, ge=1),
                   fingerprint: str | None = None, db: Session = Depends(get_db)):
    basis = current_basis(db, contract_id, revision, fingerprint)
    detail = ContractService().get_contract_detail(db, contract_id)
    result = detail.work_state
    require_unchanged(db, basis)
    return result


@router.get('/api/contracts/{contract_id}/activity')
def get_activity(contract_id: int, limit: int = Query(50, ge=1, le=200),
                 before_event_id: int | None = Query(None, ge=1), masked: bool = True,
                 revision: int | None = Query(None, ge=1), fingerprint: str | None = None,
                 db: Session = Depends(get_db)):
    return activity(db, contract_id, limit=limit, before_event_id=before_event_id,
                    masked=masked, revision=revision, fingerprint=fingerprint)
