import io
import json
import os
import re
from typing import Dict, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

# Korean regions for address masking
KOREAN_REGIONS = (
    "서울특별시|서울시|서울|부산광역시|부산시|부산|대구광역시|대구시|대구|"
    "인천광역시|인천시|인천|광주광역시|광주시|광주|대전광역시|대전시|대전|"
    "울산광역시|울산시|울산|세종특별자치시|세종시|세종|경기도|경기|"
    "강원특별자치도|강원도|강원|충청북도|충북|충청남도|충남|"
    "전북특별자치도|전라북도|전북|전라남도|전남|경상북도|경북|경상남도|경남|"
    "제주특별자치도|제주도|제주"
)

# Standard Regex Patterns
RRN_PATTERN = re.compile(r"\b(\d{6})\s*[-–]?\s*([1-8])\d{6}\b")
BIZ_REG_NO_PATTERN = re.compile(r"\b(\d{3})\s*[-–]?\s*(\d{2})\s*[-–]?\s*(\d{5})\b")
PHONE_PATTERN = re.compile(r"\b(01[016789])\s*[-–.]?\s*(\d{3,4})\s*[-–.]?\s*(\d{4})\b")
TEL_PATTERN = re.compile(r"\b(02|0[3-6][1-5]|070|080)\s*[-–.]?\s*(\d{3,4})\s*[-–.]?\s*(\d{4})\b")
ACCOUNT_PATTERN = re.compile(r"\b(\d{3,4})\s*[-–]\s*(\d{2,6})\s*[-–]\s*(\d{3,6})\b")
EMAIL_PATTERN = re.compile(r"\b([A-Za-z0-9._%+-]{2})[A-Za-z0-9._%+-]*(@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")

# Representative & Person names
REP_KEYWORD_PATTERN = re.compile(r"(?:대표이사|대표자|대표)\s*[:：]?\s*([가-힣]{2,4})\b")
STAFF_KEYWORD_PATTERN = re.compile(r"(?:팀장|상무|이사|부장|과장|대리|책임|선임|담당자)\s+([가-힣]{2,4})\b")

# Corporate name patterns
CORP_NAME_PATTERN = re.compile(r"((?:\(주\)\s*[가-힣A-Za-z0-9]+|[가-힣A-Za-z0-9]+\s*주식회사|주식회사\s*[가-힣A-Za-z0-9]+))")


def get_korean_font(size: int = 13) -> ImageFont.ImageFont:
    """Finds a suitable Korean TrueType font on Windows, falling back to default."""
    font_candidates = [
        "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/gulim.ttc",
        "C:/Windows/Fonts/batang.ttc",
        "malgun.ttf",
    ]
    for path in font_candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def mask_vendor_name(name: str) -> str:
    """Masks company / vendor name (e.g., (주)ABC -> (주)A**, ABC 주식회사 -> A** 주식회사)."""
    if not name:
        return ""
    name = name.strip()
    if name.startswith("(주)"):
        body = name[3:].strip()
        if len(body) <= 1:
            return name
        return f"(주){body[0]}{'*' * max(2, len(body) - 1)}"
    if name.endswith("주식회사"):
        body = name[:-4].strip()
        if len(body) <= 1:
            return name
        return f"{body[0]}{'*' * max(2, len(body) - 1)} 주식회사"
    if name.startswith("주식회사"):
        body = name[4:].strip()
        if len(body) <= 1:
            return name
        return f"주식회사 {body[0]}{'*' * max(2, len(body) - 1)}"
    if len(name) == 3 and re.match(r"^[가-힣]+$", name):
        return f"{name[0]}*{name[2]}"
    if len(name) == 2 and re.match(r"^[가-힣]+$", name):
        return f"{name[0]}*"
    if len(name) > 2:
        return f"{name[:2]}{'*' * max(2, len(name) - 2)}"
    return name


def mask_person_name(name: str) -> str:
    """Masks a person name (e.g. 홍길동 -> 홍*동, 이총괄 -> 이*괄, 김철 -> 김*)."""
    if not name:
        return ""
    name = name.strip()
    if len(name) == 3:
        return f"{name[0]}*{name[2]}"
    if len(name) == 2:
        return f"{name[0]}*"
    if len(name) == 4:
        return f"{name[0]}**{name[3]}"
    return f"{name[0]}*"


