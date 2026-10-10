"""Presentation-only masking. Never used by extraction, prompts, guards or evals."""
import re
import math
import json

from PIL import Image, ImageDraw
from ..ai.preprocessor import _safe_winocr_recognize
from ..ai.masking import mask_sensitive_information

SENSITIVE_KEYS = {
    'company_name', 'vendor_name', 'extracted_vendor_name', 'representative_name',
    'rep_name', 'account_number', 'business_registration_no', 'business_number',
    'extracted_vendor_reg_no', 'phone', 'address',
    'actor_name', 'assigner_name', 'assignee_name',
}


def document_sensitive_values(doc, db=None):
    """Keep known original/corrected identifiers available to presentation masks.

    Values are confined to this document's own initial extraction and audit
    history, plus its current contract. A field correction must not unmask a
    value that is still present elsewhere in the immutable original document.
    """
    result = {}

    def collect(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in SENSITIVE_KEYS and isinstance(item, str) and item.strip():
                    values = result.setdefault(key, [])
                    if item not in values:
                        values.append(item)
                else:
                    collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    if doc.contract:
        collect({'vendor_name': doc.contract.vendor_name, 'business_number': doc.contract.business_number})
    records = [doc.extract.raw_fields if doc.extract else '{}',
               doc.version.initial_fields_json if doc.version else '{}']
    if db is not None:
        from ..db.models import AuditEvent
        records.extend(raw for (raw,) in db.query(AuditEvent.details).filter_by(
            contract_id=doc.contract_id, document_id=doc.document_id, action='EXTRACT_CORRECTED'))
    for raw in records:
        try:
            collect(json.loads(raw or '{}'))
        except (ValueError, TypeError):
            continue
    return result


NUMBER_PATTERNS = [
    re.compile(r'(?<!\d)\d{3}\s*[-–.]?\s*\d{2}\s*[-–.]?\s*\d{5}(?!\d)'),
    re.compile(r'(?<!\d)\d{6}\s*[-–]?\s*\d{7}(?!\d)'),
    re.compile(r'(?<!\d)(?:01[016789]|02|0[3-6][1-5]|070|080)\s*[-–.]?\s*\d{3,4}\s*[-–.]?\s*\d{4}(?!\d)'),
    re.compile(r'(?<!\d)\d{3,6}\s*[-–]\s*\d{2,6}\s*[-–]\s*\d{3,8}(?!\d)'),
    re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'),
]
LABEL = re.compile(r'상\s*호(?:\s*명)?|업\s*체\s*명|법\s*인\s*명|거\s*래\s*처\s*명|예\s*금\s*주|대\s*표\s*(?:자|이\s*사)|성\s*명|주\s*소')
NEXT_LABEL = re.compile(r'상\s*호|업\s*체\s*명|법\s*인\s*명|대\s*표|성\s*명|주\s*소|사\s*업\s*자|등\s*록\s*번\s*호|발\s*행\s*일|공\s*급\s*가\s*액|세\s*액|합\s*계|공\s*급\s*받\s*는\s*자|공\s*급\s*자|계\s*좌|전\s*화|연\s*락\s*처')
LEGAL_NAME = re.compile(r'(?:주\s*식\s*회\s*사|\(\s*주\s*\)|㈜)\s*[^\r\n:：]+')
LEGAL_NAME_SUFFIX = re.compile(r'[가-힣A-Za-z0-9][가-힣A-Za-z0-9 \t]*주\s*식\s*회\s*사')
ACCOUNT_VALUE = re.compile(r'(?:입\s*금\s*계\s*좌|계\s*좌\s*번\s*호|계\s*좌)\s*[:：]?\s*(?:[가-힣]{2,6}\s*)?([0-9\-–]{9,20})')
BARE_REP_VALUE = re.compile(r'^\s*대\s*표(?:\s*[:：]\s*|\s+)([가-힣](?:[ \t]*[가-힣]){1,3})(?:[ \t]*\([ \t]*(?:인|서명)[ \t]*\)|[ \t]+인)?[ \t]*$')
STAFF_VALUE = re.compile(r'(?:팀장|상무|이사|부장|과장|대리|책임|선임|담당자)\s+([가-힣](?:\s*[가-힣]){1,3})\b')



def term_pattern(value):
    return re.compile(r'\s*'.join(re.escape(c) for c in str(value) if not c.isspace()))


def sensitive_terms(sensitive_dict):
    for key, values in (sensitive_dict or {}).items():
        if key not in SENSITIVE_KEYS:
            continue
        for value in values if isinstance(values, list) else [values]:
            if value and len(str(value).strip()) >= 2:
                yield value


def sensitive_spans(text, sensitive_dict=None):
    spans = [(m.start(), m.end()) for pattern in NUMBER_PATTERNS for m in pattern.finditer(text)]
    spans.extend((m.start(1), m.end(1)) for pattern in (ACCOUNT_VALUE, STAFF_VALUE) for m in pattern.finditer(text))
    offset = 0
    for raw_line in text.splitlines(keepends=True):
        line = raw_line.rstrip('\r\n')
        spans.extend((offset + m.start(1), offset + m.end(1)) for m in BARE_REP_VALUE.finditer(line))
        for label in LABEL.finditer(line):
            start = label.end()
            while start < len(line) and line[start] in ' \t:：.·':
                start += 1
            stop = NEXT_LABEL.search(line, start)
            end = stop.start() if stop else len(line)
            if line[start:end].strip():
                spans.append((offset + start, offset + end))
        for match in LEGAL_NAME.finditer(line):
            stop = NEXT_LABEL.search(line, match.start() + 1)
            spans.append((offset + match.start(), offset + (min(match.end(), stop.start()) if stop else match.end())))
        spans.extend((offset + m.start(), offset + m.end()) for m in LEGAL_NAME_SUFFIX.finditer(line))
        # Account for the exact original line separator (including CRLF).
        offset += len(raw_line)
    for value in sensitive_terms(sensitive_dict):
        spans.extend((m.start(), m.end()) for m in term_pattern(value).finditer(text))
    return spans


def export_patterns(sensitive_dict):
    return tuple(term_pattern(value) for value in sorted(
        set(sensitive_terms(sensitive_dict)), key=lambda v: len(str(v)), reverse=True))


def mask_export_text(text, sensitive_dict=None, *, patterns=None):
    """Cover known values even in filenames, arbitrary notes, or JSON strings."""
    for pattern in export_patterns(sensitive_dict) if patterns is None else patterns:
        text = pattern.sub('[가림]', text)
    text = mask_sensitive_information(text)[0]
    # Generic labeled company names may contain spaces. Process per line only.
    lines = []
    for line in text.splitlines(keepends=True):
        merged = []
        for start, end in sorted(sensitive_spans(line.rstrip('\r\n'))):
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
            else:
                merged.append((start, end))
        for start, end in reversed(merged):
            line = line[:start] + '[가림]' + line[end:]
        lines.append(line)
    return ''.join(lines)


def mask_image_with_ocr(image, sensitive_dict=None):
    """Mask spans across OCR words; reject absent or unusable position evidence."""
    if image.width <= 0 or image.height <= 0:
        raise RuntimeError('이미지 크기가 유효하지 않습니다.')
    scale = min(1.0, 2400 / max(image.size))
    target = image if scale == 1 else image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))), Image.Resampling.LANCZOS)
    target_width, target_height = target.size
    try:
        result = _safe_winocr_recognize(target, lang='ko')
    finally:
        if target is not image:
            target.close()
    lines = (result or {}).get('lines', [])
    if not lines:
        raise RuntimeError('이미지 가림에 필요한 OCR 위치를 확보하지 못했습니다.')
    if 'text' in result and re.sub(r'\s+', '', result['text'] or '') != re.sub(
            r'\s+', '', ''.join(line.get('text', '') for line in lines)):
        raise RuntimeError('OCR 전체 문구의 위치가 누락되어 가림을 중단했습니다.')
    protected = image.copy()
    draw = ImageDraw.Draw(protected)
    scale_x, scale_y = target_width / image.width, target_height / image.height
    positioned_words = 0
    try:
        for line in lines:
            words = line.get('words', [])
            if line.get('text', '').strip() and not words:
                raise RuntimeError('OCR 문구의 위치가 누락되어 가림을 중단했습니다.')
            text, offsets = '', []
            for word in words:
                value = word.get('text', '')
                rect = word.get('bounding_rect')
                if not value:
                    continue
                if not rect:
                    raise RuntimeError('OCR 글자의 위치가 유효하지 않습니다.')
                try:
                    x, y, width, height = (float(rect[key]) for key in ('x', 'y', 'width', 'height'))
                except (KeyError, TypeError, ValueError) as exc:
                    raise RuntimeError('OCR 글자의 위치가 유효하지 않습니다.') from exc
                if (not all(math.isfinite(v) for v in (x, y, width, height)) or width <= 0 or height <= 0
                        or x < -1 or y < -1 or x + width > target_width + 1 or y + height > target_height + 1):
                    raise RuntimeError('OCR 글자의 위치가 유효하지 않습니다.')
                if text:
                    text += ' '
                start = len(text)
                text += value
                offsets.append((start, len(text), (x, y, width, height)))
                positioned_words += 1
            # A line's recognized text cannot contain unpositioned extra words.
            if re.sub(r'\s+', '', line.get('text', '')) != re.sub(r'\s+', '', text):
                raise RuntimeError('OCR 문구와 글자 위치가 일치하지 않습니다.')
            spans = sensitive_spans(text, sensitive_dict)
            for start, end, (x, y, width, height) in offsets:
                if any(start < right and end > left for left, right in spans):
                    # Round outwards and pad anti-aliased edges after rescaling.
                    draw.rectangle((max(0, math.floor(x / scale_x) - 2),
                                    max(0, math.floor(y / scale_y) - 2),
                                    min(image.width - 1, math.ceil((x + width) / scale_x) + 2),
                                    min(image.height - 1, math.ceil((y + height) / scale_y) + 2)),
                                   fill=(45, 45, 45))
        if not positioned_words:
            raise RuntimeError('이미지 가림에 필요한 OCR 위치를 확보하지 못했습니다.')
        return protected
    except Exception:
        protected.close()
        raise


def render_masked_pdf_bytes(path, sensitive_dict=None, scale=1.5):
    """Contract ZIPs use exactly the same protected PDF path as individual files."""
    from ..ai.visual_masking import render_masked_pdf_bytes as render
    return render(path, sensitive_dict, scale)
