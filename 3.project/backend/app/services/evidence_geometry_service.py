"""Read-only coordinates in the oriented preview image; never infer positions."""
import math
import re
from pathlib import Path

from ..ai.pdf_runtime import (PDFIUM_LOCK, open_pdf, open_page, open_textpage,
                              page_count, page_size, render_page_image, text_rectangles)


def compact(text):
    return re.sub(r"\s+", "", text)


def normalized_box(page, rectangle, width, height):
    x, y, w, h = rectangle
    if (not width or not height or any(not math.isfinite(float(v)) for v in (x, y, w, h, width, height))
            or min(x, y) < 0 or min(w, h) <= 0 or x + w > width + .01 or y + h > height + .01):
        return None
    return {"page": page, "x": x / width, "y": y / height,
            "width": w / width, "height": h / height}


def union(boxes):
    if not boxes:
        return None
    x, y = min(b["x"] for b in boxes), min(b["y"] for b in boxes)
    right = max(b["x"] + b["width"] for b in boxes)
    bottom = max(b["y"] + b["height"] for b in boxes)
    return {"page": boxes[0]["page"], "x": x, "y": y, "width": right - x, "height": bottom - y}


def ocr_boxes(image, quotes, page_number):
    from PIL import Image
    from ..ai.preprocessor import _safe_winocr_recognize
    width, height = image.size
    target = image
    if (width < 1200 or height < 600) and max(width, height) * 2 <= 2500:
        scale = max(2, min(3, 1600 // max(width, 1)))
        target = image.resize((min(2400, width * scale), min(2400, height * scale)), Image.Resampling.LANCZOS)
    elif max(width, height) > 2500:
        scale = 2400 / max(width, height)
        target = image.resize((int(width * scale), int(height * scale)), Image.Resampling.LANCZOS)
    try:
        result = _safe_winocr_recognize(target, lang="ko") or {}
        output = {}
        for quote in quotes:
            matching = [line for line in result.get("lines", []) if compact(line.get("text", "")) == compact(quote)]
            boxes = []
            if len(matching) == 1:
                words = matching[0].get("words", [])
                for word in words:
                    rect = word.get("bounding_rect") or {}
                    if not all(key in rect for key in ("x", "y", "width", "height")):
                        boxes = []
                        break
                    box = normalized_box(page_number, tuple(rect[key] for key in ("x", "y", "width", "height")), *target.size)
                    if box is None:
                        boxes = []
                        break
                    boxes.append(box)
            output[quote] = {"bbox": union(boxes), "bboxes": boxes, "coordinate_method": "OCR_WORD_BOXES" if boxes else None}
        return output
    finally:
        if target is not image:
            target.close()


def pdf_boxes(path, page_number, quotes):
    with open_pdf(path) as pdf:
        if not 1 <= page_number <= page_count(pdf):
            return {}
        with open_page(pdf, page_number - 1) as page:
            with PDFIUM_LOCK:
                rotation = page.get_rotation()
                bounds = page.get_bbox()
            # Rotated native PDF axes are not silently guessed.
            if rotation:
                return {}
            width, height = page_size(page)
            with open_textpage(page) as text:
                with PDFIUM_LOCK:
                    has_text = text.count_chars() > 0
                if has_text:
                    output = {}
                    for quote in quotes:
                        with PDFIUM_LOCK:
                            search = text.search(quote, match_case=True)
                            try:
                                hit = search.get_next()
                                repeated = search.get_next() if hit else None
                            finally:
                                search.close()
                        boxes = []
                        if hit and not repeated:
                            for left, bottom, right, top in text_rectangles(text, *hit):
                                box = normalized_box(page_number, (left - bounds[0], bounds[3] - top,
                                                     right - left, top - bottom), width, height)
                                if box is None:
                                    boxes = []
                                    break
                                boxes.append(box)
                        output[quote] = {"bbox": union(boxes), "bboxes": boxes,
                                         "coordinate_method": "PDF_TEXT_BOXES" if boxes else None}
                    return output
            image = render_page_image(page, 2)
    try:
        return ocr_boxes(image, quotes, page_number)
    finally:
        image.close()


def attach_coordinates(path, anchors, source_sha256):
    grouped = {}
    for anchor in anchors:
        anchor.update(bbox=None, bboxes=[], coordinate_space="preview_image_normalized_top_left",
                      source_sha256=source_sha256, coordinate_method=None)
        if type(anchor.get("page")) is int and anchor["page"] > 0 and anchor.get("quote"):
            grouped.setdefault(anchor["page"], set()).add(anchor["quote"])
    path = Path(path)
    for page, quotes in grouped.items():
        output = {}
        try:
            if path.suffix.lower() == ".pdf":
                output = pdf_boxes(path, page, quotes)
            elif page == 1 and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif", ".tif", ".tiff"}:
                from PIL import Image, ImageOps
                with Image.open(path) as original:
                    image = ImageOps.exif_transpose(original).convert("RGB")
                try:
                    output = ocr_boxes(image, quotes, page)
                finally:
                    image.close()
        except Exception:
            # A coordinate failure must not erase verified textual provenance.
            output = {}
        for anchor in anchors:
            if anchor.get("page") == page:
                anchor.update(output.get(anchor.get("quote"), {}))
    return anchors
