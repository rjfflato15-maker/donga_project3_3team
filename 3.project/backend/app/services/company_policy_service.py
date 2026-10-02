# Existing settings API remains the canonical required-documents source.
"""Company presets and at most two approval stages; inference stays unchanged."""
import json
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from ..db.models import CompanySetting, ContractReview, ApprovalSignoff
from ..schemas.common import CORE_6_DOCUMENT_TYPES, DocumentType
from .workflow_service import required_types
Role = Literal['operator', 'representative']

class ApprovalStep(BaseModel):
    role: Role
    label: str = Field(min_length=1, max_length=40)
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

class CompanyPolicy(BaseModel):
    company_type: Literal['SOLE_PROPRIETOR', 'SMALL_BUSINESS', 'MID_SIZED'] = 'SMALL_BUSINESS'
    required_document_types: list[DocumentType] = Field(default_factory=lambda: list(CORE_6_DOCUMENT_TYPES), min_length=1)
    roles: dict[Role, str] = Field(default_factory=lambda: {'operator': '담당자', 'representative': '대표'})
    approval_steps: list[ApprovalStep] = Field(default_factory=lambda: [ApprovalStep(role='representative', label='최종 확인')], min_length=1, max_length=2)
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    @model_validator(mode='after')
    def validate_policy(self):
        values = [t.value for t in self.required_document_types]
        if 'unknown' in values or len(set(values)) != len(values):
            raise ValueError('필수 서류는 중복 없이 지정하고 unknown은 제외하세요.')
        if set(self.roles) != {'operator', 'representative'} or any((not v.strip() or len(v) > 80 for v in self.roles.values())):
            raise ValueError('담당자·대표 역할의 표시 이름을 모두 지정하세요.')
        if self.approval_steps[-1].role != 'representative':
            raise ValueError('최종 결재는 대표 권한으로 설정하세요.')
        return self

def company_policy(db):
    row = db.get(CompanySetting, 'organization_policy')
    result = CompanyPolicy.model_validate_json(row.value) if row else CompanyPolicy()
    result.required_document_types = required_types(db)
    return result

def presets():
    results = []
    for kind in ('SOLE_PROPRIETOR', 'SMALL_BUSINESS', 'MID_SIZED'):
        policy = CompanyPolicy(company_type=kind)
        if kind == 'SOLE_PROPRIETOR':
            policy.roles['representative'] = '사업주'
        if kind == 'MID_SIZED':
            policy.approval_steps = [ApprovalStep(role='operator', label='담당 검토'), ApprovalStep(role='representative', label='최종 결재')]
        results.append(policy.model_dump(mode='json'))
    return results

def current_cycle(db, contract_id):
    latest = db.query(ContractReview).filter_by(contract_id=contract_id).order_by(ContractReview.review_id.desc()).first()
    return latest.review_id if latest else 0

def first_signoff(db, contract_id, revision, fingerprint):
    return db.query(ApprovalSignoff).filter_by(contract_id=contract_id, revision=revision, fingerprint=fingerprint, cycle_review_id=current_cycle(db, contract_id)).order_by(ApprovalSignoff.signoff_id.desc()).first()

def require_prior_approval(db, contract_id, revision, fingerprint, actor):
    if len(company_policy(db).approval_steps) == 1:
        return
    signoff = first_signoff(db, contract_id, revision, fingerprint)
    if not signoff:
        raise HTTPException(409, '현재 자료의 1단계 검토를 먼저 완료하세요.')
    if signoff.actor_id == actor.user_id:
        raise HTTPException(403, '2단계 결재는 1단계와 다른 사람이 진행해야 합니다.')

def approval_state(db, contract_id, revision, fingerprint, *, include_history=True):
    steps = company_policy(db).approval_steps
    latest = db.query(ContractReview).filter_by(contract_id=contract_id).order_by(ContractReview.review_id.desc()).first()
    confirmed = bool(latest and latest.decision == 'CONFIRMED' and (latest.revision == revision) and (json.loads(latest.snapshot_json).get('fingerprint') == fingerprint))
    signoff = first_signoff(db, contract_id, revision, fingerprint)
    completed = len(steps) if confirmed else 1 if len(steps) == 2 and signoff else 0
    history = []
    if include_history:
        history = [{'signoff_id': r.signoff_id, 'revision': r.revision, 'actor_name': r.actor_name, 'note': r.note, 'created_at': r.created_at.isoformat(), 'current': bool(signoff and r.signoff_id == signoff.signoff_id)} for r in db.query(ApprovalSignoff).filter_by(contract_id=contract_id).order_by(ApprovalSignoff.signoff_id.desc()).limit(30)]
    return {'steps': [s.model_dump() for s in steps], 'completed_steps': completed, 'next_step': None if confirmed else completed + 1, 'status': 'CONFIRMED' if confirmed else 'IN_PROGRESS' if completed else 'PENDING', 'history': history}
