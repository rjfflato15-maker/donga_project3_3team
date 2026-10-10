"""One presentation-only PDF masking path for previews and both exports.

The returned images/PDFs are flattened. No source PDF text or image objects are
copied to the output. This is not an extraction or model/guard policy.
"""
import io
import math

from PIL import ImageDraw

MAX_PAGE_PIXELS = 16_000_000
MAX_DOCUMENT_PIXELS = 50_000_000
MAX_PAGE_EDGE = 16_000
MAX_PAGES = 50
MASK_COLOR = (45, 45, 45)


def _render_scale(width, height, scale):
    """Bound the actual rounded bitmap, not just its floating-point area."""
    if not all(math.isfinite(value) and value > 0 for value in (width, height, scale)):
        raise RuntimeError('PDF 페이지 크기 또는 렌더 배율이 유효하지 않습니다.')
    actual = min(scale, math.sqrt(MAX_PAGE_PIXELS / width / height),
                 MAX_PAGE_EDGE / width, MAX_PAGE_EDGE / height)
    for _ in range(8):
        if not math.isfinite(actual) or actual <= 0:
            break
        pixels = math.ceil(width * actual) * math.ceil(height * actual)
        if pixels <= MAX_PAGE_PIXELS:
            return actual, pixels
        actual *= math.sqrt(MAX_PAGE_PIXELS / pixels) * 0.999999
    raise RuntimeError('PDF 페이지 이미지 크기를 안전하게 제한할 수 없습니다.')


def mask_pdf_page_image(page_obj, pil_image, scale=2, sensitive_dict=None):
    """Mask native coordinates and additionally OCR every non-text render.

    Rotation and CropBox offsets are handled by PDFium's own coordinate
    conversion. A native footer never exempts image/Form, path or annotation content from OCR.
    OCR runs on the original render, outside PDFium's mutex and text handle.
    """
    from .pdf_runtime import (open_textpage, page_text, page_size,
                              page_requires_raster_masking)
    width, height = page_size(page_obj)
    if not all(math.isfinite(value) and value > 0 for value in (width, height, scale)):
        raise RuntimeError('PDF 가림 좌표를 확인할 수 없습니다.')
    if pil_image.size != (math.ceil(width * scale), math.ceil(height * scale)):
        raise RuntimeError('PDF 렌더와 가림 좌표의 크기가 일치하지 않습니다.')
    if pil_image.width * pil_image.height > MAX_PAGE_PIXELS:
        raise RuntimeError('PDF 페이지 이미지 크기가 너무 큽니다.')

    needs_ocr = page_requires_raster_masking(page_obj)
    with open_textpage(page_obj) as textpage:
        text = page_text(textpage)
        rectangles = _native_mask_rectangles(page_obj, pil_image, sensitive_dict, textpage, text) if text.strip() else []
        needs_ocr = needs_ocr or not text.strip()
    # OCR the original render after all native handles/locks have been released.
    protected = mask_image_with_ocr(pil_image, sensitive_dict) if needs_ocr else pil_image.copy()
    try:
        _apply_native_masks(protected, rectangles, scale)
        return protected
    except Exception:
        protected.close()
        raise


def _mask_pdf_text_page(page_obj, pil_image, scale, sensitive_dict, textpage, full_text):
    """Compatibility helper for callers with an open text page."""
    rectangles = _native_mask_rectangles(page_obj, pil_image, sensitive_dict, textpage, full_text)
    protected = pil_image.copy()
    try:
        _apply_native_masks(protected, rectangles, scale)
        return protected
    except Exception:
        protected.close()
        raise


def _native_mask_rectangles(page_obj, pil_image, sensitive_dict, textpage, full_text):
    from .pdf_runtime import matching_text_rectangles, page_rect_to_bitmap
    from ..services.preview_masking_service import sensitive_spans

    if len(full_text) > 1_000_000:
        raise RuntimeError('PDF 글자 수가 가림 처리 한도를 초과했습니다.')
    # PDFium search returns native character indices. Python string offsets
    # alone are not safe when PDFium inserts/excludes characters or uses UTF-16.
    values = {full_text[start:end].strip() for start, end in sensitive_spans(full_text, sensitive_dict)}
    rectangles = []
    for value in values:
        if not value:
            continue
        boxes = matching_text_rectangles(textpage, value)
        if not boxes:
            raise RuntimeError('민감한 PDF 문구의 위치를 확보하지 못했습니다.')
        for box in boxes:
            rectangles.append(page_rect_to_bitmap(page_obj, box, pil_image.size))

    return rectangles


def _apply_native_masks(protected, rectangles, scale):
    draw = ImageDraw.Draw(protected)
    pad = max(2, math.ceil(scale))
    for left, top, right, bottom in rectangles:
        # CropBox can hide all or part of a native text rectangle.
        if right <= 0 or bottom <= 0 or left >= protected.width or top >= protected.height:
            continue
        draw.rectangle((max(0, left - pad), max(0, top - pad),
                        min(protected.width - 1, right + pad),
                        min(protected.height - 1, bottom + pad)), fill=MASK_COLOR)


def mask_image_with_ocr(pil_image, sensitive_dict=None):
    """Compatibility entry point; all raster masking uses one span policy."""
    from ..services.preview_masking_service import mask_image_with_ocr as mask
    return mask(pil_image, sensitive_dict)


def render_masked_pdf_bytes(pdf_path, sensitive_dict=None, scale=2):
    """Flatten every page; on any failure discard the whole protected output."""
    from .pdf_runtime import open_pdf, open_page, page_count, page_size, render_page_image

    pages = []
    try:
        with open_pdf(pdf_path) as pdf:
            count = page_count(pdf)
            if not 1 <= count <= MAX_PAGES:
                raise RuntimeError('가림 PDF는 1~50쪽까지 지원합니다.')
            pixels = 0
            for index in range(count):
                with open_page(pdf, index) as page:
                    width, height = page_size(page)
                    actual_scale, page_pixels = _render_scale(width, height, scale)
                    pixels += page_pixels
                    if pixels > MAX_DOCUMENT_PIXELS:
                        raise RuntimeError('PDF 이미지의 전체 크기가 너무 큽니다.')
                    image = render_page_image(page, actual_scale)
                    protected = None
                    try:
                        protected = mask_pdf_page_image(page, image, scale=actual_scale, sensitive_dict=sensitive_dict)
                        pages.append(protected.convert('RGB'))
                    finally:
                        image.close()
                        if protected is not None:
                            protected.close()
        with io.BytesIO() as output:
            pages[0].save(output, format='PDF', save_all=True, append_images=pages[1:], resolution=108.0)
            return output.getvalue()
    finally:
        for page in pages:
            page.close()
