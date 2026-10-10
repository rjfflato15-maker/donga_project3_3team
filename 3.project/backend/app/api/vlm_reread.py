import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db.database import get_db
from ..db.models import AuditEvent, Document
from ..security import Actor, require_operator
from ..services.storage_service import STORAGE_LOCK
from ..services import vlm_reread_service as service
from ..schemas.document import AnalysisFields, Correction, DocumentResponse
from ..services.document_correction_service import apply_correction

router = APIRouter(tags=['Visual rereading'])


class RereadRequest(BaseModel):
    revision: int = Field(ge=1)
    page: int = Field(default=1, ge=1)
    fields: List[str] = Field(min_length=1, max_length=9)


class ConfirmRequest(BaseModel):
    run_id: int = Field(ge=1)
    revision: int = Field(ge=1)
    fields: List[str] = Field(min_length=1, max_length=9)
    note: str = Field(min_length=1, max_length=1000)
    acknowledge_original: bool = False


@router.get('/api/vlm/status')
def status():
    return service.vlm_status()


@router.get('/api/documents/{document_id}/vlm-reread')
def latest(document_id: int, revision: int, masked: bool = True, db: Session = Depends(get_db)):
    return service.latest_result(db, document_id, revision, masked)


@router.post('/api/documents/{document_id}/vlm-reread')
def reread(document_id: int, req: RereadRequest, masked: bool = True,
           db: Session = Depends(get_db), actor: Actor = Depends(require_operator)):
    return service.reread(db, document_id, req.revision, req.page, req.fields, actor, masked)


@router.post('/api/documents/{document_id}/vlm-confirm', response_model=DocumentResponse)
def confirm(document_id: int, req: ConfirmRequest, db: Session = Depends(get_db),
            actor: Actor = Depends(require_operator)):
    if not req.acknowledge_original or not req.note.strip() or len(req.fields) != len(set(req.fields)):
        raise HTTPException(422, '원문 대조 동의·선택 항목·확인 사유가 필요합니다.')
    with STORAGE_LOCK:
        source = service.snapshot(db, document_id, req.revision)
        event = db.get(AuditEvent, req.run_id)
        if not event or event.document_id != document_id or event.action != 'VLM_REREAD_COMPLETED':
            raise HTTPException(404, '이 서류의 재판독 결과를 찾을 수 없습니다.')
        data = json.loads(event.details)
        if any(data.get(key) != source[key] for key in ('revision', 'fingerprint', 'source_sha256')):
            raise HTTPException(409, '재판독 이후 자료가 변경되었습니다. 현재 원문으로 다시 읽으세요.')
        candidates = {item['field']: item for item in data['candidates']}
        if any(key not in candidates or not candidates[key]['usable'] for key in req.fields):
            raise HTTPException(422, '형식을 확인한 후보 항목만 저장할 수 있습니다.')
        values = {key: candidates[key]['value'] for key in req.fields}
        review = {'run_id': event.event_id, 'model': data['model'], 'page': data['page'],
            'source_sha256': data['source_sha256'], 'prompt_version': data['prompt_version'],
            'values': values, 'confirmed_fields': req.fields, 'evidence_verified': False,
            'automatically_applied': False}
        doc = db.get(Document, document_id)
        return apply_correction(document_id, Correction(fields=AnalysisFields(**values),
            document_type=doc.document_type, revision=req.revision, confirmed_fields=req.fields,
            note='VLM 재판독 후보를 원문 대조 후 확인: ' + req.note.strip()), db, actor, review)
