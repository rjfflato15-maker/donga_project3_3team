"""Evidence anchors and conservative field/party checks. Never consult gold labels."""
import contextlib
import io
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

GUARD_VERSION = "grounding-v2-ocr-separator"

LABELS = {
    "company_name": r"상\s*호|업체명|예금주|수급인(?:명|\s*\(을\))?|공급자명|계약상대자",
    "business_registration_no": r"사업자\s*등록\s*번호|사업자\s*번호|등록\s*번호",
    "supply_amount": r"공급\s*가액|공급\s*금액",
    "tax_amount": r"부가\s*가치세|부가세|세액",
    "total_amount": r"합계\s*금액|총\s*금액|총액|합계|계약\s*대금|계약\s*금액|견적\s*금액|검수\s*금액|청구\s*금액",
    "issue_date": r"발행\s*일|발급\s*일|작성\s*일",
    "amount_scope": r"전액|전체\s*계약|계약\s*전체|선금|잔금|부분\s*청구|분할|계약서|견적서|검수확인서"
}
BUYER = re.compile(r"공급\s*받는\s*자|매입자|발주자")
SUPPLIER = re.compile(r"공급자|매출자|수급인|계약상대자")


def canonical(field, value):
    if value is None or value == "" or value == "UNKNOWN":
        return None
    token = str(value).strip()
    if field.endswith("amount"):
        try:
            number = Decimal(token.replace(",", "").replace("원", "").strip())
            return str(number.normalize()) if number.is_finite() and number >= 0 else None
        except InvalidOperation:
            return None
    if field == "business_registration_no":
        return re.sub(r"[\s-]", "", token)
    if field == "issue_date":
        m = re.fullmatch(r"(\d{4})\s*[년./-]\s*(\d{1,2})\s*[월./-]\s*(\d{1,2})\s*일?", token)
        if not m:
            return None
        try:
            return date(*map(int, m.groups())).isoformat()
        except ValueError:
            return None
    return re.sub(r"\s+", " ", token)


def source_pages(file_path, raw_text):
    path = Path(file_path)
    body = raw_text.partition("\n")[2] if raw_text.startswith("[파일명:") else raw_text
    if path.suffix.lower() != ".pdf":
        physical = path.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
        return [{"page": 1 if physical else None, "location_kind": "page" if physical else "document_block", "text": body}]
    from pypdf import PdfReader
    from .preprocessor import run_ocr_on_image
    from .pdf_runtime import open_pdf, open_page, render_page_image
    reader = PdfReader(str(path))
    if len(reader.pages) > 50:
        return []
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if not text.strip():
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                with open_pdf(str(path)) as pdf, open_page(pdf, i) as rendered:
                    image = render_page_image(rendered, 2)
                    try:
                        text = run_ocr_on_image(image)
                    finally:
                        image.close()
        pages.append({"page": i + 1, "location_kind": "page", "text": text})
    return pages


def party_at(lines, index, document_type):
    party = "unknown"
    for line in lines[:index + 1]:
        buyer, supplier = BUYER.search(line), SUPPLIER.search(line)
        if buyer and supplier:
            party = "ambiguous"
        elif buyer:
            party = "buyer"
        elif supplier:
            party = "supplier"
    if party == "unknown" and document_type in {"business_registration", "bank_account", "inspection_confirmation"}:
        party = "supplier"
    return party


def candidates(pages, field, document_type):
    found = []
    for page in pages:
        lines = page["text"].splitlines()
        for index, line in enumerate(lines):
            for label in re.finditer(LABELS[field], line):
                # OCR can render the colon as a dot followed by whitespace.
                # A leading decimal dot without whitespace is never a separator.
                tail = re.sub(r"^\s*(?:[:：=]|[.。](?=\s))?\s*", "", line[label.end():])
                if not tail and index + 1 < len(lines):
                    tail = lines[index + 1]
                value = None
                if field.endswith("amount"):
                    match = re.match(r"(?:[₩￦]|금)?\s*(\d[\d,]*(?:\.\d+)?)", tail)
                    if match and not re.match(r"\s*(?:[%년월일]|[./-]\s*\d)", tail[match.end():]):
                        value = match.group(1)
                    if field == "total_amount" and re.search(r"부가세\s*(?:별도|미포함)|VAT\s*(?:별도|제외)|공급가액\s*기준", line, re.I):
                        value = None
                elif field == "business_registration_no":
                    match = re.match(r"(\d{3}[\s-]*\d{2}[\s-]*\d{5})(?!\d)", tail)
                    value = match.group(1) if match else None
                elif field == "issue_date":
                    match = re.match(r"(\d{4}\s*[년./-]\s*\d{1,2}\s*[월./-]\s*\d{1,2}\s*일?)", tail)
                    value = match.group(1) if match else None
                elif field == "company_name":
                    value = tail.strip() or None
                else:
                    if re.fullmatch(r"계약서|견적서|검수확인서", label.group()) and not candidates(pages, "total_amount", document_type):
                        continue
                    value = "PARTIAL" if re.search(r"선금|잔금|부분\s*청구|분할", line) else "FULL"
                token = canonical(field, value)
                if token is not None:
                    found.append({"value": token, "page": page["page"], "line": index + 1,
                                  "label": label.group(), "party": party_at(lines, index, document_type)})
    return found


