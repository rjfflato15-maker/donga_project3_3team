"""Shared field corrections for manual edits, confirmations and VLM review.

Keep publication and audit under the storage lock, then run the existing
revalidation step. Callers retain their route-specific authorization and checks.
"""
import json

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..db.models import Document
from ..schemas.document import AnalysisFields, Correction
from ..security import Actor
from .contract_service import get_document_response
from .document_version_service import require_current
from .pipeline_service import PipelineService
from .storage_service import STORAGE_LOCK
from .workflow_service import audit, touch_contract, policy_for


pipeline_service = PipelineService()


def apply_correction(document_id: int, req: Correction, db: Session, actor: Actor, vlm_review=None):
    with STORAGE_LOCK:
        doc = db.get(Document, document_id)
        if not doc or not doc.extract:
            raise HTTPException(404, "추출 결과를 찾을 수 없습니다.")
        require_current(doc)
        if req.revision != policy_for(db, doc.contract_id)["revision"]:
            raise HTTPException(409, "자료가 변경되었습니다. 새로고침 후 다시 수정하세요.")
        if not req.note.strip():
            raise HTTPException(400, "추출값 수정 사유를 입력하세요.")
        before = json.loads(doc.extract.raw_fields or "{}")
        # A sparse body changes only supplied keys. Explicit null still clears a value.
        fields = AnalysisFields(**{**AnalysisFields(**before).model_dump(),
                                  **req.fields.model_dump(exclude_unset=True)})
        if fields.amount_basis not in {"TOTAL", "SUPPLY", "UNKNOWN"} or fields.amount_scope not in {"FULL", "PARTIAL", "UNKNOWN"}:
            raise HTTPException(400, "금액 기준과 청구 범위를 확인하세요.")
        from ..validation.financial import money
        for key in ("amount", "supply_amount", "tax_amount", "total_amount"):
            value = getattr(fields, key)
            if value is not None and money(value) is None:
                raise HTTPException(400, "금액은 0 이상의 유효한 숫자로 입력하세요.")
        from .field_confirmation_service import confirm_fields, reviewed_ai
        after = fields.model_dump()
        try:
            human_review, changed_fields, confirmed_fields = confirm_fields(db, document_id, before, after, actor, req.confirmed_fields)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        previous_type=doc.document_type
        doc.document_type = req.document_type.value
        after['human_review'] = human_review
        if vlm_review:
            after['vlm_review'] = vlm_review
            if doc.processing_status == 'FAILED':
                doc.processing_status = 'REVIEW'
            for key in confirmed_fields:
                human_review['field_confirmations'][key].update(method='VLM_ORIGINAL_CONFIRMED', run_id=vlm_review['run_id'])
        elif before.get('vlm_review'):
            after['vlm_review'] = before['vlm_review']
        if before.get("ai_review"):
            after["ai_review"] = reviewed_ai(before['ai_review'], human_review['field_confirmations'])
        if before.get('llm_execution'):
            after['llm_execution']=before['llm_execution']
        if isinstance(before.get('extraction_metadata'), dict):
            after['extraction_metadata'] = before['extraction_metadata']
        doc.extract.raw_fields = json.dumps(after, ensure_ascii=False)
        doc.extract.extracted_vendor_name = fields.company_name
        doc.extract.extracted_vendor_reg_no = fields.business_registration_no
        doc.extract.extracted_amount = fields.total_amount if fields.total_amount is not None else fields.amount
        doc.extract.extracted_date = fields.issue_date
        doc.extract.extracted_status = "MANUALLY_CONFIRMED"
        touch_contract(db, doc.contract_id)
        contract_id = doc.contract_id
        audit(db, actor, "EXTRACT_CORRECTED", contract_id, document_id,
              {"note": req.note.strip()[:1000], "before": AnalysisFields(**before).model_dump(), "after": fields.model_dump(),
               "previous_document_type":previous_type,"new_document_type":req.document_type.value,
               "ai_review_before":before.get('ai_review'),"llm_execution":before.get('llm_execution'),
               "vlm_review":after.get('vlm_review'),
               "changed_fields":changed_fields,"confirmed_fields":confirmed_fields,
               "revision": policy_for(db, contract_id)['revision']})
    pipeline_service.revalidate_contract(db, contract_id)
    return get_document_response(doc)
