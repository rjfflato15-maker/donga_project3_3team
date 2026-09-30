import io
import json
import os
import re
from typing import Dict, List, Optional, Tuple, Set
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
RRN_OR_CORP_PATTERN = re.compile(r"\b(\d{6})\s*[-–]?\s*(\d{7})\b")
BIZ_REG_NO_PATTERN = re.compile(r"\b(\d{3})\s*[-–]?\s*(\d{2})\s*[-–]?\s*(\d{5})\b")
PHONE_OR_TEL_PATTERN = re.compile(r"\b(?:01[016789]|02|0[3-6][1-5]|070|080)\s*[-–.]?\s*(\d{3,4})\s*[-–.]?\s*(\d{4})\b")
ACCOUNT_KEYWORD_PATTERN = re.compile(r"(?:입\s*금\s*계\s*좌|계\s*좌\s*번\s*호|계\s*좌)\s*[:：]?\s*(?:[가-힣]{2,6}\s*)?([0-9\-–]{9,20})")
EMAIL_PATTERN = re.compile(r"\b([A-Za-z0-9._%+-]{2})[A-Za-z0-9._%+-]*(@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")

# Representative & Person names (with flexible spacing between characters)
REP_KEYWORD_PATTERN = re.compile(r"대\s*표\s*(?:이\s*사|자)?\s*[:：]?\s*([가-힣](?:\s*[가-힣]){1,3})\b")
NAME_KEYWORD_PATTERN = re.compile(r"성\s*명\s*[:：]?\s*([가-힣](?:\s*[가-힣]){1,3})\b")
STAFF_KEYWORD_PATTERN = re.compile(r"(?:팀장|상무|이사|부장|과장|대리|책임|선임|담당자)\s+([가-힣](?:\s*[가-힣]){1,3})\b")

# Corporate / Company name patterns
CORP_NAME_PATTERN = re.compile(r"((?:\(주\)\s*[가-힣A-Za-z0-9\s]+|[가-힣A-Za-z0-9\s]+\s*주식회사|주식회사\s*[가-힣A-Za-z0-9\s]+))")
COMPANY_HEADER_PATTERN = re.compile(r"상\s*호\s*[:：]?\s*([^\r\n]+)")

