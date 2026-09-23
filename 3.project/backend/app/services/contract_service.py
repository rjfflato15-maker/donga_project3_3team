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
    ContractListItem,
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


def get_document_response(doc: Document) -> DocumentResponse:
    # Read raw and masked text if exists
    raw_text = ""
    masked_text = ""
    if doc.storage_path and os.path.exists(doc.storage_path):
        try:
            with open(doc.storage_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_text = f.read()
        except Exception:
            pass

    if doc.masking and doc.masking.masked_file_path and os.path.exists(doc.masking.masked_file_path):
        try:
            with open(doc.masking.masked_file_path, "r", encoding="utf-8", errors="ignore") as f:
                masked_text = f.read()
        except Exception:
            pass

    # Fields
    fields = AnalysisFields()
    if doc.extract and doc.extract.raw_fields:
        try:
            fields_dict = json.loads(doc.extract.raw_fields)
            fields = AnalysisFields(**fields_dict)
        except Exception:
            fields = AnalysisFields(
                company_name=doc.extract.extracted_vendor_name,
                business_registration_no=doc.extract.extracted_vendor_reg_no,
                amount=doc.extract.extracted_amount,
                issue_date=doc.extract.extracted_date,
            )

    mask_categories = []
    if doc.masking and doc.masking.masked_types:
        try:
            mask_categories = json.loads(doc.masking.masked_types)
        except Exception:
            mask_categories = []

    return DocumentResponse(
        document_id=doc.document_id,
        contract_id=doc.contract_id,
        original_file_name=doc.file_name,
        document_type=DocumentType(doc.document_type) if doc.document_type in [t.value for t in DocumentType] else DocumentType.UNKNOWN,
        confidence=doc.class_confidence or 0.0,
        processing_status=ProcessingStatus(doc.processing_status) if doc.processing_status in [s.value for s in ProcessingStatus] else ProcessingStatus.COMPLETED,
        mask_status=MaskStatus(doc.masking.masking_status) if (doc.masking and doc.masking.masking_status in [m.value for m in MaskStatus]) else MaskStatus.NOT_STARTED,
        analysis=DocumentAnalysis(fields=fields, warnings=[]),
        raw_text=raw_text,
        masked_text=masked_text,
        business_status=doc.verification.business_status if doc.verification else None,
    )


class ContractService:
    def __init__(self):
        self.pipeline_service = PipelineService()

    def list_contracts(self, db: Session) -> List[ContractListItem]:
        contracts = db.query(Contract).order_by(Contract.contract_id.desc()).all()
        result = []
        for c in contracts:
            docs = c.documents
            submitted_types = set(d.document_type for d in docs)
            submitted_cnt = len([t for t in CORE_6_DOCUMENT_TYPES if t.value in submitted_types])
            completeness = round((submitted_cnt / 6.0) * 100.0, 1)

            result.append(
                ContractListItem(
                    contract_id=c.contract_id,
                    title=c.title,
                    vendor_name=c.vendor_name,
                    business_number=c.business_number,
                    contract_amount=c.contract_amount,
                    review_status=c.review_status,
                    completeness_rate=completeness,
                    submitted_docs_count=submitted_cnt,
                    total_docs_count=6,
                    created_at=c.created_at,
                )
            )
        return result

    def get_contract_detail(self, db: Session, contract_id: int) -> Optional[ContractDetailResponse]:
        contract = db.query(Contract).filter(Contract.contract_id == contract_id).first()
        if not contract:
            return None

        docs = contract.documents
        doc_responses = [get_document_response(d) for d in docs]

        validation_results = contract.validation_results
        checks = [
            ValidationCheck(
                rule_id=vr.validation_type,
                status=ValidationStatus(vr.status) if vr.status in [s.value for s in ValidationStatus] else ValidationStatus.PASS,
                field=vr.field or "",
                expected=vr.expected,
                actual=vr.actual,
                message=vr.memo or "",
            )
            for vr in validation_results
        ]

        submitted_types = set(d.document_type for d in docs)
        submitted_cnt = len([t for t in CORE_6_DOCUMENT_TYPES if t.value in submitted_types])
        from ..validation.metrics import calculate_validation_metrics
        summary = calculate_validation_metrics(
            required_count=6,
            submitted_count=submitted_cnt,
            checks=checks,
        )

        return ContractDetailResponse(
            contract_id=contract.contract_id,
            title=contract.title,
            vendor_name=contract.vendor_name,
            business_number=contract.business_number,
            contract_amount=contract.contract_amount,
            review_status=contract.review_status,
            required_document_types=CORE_6_DOCUMENT_TYPES,
            documents=doc_responses,
            summary=summary,
            checks=checks,
            created_at=contract.created_at,
            updated_at=contract.updated_at,
        )

    def create_contract(self, db: Session, req: ContractCreate) -> Contract:
        contract = Contract(
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

        # Trigger initial validation (which will flag missing documents)
        self.pipeline_service.revalidate_contract(db, contract.contract_id)
        db.refresh(contract)
        return contract

    def update_contract(self, db: Session, contract_id: int, req: ContractUpdate) -> Optional[ContractDetailResponse]:
        contract = db.query(Contract).filter(Contract.contract_id == contract_id).first()
        if not contract:
            return None

        if req.title is not None:
            contract.title = req.title
        if req.vendor_name is not None:
            contract.vendor_name = req.vendor_name
        if req.business_number is not None:
            contract.business_number = req.business_number
        if req.contract_amount is not None:
            contract.contract_amount = req.contract_amount

        contract.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(contract)

        # Also update DocumentExtract for attached 'contract' document if present
        contract_docs = db.query(Document).filter(
            Document.contract_id == contract_id,
            Document.document_type == "contract"
        ).all()
        for cdoc in contract_docs:
            if cdoc.extract:
                if req.vendor_name is not None:
                    cdoc.extract.extracted_vendor_name = req.vendor_name
                if req.business_number is not None:
                    cdoc.extract.extracted_vendor_reg_no = req.business_number
                if req.contract_amount is not None:
                    cdoc.extract.extracted_amount = req.contract_amount

                fields_dict = {
                    "company_name": cdoc.extract.extracted_vendor_name,
                    "business_registration_no": cdoc.extract.extracted_vendor_reg_no,
                    "amount": cdoc.extract.extracted_amount,
                    "issue_date": cdoc.extract.extracted_date,
                }
                cdoc.extract.raw_fields = json.dumps(fields_dict, ensure_ascii=False)
        db.commit()

        # Re-run rule engine validation with updated contract info
        self.pipeline_service.revalidate_contract(db, contract_id)
        db.refresh(contract)

        return self.get_contract_detail(db, contract_id)

    def delete_contract(self, db: Session, contract_id: int) -> bool:
        contract = db.query(Contract).filter(Contract.contract_id == contract_id).first()
        if not contract:
            return False

        # Clean up physical document files
        for doc in contract.documents:
            if doc.storage_path and os.path.exists(doc.storage_path):
                try:
                    os.remove(doc.storage_path)
                except Exception:
                    pass
            if doc.masking and doc.masking.masked_file_path and os.path.exists(doc.masking.masked_file_path):
                try:
                    os.remove(doc.masking.masked_file_path)
                except Exception:
                    pass

        db.delete(contract)
        db.commit()
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
            if len(existing.documents) >= 5:
                return existing
            db.delete(existing)
            db.commit()

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
