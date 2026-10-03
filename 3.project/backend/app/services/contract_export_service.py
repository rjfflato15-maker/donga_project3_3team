"""A single-contract snapshot, exported without any company-wide backup data."""
import hashlib
import io
import json
import re
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from PIL import Image, ImageOps

from ..db.models import (Contract, Document, DocumentFileInfo, ValidationResult,
                         AuditEvent, ContractReview, ApprovalSignoff,
                         ResubmissionRequest, WorkAssignment)
from ..schemas.document import AnalysisFields
from .pipeline_service import PipelineService
from .preview_masking_service import mask_image_with_ocr, mask_export_text, SENSITIVE_KEYS
from .storage_service import resolve_path, read_texts, STORAGE_LOCK
from .workflow_service import policy_for, fingerprint_for, audit

RASTERS = {'.png', '.jpg', '.jpeg', '.bmp', '.webp', '.gif', '.tif', '.tiff'}
MAX_SOURCE_BYTES = 250 * 1024 * 1024
MAX_EXPORT_BYTES = 250 * 1024 * 1024
EXCLUDED_KEYS = {'storage_path', 'raw_text', 'masked_text', 'password', 'token', 'prompt', 'response'}
OPAQUE_KEYS = {'fingerprint', 'contract_fingerprint', 'source_sha256', 'export_sha256', 'sha256'}


def row_data(row):
    result = {}
    for column in row.__table__.columns:
        key = column.name
        if key in EXCLUDED_KEYS:
            continue
        value = getattr(row, key)
        if key in {'details', 'snapshot_json', 'initial_fields_json'}:
            value = json.loads(value or '{}')
        result[key] = value.isoformat() if isinstance(value, datetime) else value
    return result


def source_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def safe_name(name):
    # User filenames cannot create ZIP paths, overwrite metadata, or be absolute.
    name = Path(name.replace('\\', '/')).name
    return re.sub(r'[\x00-\x1f<>:"/\\|?*]', '_', name)[:150] or 'document'


def export_snapshot(db, cid, revision=None):
    contract = db.get(Contract, cid)
    if not contract:
        raise HTTPException(404, '계약을 찾을 수 없습니다.')
    policy = policy_for(db, cid)
    if revision is not None and revision != policy['revision']:
        raise HTTPException(409, '계약 자료가 변경되었습니다. 새로 불러오세요.')
    fingerprint = fingerprint_for(db, contract, PipelineService().validation_inputs(db, contract))
    sensitive = {'vendor_name': contract.vendor_name, 'business_number': contract.business_number}
    documents = []
    for doc in db.query(Document).filter_by(contract_id=cid).order_by(Document.document_id):
        path = resolve_path(doc.storage_path)
        if not path:
            raise HTTPException(409, f'문서 {doc.document_id}의 원본이 없어 묶음을 만들 수 없습니다.')
        fields = json.loads(doc.extract.raw_fields or '{}') if doc.extract else {}
        values = {key: str(fields[key]) for key in SENSITIVE_KEYS if fields.get(key)}
        # Use per-document values during rendering; all old/new values for metadata.
        for key, value in values.items():
            sensitive.setdefault(key, [])
            if not isinstance(sensitive[key], list):
                sensitive[key] = [sensitive[key]]
            if value not in sensitive[key]:
                sensitive[key].append(value)
        info = db.get(DocumentFileInfo, doc.document_id)
        documents.append({
            'document_id': doc.document_id, 'file_name': doc.file_name,
            'document_type': doc.document_type, 'processing_status': doc.processing_status,
            'version': row_data(doc.version) if doc.version else {
                'document_id': doc.document_id, 'logical_document_id': doc.document_id,
                'version_number': 1, 'is_current': True},
            'fields': AnalysisFields(**fields).model_dump(),
            'human_review': fields.get('human_review'), 'ai_review': fields.get('ai_review'),
            '_path': path, '_text': read_texts(doc)[0],
            '_sensitive': {**values, 'vendor_name': contract.vendor_name,
                           'business_number': contract.business_number},
            '_expected_sha256': info.sha256 if info else None,
        })
    history = {}
    for label, model, order in (
        ('requests', ResubmissionRequest, ResubmissionRequest.request_id),
        ('edits_and_events', AuditEvent, AuditEvent.event_id),
        ('final_reviews', ContractReview, ContractReview.review_id),
        ('approvals', ApprovalSignoff, ApprovalSignoff.signoff_id),
        ('assignments', WorkAssignment, WorkAssignment.assignment_id),
    ):
        history[label] = [row_data(row) for row in db.query(model).filter_by(contract_id=cid).order_by(order)]
    data = {'contract_id': cid, 'revision': policy['revision'], 'fingerprint': fingerprint,
            'captured_at': datetime.now(timezone.utc).isoformat(),
            'contract': {**row_data(contract), 'policy': policy}, 'documents': documents,
            'validation_results': [row_data(row) for row in db.query(ValidationResult).filter_by(contract_id=cid).order_by(ValidationResult.validation_id)],
            'history': history, '_sensitive': sensitive}
    collect_sensitive(data, sensitive)
    db.rollback()  # OCR and rendering must not hold the company DB transaction.
    return data