# Address pattern (capturing detail building/floor to mask)
ADDRESS_HEADER_PATTERN = re.compile(r"주\s*소\s*[:：]?\s*(([가-힣A-Za-z0-9\s,.~·\-–]+?(?:시|군|구))\s*([^\r\n]+))")


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
    clean = re.sub(r"\s+", "", name.strip())
    clean = re.sub(r"인$", "", clean)
    if len(clean) == 3:
        return f"{clean[0]}*{clean[2]}"
    if len(clean) == 2:
        return f"{clean[0]}*"
    if len(clean) >= 4:
        return f"{clean[0]}**{clean[-1]}"
    return f"{clean[0]}*"


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
    box_w = max(x1 - x0, 24)
    box_h = max(y1 - y0, 16)

    try:
        bbox = font.getbbox(masked_text)
        t_w = bbox[2] - bbox[0]
        t_h = bbox[3] - bbox[1]
    except Exception:
        t_w = len(masked_text) * 7
        t_h = 12

    if box_w < t_w + 8:
        box_w = t_w + 8
    if box_h < t_h + 4:
        box_h = t_h + 4

    # Rounded rectangle badge: elegant light slate/indigo badge with subtle border
    draw.rounded_rectangle(
        [x0, y0, x0 + box_w, y0 + box_h],
        radius=3,
        fill=(248, 250, 252),
        outline=(165, 180, 252),
        width=1,
    )

    tx = x0 + max(2, (box_w - t_w) // 2)
    ty = y0 + max(1, (box_h - t_h) // 2)

    try:
        draw.text((tx, ty), masked_text, fill=(67, 56, 202), font=font)
    except Exception:
        draw.rectangle([x0, y0, x0 + box_w, y0 + box_h], fill=(30, 41, 59))


def mask_pdf_page_image(
    page_obj,
    pil_image: Image.Image,
    scale: int = 2,
    sensitive_dict: Optional[Dict[str, str]] = None,
) -> Image.Image:
    """
    Renders visual masking on a single PDF page image.
    Uses pypdfium2's textpage to accurately detect bounding boxes of sensitive business & personal information.
    """
    page_width, page_height = page_obj.get_size()
    image_copy = pil_image.copy()
    draw = ImageDraw.Draw(image_copy)
    font = get_korean_font(size=max(11, int(6.5 * scale)))

    textpage = page_obj.get_textpage()
    full_text = textpage.get_text_range()
    if not full_text:
        return image_copy

    masked_spans: Set[Tuple[int, int]] = set()

    def mask_span_range(start: int, end: int, label: str):
        if start < 0 or end <= start or start >= len(full_text):
            return
        # Avoid overlapping duplicate masks
        for (s, e) in list(masked_spans):
            if not (end <= s or start >= e):
                # Overlaps significantly
                if (end - start) <= (e - s):
                    return
        masked_spans.add((start, end))

        n_rects = textpage.count_rects(start, end - start)
        if n_rects > 0:
            boxes = [textpage.get_rect(i) for i in range(n_rects)]
            min_l = min(b[0] for b in boxes)
            min_b = min(b[1] for b in boxes)
            max_r = max(b[2] for b in boxes)
            max_t = max(b[3] for b in boxes)

            pad = max(2, int(scale))
            x0 = int(min_l * scale - pad)
            y0 = int((page_height - max_t) * scale - pad)
            x1 = int(max_r * scale + pad)
            y1 = int((page_height - min_b) * scale + pad)

            draw_redaction_badge(draw, x0, y0, x1, y1, label, font)

    # 1. Business Registration Number (사업자등록번호 10자리)
    for m in BIZ_REG_NO_PATTERN.finditer(full_text):
        lbl = f"{m.group(0)[:3]}-**-*****"
        mask_span_range(m.start(), m.end(), lbl)

    # 2. Corporate ID & Resident Reg No (법인등록번호 및 주민등록번호 13자리)
    for m in RRN_OR_CORP_PATTERN.finditer(full_text):
        mask_span_range(m.start(), m.end(), "******-*******")

    # 3. Phone & Telephone (전화번호, 휴대폰, 유선번호)
    for m in PHONE_OR_TEL_PATTERN.finditer(full_text):
        num = m.group(0).strip()
        lbl = "010-****-****" if num.startswith("01") else "02-***-****"
        mask_span_range(m.start(), m.end(), lbl)

    # 4. Bank Account (입금 계좌번호)
    for m in ACCOUNT_KEYWORD_PATTERN.finditer(full_text):
        mask_span_range(m.start(1), m.end(1), "***-***-******")

    # General Account numbers with hyphens
    for m in re.finditer(r"\b\d{3,6}\s*[-–]\s*\d{2,6}\s*[-–]\s*\d{3,8}\b", full_text):
        mask_span_range(m.start(), m.end(), "***-***-*****")

    # 5. Representative & Person Names (대표이사, 대표자, 성명)
    for m in REP_KEYWORD_PATTERN.finditer(full_text):
        raw_name = m.group(1).strip()
        clean = re.sub(r"\s+", "", raw_name)
        clean = re.sub(r"인$", "", clean)
        lbl = mask_person_name(clean)
        mask_span_range(m.start(1), m.start(1) + len(raw_name.rstrip(" 인")), lbl)

    for m in NAME_KEYWORD_PATTERN.finditer(full_text):
        raw_name = m.group(1).strip()
        clean = re.sub(r"\s+", "", raw_name)
        clean = re.sub(r"인$", "", clean)
        lbl = mask_person_name(clean)
        mask_span_range(m.start(1), m.start(1) + len(raw_name.rstrip(" 인")), lbl)

    for m in STAFF_KEYWORD_PATTERN.finditer(full_text):
        raw_name = m.group(1).strip()
        clean = re.sub(r"\s+", "", raw_name)
        lbl = mask_person_name(clean)
        mask_span_range(m.start(1), m.end(1), lbl)

    # 6. Detailed Address (상세주소 및 건물호수)
    for m in ADDRESS_HEADER_PATTERN.finditer(full_text):
        detail = m.group(3).strip()
        if len(detail) >= 3:
            mask_span_range(m.start(3), m.end(3), "[상세주소 비식별화]")

    # 7. Company / Vendor Names (상호 / 업체명)
    for m in COMPANY_HEADER_PATTERN.finditer(full_text):
        name = m.group(1).strip()
        lbl = mask_vendor_name(name)
        mask_span_range(m.start(1), m.end(1), lbl)

    for m in CORP_NAME_PATTERN.finditer(full_text):
        corp = m.group(1).strip()
        if len(corp) >= 4:
            mask_span_range(m.start(1), m.end(1), mask_vendor_name(corp))

    # 8. Email Addresses
    for m in EMAIL_PATTERN.finditer(full_text):
        mask_span_range(m.start(), m.end(), "us***@***.com")

    # 9. Explicit Sensitive Terms from database/contract
    if sensitive_dict:
        for k in ["company_name", "vendor_name", "extracted_vendor_name"]:
            val = sensitive_dict.get(k)
            if val and len(val.strip()) >= 2:
                term = val.strip()
                pat_str = "".join(re.escape(c) + r"\s*" for c in term).rstrip(r"\s*")
                try:
                    for m in re.finditer(pat_str, full_text):
                        mask_span_range(m.start(), m.end(), mask_vendor_name(term))
                except Exception:
                    pass

        for k in ["representative_name", "rep_name"]:
            val = sensitive_dict.get(k)
            if val and len(val.strip()) >= 2:
                term = val.strip()
                pat_str = "".join(re.escape(c) + r"\s*" for c in term).rstrip(r"\s*")
                try:
                    for m in re.finditer(pat_str, full_text):
                        mask_span_range(m.start(), m.end(), mask_person_name(term))
                except Exception:
                    pass

        for k in ["business_registration_no", "extracted_vendor_reg_no", "business_number"]:
            val = sensitive_dict.get(k)
            if val and len(val.strip()) >= 5:
                term = val.strip()
                escaped = re.escape(term)
                try:
                    for m in re.finditer(escaped, full_text):
                        mask_span_range(m.start(), m.end(), f"{term[:3]}-**-*****")
                except Exception:
                    pass

        for k in ["account_number"]:
            val = sensitive_dict.get(k)
            if val and len(val.strip()) >= 5:
                term = val.strip()
                escaped = re.escape(term)
                try:
                    for m in re.finditer(escaped, full_text):
                        mask_span_range(m.start(), m.end(), "***-***-******")
                except Exception:
                    pass

    return image_copy


def mask_image_with_ocr(
    pil_image: Image.Image,
    sensitive_dict: Optional[Dict[str, str]] = None,
) -> Image.Image:
    """
    Renders visual masking on an image document (PNG, JPG, BMP, TIFF) using Windows Native OCR.
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
    sensitive_values: List[str] = []
    if sensitive_dict:
        for val in sensitive_dict.values():
            if val and isinstance(val, str) and len(val.strip()) >= 2:
                sensitive_values.append(val.strip())

    for line in lines:
        line_text = line.get("text", "")
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

            # 1. Business Registration No
            if re.search(r"\d{3}[-–.]?\d{2}[-–.]?\d{5}", txt) or re.search(r"\d{3}-\d{2}", txt):
                should_mask = True
                masked_val = "123-**-*****"
            # 2. Corporate ID or RRN (13 digits)
            elif re.search(r"\d{6}[-–]?\d{7}", txt):
                should_mask = True
                masked_val = "******-*******"
            # 3. Phone / Tel
            elif re.search(r"(?:01[016789]|02|0[3-6][1-5]|070|080)[-–.]?\d{3,4}[-–.]?\d{4}", txt):
                should_mask = True
                masked_val = "010-****-****" if txt.startswith("01") else "02-***-****"
            # 4. Bank Account
            elif re.search(r"\d{3,6}[-–]\d{2,6}[-–]\d{3,6}", txt):
                should_mask = True
                masked_val = "***-***-******"
            # 5. Corporate name
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
