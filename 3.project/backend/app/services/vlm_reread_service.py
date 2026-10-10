import hashlib
import io
import json
import math
import re
import threading
from datetime import datetime, timezone

from fastapi import HTTPException
from PIL import Image, ImageOps

from ..ai.local_vlm import FIELDS, PROMPT_VERSION, LocalVlmClient, VlmError
from ..ai.grounding import canonical
from ..db.models import Document, DocumentFileInfo, AuditEvent
from ..validation.financial import money
from ..validation.billing import scope_in_document
from .document_version_service import require_current
from .storage_service import resolve_path, STORAGE_LOCK
from .workflow_service import policy_for, fingerprint_for
from .pipeline_service import PipelineService
from .contract_export_service import collect_sensitive, public_data

VLM_SLOT = threading.Semaphore(1)
VISUAL_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tif', '.tiff'}
ERROR_TEXT = {
    'DISABLED': 'VLM 재판독이 꺼져 있습니다. 서버 설정을 확인하세요.',
    'OLLAMA_UNAVAILABLE': '서버 PC의 Ollama가 켜져 있는지 확인하세요.',
    'LOCAL_MODEL_NOT_INSTALLED': '설정된 VLM이 서버 PC에 없습니다. 설치된 이미지 모델을 선택하세요.',
    'MODEL_HAS_NO_VISION': '이 모델은 이미지 입력을 지원하지 않습니다.',
    'CLOUD_DISABLE_CONFIG_REQUIRED': '서버 실행 계정의 Ollama 클라우드 비활성 설정을 확인하세요.',
    'INVALID_LOCAL_CONFIGURATION': '로컬 VLM 설정을 확인하세요.',
    'TIMEOUT': 'VLM 재판독 시간이 초과됐습니다. 저장값은 유지됩니다.',
    'INVALID_RESPONSE': 'VLM 답변 형식을 확인하지 못했습니다. 저장값은 유지됩니다.',
    'OUTPUT_LIMIT': 'VLM 답변이 길어 완료되지 않았습니다. 저장값은 유지됩니다. 서버의 모델 설정을 확인하세요.',
}


def vlm_status():
    try:
        client = LocalVlmClient()
        metadata = client.metadata()
        return {'ready': True, 'model': metadata['name'], 'message': '현재 쪽을 로컬 이미지 모델로 다시 읽습니다.'}
    except VlmError as error:
        return {'ready': False, 'model': None, 'message': ERROR_TEXT.get(str(error), ERROR_TEXT['INVALID_LOCAL_CONFIGURATION'])}


def snapshot(db, document_id, revision=None):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, '문서를 찾을 수 없습니다.')
    require_current(doc)
    policy = policy_for(db, doc.contract_id)
    if revision is not None and revision != policy['revision']:
        raise HTTPException(409, '계약 자료가 변경되었습니다. 최신 내용을 불러오세요.')
    path = resolve_path(doc.storage_path)
    info = db.get(DocumentFileInfo, document_id)
    if not path or not info:
        raise HTTPException(409, '등록된 원본을 확인하지 못했습니다. 원본을 다시 등록하세요.')
    if path.suffix.lower() not in VISUAL_EXTENSIONS:
        raise HTTPException(422, 'VLM 재판독은 PDF 또는 이미지 서류에서 사용할 수 있습니다.')
    if path.stat().st_size > 20 * 1024 * 1024:
        raise HTTPException(413, 'VLM 재판독 원본은 20MB까지 지원합니다.')
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != info.sha256:
        raise HTTPException(409, '원본이 등록 당시와 다릅니다. 원본을 확인하세요.')
    inputs = PipelineService().validation_inputs(db, doc.contract)
    result = {'document_id': document_id, 'contract_id': doc.contract_id, 'document_type': doc.document_type,
        'revision': policy['revision'], 'fingerprint': fingerprint_for(db, doc.contract, inputs),
        'current_fields': json.loads(doc.extract.raw_fields) if doc.extract and doc.extract.raw_fields else {},
        'source_sha256': info.sha256, 'suffix': path.suffix.lower(), 'content': content}
    db.rollback()
    return result


