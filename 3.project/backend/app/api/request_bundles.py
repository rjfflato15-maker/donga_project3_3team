"""Contract-scoped request records and partial replies, with no message sending."""
from typing import Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from ..db.database import get_db
from ..security import Actor, get_current_user
from ..services.request_bundle_service import bundle_context, create_bundle, resolve_items, correct_items
from .workflow import RequestCreate

router = APIRouter(tags=['Request bundles'])


class SelectedIssue(BaseModel):
    issue_key: str = Field(min_length=1, max_length=100)
    reviewed_original: bool = Field(default=False, strict=True)
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class BundleCreate(RequestCreate):
    revision: int = Field(ge=1, strict=True)
    fingerprint: str = Field(pattern=r'^[0-9a-f]{64}$')
    idempotency_key: str = Field(min_length=1, max_length=100)
    items: list[SelectedIssue] = Field(min_length=1, max_length=30)

    @model_validator(mode='after')
    def dates(self):
        # An omitted request day changes at midnight. Exact replay must reach
        # the existing-key lookup before checking the deadline against today.
        # New requests enforce the inherited date rule in create_bundle.
        return self

    @model_validator(mode='after')
    def unique_items(self):
        if len({item.issue_key for item in self.items}) != len(self.items):
            raise ValueError('묶음 항목은 중복 없이 선택하세요.')
        return self


class ItemResolution(BaseModel):
    item_id: int = Field(ge=1, strict=True)
    status: Literal['RECEIVED', 'CANCELLED']
    note: str = Field(min_length=1, max_length=2000)
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class BundleResolution(BaseModel):
    revision: int = Field(ge=1, strict=True)
    fingerprint: str = Field(pattern=r'^[0-9a-f]{64}$')
    request_revision: int = Field(ge=1, strict=True)
    items: list[ItemResolution] = Field(min_length=1, max_length=30)
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    @model_validator(mode='after')
    def unique_items(self):
        if len({item.item_id for item in self.items}) != len(self.items):
            raise ValueError('회신 항목은 중복 없이 선택하세요.')
        return self


class ItemCorrection(BaseModel):
    item_id: int = Field(ge=1, strict=True)
    status: Literal['WAITING_RESPONSE', 'RECEIVED', 'CANCELLED']
    note: str = Field(min_length=3, max_length=2000)
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class BundleCorrection(BundleResolution):
    items: list[ItemCorrection] = Field(min_length=1, max_length=30)


@router.get('/api/pilot/contracts/{contract_id}/resubmission-bundle-context')
def get_bundle_context(contract_id: int, db: Session = Depends(get_db)):
    return bundle_context(db, contract_id)


@router.post('/api/pilot/contracts/{contract_id}/resubmission-bundles', status_code=201)
def record_bundle(contract_id: int, req: BundleCreate, response: Response,
                  db: Session = Depends(get_db), actor: Actor = Depends(get_current_user)):
    result, created = create_bundle(db, contract_id, req, actor)
    response.status_code = 201 if created else 200
    return result


@router.patch('/api/pilot/contracts/{contract_id}/resubmission-bundles/{request_id}/items')
def receive_items(contract_id: int, request_id: int, req: BundleResolution,
                  db: Session = Depends(get_db), actor: Actor = Depends(get_current_user)):
    return resolve_items(db, contract_id, request_id, req, actor)


@router.post('/api/pilot/contracts/{contract_id}/resubmission-bundles/{request_id}/corrections')
def correct_reply_items(contract_id: int, request_id: int, req: BundleCorrection,
                        db: Session = Depends(get_db), actor: Actor = Depends(get_current_user)):
    return correct_items(db, contract_id, request_id, req, actor)
