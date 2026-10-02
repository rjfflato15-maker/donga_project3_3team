"""Observed field edits and waiting-inclusive elapsed time; no inferred savings."""
import json
from ..db.models import Contract, ContractReview, AuditEvent, ResubmissionRequest
from ..schemas.document import AnalysisFields
from .contract_service import ContractService
from .document_version_service import active_documents
from .llm_status_service import contract_execution
from .workflow_service import review_state, fingerprint_for


def performance(db, contract_id=None):
    query=db.query(Contract)
    if contract_id is not None:query=query.filter_by(contract_id=contract_id)
    service=ContractService()
    rows=[]
    for contract in query.order_by(Contract.contract_id).all():
        inputs=service.pipeline_service.validation_inputs(db,contract)
        current=review_state(db,contract.contract_id,fingerprint_for(db,contract,inputs))
        confirmation=None
        if current['approval_status']=='CONFIRMED':
            confirmation=db.query(ContractReview).filter_by(contract_id=contract.contract_id,revision=current['revision'],decision='CONFIRMED').order_by(ContractReview.review_id.desc()).first()
        elapsed=(confirmation.created_at-contract.created_at).total_seconds() if confirmation and confirmation.created_at>=contract.created_at else None
        events=db.query(AuditEvent).filter_by(contract_id=contract.contract_id,action='EXTRACT_CORRECTED').all()
        changed_count=0;unique=set();unknown=0
        for event in events:
            try:
                body=json.loads(event.details)
                if 'before' not in body or 'after' not in body:raise ValueError('no field snapshots')
                before=AnalysisFields(**body['before']).model_dump();after=AnalysisFields(**body['after']).model_dump()
                changed=[key for key in before if before[key]!=after[key]]
                changed_count+=len(changed)
                unique.update((event.document_id,key) for key in changed)
            except (ValueError,TypeError):unknown+=1
        ai=contract_execution(inputs)
        rows.append({'contract_id':contract.contract_id,'revision':current['revision'],'approval_status':current['approval_status'],
                     'registered_at':contract.created_at.isoformat(),'current_final_confirmed_at':confirmation.created_at.isoformat() if confirmation else None,
                     'registration_to_current_final_confirmation_elapsed_seconds':elapsed,
                     'active_document_count':len(active_documents(contract)),'document_version_count':len(contract.documents),
                     'resubmission_request_count':db.query(ResubmissionRequest).filter_by(contract_id=contract.contract_id).count(),
                     'human_correction_save_count':len(events),'human_field_edit_count':changed_count,
                     'human_changed_unique_field_count':len(unique),'unknown_correction_event_count':unknown,
                     'ai_applied_value_field_count':ai['applied_value_field_count'],
                     'ai_current_matching_value_field_count':ai['current_matching_ai_value_field_count'],
                     'active_review_seconds':None,'measured_time_saving_seconds':None})
    observed=[r['registration_to_current_final_confirmation_elapsed_seconds'] for r in rows if r['registration_to_current_final_confirmation_elapsed_seconds'] is not None]
    keys=('resubmission_request_count','human_correction_save_count','human_field_edit_count','human_changed_unique_field_count','unknown_correction_event_count','ai_applied_value_field_count')
    return {'scope':'현재 계약의 이력 전체; AI 보완은 현재 활성 문서만',
            'timing_basis':'계약 등록 → 현재 자료의 최종 대표 확인, 대기 포함',
            'field_edit_basis':'수정 저장 전후 AnalysisFields 값이 달라진 칸 수의 합계; 동일 저장 0칸',
            'ai_basis':'실제로 applied=true인 VALUE 제안; ABSENT/REVIEW/파생 amount는 제외',
            'active_work_time_measured':False,'time_savings_measured':False,'contracts':rows,
            'totals':{'contract_count':len(rows),'currently_confirmed_contract_count':len(observed),
                      'mean_registration_to_current_final_confirmation_elapsed_seconds':sum(observed)/len(observed) if observed else None,
                      **{key:sum(r[key] for r in rows) for key in keys}}}
