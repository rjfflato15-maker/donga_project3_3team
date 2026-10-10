"""Resume one registration safely after a partial upload or a lost response."""
import hashlib
import json
import threading
import uuid

from fastapi import HTTPException
from ..db.models import Contract, ContractWorkflow, RegistrationAttempt, DocumentFileInfo, Document, DocumentVersion, ContractExclusion
from .storage_service import STORAGE_LOCK, clean_name
from .workflow_service import audit, policy_for

_locks = [threading.RLock() for _ in range(64)]


def register_batch(db, actor, data, contents, hints, request_key, service, pipeline):
    key = request_key or uuid.uuid4().hex
    payload = {'data': data.model_dump(), 'files': [
        {'name': clean_name(file.filename), 'sha256': hashlib.sha256(content).hexdigest(), 'type': hint}
        for (file, content), hint in zip(contents, hints)]}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    with _locks[hash((actor.user_id, key)) % len(_locks)]:
        with STORAGE_LOCK:
            attempt = db.query(RegistrationAttempt).filter_by(actor_id=actor.user_id, request_key=key).first()
            if attempt and attempt.payload_sha256 != digest:
                raise HTTPException(409, '이 등록 요청의 자료가 바뀌었습니다. 기존 계약을 확인하세요.')
            if attempt and db.get(ContractExclusion, attempt.contract_id):
                raise HTTPException(409, '이미 만든 계약을 제외했습니다. 계약 찾기에서 복원하세요.')
            if not attempt:
                contract = Contract(user_id=actor.user_id, title=data.title, vendor_name=data.vendor_name,
                    business_number=data.business_number, contract_amount=data.contract_amount, review_status='REVIEW')
                db.add(contract)
                db.flush()
                db.add(ContractWorkflow(contract_id=contract.contract_id, amount_basis=data.amount_basis,
                    tax_amount=data.tax_amount, payment_mode=data.payment_mode))
                attempt = RegistrationAttempt(actor_id=actor.user_id, request_key=key,
                    payload_sha256=digest, contract_id=contract.contract_id, receipts_json='{}')
                db.add(attempt)
                db.commit()
                audit(db, actor, 'AUTO_CONTRACT_CREATED', contract.contract_id, details={'document_count': len(contents)})
            cid = attempt.contract_id
            attempt_id = attempt.attempt_id
        failed = []
        for index, ((file, content), hint) in enumerate(zip(contents, hints)):
            attempt = db.get(RegistrationAttempt, attempt_id)
            receipts = json.loads(attempt.receipts_json)
            receipt_document = db.get(Document, receipts[str(index)]) if str(index) in receipts else None
            if receipt_document and receipt_document.processing_status == 'COMPLETED':
                continue
            name = clean_name(file.filename)
            file_hash = payload['files'][index]['sha256']
            # A crash after document publication but before the receipt must not republish it.
            published = db.query(Document).join(DocumentFileInfo).filter(
                Document.contract_id == cid, Document.file_name == name, DocumentFileInfo.sha256 == file_hash)
            candidates = published.order_by(Document.document_id.desc()).all()
            # Recover a crash after publication, including recovery of legacy
            # FAILED receipts, before deciding whether OCR must run again.
            document = next((doc for doc in candidates if doc.processing_status == 'COMPLETED'
                and (not hint or doc.document_type == hint)), None)
            if receipt_document and receipt_document.version and not receipt_document.version.is_current:
                # A person may already have supplied a corrected original.
                # A stale batch retry must not revive the superseded bad input.
                document = db.query(Document).join(DocumentVersion).filter(
                    Document.contract_id == cid, Document.processing_status == 'COMPLETED',
                    DocumentVersion.logical_document_id == receipt_document.version.logical_document_id,
                    DocumentVersion.is_current.is_(True)).first() or document
            failed_document = next((doc for doc in candidates if doc.processing_status == 'FAILED'
                and (not doc.version or doc.version.is_current)), None)
            try:
                if not document:
                    replacement = {}
                    if failed_document:
                        # Old releases published failed reads as successes. A
                        # recovery is a new version: retain the failed original
                        # and its correction history instead of overwriting it.
                        replacement = {'replaces_document_id': failed_document.document_id,
                            'expected_contract_revision': policy_for(db, cid)['revision'],
                            'change_note': '최초 등록 판독 실패 재시도', 'retry_failed_registration': True}
                    document = pipeline.process_document_upload(db=db, contract_id=cid, file_name=name,
                        file_bytes=content, target_document_type=hint, actor=actor, force_document_type=bool(hint),
                        require_readable=True, **replacement)
                receipts[str(index)] = document.document_id
                attempt = db.get(RegistrationAttempt, attempt_id)
                attempt.receipts_json = json.dumps(receipts)
                db.commit()
            except Exception:
                db.rollback()
                failed.append({'index': index, 'file_name': name, 'message': '파일 처리를 완료하지 못했습니다.'})
        try:
            pipeline.revalidate_contract(db, cid)
        except Exception:
            db.rollback()
            failed.append({'index': None, 'file_name': None, 'message': '자동 검사 재실행이 필요합니다.'})
        detail = service.get_contract_detail(db, cid)
        if detail is None:
            raise HTTPException(404, '계약을 찾을 수 없습니다. 제외한 계약은 먼저 복원하세요.')
        detail.registration = {'request_key': key, 'complete': not failed, 'failed_files': failed}
        return detail
