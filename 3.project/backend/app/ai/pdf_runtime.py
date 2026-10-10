"""Short, process-local guards for native PDFium calls and handle cleanup.

PDFium handles are not context managers in every supported pypdfium2 release.
Keep native calls serialized, but run OCR, image encoding and file I/O outside
this mutex. This guard is independent of the database publication lock.
"""
import threading
from contextlib import contextmanager


PDFIUM_LOCK = threading.RLock()


@contextmanager
def open_pdf(path):
    import pypdfium2 as pdfium
    with PDFIUM_LOCK:
        document = pdfium.PdfDocument(str(path))
    try:
        yield document
    finally:
        with PDFIUM_LOCK:
            document.close()


@contextmanager
def open_page(document, index):
    with PDFIUM_LOCK:
        page = document[index]
    try:
        yield page
    finally:
        with PDFIUM_LOCK:
            page.close()


@contextmanager
def open_textpage(page):
    with PDFIUM_LOCK:
        textpage = page.get_textpage()
    try:
        yield textpage
    finally:
        with PDFIUM_LOCK:
            textpage.close()


def page_count(document):
    with PDFIUM_LOCK:
        return len(document)


def page_size(page):
    with PDFIUM_LOCK:
        return page.get_size()


def page_text(textpage):
    with PDFIUM_LOCK:
        return textpage.get_text_range()


def text_rectangles(textpage, start, count):
    with PDFIUM_LOCK:
        return [textpage.get_rect(index) for index in range(textpage.count_rects(start, count))]


def render_page_image(page, scale):
    """Return a detached PIL image before releasing the native bitmap handle."""
    with PDFIUM_LOCK:
        bitmap = page.render(scale=scale)
        try:
            return bitmap.to_pil().copy()
        finally:
            bitmap.close()


def page_is_blank(page):
    """Verify an actually empty page, not merely an empty OCR/text result."""
    import pypdfium2.raw as raw
    with PDFIUM_LOCK:
        annotations = raw.FPDFPage_GetAnnotCount(page)
        objects = raw.FPDFPage_CountObjects(page)
        if annotations < 0 or not 0 <= objects <= 100_000:
            raise RuntimeError('PDF 빈 페이지 여부를 확인할 수 없습니다.')
        return annotations == 0 and objects == 0


def page_requires_raster_masking(page):
    """A native text layer does not prove all rendered content is covered.

    Inspect top-level objects only: any Form requires raster inspection, so
    deeply nested forms cannot evade coverage or trigger unbounded recursion.
    Object pointers belong to the page; they must not be destroyed separately.
    """
    import pypdfium2.raw as raw
    with PDFIUM_LOCK:
        # Annotations are rendered by page.render(), but are absent from the
        # page object list/text page. Treat their appearances as raster content.
        annotation_count = raw.FPDFPage_GetAnnotCount(page)
        if annotation_count < 0:
            raise RuntimeError('PDF 주석을 확인할 수 없습니다.')
        if annotation_count:
            return True
        count = raw.FPDFPage_CountObjects(page)
        if not 0 <= count <= 100_000:
            raise RuntimeError('PDF 페이지 객체를 안전하게 검사할 수 없습니다.')
        for index in range(count):
            obj = raw.FPDFPage_GetObject(page, index)
            if not obj:
                raise RuntimeError('PDF 페이지 객체를 확인할 수 없습니다.')
            kind = raw.FPDFPageObj_GetType(obj)
            # Paths may be outlined glyphs, even when they look like ordinary
            # line/table art. Only an exclusively native-text page can skip OCR.
            if kind != raw.FPDF_PAGEOBJ_TEXT:
                return True
        return False


def matching_text_rectangles(textpage, value):
    """Find native indices rather than assuming Python offsets are PDF indices."""
    with PDFIUM_LOCK:
        search = textpage.search(value, match_case=True)
        try:
            rectangles = []
            while True:
                match = search.get_next()
                if match is None:
                    return rectangles
                start, count = match
                boxes = text_rectangles(textpage, start, count)
                if not boxes:
                    raise RuntimeError('PDF 문구의 가림 위치가 누락되었습니다.')
                rectangles.extend(boxes)
                if len(rectangles) > 100_000:
                    raise RuntimeError('PDF 가림 위치 수가 처리 한도를 초과했습니다.')
        finally:
            search.close()


def page_rect_to_bitmap(page, box, image_size):
    """Match render_page_image(scale)'s uncropped, unrotated render arguments.

    The page's own Rotate/CropBox are handled internally by FPDF_PageToDevice.
    Converting every corner supports all four native page rotations.
    """
    import math
    import pypdfium2 as pdfium
    left, bottom, right, top = box
    if not all(math.isfinite(value) for value in box) or right <= left or top <= bottom:
        raise RuntimeError('PDF 문구의 가림 위치가 유효하지 않습니다.')
    with PDFIUM_LOCK:
        converter = pdfium.PdfPosConv(page, (0, 0, image_size[0], image_size[1], 0))
        points = [converter.to_bitmap(x, y) for x in (left, right) for y in (bottom, top)]
    return (min(x for x, _ in points), min(y for _, y in points),
            max(x for x, _ in points), max(y for _, y in points))
