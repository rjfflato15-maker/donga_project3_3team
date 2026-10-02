import os
import json
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from ..db.models import (
    User,
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
from ..schemas.contract import (
    ContractCreate,
    ContractUpdate,
    ContractDetailResponse,
)
from ..schemas.document import (
    DocumentResponse,
    DocumentAnalysis,
    AnalysisFields,
    MaskInfo,
)
from ..schemas.validation import (
    ValidationCheck,
    ValidationSummary,
)
from .pipeline_service import PipelineService
from .company_policy_service import approval_state
from .review_summary_service import (
    ContractDashboardListItem,
    build_action_summary,
    display_issue_counts,
    pending_ai_count,
    waiting_request_stats,
)


def get_document_response(doc: Document) -> DocumentResponse:
    from .storage_service import read_texts, resolve_path
    from ..config import NTS_MODE
    raw_text, masked_text = read_texts(doc)
    source = resolve_path(doc.storage_path)
    fields = AnalysisFields()
    ai_review = None
    if doc.extract:
        try:
            stored_fields = json.loads(doc.extract.raw_fields or "{}")
            fields = AnalysisFields(**stored_fields)
            ai_review = stored_fields.get("ai_review")
        except (ValueError, TypeError):
            fields = AnalysisFields(company_name=doc.extract.extracted_vendor_name,
                                    business_registration_no=doc.extract.extracted_vendor_reg_no,
                                    amount=doc.extract.extracted_amount, issue_date=doc.extract.extracted_date)
    warnings = []
    if source is None:
        warnings.append("공용 서버에 원본이 없습니다. 원본을 다시 등록하세요.")
    if doc.processing_status == "FAILED":
        warnings.append("문서 인식에 실패했습니다. 원본을 확인하고 추출값을 보완하세요.")
    return DocumentResponse(
        document_id=doc.document_id, contract_id=doc.contract_id, original_file_name=doc.file_name,
        document_type=DocumentType(doc.document_type) if doc.document_type in [t.value for t in DocumentType] else DocumentType.UNKNOWN,
        confidence=doc.class_confidence or 0.0,
        processing_status=ProcessingStatus(doc.processing_status) if doc.processing_status in [s.value for s in ProcessingStatus] else ProcessingStatus.REVIEW,
        mask_status=MaskStatus(doc.masking.masking_status) if doc.masking and doc.masking.masking_status in [m.value for m in MaskStatus] else MaskStatus.NOT_STARTED,
        analysis=DocumentAnalysis(fields=fields, warnings=warnings, ai_review=ai_review), raw_text=raw_text, masked_text=masked_text,
        business_status="미연동" if NTS_MODE == "disabled" else (
            "데모 데이터 · 실제 조회 아님" if NTS_MODE == "demo" else (
                doc.verification.business_status if doc.verification else "미확인")),
        file_available=source is not None, file_size=source.stat().st_size if source else None,
    )


class ContractService:
    def __init__(self):
        self.pipeline_service = PipelineService()

    def list_contracts(self, db: Session) -> List[ContractDashboardListItem]:
        from .workflow_service import required_types, review_state, fingerprint_for, policy_for
        from .storage_service import resolve_path
        required = required_types(db)
        waiting_by_contract = waiting_request_stats(db)
        result = []
        for contract in db.query(Contract).order_by(Contract.contract_id.desc()).all():
            submitted = {d.document_type for d in contract.documents}
            count = sum(t.value in submitted for t in required)
            inputs = self.pipeline_service.validation_inputs(db, contract)
            workflow = review_state(db, contract.contract_id, fingerprint_for(db, contract, inputs))
            summary, current_checks = self.pipeline_service.rule_engine.validate_contract_evidence(
                contract.contract_id, contract.title, contract.vendor_name, contract.business_number,
                contract.contract_amount, inputs, required_document_types=required,
                amount_policy=policy_for(db, contract.contract_id))
            current_status = "PASS" if all(c.status == ValidationStatus.PASS for c in current_checks) else "REVIEW"
            approval = approval_state(
                db, contract.contract_id, workflow["revision"], workflow["fingerprint"],
                include_history=False,
            )
            waiting_count, earliest_due_on = waiting_by_contract.get(contract.contract_id, (0, None))
            ai_pending = pending_ai_count(d["fields"].get("ai_review") for d in inputs)
            issue_counts = display_issue_counts(current_checks)
            result.append(ContractDashboardListItem(
                contract_id=contract.contract_id, title=contract.title, vendor_name=contract.vendor_name,
                business_number=contract.business_number, contract_amount=contract.contract_amount,
                review_status=current_status, completeness_rate=round(count / len(required) * 100, 1) if required else 100,
                submitted_docs_count=count, total_docs_count=len(required),
                submitted_document_types=[t.value for t in required if t.value in submitted], created_at=contract.created_at,
                approval_status=workflow["approval_status"], revision=workflow["revision"],
                missing_original_count=sum(resolve_path(d.storage_path) is None for d in contract.documents),
                action_summary=build_action_summary(issue_counts, workflow, approval, waiting_count, ai_pending),
                open_issue_count=sum(issue_counts.values()),
                waiting_request_count=waiting_count, earliest_due_on=earliest_due_on,
                approval_next_step=approval["next_step"],
            ))
        return result

    def get_contract_detail(self, db: Session, contract_id: int) -> Optional[ContractDetailResponse]:
        from .workflow_service import required_types, policy_for, review_state, fingerprint_for
        contract = db.get(Contract, contract_id)
        if not contract:
            return None
        docs = self.pipeline_service.validation_inputs(db, contract)
        required = required_types(db)
        summary, checks = self.pipeline_service.rule_engine.validate_contract_evidence(
            contract.contract_id, contract.title, contract.vendor_name, contract.business_number, contract.contract_amount,
            docs, required_document_types=required, amount_policy=policy_for(db, contract_id))
        status = "REVIEW" if any(c.status != ValidationStatus.PASS for c in checks) else "PASS"
        return ContractDetailResponse(
            contract_id=contract.contract_id, title=contract.title, vendor_name=contract.vendor_name,
            business_number=contract.business_number, contract_amount=contract.contract_amount, review_status=status,
            required_document_types=required, documents=[get_document_response(d) for d in contract.documents],
            summary=summary, checks=checks, created_at=contract.created_at, updated_at=contract.updated_at,
            workflow=review_state(db, contract_id, fingerprint_for(db, contract, docs)),
        )

    def create_contract(self, db: Session, req: ContractCreate, user_id=None) -> Contract:
        contract = Contract(
            user_id=user_id,
            title=req.title,
            vendor_name=req.vendor_name,
            business_number=req.business_number,
            contract_amount=req.contract_amount,
            review_status="REVIEW",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(contract)
        db.commit()
        db.refresh(contract)

        from ..db.models import ContractWorkflow
        db.add(ContractWorkflow(contract_id=contract.contract_id, amount_basis=req.amount_basis,
                                tax_amount=req.tax_amount, payment_mode=req.payment_mode))
        db.commit()
        # Trigger initial validation (which will flag missing documents)
        self.pipeline_service.revalidate_contract(db, contract.contract_id)
        db.refresh(contract)
        return contract

    def update_contract(self, db: Session, contract_id: int, req: ContractUpdate) -> Optional[ContractDetailResponse]:
        from fastapi import HTTPException
        from ..config import IS_PILOT
        from ..db.models import ContractWorkflow
        from .workflow_service import policy_for, touch_contract
        from .storage_service import STORAGE_LOCK
        with STORAGE_LOCK:
            contract = db.get(Contract, contract_id)
            if not contract:
                return None
            policy = policy_for(db, contract_id)
            if IS_PILOT and (req.revision is None or req.revision != policy["revision"]):
                raise HTTPException(409, "다른 사용자가 변경했습니다. 새로고침 후 다시 수정하세요.")
            if IS_PILOT and len((req.change_note or "").strip()) < 3:
                raise HTTPException(400, "변경 사유를 3자 이상 남기세요.")
            for key in ("title", "vendor_name", "business_number", "contract_amount"):
                value = getattr(req, key)
                if value is not None:
                    setattr(contract, key, value)
            touch_contract(db, contract_id)
            workflow = db.get(ContractWorkflow, contract_id)
            if req.amount_basis is not None:
                workflow.amount_basis = req.amount_basis
            if "tax_amount" in req.model_fields_set:
                workflow.tax_amount = req.tax_amount
            if req.payment_mode is not None:
                workflow.payment_mode = req.payment_mode
            # Contract reference edits never overwrite OCR evidence.
            contract.updated_at = datetime.utcnow()
            db.commit()
        self.pipeline_service.revalidate_contract(db, contract_id)
        return self.get_contract_detail(db, contract_id)

    def delete_contract(self, db: Session, contract_id: int) -> bool:
        from ..db.models import ContractWorkflow, DocumentFileInfo
        from .storage_service import STORAGE_LOCK
        with STORAGE_LOCK:
            contract = db.get(Contract, contract_id)
            if not contract:
                return False
            for doc in contract.documents:
                db.query(DocumentFileInfo).filter(DocumentFileInfo.document_id == doc.document_id).delete()
            db.query(ContractWorkflow).filter(ContractWorkflow.contract_id == contract_id).delete()
            db.delete(contract)
            db.commit()
            # Original bytes are retained in server backups/storage pending an agreed retention policy.
            return True

    def seed_demo_contract(self, db: Session) -> Contract:
        """
        Seeds the demo contract matching the presentation slides:
        - Title: "ABC 홈페이지 구축 외주 계약"
        - Vendor: "ABC 주식회사", "123-45-67890"
        - Amount: 11,000,000 KRW
        - 5 documents submitted (contract, estimate, business_registration, bank_account, tax_invoice)
        - 1 document missing (inspection_confirmation)
        - Tax invoice amount: 10,450,000 KRW -> 550,000 KRW mismatch with contract 11,000,000 KRW
        - Result: Completeness 83.3%, Review Needed 2 items!
        """
        # Check if demo contract already exists
        existing = db.query(Contract).filter(Contract.title == "ABC 홈페이지 구축 외주 계약").first()
        from ..config import SAMPLE_DIR

        if existing:
            # Delete existing contract and associated docs to ensure a true clean reset
            self.delete_contract(db, existing.contract_id)

        contract = Contract(
            title="ABC 홈페이지 구축 외주 계약",
            vendor_name="ABC 주식회사",
            business_number="123-45-67890",
            contract_amount=11000000.0,
            review_status="REVIEW",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(contract)
        db.commit()
        db.refresh(contract)

        # Read sample files and upload them
        demo_files = [
            "01_계약서_ABC홈페이지구축.txt",
            "02_견적서_ABC홈페이지구축.txt",
            "03_사업자등록증_ABC주식회사.txt",
            "04_통장사본_ABC주식회사.txt",
            "05_세금계산서_10450000원.txt",
        ]

        for fname in demo_files:
            fpath = SAMPLE_DIR / fname
            if fpath.exists():
                with open(fpath, "rb") as f:
                    file_bytes = f.read()
                self.pipeline_service.process_document_upload(
                    db=db,
                    contract_id=contract.contract_id,
                    file_name=fname,
                    file_bytes=file_bytes,
                )

        db.refresh(contract)
        return contract
