import re
from decimal import Decimal, InvalidOperation


def money(value):
    if value is None or value == "":
        return None
    try:
        result = Decimal(str(value).replace(",", ""))
        return result if result.is_finite() and result >= 0 else None
    except InvalidOperation:
        return None


def _label(value):
    return r"\s*".join(re.escape(char) for char in value)


_NUMBER = r"(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?"
_UNIT = r"(?:\([^()\r\n]{0,40}\))?"
_VALUE = re.compile(
    r"\s*(?P<unit>" + _UNIT + r")\s*(?P<separator>[:：=])?\s*"
    r"(?P<currency>[₩￦\\]|금)?\s*(?P<number>" + _NUMBER + r")(?![0-9,])(?P<won>\s*원)?"
)
_TOKEN = re.compile(r"\s*(?P<currency>[₩￦\\]|금)?\s*(?P<number>" + _NUMBER + r")(?![0-9,])(?P<won>[ \t]*원)?")
_DATE = re.compile(r"\s*[0-9]{4}\s*(?:년|[./-])\s*[0-9]{1,2}\s*(?:월|[./-])\s*[0-9]{1,2}\s*일?\s*")
_DATE_OR_RATE_SUFFIX = re.compile(r"[ \t]*(?:년|월|일|%)")
_SUPPLY = "(?:" + "|".join(_label(label) for label in ("공급가액", "공급금액")) + ")"
_TAX = "(?:" + "|".join(_label(label) for label in ("부가가치세", "부가세", "세액")) + ")"
_TOTAL_LABELS = ("총합계금액", "견적합계금액", "총견적합계", "총계약금액", "총견적금액",
                 "총검수금액", "총납품금액", "합계금액", "총금액", "총액", "합계")
_REFERENCE_LABELS = ("계약금액", "견적금액", "검수금액", "납품금액", "청구금액", "인정금액")


def _valid_token(match, text, *, separator=False, unit=False):
    suffix = text[match.end():]
    if _DATE_OR_RATE_SUFFIX.match(suffix):
        return None
    raw = match.group("number")
    if len(raw) == 4 and re.match(r"[ \t]*[./-][ \t]*[0-9]{1,2}[ \t]*[./-][ \t]*[0-9]{1,2}", suffix):
        return None
    # A table header can be followed by its first row's date, item number or
    # quantity. Bare small numbers are not monetary evidence. Small legitimate
    # amounts still work with a colon, currency marker, explicit unit or 원.
    marked = bool(match.group("currency") or match.group("won") or separator or unit)
    if not marked and re.match(r"[ \t]*[/\-]", suffix):
        return None
    if not marked and "," not in raw and len(raw.split(".")[0]) < 5:
        return None
    return money(raw)


def _direct_values(text, label):
    values = set()
    for heading in re.finditer(label, text):
        values.update(_after_label_values(text[heading.end():]))
    return values


def _after_label_values(tail):
    match = _VALUE.match(tail)
    if match:
        same_line_unit = bool(match.group("unit")) and "\n" not in tail[:match.start("number")]
        value = _valid_token(match, tail, separator=bool(match.group("separator")), unit=same_line_unit)
        if value is not None:
            return {value}
    # Korean amounts such as '일금 ... (₩ 38,500,000)' are accepted only
    # within the label's own line, not by scanning later item rows.
    values = set()
    line = tail.splitlines()[0] if tail.splitlines() else tail
    for parenthesis in re.finditer(r"\(([^()]{0,100})\)", line):
        prefix = line[:parenthesis.start()]
        if not re.fullmatch(r"\s*" + _UNIT + r"\s*[:：=]?\s*", prefix) and not re.search(_label("일금"), prefix):
            continue
        token = _TOKEN.fullmatch(parenthesis.group(1).strip())
        if token and (token.group("currency") or token.group("won")):
            value = _valid_token(token, parenthesis.group(1).strip())
            if value is not None:
                values.add(value)
    return values


def _line_pair(text, *, permit_date=False):
    """Read two summary columns only; never skip arbitrary item descriptions."""
    tail = text
    if permit_date:
        date = _DATE.match(tail)
        if date:
            tail = tail[date.end():]
    values = []
    for _ in range(2):
        leading = re.match(r"\s*", tail).end()
        tail = tail[leading:]
        token = _TOKEN.match(tail)
        if not token:
            return None
        value = _valid_token(token, tail)
        if value is None:
            return None
        values.append(value)
        tail = tail[token.end():]
    # More columns need layout information; do not guess their mapping.
    if not re.match(r"^[ \t]*(?:\r?\n|$)", tail):
        return None
    return values


def _summary_pairs(text):
    header = _SUPPLY + r"\s*" + _UNIT + r"\s*" + _TAX + r"\s*" + _UNIT
    headers = list(re.finditer(header, text))
    pairs = []
    for heading in headers:
        pair = _line_pair(text[heading.end():], permit_date=True)
        if pair:
            pairs.append(pair)
    # A subtotal pair inherits meaning only from the explicit supply/tax
    # column order above it. This is an aggregate, not one arbitrary line item.
    for subtotal in re.finditer(_label("소계") + r"[ \t]*[:：=]?", text):
        if not any(heading.end() <= subtotal.start() for heading in headers):
            continue
        pair = _line_pair(text[subtotal.end():])
        if pair:
            pairs.append(pair)
    return pairs


