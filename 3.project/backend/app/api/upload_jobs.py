from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,BackgroundTasks,UploadFile,File,Form
from pydantic import BaseModel,Field,ConfigDict
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..db.models import DocumentUploadJob
from ..schemas.common import DocumentType
from ..security import Actor,require_operator
from ..services.storage_service import read_upload,STORAGE_LOCK
from ..services.upload_job_service import enqueue,response,retry,run_upload_job,require_visible_contract

router=APIRouter(tags=['Document upload jobs'])


@router.post('/api/pilot/contracts/{contract_id}/document-jobs',status_code=202)
def create_job(contract_id:int,background_tasks:BackgroundTasks,file:UploadFile=File(...),
               idempotency_key:str=Form(...,min_length=8,max_length=100),revision:int=Form(...,ge=1),
               upload_mode:Literal['ADD','REISSUE']=Form('ADD'),target_document_type:DocumentType|None=Form(None),
               replaces_document_id:int|None=Form(None),change_note:str=Form('',max_length=2000),
               db:Session=Depends(get_db),actor:Actor=Depends(require_operator)):
    if upload_mode=='REISSUE' and (replaces_document_id is None or not change_note.strip()):
        raise HTTPException(400,'재발행 대상과 변경 사유가 필요합니다.')
    if upload_mode=='ADD' and replaces_document_id is not None:raise HTTPException(400,'교체에는 REISSUE를 사용하세요.')
    payload={'revision':revision,'upload_mode':upload_mode,'target_document_type':target_document_type.value if target_document_type else None,
             'replaces_document_id':replaces_document_id,'change_note':change_note.strip()}
    row,replayed=enqueue(db,contract_id,file.filename,read_upload(file),idempotency_key,payload,actor)
    data={**response(row,db),'replayed':replayed}
    db.rollback()
    if data['status']=='QUEUED':background_tasks.add_task(run_upload_job,data['job_id'])
    return data


@router.get('/api/pilot/document-jobs/{job_id}')
def get_job(job_id:str,db:Session=Depends(get_db)):
    row=db.get(DocumentUploadJob,job_id)
    if not row:raise HTTPException(404,'등록 작업을 찾을 수 없습니다.')
    require_visible_contract(db,row.contract_id)
    return response(row,db)


class JobRetry(BaseModel):
    job_revision:int=Field(ge=1)
    contract_revision:int=Field(ge=1)
    model_config=ConfigDict(extra='forbid')


@router.post('/api/pilot/document-jobs/{job_id}/retry',status_code=202)
def retry_job(job_id:str,req:JobRetry,background_tasks:BackgroundTasks,db:Session=Depends(get_db),actor:Actor=Depends(require_operator)):
    with STORAGE_LOCK:
        row=db.get(DocumentUploadJob,job_id)
        if not row:raise HTTPException(404,'등록 작업을 찾을 수 없습니다.')
        row=retry(db,row,req.job_revision,req.contract_revision,actor)
        data=response(row,db)
    db.rollback()
    background_tasks.add_task(run_upload_job,job_id)
    return data
