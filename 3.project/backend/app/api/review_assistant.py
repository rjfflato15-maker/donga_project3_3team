"""Code summaries and review previews without operational writes."""
from typing import Literal
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..services.contract_summary_service import contract_summary

router=APIRouter(tags=['Review assistant previews'])


@router.get('/api/contracts/{contract_id}/summary')
def summary_text(contract_id:int,style:Literal['brief','detail']='brief',revision:int|None=Query(None,ge=1),db:Session=Depends(get_db)):
    return contract_summary(db,contract_id,style,revision)