def _vat_basis(text):
    compact = re.sub(r"\s+", "", text)
    included = re.search(r"(?:부가가치세|부가세|VAT)(?:포함|포함된)", compact, re.I)
    excluded = re.search(r"(?:부가가치세|부가세|VAT)(?:미포함|불포함|제외|별도)", compact, re.I)
    return "TOTAL" if included and not excluded else "SUPPLY" if excluded and not included else "UNKNOWN"


def extract_reference_amount(text: str):
    """An explicit contract/document amount, without inventing its tax basis."""
    values = set()
    for label in _TOTAL_LABELS + _REFERENCE_LABELS:
        values.update(_direct_values(text, _label(label)))
    if len(values) == 1:
        return float(next(iter(values)))
    if values:
        return None
    # Unlabelled currency amounts are usable only when unambiguous. No bare
    # years, approval numbers, account numbers or quantities enter this path.
    for token in _TOKEN.finditer(text):
        if not (token.group("currency") or token.group("won")):
            continue
        value = _valid_token(token, text)
        if value is not None:
            values.add(value)
    return float(next(iter(values))) if len(values) == 1 else None


def extract_financial_fields(text: str, document_type=None):
    # Only explicit labels/ordered summary columns assign a tax meaning.
    # No default 10% tax and no item-table summation without layout evidence.
    result = {"supply_amount": None, "tax_amount": None, "total_amount": None,
              "amount_basis": "UNKNOWN", "amount_scope": "UNKNOWN"}
    candidates = {field: set() for field in ("supply_amount", "tax_amount", "total_amount")}
    candidates["supply_amount"].update(_direct_values(text, _SUPPLY))
    candidates["tax_amount"].update(_direct_values(text, _TAX))
    for supply, tax in _summary_pairs(text):
        candidates["supply_amount"].add(supply)
        candidates["tax_amount"].add(tax)
    for label in _TOTAL_LABELS:
        for heading in re.finditer(_label(label), text):
            line_start = text.rfind("\n", 0, heading.start()) + 1
            line_end = text.find("\n", heading.end())
            context = text[line_start:line_end if line_end >= 0 else len(text)]
            field = "supply_amount" if _vat_basis(context) == "SUPPLY" else "total_amount"
            # Preserve next-line labeled amounts while using the heading line
            # to distinguish explicit VAT-exclusive totals.
            candidates[field].update(_after_label_values(text[heading.end():]))
    basis = _vat_basis(text)
    for label in _REFERENCE_LABELS:
        for heading in re.finditer(_label(label), text):
            line_start = text.rfind("\n", 0, heading.start()) + 1
            line_end = text.find("\n", heading.end())
            context = text[line_start:line_end if line_end >= 0 else len(text)]
            context_basis = _vat_basis(context)
            if context_basis in {"TOTAL", "SUPPLY"}:
                field = "total_amount" if context_basis == "TOTAL" else "supply_amount"
                candidates[field].update(_direct_values(context, _label(label)))
    # Standard invoice totals put payment columns between the total heading
    # and its value. Only recognize the explicit four-column header sequence.
    payment_header = r"\s*".join(_label(label) for label in ("현금", "수표", "어음", "외상미수금"))
    for heading in re.finditer(_label("총합계금액") + r"\s*" + payment_header, text):
        tail = text[heading.end():]
        token = _TOKEN.match(tail)
        if token:
            value = _valid_token(token, tail)
            if value is not None:
                candidates["total_amount"].add(value)
    for field, values in candidates.items():
        if len(values) == 1:
            result[field] = float(next(iter(values)))
    if result["total_amount"] is not None:
        result["amount_basis"] = "TOTAL"
    elif result["supply_amount"] is not None:
        result["amount_basis"] = "SUPPLY"
    else:
        result["amount_basis"] = basis
    compact = re.sub(r"\s+", "", text)
    kind = getattr(document_type, "value", document_type)
    aggregate_document = kind in {"contract", "estimate", "inspection_confirmation"}
    if kind is None:
        aggregate_document = bool(re.search(r"계약서|견적서|검수확인서", compact[:250]))
    partial_claim = re.search(r"부분(?:청구|지급)|(?:착수금|중도금|선급금|선금|잔금)(?:정산)?청구(?:건|분)?", compact)
    if partial_claim and not aggregate_document:
        result["amount_scope"] = "PARTIAL"
    elif re.search(r"전액(?:청구|지급)|전체금액", compact) or (aggregate_document and result["total_amount"] is not None):
        result["amount_scope"] = "FULL"
    return result


def document_total(fields):
    total = money(fields.get("total_amount"))
    supply = money(fields.get("supply_amount"))
    tax = money(fields.get("tax_amount"))
    if total is not None:
        return total
    if supply is not None and tax is not None:
        return supply + tax
    if fields.get("amount_basis") == "TOTAL":
        return money(fields.get("amount"))
    return None
