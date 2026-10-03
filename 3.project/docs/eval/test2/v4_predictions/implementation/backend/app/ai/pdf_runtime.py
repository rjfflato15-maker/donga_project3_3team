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
