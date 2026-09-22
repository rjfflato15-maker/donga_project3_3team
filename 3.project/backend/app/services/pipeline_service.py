import os
import json
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

    def process_document_upload(
        self,
        db: Session,
        contract_id: int,
        file_name: str,
        file_bytes: bytes,
        target_document_type: str = "",
    ) -> Document:
        contract = db.query(Contract).filter(Contract.contract_id == contract_id).first()
        if not contract:
            raise ValueError(f"Contract {contract_id} not found")

        # 1. Save raw file to storage/raw
        safe_filename = f"{contract_id}_{int(datetime.utcnow().timestamp())}_{file_name}"
        raw_file_path = os.path.join(RAW_STORAGE_DIR, safe_filename)
        with open(raw_file_path, "wb") as f:
            f.write(file_bytes)

        # 2. Run Local Document AI Pipeline (Preprocess -> Masking -> Classify -> Extract)
        analysis_res, raw_text, masked_text = analyze_document(
            raw_file_path, file_name=file_name, target_document_type=target_document_type
        )

        # 3. Save masked file to storage/masked
        masked_file_path = os.path.join(MASKED_STORAGE_DIR, f"masked_{safe_filename}")
        with open(masked_file_path, "w", encoding="utf-8") as f:
            f.write(masked_text)

        # 4. Create or update Document record
        doc_record = Document(
            contract_id=contract_id,
            file_name=file_name,
            storage_path=raw_file_path,
            document_type=analysis_res.document_type.value,
            class_confidence=analysis_res.confidence,
            processing_status=ProcessingStatus.COMPLETED.value,
            uploaded_at=datetime.utcnow(),
        )
        db.add(doc_record)
        db.flush()

        # 5. Save DocumentMasking
        masking_record = DocumentMasking(
            document_id=doc_record.document_id,
            masked_file_path=masked_file_path,
            masking_status=analysis_res.mask.status.value,
            masked_item_count=analysis_res.mask.masked_count,
            masked_types=json.dumps(analysis_res.mask.categories, ensure_ascii=False),
            processed_at=datetime.utcnow(),
        )
        db.add(masking_record)

        # 6. Save DocumentExtract
        extract_record = DocumentExtract(
            document_id=doc_record.document_id,
            extracted_vendor_name=analysis_res.fields.company_name,
            extracted_vendor_reg_no=analysis_res.fields.business_registration_no,
            extracted_amount=analysis_res.fields.amount,
            extracted_date=analysis_res.fields.issue_date,
            extracted_status="COMPLETED",
            confidence=analysis_res.confidence,
            raw_fields=analysis_res.fields.model_dump_json(),
        )
        db.add(extract_record)

        # 7. If this is business registration or contains biz reg no, query NTS
        b_no = analysis_res.fields.business_registration_no or contract.business_number
        nts_info = self.nts_client.check_business_status(b_no)
        verification_record = BusinessVerification(
            document_id=doc_record.document_id,
            business_number=b_no,
            business_status=nts_info.get("status", "계속사업자"),
            verified_at=datetime.utcnow(),
        )
        db.add(verification_record)

        db.commit()
        db.refresh(doc_record)

        # 8. Trigger full contract re-validation
        self.revalidate_contract(db, contract_id)

        return doc_record

    def revalidate_contract(self, db: Session, contract_id: int):
        contract = db.query(Contract).filter(Contract.contract_id == contract_id).first()
        if not contract:
            return

        # Fetch all documents and extracts
        docs = db.query(Document).filter(Document.contract_id == contract_id).all()

        docs_data = []
        for d in docs:
            fields_dict = {}
            if d.extract and d.extract.raw_fields:
                try:
                    fields_dict = json.loads(d.extract.raw_fields)
                except Exception:
                    fields_dict = {
                        "company_name": d.extract.extracted_vendor_name,
                        "business_registration_no": d.extract.extracted_vendor_reg_no,
                        "amount": d.extract.extracted_amount,
                        "issue_date": d.extract.extracted_date,
                    }
            docs_data.append({
                "document_id": d.document_id,
                "document_type": d.document_type,
                "fields": fields_dict,
            })

        summary, checks = self.rule_engine.validate_contract_evidence(
            contract_id=contract.contract_id,
            contract_title=contract.title,
            expected_vendor_name=contract.vendor_name,
            expected_biz_no=contract.business_number,
            contract_amount=contract.contract_amount,
            documents_data=docs_data,
        )

        # Clear existing validation results for contract
        db.query(ValidationResult).filter(ValidationResult.contract_id == contract_id).delete()

        # Insert new validation results
        has_fail = False
        has_missing = False
        has_review = False

        for c in checks:
            if c.status == ValidationStatus.FAIL:
                has_fail = True
            elif c.status == ValidationStatus.MISSING:
                has_missing = True
            elif c.status == ValidationStatus.REVIEW:
                has_review = True

            v_res = ValidationResult(
                contract_id=contract_id,
                validation_type=c.rule_id,
                is_match=(c.status == ValidationStatus.PASS),
                status=c.status.value,
                field=c.field,
                expected=c.expected,
                actual=c.actual,
                memo=c.message,
                created_at=datetime.utcnow(),
            )
            db.add(v_res)

        # Update contract review_status
        if has_fail or has_missing or has_review:
            contract.review_status = "REVIEW"
        else:
            contract.review_status = "PASS"

        contract.updated_at = datetime.utcnow()
        db.commit()

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

        docs = db.query(Document).filter(Document.contract_id == contract_id).all()

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
            "message": f"민감정보 {sum(d.masking.masked_item_count if d.masking else 0 for d in docs)}건 마스킹 완료 및 국세청 사업자 진위확인 완료",
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
            "message": f"AI 분석 완료 (평균 신뢰도: {round(sum(d.class_confidence or 0 for d in docs) / max(len(docs), 1) * 100, 1)}%)",
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
            "message": "금액, 사업자번호, 업체명 규격 표준화 및 매핑 완료",
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
