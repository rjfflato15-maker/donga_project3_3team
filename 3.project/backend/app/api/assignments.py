"""Task ownership never grants document or approval permissions."""
import json
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..db.models import Contract, Document, WorkAssignment, UserProfile, AuditEvent
from ..security import Actor, get_current_user
from ..services.storage_service import STORAGE_LOCK
from ..services.workflow_service import policy_for, fingerprint_for
from ..services.pipeline_service import PipelineService
from ..services.document_version_service import require_current

router=APIRouter(tags=['Work assignments'])


def basis(db,cid):
    contract=db.get(Contract,cid)
    if not contract:raise HTTPException(404,'계약을 찾을 수 없습니다.')
    inputs=PipelineService().validation_inputs(db,contract)
    return policy_for(db,cid)['revision'],fingerprint_for(db,contract,inputs)


def assignee(db,uid):
    profile=db.get(UserProfile,uid)
    if not profile or not profile.active or profile.role not in {'operator','representative','admin'}:
        raise HTTPException(400,'현재 활성 업무 계정에게 맡기세요.')
    return profile


def payload(row,current_basis):
    stale=(row.contract_revision,row.contract_fingerprint)!=current_basis
    today=datetime.now(timezone(timedelta(hours=9))).date().isoformat()
    return {'assignment_id':row.assignment_id,'contract_id':row.contract_id,'document_id':row.document_id,
            'contract_revision':row.contract_revision,'assignment_revision':row.assignment_revision,
            'assigner_id':row.assigner_id,'assigner_name':row.assigner_name,'assignee_id':row.assignee_id,'assignee_name':row.assignee_name,
            'title':row.title,'memo':row.memo,'due_on':row.due_on,'status':row.status,'is_stale':stale,
            'overdue':bool(row.due_on and row.due_on<today and row.status in {'OPEN','IN_PROGRESS'}),
            'created_at':row.created_at.isoformat()+'Z','updated_at':row.updated_at.isoformat()+'Z',
            'completed_at':row.completed_at.isoformat()+'Z' if row.completed_at else None}


def record(db,actor,action,row,details):
    db.add(AuditEvent(actor_id=actor.user_id,actor_name=actor.display_name,action=action,contract_id=row.contract_id,
                      document_id=row.document_id,details=json.dumps({'assignment_id':row.assignment_id,**details},ensure_ascii=False)))


class AssignmentCreate(BaseModel):
    assignee_id:int=Field(ge=1)
    contract_revision:int=Field(ge=1)
    document_id:int|None=None
    title:str=Field(min_length=1,max_length=200)
    memo:str=Field(default='',max_length=2000)
    due_on:date|None=None
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)


class AssignmentChange(BaseModel):
    action:Literal['START','COMPLETE','CANCEL','REASSIGN','UPDATE']
    assignment_revision:int=Field(ge=1)
    note:str=Field(min_length=1,max_length=2000)
    assignee_id:int|None=None
    contract_revision:int|None=None
    title:str|None=Field(default=None,min_length=1,max_length=200)
    memo:str|None=Field(default=None,max_length=2000)
    due_on:date|None=None
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)

    @model_validator(mode='after')
    def action_fields(self):
        if self.action=='REASSIGN' and (self.assignee_id is None or self.contract_revision is None):
            raise ValueError('재배정에는 assignee_id와 현재 contract_revision이 필요합니다.')
        if self.action!='REASSIGN' and (self.assignee_id is not None or self.contract_revision is not None):
            raise ValueError('담당자와 자료 기준은 REASSIGN으로 변경하세요.')
        if self.action not in {'UPDATE','REASSIGN'} and {'title','memo','due_on'} & self.model_fields_set:
            raise ValueError('업무 내용·기한 변경에는 UPDATE 또는 REASSIGN을 사용하세요.')
        return self


@router.get('/api/pilot/assignees')
def list_assignees(db:Session=Depends(get_db)):
    return [{'user_id':p.user_id,'display_name':p.display_name,'role':p.role} for p in db.query(UserProfile).filter_by(active=True).all() if p.role in {'operator','representative','admin'}]


@router.get('/api/pilot/assignments/mine')
def my_assignments(include_closed:bool=False,db:Session=Depends(get_db),actor:Actor=Depends(get_current_user)):
    query=db.query(WorkAssignment).filter_by(assignee_id=actor.user_id)
    if not include_closed:query=query.filter(WorkAssignment.status.in_(['OPEN','IN_PROGRESS']))
    bases={}
    items=[]
    for row in query.order_by(WorkAssignment.assignment_id.desc()).all():
        if row.contract_id not in bases:bases[row.contract_id]=basis(db,row.contract_id)
        items.append(payload(row,bases[row.contract_id]))
    return {'assignee_id':actor.user_id,'assignments':items,'count':len(items)}


@router.get('/api/pilot/contracts/{contract_id}/assignments')
def list_assignments(contract_id:int,db:Session=Depends(get_db)):
    current=basis(db,contract_id)
    return {'contract_id':contract_id,'contract_revision':current[0],
            'assignments':[payload(r,current) for r in db.query(WorkAssignment).filter_by(contract_id=contract_id).order_by(WorkAssignment.assignment_id.desc()).all()]}


