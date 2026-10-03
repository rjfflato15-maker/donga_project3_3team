"""Presentation-only masking. Never used by extraction, prompts, guards or evals."""
import re

from PIL import Image, ImageDraw
from ..ai.preprocessor import _safe_winocr_recognize
from ..ai.masking import mask_sensitive_information

SENSITIVE_KEYS = {
    'company_name', 'vendor_name', 'extracted_vendor_name', 'representative_name',
    'rep_name', 'account_number', 'business_registration_no', 'business_number',
    'extracted_vendor_reg_no', 'phone', 'address',
    'actor_name', 'assigner_name', 'assignee_name',
}
NUMBER_PATTERNS = [
    re.compile(r'(?<!\d)\d{3}\s*[-–.]?\s*\d{2}\s*[-–.]?\s*\d{5}(?!\d)'),
    re.compile(r'(?<!\d)\d{6}\s*[-–]?\s*\d{7}(?!\d)'),
    re.compile(r'(?<!\d)(?:01[016789]|02|0[3-6][1-5]|070|080)\s*[-–.]?\s*\d{3,4}\s*[-–.]?\s*\d{4}(?!\d)'),
    re.compile(r'(?<!\d)\d{3,6}\s*[-–]\s*\d{2,6}\s*[-–]\s*\d{3,6}(?!\d)'),
    re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'),
]
LABEL = re.compile(r'상\s*호(?:\s*명)?|업\s*체\s*명|법\s*인\s*명|거\s*래\s*처\s*명|예\s*금\s*주|대\s*표\s*(?:자|이\s*사)|성\s*명|주\s*소')
NEXT_LABEL = re.compile(r'상\s*호|업\s*체\s*명|법\s*인\s*명|대\s*표|성\s*명|주\s*소|사\s*업\s*자|등\s*록\s*번\s*호|발\s*행\s*일|공\s*급\s*가\s*액|세\s*액|합\s*계|공\s*급\s*받\s*는\s*자|공\s*급\s*자|계\s*좌|전\s*화|연\s*락\s*처')
LEGAL_NAME = re.compile(r'(?:주\s*식\s*회\s*사|\(\s*주\s*\)|㈜)\s*[^\r\n:：]+')


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
    for label in LABEL.finditer(text):
        start = label.end()
        while start < len(text) and text[start] in ' \t:：.·':
            start += 1
        stop = NEXT_LABEL.search(text, start)
        end = stop.start() if stop else len(text)
        if text[start:end].strip():
            spans.append((start, end))
    for match in LEGAL_NAME.finditer(text):
        stop = NEXT_LABEL.search(text, match.start() + 1)
        spans.append((match.start(), min(match.end(), stop.start()) if stop else match.end()))
    for value in sensitive_terms(sensitive_dict):
        spans.extend((m.start(), m.end()) for m in term_pattern(value).finditer(text))
    return spans


def mask_export_text(text, sensitive_dict=None):
    """Cover known values even in filenames, arbitrary notes, or JSON strings."""
    for value in sorted(set(sensitive_terms(sensitive_dict)), key=lambda v: len(str(v)), reverse=True):
        text = term_pattern(value).sub('[가림]', text)
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
    """Mask character spans across OCR words, with exact identifier formats."""
    scale = min(1.0, 2400 / max(image.size))
    target = image if scale == 1 else image.resize(
        (round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    try:
        result = _safe_winocr_recognize(target, lang='ko')
    finally:
        if target is not image:
            target.close()
    lines = (result or {}).get('lines', [])
    if not lines:
        raise RuntimeError('이미지 가림에 필요한 OCR 위치를 확보하지 못했습니다.')
    protected = image.copy()
    draw = ImageDraw.Draw(protected)
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
                if not rect or rect.get('width', 0) <= 0 or rect.get('height', 0) <= 0:
                    raise RuntimeError('OCR 글자의 위치가 유효하지 않습니다.')
                if text:
                    text += ' '
                start = len(text)
                text += value
                offsets.append((start, len(text), rect))
            spans = sensitive_spans(text, sensitive_dict)
            for start, end, rect in offsets:
                if any(start < right and end > left for left, right in spans):
                    x, y = rect['x'] / scale, rect['y'] / scale
                    draw.rectangle((x, y, x + rect['width'] / scale, y + rect['height'] / scale), fill=(45, 45, 45))
        return protected
    except Exception:
        protected.close()
        raise


def render_masked_pdf_bytes(path, sensitive_dict=None, scale=1.5):
    """Flatten PDFs; scanned pages use the presentation-only raster policy."""
    import io
    from ..ai.pdf_runtime import (open_pdf, open_page, open_textpage, page_text,
                                  page_count, page_size, render_page_image)
    from ..ai.visual_masking import _mask_pdf_text_page
    pages = []
    try:
        with open_pdf(path) as pdf:
            count, pixels = page_count(pdf), 0
            if not 1 <= count <= 50:
                raise RuntimeError('가림 PDF는 1~50쪽까지 지원합니다.')
            for index in range(count):
                with open_page(pdf, index) as page:
                    width, height = page_size(page)
                    actual_scale = min(scale, (16_000_000 / max(width * height, 1)) ** 0.5)
                    pixels += width * height * actual_scale ** 2
                    if pixels > 50_000_000:
                        raise RuntimeError('PDF 이미지의 전체 크기가 너무 큽니다.')
                    image = render_page_image(page, actual_scale)
                    protected = None
                    try:
                        with open_textpage(page) as textpage:
                            text = page_text(textpage)
                            # Native text rectangles are not normalized for rotated pages.
                            # Read the rendered orientation with OCR in that case.
                            if text.strip() and not page.get_rotation():
                                protected = _mask_pdf_text_page(page, image, actual_scale, sensitive_dict, textpage, text)
                        if protected is None:
                            protected = mask_image_with_ocr(image, sensitive_dict)
                        pages.append(protected.convert('RGB'))
                    finally:
                        image.close()
                        if protected is not None:
                            protected.close()
        output = io.BytesIO()
        pages[0].save(output, format='PDF', save_all=True, append_images=pages[1:], resolution=108.0)
        return output.getvalue()
    finally:
        for page in pages:
            page.close()