def collect_sensitive(value, output):
    """Include old names from correction/version history, not just current fields."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key.startswith('_'):
                continue
            if key in SENSITIVE_KEYS and isinstance(item, str) and item.strip():
                previous = output.get(key, [])
                previous = previous if isinstance(previous, list) else [previous]
                output[key] = list(dict.fromkeys([*previous, item]))
            else:
                collect_sensitive(item, output)
    elif isinstance(value, list):
        for item in value:
            collect_sensitive(item, output)


def public_data(value, masked, sensitive):
    if isinstance(value, dict):
        return {key: item if key in OPAQUE_KEYS else public_data(item, masked, sensitive) for key, item in value.items()
                if not key.startswith('_') and key not in EXCLUDED_KEYS}
    if isinstance(value, list):
        return [public_data(item, masked, sensitive) for item in value]
    if masked and isinstance(value, str):
        return mask_export_text(value, sensitive)
    return value


def masked_document(doc):
    path = doc['_path']
    suffix = path.suffix.lower()
    if suffix == '.pdf':
        from .preview_masking_service import render_masked_pdf_bytes
        return render_masked_pdf_bytes(str(path), sensitive_dict=doc['_sensitive'], scale=1.5), '.pdf', 'MASKED_PDF'
    if suffix in RASTERS:
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert('RGB')
        protected = None
        try:
            protected = mask_image_with_ocr(image, doc['_sensitive'])
            buffer = io.BytesIO()
            protected.save(buffer, format='PNG')
            return buffer.getvalue(), '.png', 'MASKED_IMAGE'
        finally:
            image.close()
            if protected is not None:
                protected.close()
    if not doc['_text']:
        raise RuntimeError('가림용 문서 본문이 없습니다.')
    return mask_export_text(doc['_text'], doc['_sensitive']).encode('utf-8'), '.txt', 'MASKED_TEXT_LAYOUT_NOT_PRESERVED'


def create_bundle(db, cid, actor, masked=True, revision=None):
    workspace = tempfile.TemporaryDirectory(prefix='contract-export-')
    try:
        data = export_snapshot(db, cid, revision)
        if len(data['documents']) > 100 or sum(d['_path'].stat().st_size for d in data['documents']) > MAX_SOURCE_BYTES:
            raise HTTPException(413, '계약 묶음은 원본 100개, 총 250MB까지 지원합니다.')
        destination = Path(workspace.name) / 'bundle.zip'
        manifest = []
        export_bytes = 0
        with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
            for doc in data['documents']:
                digest = source_hash(doc['_path'])
                if doc['_expected_sha256'] and digest != doc['_expected_sha256']:
                    raise HTTPException(409, '저장된 원본 해시와 파일이 다릅니다. 담당자가 원본을 확인하세요.')
                version = doc['version']
                state = 'current' if version['is_current'] else 'previous'
                filename = f"documents/{state}/doc_{doc['document_id']}_v{version['version_number']}"
                if masked:
                    content, suffix, mode = masked_document(doc)
                    # Masked filenames expose only stable IDs and file format.
                    filename += suffix
                    export_bytes += len(content)
                    if export_bytes > MAX_EXPORT_BYTES:
                        raise HTTPException(413, '가림 자료 묶음이 250MB를 초과합니다. 개별 서류로 받으세요.')
                    archive.writestr(filename, content)
                    export_hash = hashlib.sha256(content).hexdigest()
                else:
                    filename += '__' + safe_name(doc['file_name'])
                    copied_hash = hashlib.sha256()
                    with doc['_path'].open('rb') as source, archive.open(filename, 'w') as target:
                        for chunk in iter(lambda: source.read(1024 * 1024), b''):
                            export_bytes += len(chunk)
                            if export_bytes > MAX_EXPORT_BYTES:
                                raise HTTPException(413, '자료 묶음이 250MB를 초과합니다.')
                            target.write(chunk)
                            copied_hash.update(chunk)
                    export_hash = copied_hash.hexdigest()
                    mode = 'ORIGINAL'
                if source_hash(doc['_path']) != digest or (not masked and export_hash != digest):
                    raise HTTPException(409, '묶음 생성 중 원본 파일이 변경되었습니다. 다시 시도하세요.')
                manifest.append({'document_id': doc['document_id'], 'version_number': version['version_number'],
                    'is_current': version['is_current'], 'document_type': doc['document_type'],
                    'entry': filename, 'source_sha256': digest, 'export_sha256': export_hash,
                    'source_hash_verified_against_receipt': bool(doc['_expected_sha256']), 'mode': mode})
            metadata = {
                'contract.json': {key: data[key] for key in ('contract_id', 'revision', 'fingerprint', 'captured_at', 'contract', 'documents')},
                'validation_results.json': data['validation_results'], 'history.json': data['history'],
                'manifest.json': {'schema_version': 1, 'masked': masked, 'captured_at': data['captured_at'], 'documents': manifest},
            }
            for filename, value in metadata.items():
                content = json.dumps(public_data(value, masked, data['_sensitive']), ensure_ascii=False, indent=2).encode('utf-8')
                export_bytes += len(content)
                if export_bytes > MAX_EXPORT_BYTES:
                    raise HTTPException(413, '이력을 포함한 자료 묶음이 250MB를 초과합니다.')
                archive.writestr(filename, content)
            archive.writestr('README.txt',
                '계약 한 건 자료 묶음\n현재본과 이전본은 documents/current, documents/previous에 있습니다.\n'
                '검수 결과는 저장 당시 결과이며 이 다운로드는 재판정하거나 결재하지 않습니다.\n'
                '요청·수정·결재·맡기기 이력은 history.json에 있습니다. 생성 시각 기준입니다.\n'
                + ('가림 ON: PDF/이미지는 가린 본, Word 등은 가린 본문 TXT입니다(페이지 배치 미보존).\n'
                   'OCR가 읽은 범위와 알려진 민감값을 가립니다. 개인정보 완전 제거를 보증하지 않습니다.\n'
                   if masked else '가림 OFF: 개인정보가 포함될 수 있는 원본입니다. 권한과 전달 대상을 확인하세요.\n'))
        with STORAGE_LOCK:
            db.expire_all()
            contract = db.get(Contract, cid)
            if not contract or fingerprint_for(db, contract, PipelineService().validation_inputs(db, contract)) != data['fingerprint']:
                raise HTTPException(409, '묶음 생성 중 계약 자료가 변경되었습니다. 새로 불러오세요.')
            audit(db, actor, 'CONTRACT_BUNDLE_EXPORT_REQUEST', cid,
                  details={'masked': masked, 'document_count': len(manifest), 'revision': data['revision']})
        return destination, workspace
    except HTTPException:
        workspace.cleanup()
        db.rollback()
        raise
    except Exception as exc:
        workspace.cleanup()
        db.rollback()
        raise HTTPException(503, '계약 묶음을 생성하지 못했습니다. 원본으로 자동 대체하지 않습니다.') from exc
