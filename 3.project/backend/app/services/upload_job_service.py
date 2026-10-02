"""Durable one-file upload requests; publication and retry are idempotent."""
import hashlib
import json
from datetime import datetime, timedelta
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from ..db.models import DocumentUploadJob, Contract, Document, UserProfile
from ..security import Actor
from .storage_service import STORAGE_LOCK, store_original, resolve_path, clean_name
from .workflow_service import policy_for
from .pipeline_service import PipelineService


def response(row,db):
    document=db.get(Document,row.document_id) if row.document_id is not None else None
    active=bool(document and (not document.version or document.version.is_current))
    return {'job_id':row.job_id,'contract_id':row.contract_id,'file_name':row.file_name,'status':row.status,'stage':row.stage,
            'job_revision':row.job_revision,'attempt_count':row.attempt_count,'document_id':row.document_id,
            'document_available':bool(document),'document_is_current':active,'error_code':row.error_code,'error_message':row.error_message,
            'created_at':row.created_at.isoformat()+'Z','updated_at':row.updated_at.isoformat()+'Z',
            'retry_creates_document':row.document_id is None,'lease_expires_at':row.lease_expires_at.isoformat()+'Z' if row.lease_expires_at else None}


def enqueue(db,cid,name,content,key,payload,actor):
    filename=clean_name(name)
    digest=hashlib.sha256(content).hexdigest()
    requested={'file_name':filename,'source_sha256':digest,**payload}
    receipt=hashlib.sha256(json.dumps(requested,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    with STORAGE_LOCK:
        existing=db.query(DocumentUploadJob).filter_by(contract_id=cid,idempotency_key=key).first()
        if existing:
            if existing.request_sha256!=receipt or existing.actor_id!=actor.user_id:
                raise HTTPException(409,'같은 idempotency_key를 다른 파일·조건·사용자에 재사용할 수 없습니다.')
            return existing,True
        if not db.get(Contract,cid):raise HTTPException(404,'계약을 찾을 수 없습니다.')
        if policy_for(db,cid)['revision']!=payload['revision']:raise HTTPException(409,'최신 계약 revision으로 등록하세요.')
    db.rollback()
    source_key,_,sha=store_original(cid,filename,content)
    with STORAGE_LOCK:
        row=DocumentUploadJob(job_id=str(uuid4()),contract_id=cid,idempotency_key=key,request_sha256=receipt,
                              source_path=source_key,source_sha256=sha,file_name=filename,actor_id=actor.user_id,
                              payload_json=json.dumps(payload,ensure_ascii=False))
        db.add(row)
        try:db.commit()
        except IntegrityError:
            db.rollback()
            row=db.query(DocumentUploadJob).filter_by(contract_id=cid,idempotency_key=key).first()
            if not row or row.request_sha256!=receipt or row.actor_id!=actor.user_id:
                raise HTTPException(409,'다른 요청이 같은 키로 등록되었습니다.')
            return row,True
        return row,False


def retry(db,row,job_revision,contract_revision,actor):
    if row.actor_id!=actor.user_id:raise HTTPException(403,'처음 등록을 요청한 담당자가 재시도할 수 있습니다.')
    if row.job_revision!=job_revision:raise HTTPException(409,'작업 상태가 변경되었습니다. 다시 불러오세요.')
    if row.status=='COMPLETED':raise HTTPException(409,'이미 완료한 작업입니다. 결과 문서를 확인하세요.')
    if row.status in {'RUNNING','VALIDATING'} and row.lease_expires_at and row.lease_expires_at>datetime.utcnow():
        raise HTTPException(409,'처리가 진행 중입니다. 상태를 확인하세요.')
    if policy_for(db,row.contract_id)['revision']!=contract_revision:raise HTTPException(409,'최신 계약 revision으로 재시도하세요.')
    payload=json.loads(row.payload_json)
    payload['revision']=contract_revision
    changed=db.query(DocumentUploadJob).filter_by(job_id=row.job_id,job_revision=job_revision).update({
        'payload_json':json.dumps(payload,ensure_ascii=False),'status':'QUEUED','stage':'QUEUED',
        'lease_token':None,'lease_expires_at':None,'error_code':None,'error_message':None,
        'job_revision':job_revision+1,'updated_at':datetime.utcnow()},synchronize_session='fetch')
    if changed!=1:
        db.rollback();raise HTTPException(409,'동시에 작업 상태가 변경되었습니다.')
    db.commit();db.refresh(row)
    return row


def run_upload_job(job_id):
    from ..db.database import SessionLocal
    token=str(uuid4())
    with SessionLocal() as db:
        with STORAGE_LOCK:
            row=db.get(DocumentUploadJob,job_id)
            if not row or row.status!='QUEUED':return
            revision=row.job_revision
            changed=db.query(DocumentUploadJob).filter_by(job_id=job_id,status='QUEUED',job_revision=revision).update({
                'status':'RUNNING','stage':'ANALYZING' if row.document_id is None else 'VALIDATING','lease_token':token,
                'lease_expires_at':datetime.utcnow()+timedelta(minutes=10),'job_revision':revision+1,
                'attempt_count':row.attempt_count+1,'updated_at':datetime.utcnow()},synchronize_session='fetch')
            if changed!=1:db.rollback();return
            db.commit();db.refresh(row)
            args=json.loads(row.payload_json)
            cid,name,source,sha,uid,did=row.contract_id,row.file_name,row.source_path,row.source_sha256,row.actor_id,row.document_id
        try:
            profile=db.get(UserProfile,uid)
            if not profile or not profile.active or profile.must_change_password or profile.role not in {'operator','admin'}:
                raise HTTPException(403,'자료 등록 권한이 변경되었습니다.')
            actor=Actor(uid,'',profile.role,profile.display_name,False)
            db.rollback()
            pipeline=PipelineService()
            if did is None:
                path=resolve_path(source)
                if not path:raise HTTPException(422,'보관한 원본이 없습니다. 새 파일로 등록하세요.')
                content=path.read_bytes()
                if hashlib.sha256(content).hexdigest()!=sha:raise HTTPException(422,'보관한 원본이 변경되었습니다. 새 파일로 등록하세요.')
                pipeline.process_document_upload(db,cid,name,content,args.get('target_document_type') or '',
                    replaces_document_id=args.get('replaces_document_id'),expected_contract_revision=args['revision'],
                    change_note=args.get('change_note',''),actor=actor,upload_job_id=job_id,upload_job_lease=token,require_readable=True)
            else:
                # The document was already committed, perhaps before a crash.
                # Recover only rule validation; never repeat OCR or LLM calls.
                pipeline.revalidate_contract(db,cid)
            with STORAGE_LOCK:
                db.expire_all();row=db.get(DocumentUploadJob,job_id)
                if row and row.lease_token==token:
                    row.status='COMPLETED';row.stage='COMPLETED';row.job_revision+=1
                    row.error_code=None;row.error_message=None;row.lease_token=None;row.lease_expires_at=None;row.updated_at=datetime.utcnow()
                    db.commit()
        except Exception as error:
            db.rollback()
            with STORAGE_LOCK:
                row=db.get(DocumentUploadJob,job_id)
                if row and row.lease_token==token:
                    row.status='FAILED';row.stage='FAILED';row.job_revision+=1;row.updated_at=datetime.utcnow()
                    row.error_code={403:'ACTOR_INACTIVE',404:'NOT_FOUND',409:'DATA_CHANGED',422:'SOURCE_UNREADABLE'}.get(getattr(error,'status_code',None),'PROCESSING_FAILED')
                    row.error_message=str(error.detail)[:500] if isinstance(error,HTTPException) else '문서 처리를 완료하지 못했습니다. 원문과 현재 계약 상태를 확인하세요.'
                    row.lease_token=None;row.lease_expires_at=None
                    db.commit()