def draw_redaction_badge(
    draw: ImageDraw.ImageDraw,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    masked_text: str,
    font: ImageFont.ImageFont,
):
    """Draws a clean, high-visibility redaction badge over sensitive text."""
    # Ensure minimum height/width for legible badge
    box_w = max(x1 - x0, 24)
    box_h = max(y1 - y0, 16)
    x1 = x0 + box_w
    y1 = y0 + box_h

    # Fill box with clean off-white badge with subtle border
    draw.rounded_rectangle(
        [x0, y0, x1, y1],
        radius=3,
        fill=(248, 250, 252),
        outline=(199, 210, 254),
        width=1,
    )

    # Calculate centered text position
    try:
        bbox = font.getbbox(masked_text)
        t_w = bbox[2] - bbox[0]
        t_h = bbox[3] - bbox[1]
    except Exception:
        t_w = len(masked_text) * 7
        t_h = 12

    tx = x0 + max(2, (box_w - t_w) // 2)
    ty = y0 + max(1, (box_h - t_h) // 2)

    try:
        draw.text((tx, ty), masked_text, fill=(67, 56, 202), font=font)
    except Exception:
        # Fallback to dark solid bar if drawing text fails
        draw.rectangle([x0, y0, x1, y1], fill=(30, 41, 59))


def mask_pdf_page_image(
    page_obj,
    pil_image: Image.Image,
    scale: int = 2,
    sensitive_dict: Optional[Dict[str, str]] = None,
) -> Image.Image:
    """
    Renders visual masking on a single PDF page image.
    Uses pypdfium2's textpage to accurately detect bounding boxes of sensitive information.
    """
    page_width, page_height = page_obj.get_size()
    image_copy = pil_image.copy()
    draw = ImageDraw.Draw(image_copy)
    font = get_korean_font(size=max(11, int(6.5 * scale)))

    textpage = page_obj.get_textpage()
    full_text = textpage.get_text_range()
    if not full_text:
        return image_copy

    # Gather search rules: (pattern, replacement_or_callable)
    rules: List[Tuple[str, str]] = [
        (r"\b\d{6}\s*[-–]?\s*[1-8]\d{6}\b", "******-*******"),
        (r"\b\d{3}\s*[-–]?\s*\d{2}\s*[-–]?\s*\d{5}\b", "123-**-*****"),
        (r"\b01[016789]\s*[-–.]?\s*\d{3,4}\s*[-–.]?\s*\d{4}\b", "010-****-****"),
        (r"\b(?:02|0[3-6][1-5]|070|080)\s*[-–.]?\s*\d{3,4}\s*[-–.]?\s*\d{4}\b", "02-***-****"),
        (r"\b\d{3,4}\s*[-–]\s*\d{2,6}\s*[-–]\s*\d{3,6}\b", "***-***-*****"),
        (r"\b[A-Za-z0-9._%+-]{2}[A-Za-z0-9._%+-]*@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "us***@***.com"),
    ]

    # Explicit sensitive terms from document/contract extracts
    if sensitive_dict:
        # Company / Vendor name
        for k in ["company_name", "vendor_name", "extracted_vendor_name"]:
            val = sensitive_dict.get(k)
            if val and len(val.strip()) >= 2:
                raw_term = val.strip()
                # Create flexible pattern with optional whitespace between characters
                escaped = re.escape(raw_term)
                masked_val = mask_vendor_name(raw_term)
                rules.append((escaped, masked_val))

        # Representative name
        for k in ["representative_name", "rep_name"]:
            val = sensitive_dict.get(k)
            if val and len(val.strip()) >= 2:
                raw_term = val.strip()
                escaped = re.escape(raw_term)
                masked_val = mask_person_name(raw_term)
                rules.append((escaped, masked_val))

        # Business Registration No.
        for k in ["business_registration_no", "extracted_vendor_reg_no", "business_number"]:
            val = sensitive_dict.get(k)
            if val and len(val.strip()) >= 5:
                raw_term = val.strip()
                escaped = re.escape(raw_term)
                rules.append((escaped, "123-**-*****"))

        # Account number
        for k in ["account_number"]:
            val = sensitive_dict.get(k)
            if val and len(val.strip()) >= 5:
                raw_term = val.strip()
                escaped = re.escape(raw_term)
                rules.append((escaped, "110-***-456789"))

    # Also detect representative names and corporate names from text
    for m in REP_KEYWORD_PATTERN.finditer(full_text):
        name = m.group(1)
        if name and len(name) >= 2:
            rules.append((re.escape(name), mask_person_name(name)))

    for m in STAFF_KEYWORD_PATTERN.finditer(full_text):
        name = m.group(1)
        if name and len(name) >= 2:
            rules.append((re.escape(name), mask_person_name(name)))

    for m in CORP_NAME_PATTERN.finditer(full_text):
        corp = m.group(1)
        if corp and len(corp) >= 4:
            rules.append((re.escape(corp), mask_vendor_name(corp)))

    # Apply all rules and find bounding boxes
    masked_spans = set()
    for pat, masked_label in rules:
        try:
            for m in re.finditer(pat, full_text):
                start, end = m.span()
                # Avoid overlapping duplicate masks
                span_key = (start, end)
                if span_key in masked_spans:
                    continue
                masked_spans.add(span_key)

                n_rects = textpage.count_rects(start, end - start)
                if n_rects > 0:
                    boxes = [textpage.get_rect(i) for i in range(n_rects)]
                    min_l = min(b[0] for b in boxes)
                    min_b = min(b[1] for b in boxes)
                    max_r = max(b[2] for b in boxes)
                    max_t = max(b[3] for b in boxes)

                    # Transform PDF points to image pixels
                    pad = max(2, int(scale))
                    x0 = int(min_l * scale - pad)
                    y0 = int((page_height - max_t) * scale - pad)
                    x1 = int(max_r * scale + pad)
                    y1 = int((page_height - min_b) * scale + pad)

                    # Dynamic label if pattern has groups
                    lbl = masked_label
                    if pat.startswith(r"\b\d{3}\s*[-–]?\s*\d{2}"):
                        lbl = f"{m.group(0)[:3]}-**-*****"

                    draw_redaction_badge(draw, x0, y0, x1, y1, lbl, font)
        except Exception:
            continue

    return image_copy


def mask_image_with_ocr(
    pil_image: Image.Image,
    sensitive_dict: Optional[Dict[str, str]] = None,
) -> Image.Image:
    """
    Renders visual masking on an image document (PNG, JPG, BMP, TIFF) using Windows OCR.
    """
    image_copy = pil_image.copy()
    draw = ImageDraw.Draw(image_copy)
    font = get_korean_font(size=13)

    try:
        import winocr
        res = winocr.recognize_pil_sync(image_copy, lang="ko")
        lines = res.get("lines", [])
    except Exception:
        lines = []

    if not lines:
        return image_copy

    # Collect sensitive words/terms to mask
    sensitive_values = []
    if sensitive_dict:
        for val in sensitive_dict.values():
            if val and isinstance(val, str) and len(val.strip()) >= 2:
                sensitive_values.append(val.strip())

    for line in lines:
        for word in line.get("words", []):
            txt = word.get("text", "")
            rect = word.get("bounding_rect", {})
            if not txt or not rect:
                continue

            x = int(rect.get("x", 0))
            y = int(rect.get("y", 0))
            w = int(rect.get("width", 0))
            h = int(rect.get("height", 0))

            should_mask = False
            masked_val = "***"

            # Check business number
            if re.search(r"\d{3}[-–.]?\d{2}[-–.]?\d{5}", txt) or re.search(r"\d{3}-\d{2}", txt):
                should_mask = True
                masked_val = "123-**-*****"
            # Check phone
            elif re.search(r"01[016789][\s\-.]?\d{3,4}[\s\-.]?\d{4}", txt):
                should_mask = True
                masked_val = "010-****-****"
            # Check RRN
            elif re.search(r"\d{6}[-–]?\d{7}", txt):
                should_mask = True
                masked_val = "******-*******"
            # Check corporate name
            elif "주식회사" in txt or "(주)" in txt:
                should_mask = True
                masked_val = mask_vendor_name(txt)
            else:
                # Check sensitive terms
                for s in sensitive_values:
                    if s in txt:
                        should_mask = True
                        masked_val = mask_vendor_name(s)
                        break

            if should_mask:
                draw_redaction_badge(draw, x, y, x + w, y + h, masked_val, font)

    return image_copy


def render_masked_pdf_bytes(
    pdf_path: str,
    sensitive_dict: Optional[Dict[str, str]] = None,
    scale: int = 2,
) -> bytes:
    """Renders all pages of a PDF with masking applied and exports as a clean redacted PDF file."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(pdf_path)
    masked_pages: List[Image.Image] = []

    for page_idx in range(len(pdf)):
        page_obj = pdf[page_idx]
        pil_img = page_obj.render(scale=scale).to_pil()
        masked_img = mask_pdf_page_image(page_obj, pil_img, scale=scale, sensitive_dict=sensitive_dict)
        masked_pages.append(masked_img)

    buf = io.BytesIO()
    if masked_pages:
        masked_pages[0].save(
            buf,
            format="PDF",
            save_all=True,
            append_images=masked_pages[1:],
            resolution=150.0,
        )
    return buf.getvalue()
