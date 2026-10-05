"""Recording a payment fact never transfers funds or changes approval rights."""
import re
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from ..db.database import get_db
from ..security import Actor, get_current_user
from ..services.contract_service import ContractService
from ..services.payment_service import record_payment, reconfirm_payment

router = APIRouter(tags=['Payment records'])


class PaymentRequest(BaseModel):
    paid_on: str
    method: Literal['TRANSFER', 'OTHER']
    note: str = Field(default='', max_length=2000)
    revision: int = Field(ge=1, strict=True)
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    @field_validator('paid_on')
    @classmethod
    def validate_day(cls, value):
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            raise ValueError('지급일은 YYYY-MM-DD 형식으로 입력하세요.')
        day = date.fromisoformat(value)
        if day > (datetime.now(timezone.utc) + timedelta(hours=9)).date():
            raise ValueError('미래 지급일은 기록할 수 없습니다.')
        return value


class PaymentReconfirmation(BaseModel):
    revision: int = Field(ge=1, strict=True)
    note: str = Field(min_length=10, max_length=2000)
    acknowledge_same_payment: Literal[True]
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    @field_validator('acknowledge_same_payment', mode='before')
    @classmethod
    def require_explicit_boolean(cls, value):
        if value is not True:
            raise ValueError('기존 지급 사실과 동일함을 확인해야 합니다.')
        return value


def payment_actor(actor: Actor = Depends(get_current_user)):
    if actor.role not in {'operator', 'representative', 'admin'}:
        raise HTTPException(403, '담당자 또는 대표 권한이 필요합니다.')
    return actor


@router.post('/api/pilot/contracts/{contract_id}/payment', status_code=201)
def create_payment(contract_id: int, req: PaymentRequest, response: Response,
                   db: Session = Depends(get_db), actor: Actor = Depends(payment_actor)):
    state, created = record_payment(db, contract_id, req, actor)
    response.status_code = 201 if created else 200
    return state


@router.get('/api/pilot/contracts/{contract_id}/payment')
def get_payment(contract_id: int, db: Session = Depends(get_db)):
    detail = ContractService().get_contract_detail(db, contract_id)
    if not detail:
        raise HTTPException(404, '계약을 찾을 수 없습니다.')
    return detail.payment


@router.post('/api/pilot/contracts/{contract_id}/payment/{payment_id}/reconfirm')
def confirm_payment(contract_id: int, payment_id: int, req: PaymentReconfirmation,
                    db: Session = Depends(get_db), actor: Actor = Depends(payment_actor)):
    state, _ = reconfirm_payment(db, contract_id, payment_id, req, actor)
    return state