def same_source(a, b):
    return all(a[key] == b[key] for key in ('document_id', 'revision', 'fingerprint', 'source_sha256'))


def page_image(source, page):
    try:
        if type(page) is not int or page < 1:
            raise HTTPException(422, '문서의 페이지 범위를 확인하세요.')
        if source['suffix'] == '.pdf':
            import pypdfium2 as pdfium
            from ..ai.pdf_runtime import PDFIUM_LOCK, open_page, page_count, page_size, render_page_image
            # VLM uses the snapshotted bytes, but shares the same process-wide
            # PDFium lock and detached bitmap handling as OCR and previews.
            with PDFIUM_LOCK:
                pdf = pdfium.PdfDocument(source['content'])
            try:
                if page > page_count(pdf):
                    raise HTTPException(422, '문서의 페이지 범위를 확인하세요.')
                with open_page(pdf, page - 1) as pdf_page:
                    width, height = page_size(pdf_page)
                    if not all(math.isfinite(value) and value > 0 for value in (width, height)):
                        raise ValueError('INVALID_PAGE_SIZE')
                    with render_page_image(pdf_page, min(2, 1600 / max(width, height))) as rendered:
                        image = rendered.convert('RGB')
            finally:
                with PDFIUM_LOCK:
                    pdf.close()
        else:
            if page != 1:
                raise HTTPException(422, '이미지는 첫 쪽만 재판독할 수 있습니다.')
            with Image.open(io.BytesIO(source['content'])) as original:
                if original.width * original.height > 40_000_000:
                    raise HTTPException(413, '이미지 해상도가 너무 큽니다. 크기를 줄인 원본을 등록하세요.')
                image = ImageOps.exif_transpose(original).convert('RGB')
        try:
            image.thumbnail((1600, 1600))
            stream = io.BytesIO()
            image.save(stream, format='JPEG', quality=90)
            return stream.getvalue()
        finally:
            image.close()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, '원본 이미지나 PDF 페이지를 읽지 못했습니다. 선명한 고친 본을 등록하세요.') from None


def candidate(field, answer):
    result = {'field': field, 'value': None, 'quote': '', 'usable': False, 'reason': '읽지 못함·원문 확인 필요'}
    if not isinstance(answer, dict) or set(answer) != {'state', 'value', 'quote', 'party'}:
        return {**result, 'reason': '답변 형식 확인 필요'}
    state, value, quote, party = (answer[key] for key in ('state', 'value', 'quote', 'party'))
    if (not isinstance(state, str) or state not in {'VALUE', 'ABSENT', 'REVIEW'}
            or not isinstance(quote, str) or not isinstance(party, str)
            or party not in {'SUPPLIER', 'BUYER', 'UNKNOWN'}):
        return {**result, 'reason': '답변 형식 확인 필요'}
    result['quote'] = quote[:300]
    if state != 'VALUE' or not isinstance(value, str) or not value.strip() or len(value) > 200 or not quote.strip():
        return result
    if party == 'BUYER' or field in {'company_name', 'business_registration_no', 'account_number', 'bank_name'} and party != 'SUPPLIER':
        return {**result, 'reason': '공급자·예금주 구분 확인 필요'}
    value = value.strip()
    if field.endswith('amount'):
        number = money(value)
        if number is None or not math.isfinite(float(number)) or not any(money(token) == number for token in re.findall(r'\d[\d,]*(?:\.\d+)?', quote)):
            return {**result, 'reason': '금액 형식·제안 문구 확인 필요'}
        value = float(number)
    elif field == 'business_registration_no':
        digits = re.sub(r'[-\s]', '', value)
        if not re.fullmatch(r'\d{10}', digits) or digits not in re.sub(r'[-\s]', '', quote):
            return {**result, 'reason': '사업자번호 형식·제안 문구 확인 필요'}
    elif field == 'account_number':
        digits = re.sub(r'[-\s]', '', value)
        if not re.fullmatch(r'\d{8,20}', digits) or digits not in re.sub(r'[-\s]', '', quote):
            return {**result, 'reason': '계좌번호 형식·제안 문구 확인 필요'}
    elif field == 'issue_date':
        value = canonical(field, value)
        dates = re.findall(r'\d{4}\s*[년./-]\s*\d{1,2}\s*[월./-]\s*\d{1,2}\s*일?', quote)
        if not value or not any(value == canonical(field, date) for date in dates):
            return {**result, 'reason': '날짜 형식·제안 문구 확인 필요'}
    elif field == 'amount_scope':
        if value not in {'FULL', 'PARTIAL'} or scope_in_document(quote) != value:
            return {**result, 'reason': '청구 범위 확인 필요'}
    elif re.sub(r'\s', '', value) not in re.sub(r'\s', '', quote):
        return {**result, 'reason': '제안 문구와 값이 다름'}
    return {**result, 'value': value, 'usable': True, 'reason': '형식 확인 · 원문 대조 전 후보값'}