def checksum_valid(number):
    if not re.fullmatch(r"\d{10}", number or ""):
        return False
    digits = list(map(int, number))
    total = sum(n * weight for n, weight in zip(digits[:9], (1, 3, 7, 1, 3, 7, 1, 3, 5))) + digits[8] * 5 // 10
    return (10 - total % 10) % 10 == digits[9]


def guard_proposal(field, proposal, pages, document_type):
    reasons, warnings = [], []
    state, value = proposal.get("state"), proposal.get("value")
    token = canonical(field, value)
    options = candidates(pages, field, document_type)
    if field in {"company_name", "business_registration_no"}:
        eligible = [item for item in options if item["party"] == "supplier"]
    else:
        eligible = options
    distinct = {item["value"] for item in eligible}
    if state in {"ABSENT", "REVIEW"}:
        if value not in (None, ""):
            reasons.append("INVALID_FORMAT")
        if state == "ABSENT" and options or state == "REVIEW" and len(distinct) == 1:
            reasons.append("UNSUPPORTED_ABSTENTION")
        return {"field": field, "proposal": proposal, "accepted": not reasons, "reasons": reasons,
                "warnings": warnings, "anchor": None, "human_confirmed": False}
    if state != "VALUE" or token is None:
        reasons.append("INVALID_FORMAT")
    matching_page = next((p for p in pages if p["page"] == proposal.get("page")), None)
    if proposal.get("page") is None or not matching_page or matching_page["location_kind"] != "page":
        reasons.append("PAGE_UNVERIFIED")
    quote, line_no = proposal.get("quote", ""), proposal.get("line")
    anchor = None
    if matching_page and isinstance(line_no, int) and line_no >= 1:
        lines = matching_page["text"].splitlines()
        if line_no <= len(lines) and quote and quote in lines[line_no - 1]:
            start = sum(len(line) + 1 for line in lines[:line_no - 1]) + lines[line_no - 1].index(quote)
            anchor = {"page": proposal.get("page"), "line": line_no, "start": start, "end": start + len(quote),
                      "quote": quote, "location_kind": matching_page["location_kind"]}
    if anchor is None:
        reasons.append("EVIDENCE_NOT_FOUND")
    if field != "amount_scope" and token is not None:
        if field.endswith("amount"):
            in_quote = any(canonical(field, m.group()) == token for m in re.finditer(r"(?<!\d)\d[\d,]*(?:\.\d+)?(?!\d)", quote))
        elif field == "business_registration_no":
            in_quote = any(canonical(field, m.group()) == token for m in re.finditer(r"\d{3}[\s-]*\d{2}[\s-]*\d{5}", quote))
        elif field == "issue_date":
            in_quote = any(canonical(field, m.group()) == token for m in re.finditer(r"\d{4}\s*[년./-]\s*\d{1,2}\s*[월./-]\s*\d{1,2}\s*일?", quote))
        else:
            in_quote = token in (canonical(field, quote) or "")
        if not in_quote:
            reasons.append("VALUE_NOT_IN_QUOTE")
    local = [item for item in options if item["page"] == proposal.get("page") and item["line"] == line_no]
    matches = [item for item in local if item["value"] == token]
    if not matches:
        reasons.append("FIELD_LABEL_OR_VALUE_MISMATCH")
    if field in {"company_name", "business_registration_no"} and matches and any(item["party"] != "supplier" for item in matches):
        reasons.append("WRONG_PARTY")
    if len(distinct) > 1:
        reasons.append("AMBIGUOUS")
    if field == "business_registration_no" and not checksum_valid(token):
        reasons.append("INVALID_CHECKSUM")
    if field == "amount_scope" and token not in {"FULL", "PARTIAL"}:
        reasons.append("INVALID_FORMAT")
    # Raw printed inconsistencies belong to the rule engine, not value repair.
    numbers = {key: {item["value"] for item in candidates(pages, key, document_type)} for key in ("supply_amount", "tax_amount", "total_amount")}
    if all(len(values) == 1 for values in numbers.values()):
        supply, tax, total = (Decimal(next(iter(numbers[key]))) for key in ("supply_amount", "tax_amount", "total_amount"))
        if supply + tax != total:
            warnings.append("SOURCE_ARITHMETIC_MISMATCH")
    return {"field": field, "proposal": proposal, "accepted": not reasons, "reasons": list(dict.fromkeys(reasons)),
            "warnings": warnings, "anchor": anchor, "human_confirmed": False}


def supplementation_targets(fields, pages, document_type):
    expected = {"company_name", "business_registration_no", "issue_date"}
    if document_type == "bank_account":
        expected.discard("business_registration_no")
    if document_type in {"contract", "estimate", "tax_invoice", "inspection_confirmation"}:
        expected.update(("supply_amount", "tax_amount", "total_amount", "amount_scope"))
    targets = set()
    for field in expected:
        current = canonical(field, fields.get(field))
        options = candidates(pages, field, document_type)
        eligible = [o for o in options if field not in {"company_name", "business_registration_no"} or o["party"] == "supplier"]
        choices = {o["value"] for o in eligible}
        if current is None or current not in choices or len(choices) > 1:
            targets.add(field)
    monetary = [canonical(key, fields.get(key)) for key in ("supply_amount", "tax_amount", "total_amount")]
    if all(value is not None for value in monetary) and Decimal(monetary[0]) + Decimal(monetary[1]) != Decimal(monetary[2]):
        targets.update(("supply_amount", "tax_amount", "total_amount"))
    return tuple(field for field in LABELS if field in targets)
