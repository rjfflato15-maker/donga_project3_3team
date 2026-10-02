"""Copy stored inputs, run local rules in memory, and discard the read transaction."""
from fastapi import HTTPException
from ..db.models import Contract, ValidationResult
from ..validation.engine import RuleEngine
from ..integrations.nts_client import DisabledNtsClient
from .pipeline_service import PipelineService
from .workflow_service import policy_for, required_types, fingerprint_for, review_state


def snapshot(db,cid,revision=None,fingerprint=None):
    contract=db.get(Contract,cid)
    if not contract:raise HTTPException(404,'계약을 찾을 수 없습니다.')
    documents=PipelineService().validation_inputs(db,contract)
    policy=policy_for(db,cid)
    digest=fingerprint_for(db,contract,documents)
    if revision is not None and revision!=policy['revision'] or fingerprint is not None and fingerprint!=digest:
        raise HTTPException(409,'계약 자료가 변경되었습니다. 최신 검수 자료를 불러오세요.')
    data={'contract_id':cid,'revision':policy['revision'],'fingerprint':digest,
          'reference':{'title':contract.title,'vendor_name':contract.vendor_name,'business_number':contract.business_number,'contract_amount':contract.contract_amount},
          'documents':documents,'policy':policy,'required_types':required_types(db),
          'workflow':review_state(db,cid,digest),
          'recorded_checks':[{'rule_id':r.validation_type,'field':r.field,'status':r.status,'expected':r.expected,'actual':r.actual} for r in db.query(ValidationResult).filter_by(contract_id=cid).all()]}
    db.rollback()
    engine=RuleEngine()
    engine.nts_client=DisabledNtsClient()
    summary,checks=engine.validate_contract_evidence(cid,data['reference']['title'],data['reference']['vendor_name'],
        data['reference']['business_number'],data['reference']['contract_amount'],documents,
        required_document_types=data['required_types'],amount_policy=policy)
    data.update(summary=summary,checks=checks)
    return data


def require_unchanged(db,data):
    db.expire_all()
    contract=db.get(Contract,data['contract_id'])
    if not contract or fingerprint_for(db,contract,PipelineService().validation_inputs(db,contract))!=data['fingerprint']:
        db.rollback()
        raise HTTPException(409,'미리보기 생성 중 계약 자료가 변경되었습니다. 다시 불러오세요.')
    db.rollback()