def public_result(event, masked, current_fields):
    data = json.loads(event.details)
    result = {key: data[key] for key in ('revision', 'fingerprint', 'page', 'model', 'candidates', 'prompt_version')}
    # Compare before redaction: two different identifiers may share the same masked display.
    result['candidates'] = [{**item, 'changed': canonical(item['field'], item['value']) !=
        canonical(item['field'], current_fields.get(item['field']))} for item in result['candidates']]
    result.update(run_id=event.event_id, document_id=event.document_id, created_at=event.created_at.isoformat(),
                  evidence_verified=False, automatically_applied=False)
    if masked:
        sensitive = {}
        collect_sensitive(data, sensitive)
        result = public_data(result, True, sensitive)
    return result


def reread(db, document_id, revision, page, fields, actor, masked):
    if not fields or len(fields) != len(set(fields)) or set(fields) - set(FIELDS):
        raise HTTPException(422, '재판독할 항목을 확인하세요.')
    with STORAGE_LOCK:
        source = snapshot(db, document_id, revision)
    if not VLM_SLOT.acquire(blocking=False):
        raise HTTPException(409, '다른 서류를 VLM으로 읽고 있습니다. 완료 후 다시 시도하세요.')
    try:
        try:
            answers, model = LocalVlmClient().read(page_image(source, page), fields, source['document_type'])
        except VlmError as error:
            raise HTTPException(503, ERROR_TEXT.get(str(error), ERROR_TEXT['INVALID_RESPONSE'])) from None
        proposals = [candidate(field, answers.get(field)) for field in fields]
    finally:
        VLM_SLOT.release()
    with STORAGE_LOCK:
        db.expire_all()
        live = snapshot(db, document_id, revision)
        if not same_source(source, live):
            raise HTTPException(409, '재판독 중 계약 자료가 변경되었습니다. 최신 자료로 다시 읽으세요.')
        details = {key: source[key] for key in ('revision', 'fingerprint', 'source_sha256')}
        details.update(page=page, model=model, prompt_version=PROMPT_VERSION, candidates=proposals,
            automatically_applied=False, evidence_verified=False,
            sensitive_values={item['field']: str(item['value']) for item in proposals if item['value'] is not None})
        event = AuditEvent(actor_id=actor.user_id, actor_name=actor.display_name, action='VLM_REREAD_COMPLETED',
            contract_id=source['contract_id'], document_id=document_id, details=json.dumps(details, ensure_ascii=False),
            created_at=datetime.now(timezone.utc).replace(tzinfo=None))
        db.add(event)
        db.commit()
        return public_result(event, masked, live['current_fields'])


def latest_result(db, document_id, revision, masked):
    source = snapshot(db, document_id, revision)
    for event in db.query(AuditEvent).filter_by(document_id=document_id, action='VLM_REREAD_COMPLETED').order_by(AuditEvent.event_id.desc()).limit(20):
        data = json.loads(event.details)
        if all(data.get(key) == source[key] for key in ('revision', 'fingerprint', 'source_sha256')):
            return public_result(event, masked, source['current_fields'])
    return None