@router.post('/api/pilot/contracts/{contract_id}/assignments',status_code=201)
def create_assignment(contract_id:int,req:AssignmentCreate,db:Session=Depends(get_db),actor:Actor=Depends(get_current_user)):
    with STORAGE_LOCK:
        current=basis(db,contract_id)
        if req.contract_revision!=current[0]:raise HTTPException(409,'계약 자료가 변경되었습니다. 최신 자료로 맡기세요.')
        profile=assignee(db,req.assignee_id)
        if req.document_id is not None:
            doc=db.get(Document,req.document_id)
            if not doc or doc.contract_id!=contract_id:raise HTTPException(404,'이 계약의 문서를 찾을 수 없습니다.')
            require_current(doc)
        row=WorkAssignment(contract_id=contract_id,document_id=req.document_id,contract_revision=current[0],contract_fingerprint=current[1],
                           assigner_id=actor.user_id,assigner_name=actor.display_name,assignee_id=req.assignee_id,assignee_name=profile.display_name,
                           title=req.title,memo=req.memo,due_on=req.due_on.isoformat() if req.due_on else None)
        db.add(row);db.flush()
        record(db,actor,'ASSIGNMENT_CREATED',row,{'after':payload(row,current)})
        db.commit()
        return payload(row,current)


@router.patch('/api/pilot/contracts/{contract_id}/assignments/{assignment_id}')
def change_assignment(contract_id:int,assignment_id:int,req:AssignmentChange,db:Session=Depends(get_db),actor:Actor=Depends(get_current_user)):
    with STORAGE_LOCK:
        current=basis(db,contract_id)
        row=db.get(WorkAssignment,assignment_id)
        if not row or row.contract_id!=contract_id:raise HTTPException(404,'맡기기 기록이 없습니다.')
        if req.assignment_revision!=row.assignment_revision:raise HTTPException(409,'다른 사용자가 업무를 변경했습니다. 새로 불러오세요.')
        if row.status in {'COMPLETED','CANCELLED'}:raise HTTPException(409,'완료·취소한 업무는 변경할 수 없습니다.')
        manager=actor.user_id==row.assigner_id or actor.role in {'representative','admin'}
        owner=actor.user_id==row.assignee_id
        if req.action in {'REASSIGN','CANCEL','UPDATE'} and not manager:raise HTTPException(403,'맡긴 사람 또는 대표가 변경할 수 있습니다.')
        if req.action=='START' and not owner:raise HTTPException(403,'현재 맡은 사람이 시작할 수 있습니다.')
        if req.action=='COMPLETE' and not (owner or actor.role in {'representative','admin'}):raise HTTPException(403,'현재 맡은 사람 또는 대표가 완료할 수 있습니다.')
        before=payload(row,current)
        if req.action=='START' and before['is_stale']:
            raise HTTPException(409,'맡긴 뒤 계약 자료가 바뀌었습니다. 현재 자료를 기준으로 재배정하세요.')
        if req.action=='COMPLETE' and row.document_id is not None:
            doc=db.get(Document,row.document_id)
            if not doc or doc.contract_id!=contract_id:
                raise HTTPException(409,'맡긴 문서가 현재 계약에 없습니다. 이 업무를 취소하고 현재 자료에 새 업무를 맡기세요.')
            require_current(doc)
        updates={'assignment_revision':row.assignment_revision+1,'updated_at':datetime.utcnow()}
        if req.action=='REASSIGN':
            if req.contract_revision!=current[0]:raise HTTPException(409,'최신 계약 revision으로 재배정하세요.')
            profile=assignee(db,req.assignee_id)
            if row.document_id is not None:
                doc=db.get(Document,row.document_id)
                if not doc or (doc.version and not doc.version.is_current):
                    raise HTTPException(409,'재발행된 문서의 업무입니다. 현재 문서에 새 업무를 맡기고 이전 업무를 취소하세요.')
            updates.update(assignee_id=req.assignee_id,assignee_name=profile.display_name,status='OPEN',contract_revision=current[0],contract_fingerprint=current[1])
        elif req.action=='START':
            if row.status!='OPEN':raise HTTPException(409,'이미 진행 중인 업무입니다.')
            updates['status']='IN_PROGRESS'
        elif req.action=='COMPLETE':updates.update(status='COMPLETED',completed_at=datetime.utcnow())
        elif req.action=='CANCEL':updates['status']='CANCELLED'
        for key in ('title','memo','due_on'):
            if key in req.model_fields_set:
                value=getattr(req,key)
                if key=='due_on':value=value.isoformat() if value else None
                if key in {'title','memo'} and value is None:raise HTTPException(422,'제목과 메모는 null일 수 없습니다.')
                updates[key]=value
        changed=db.query(WorkAssignment).filter_by(assignment_id=assignment_id,assignment_revision=req.assignment_revision).update(updates,synchronize_session='fetch')
        if changed!=1:
            db.rollback();raise HTTPException(409,'동시에 업무가 변경되었습니다. 다시 불러오세요.')
        db.flush();db.refresh(row)
        details={'action':req.action,'note':req.note,'before':before,'after':payload(row,current)}
        if req.action=='COMPLETE':
            # Fixing the assigned work can change its basis. Keep both snapshots;
            # completing a task does not approve or refresh the contract review.
            details['completion_context']={'was_stale':before['is_stale'],
                'assigned_basis':{'revision':row.contract_revision,'fingerprint':row.contract_fingerprint},
                'completed_basis':{'revision':current[0],'fingerprint':current[1]}}
        record(db,actor,'ASSIGNMENT_CHANGED',row,details)
        db.commit()
        return payload(row,current)
