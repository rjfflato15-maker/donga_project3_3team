import os
import json
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from ..db.models import (
    Contract,
    Document,
    DocumentMasking,
    DocumentExtract,
    BusinessVerification,
    ValidationResult,
)
from ..schemas.common import (
    DocumentType,
    ProcessingStatus,
    MaskStatus,
    ValidationStatus,
    CORE_6_DOCUMENT_TYPES,
)
from ..schemas.document import DocumentResponse, DocumentAnalysis, AnalysisFields
from ..ai import analyze_document
from ..validation.engine import RuleEngine
from ..integrations.nts_client import get_nts_client

from ..config import RAW_STORAGE_DIR, MASKED_STORAGE_DIR


class PipelineService:
    def __init__(self):
        self.rule_engine = RuleEngine()
        self.nts_client = get_nts_client()

    def process_document_upload(self, db: Session, contract_id: int, file_name: str, file_bytes: bytes,
                                target_document_type: str = "", existing_document_id=None,
                                restoration_revision=None, replaces_document_id=None,
                                expected_contract_revision=None, change_note="", actor=None) -> Document:
        from fastapi import HTTPException
        from .storage_service import STORAGE_LOCK, store_original, store_text, clean_name, resolve_path
        from .workflow_service import touch_contract, policy_for
        from ..db.models import DocumentFileInfo, DocumentVersion, AuditEvent
        from .document_version_service import require_current, metadata
        from ..schemas.document import DocumentAnalysisResponse, MaskInfo

        # Read the small precondition snapshot, then release the transaction
        # before OCR/network/file work. No database publication lock is held.
        db.rollback()
        db.expire_all()
        contract = db.get(Contract, contract_id)
        if not contract:
            raise ValueError("계약을 찾을 수 없습니다.")
        expected_revision = None
        if expected_contract_revision is not None and policy_for(db, contract_id)['revision'] != expected_contract_revision:
            raise HTTPException(409,"계약 자료가 변경되었습니다. 새로고침 후 등록하세요.")
        if replaces_document_id is not None:
            previous = db.get(Document, replaces_document_id)
            if not previous or previous.contract_id != contract_id:
                raise HTTPException(404,"재발행할 문서를 찾을 수 없습니다.")
            require_current(previous)
            if expected_contract_revision is None or not change_note.strip():
                raise HTTPException(400,"재발행에는 revision과 변경 사유가 필요합니다.")
            if target_document_type and target_document_type != previous.document_type:
                raise HTTPException(400,"재발행 문서는 이전 문서와 같은 종류로 등록하세요.")
            target_document_type = previous.document_type
        if existing_document_id is not None:
            existing = db.get(Document, existing_document_id)
            if not existing or existing.contract_id != contract_id:
                raise HTTPException(404, "복구할 문서를 찾을 수 없습니다.")
            if resolve_path(existing.storage_path):
                raise HTTPException(409, "원본이 이미 보관되어 있습니다.")
            expected_revision = policy_for(db, contract_id)["revision"]
            if restoration_revision is not None and restoration_revision != expected_revision:
                raise HTTPException(409, "복구 요청 중 계약 자료가 변경되었습니다. 새로고침하세요.")
            target_document_type = existing.document_type
            info = db.get(DocumentFileInfo, existing_document_id)
            if info and info.sha256 != hashlib.sha256(file_bytes).hexdigest():
                raise HTTPException(409, "이전에 저장한 원본과 내용이 다릅니다.")
        business_number = contract.business_number
        db.rollback()

        raw_key, raw_path, digest = store_original(contract_id, file_name, file_bytes)
        llm_enabled = os.getenv('APP_LLM_ENABLED','false').lower() == 'true'
        failed = False
        try:
            analysis, raw_text, masked_text = analyze_document(str(raw_path), file_name=file_name,
                                                               target_document_type=target_document_type)
            body_text = raw_text.partition("\n")[2] if raw_text.startswith("[파일명:") else raw_text
            failed = not bool(body_text.strip())
        except Exception:
            failed = True
            raw_text, masked_text = "", ""
            analysis = DocumentAnalysisResponse(document_type=DocumentType.UNKNOWN, confidence=0,
                mask=MaskInfo(status=MaskStatus.FAILED), fields=AnalysisFields(), warnings=["문서 인식 실패"])
        masked_key = store_text(raw_key, raw_text, masked_text)
        if replaces_document_id is not None and failed:
            raise HTTPException(422,"재발행본을 읽지 못했습니다. 이전 버전은 유지됩니다. 파일을 확인하세요.")
        if replaces_document_id is not None and analysis.document_type.value != target_document_type:
            raise HTTPException(422,"재발행본의 문서 종류를 확인하지 못했습니다. 이전 버전은 유지됩니다.")
        b_no = analysis.fields.business_registration_no or business_number
        verification_status = self.nts_client.check_business_status(b_no).get("status", "확인 불가")

        # Publish the completed immutable files and all related rows together.
        # Recheck restoration after OCR so concurrent edits/deletion cannot be
        # overwritten and two restore requests cannot replace one another.
        with STORAGE_LOCK:
            db.expire_all()
            contract = db.get(Contract, contract_id)
            if not contract:
                raise ValueError("계약을 찾을 수 없습니다.")
            if expected_contract_revision is not None and policy_for(db, contract_id)['revision'] != expected_contract_revision:
                raise HTTPException(409,"분석 중 계약 자료가 변경되었습니다. 새로고침 후 다시 등록하세요.")
            previous = db.get(Document,replaces_document_id) if replaces_document_id is not None else None
            if replaces_document_id is not None:
                if not previous or previous.contract_id != contract_id:
                    raise HTTPException(409,"분석 중 이전 문서가 삭제되었습니다.")
                require_current(previous)
            doc = db.get(Document, existing_document_id) if existing_document_id is not None else None
            if existing_document_id is not None:
                if not doc or doc.contract_id != contract_id:
                    raise HTTPException(409, "복구 중 문서가 삭제 또는 변경되었습니다. 새로고침하세요.")
                if resolve_path(doc.storage_path) or policy_for(db, contract_id)["revision"] != expected_revision:
                    raise HTTPException(409, "복구 중 계약 자료가 변경되었습니다. 새로고침 후 다시 등록하세요.")
                current_info = db.get(DocumentFileInfo, doc.document_id)
                if current_info and current_info.sha256 != digest:
                    raise HTTPException(409, "이전에 저장한 원본과 내용이 다릅니다.")
            else:
                doc = Document(contract_id=contract_id)
                db.add(doc)
            doc.file_name = clean_name(file_name)
            doc.storage_path = raw_key
            doc.document_type = analysis.document_type.value
            doc.class_confidence = analysis.confidence
            doc.processing_status = "FAILED" if failed else "COMPLETED"
            doc.uploaded_at = datetime.utcnow()
            db.flush()
            masking = db.query(DocumentMasking).filter_by(document_id=doc.document_id).first()
            if masking is None:
                masking = DocumentMasking(document_id=doc.document_id)
                db.add(masking)
            masking.masked_file_path, masking.masking_status = masked_key, analysis.mask.status.value
            masking.masked_item_count, masking.masked_types = analysis.mask.masked_count, json.dumps(analysis.mask.categories, ensure_ascii=False)
            masking.processed_at = datetime.utcnow()
            extract = db.query(DocumentExtract).filter_by(document_id=doc.document_id).first()
            if extract is None:
                extract = DocumentExtract(document_id=doc.document_id)
                db.add(extract)
            extract.extracted_vendor_name = analysis.fields.company_name
            extract.extracted_vendor_reg_no = analysis.fields.business_registration_no
            extract.extracted_amount = analysis.fields.amount
            extract.extracted_date = analysis.fields.issue_date
            extract.extracted_status = "FAILED" if failed else "COMPLETED"
            extract.confidence = analysis.confidence
            stored_fields = analysis.fields.model_dump()
            if analysis.ai_review is not None:
                stored_fields["ai_review"] = analysis.ai_review
            review = analysis.ai_review or {}
            attempts = review.get('attempts')
            stored_fields['llm_execution'] = {
                'configured_enabled_at_analysis':llm_enabled,
                'status':'DISABLED' if not llm_enabled else review.get('status','FAILED' if failed else 'UNKNOWN'),
                'inference_invoked':False if not llm_enabled or review.get('status')=='NOT_NEEDED' else attempts>0 if isinstance(attempts,int) else None,
                'invocation_count':0 if not llm_enabled or review.get('status')=='NOT_NEEDED' else attempts,
                'error':review.get('error') or ('ANALYSIS_FAILED' if failed else None),
                'recorded_at':datetime.utcnow().isoformat()+'Z'}
            extract.raw_fields = json.dumps(stored_fields, ensure_ascii=False)
            verification = db.query(BusinessVerification).filter_by(document_id=doc.document_id).first()
            if verification is None:
                verification = BusinessVerification(document_id=doc.document_id)
                db.add(verification)
            verification.business_number = b_no
            verification.business_status = verification_status
            verification.verified_at = datetime.utcnow()
            info = db.get(DocumentFileInfo, doc.document_id)
            if info is None:
                info = DocumentFileInfo(document_id=doc.document_id)
                db.add(info)
            info.sha256, info.byte_size = digest, len(file_bytes)
            if existing_document_id is None:
                group, number = doc.document_id, 1
                if previous is not None:
                    if previous.version is None:
                        db.add(DocumentVersion(document_id=previous.document_id,logical_document_id=previous.document_id,
                            version_number=1,is_current=False,actor_name="기존 기록",change_note="버전 관리 이전 등록",
                            initial_fields_json=previous.extract.raw_fields if previous.extract else '{}',
                            created_at=previous.uploaded_at,superseded_at=datetime.utcnow()))
                        db.flush()
                        db.refresh(previous)
                    else:
                        previous.version.is_current=False
                        previous.version.superseded_at=datetime.utcnow()
                        db.flush()
                    group,number=metadata(previous)['logical_document_id'],metadata(previous)['version_number']+1
                db.add(DocumentVersion(document_id=doc.document_id,logical_document_id=group,version_number=number,
                    previous_document_id=replaces_document_id,is_current=True,actor_id=actor.user_id if actor else None,
                    actor_name=actor.display_name if actor else "시스템",change_note=change_note.strip() or "새 증빙 추가",
                    initial_fields_json=extract.raw_fields))
                if previous is not None:
                    db.add(AuditEvent(actor_id=actor.user_id if actor else None,actor_name=actor.display_name if actor else "시스템",
                        action="DOCUMENT_REISSUED",contract_id=contract_id,document_id=doc.document_id,
                        details=json.dumps({"previous_document_id":previous.document_id,"logical_document_id":group,
                                            "version_number":number,"note":change_note.strip()},ensure_ascii=False)))
            touch_contract(db, contract_id)
            db.commit()
            db.refresh(doc)
        self.revalidate_contract(db, contract_id)
        db.refresh(doc)
        return doc

    def validation_inputs(self, db: Session, contract):
        from .storage_service import resolve_path
        from ..db.models import DocumentFileInfo
        result = []
        from .document_version_service import active_documents
        for doc in active_documents(contract):
            try:
                fields = json.loads(doc.extract.raw_fields or "{}") if doc.extract else {}
            except (ValueError, TypeError):
                fields = {}
            info = db.get(DocumentFileInfo, doc.document_id)
            result.append({"document_id": doc.document_id, "document_type": doc.document_type,
                           "file_name": doc.file_name, "fields": fields,
                           "file_available": resolve_path(doc.storage_path) is not None,
                           "sha256": info.sha256 if info else None, "processing_status": doc.processing_status})
        return result

    def revalidate_contract(self, db: Session, contract_id: int):
        from fastapi import HTTPException
        from .storage_service import STORAGE_LOCK
        from .workflow_service import required_types, policy_for, fingerprint_for
        from ..db.models import AuditEvent

        for _ in range(3):
            # Snapshot the inputs and release the read transaction before any
            # rule evaluation (including an explicitly enabled NTS request).
            db.rollback()
            db.expire_all()
            contract = db.get(Contract, contract_id)
            if not contract:
                return False
            docs_data = self.validation_inputs(db, contract)
            required = required_types(db)
            policy = policy_for(db, contract_id)
            fingerprint = fingerprint_for(db, contract, docs_data)
            values = dict(contract_id=contract.contract_id, contract_title=contract.title,
                          expected_vendor_name=contract.vendor_name, expected_biz_no=contract.business_number,
                          contract_amount=contract.contract_amount, documents_data=docs_data,
                          required_document_types=required, amount_policy=policy)
            db.rollback()
            _, checks = self.rule_engine.validate_contract_evidence(**values)

            # Only publish if the documents, reference values and policy still
            # match the evaluated snapshot. Concurrent uploads/reviews cannot
            # receive validation results from an older revision.
            with STORAGE_LOCK:
                db.expire_all()
                contract = db.get(Contract, contract_id)
                if not contract:
                    return False
                current_inputs = self.validation_inputs(db, contract)
                if fingerprint_for(db, contract, current_inputs) != fingerprint:
                    db.rollback()
                    continue
                db.query(ValidationResult).filter(ValidationResult.contract_id == contract_id).delete()
                for check in checks:
                    db.add(ValidationResult(
                        contract_id=contract_id, validation_type=check.rule_id,
                        is_match=check.status == ValidationStatus.PASS, status=check.status.value,
                        field=check.field, expected=check.expected, actual=check.actual,
                        memo=check.message, created_at=datetime.utcnow()))
                contract.review_status = "PASS" if all(check.status == ValidationStatus.PASS for check in checks) else "REVIEW"
                contract.updated_at = datetime.utcnow()
                db.add(AuditEvent(actor_name="시스템", action="RULE_VALIDATION", contract_id=contract_id,
                                 details=json.dumps({"revision": policy["revision"], "fingerprint": fingerprint,
                                     "checks": [check.model_dump(mode="json") for check in checks]}, ensure_ascii=False)))
                db.commit()
                return True
        raise HTTPException(409, "검수 중 계약 자료가 여러 번 변경되었습니다. 최신 자료로 다시 검수하세요.")

    def simulate_pipeline(self, db: Session, contract_id: int) -> Dict[str, Any]:
        """
        Runs the 5-step pipeline simulation for UI interactive walkthrough:
        1. 계약/문서 업로드 확인 (CONTRACTS, DOCUMENTS)
        2. 마스킹 & 국세청 검증 (1:0..1 비동기 결과 적재)
        3. AI OCR 분석 (최신 추출 레코드)
        4. 문서별 필드 정규화 (가변 필드 매핑)
        5. 최종 대조 검수 (extract_id 기반 교차 대조 검수)
        """
        contract = db.query(Contract).filter(Contract.contract_id == contract_id).first()
        if not contract:
            raise ValueError(f"Contract {contract_id} not found")

        from .document_version_service import active_documents
        docs = active_documents(contract)

        step1 = {
            "step": 1,
            "title": "계약 및 문서 업로드",
            "status": "COMPLETED",
            "message": f"계약명 '{contract.title}' 및 증빙문서 {len(docs)}건 메타데이터 적재 완료",
            "details": [
                {"file_name": d.file_name, "document_type": d.document_type, "status": d.processing_status}
                for d in docs
            ],
        }

        step2 = {
            "step": 2,
            "title": "마스킹 및 국세청 검증",
            "status": "COMPLETED",
            "message": f"민감정보 {sum(d.masking.masked_item_count if d.masking else 0 for d in docs)}건 자동 마스킹 결과 저장. 국세청 상태는 실제 조회·데모·미연동을 구분해 표시",
            "details": [
                {
                    "file_name": d.file_name,
                    "mask_status": d.masking.masking_status if d.masking else "NOT_STARTED",
                    "masked_count": d.masking.masked_item_count if d.masking else 0,
                    "nts_status": d.verification.business_status if d.verification else "미확인",
                }
                for d in docs
            ],
        }

        step3 = {
            "step": 3,
            "title": "AI OCR 및 정보 추출",
            "status": "COMPLETED",
            "message": f"저장된 추출 결과 확인 (문서분류 참고점수: {round(sum(d.class_confidence or 0 for d in docs) / max(len(docs), 1) * 100, 1)}%)",
            "details": [
                {
                    "file_name": d.file_name,
                    "document_type": d.document_type,
                    "confidence": d.class_confidence,
                    "vendor_name": d.extract.extracted_vendor_name if d.extract else None,
                    "biz_no": d.extract.extracted_vendor_reg_no if d.extract else None,
                    "amount": d.extract.extracted_amount if d.extract else None,
                }
                for d in docs
            ],
        }

        step4 = {
            "step": 4,
            "title": "문서별 필드 정규화",
            "status": "COMPLETED",
            "message": "저장된 추출값과 금액 기준을 확인합니다. 사업자번호는 숫자로 비교하며, 금액은 합계 의미가 확인될 때 비교합니다.",
            "details": {
                "target_vendor": contract.vendor_name,
                "target_biz_no": contract.business_number,
                "target_amount": contract.contract_amount,
            },
        }

        # Re-run rule validation
        self.revalidate_contract(db, contract_id)
        results = db.query(ValidationResult).filter(ValidationResult.contract_id == contract_id).all()

        step5 = {
            "step": 5,
            "title": "최종 대조 검수",
            "status": "COMPLETED",
            "message": f"Rule Engine 검수 완료 (총 {len(results)}개 검수 규칙 실행)",
            "details": [
                {
                    "rule": r.validation_type,
                    "status": r.status,
                    "memo": r.memo,
                }
                for r in results
            ],
        }

        return {
            "contract_id": contract_id,
            "simulated_at": datetime.utcnow().isoformat(),
            "steps": [step1, step2, step3, step4, step5],
        }
