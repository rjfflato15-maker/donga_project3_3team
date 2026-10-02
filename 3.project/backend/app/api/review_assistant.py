"""Code summaries and review previews without operational writes."""
from typing import Literal
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..services.contract_summary_service import contract_summary
from ..services.review_assistant_service import assistant_preview

router=APIRouter(tags=['Review assistant previews'])


@router.get('/api/contracts/{contract_id}/summary')
def summary_text(contract_id:int,style:Literal['brief','detail']='brief',revision:int|None=Query(None,ge=1),db:Session=Depends(get_db)):
    return contract_summary(db,contract_id,style,revision)


class AssistantPreviewRequest(BaseModel):
    revision:int=Field(ge=1)
    fingerprint:str=Field(min_length=64,max_length=64)
    issue_ids:list[str]|None=Field(default=None,max_length=100)
    model_config=ConfigDict(extra='forbid')


@router.post('/api/pilot/contracts/{contract_id}/assistant-preview')
def preview_assistant(contract_id:int,req:AssistantPreviewRequest,db:Session=Depends(get_db)):
    return assistant_preview(db,contract_id,req.revision,req.fingerprint,req.issue_ids)
