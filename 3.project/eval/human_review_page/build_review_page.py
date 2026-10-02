# -*- coding: utf-8 -*-
"""Build a click-through human review page from human_review.xlsx (items) + originals."""
import datetime, json, os, re, zipfile
from xml.etree import ElementTree as ET

PROJ = r"C:\3조 색인\3.project"
PAGE_DIR = os.path.join(PROJ, "eval", "human_review_page")
RAW = os.path.join(PAGE_DIR, "_items_raw.json")
BLIND = os.path.join(PROJ, "eval", "claude_blind_review")
DEV = os.path.join(PROJ, "eval", "dataset", "dev")

TYPE_KO = {"contract": "외주용역 계약서", "estimate": "견적서", "business_registration": "사업자등록증",
           "bank_account": "통장사본", "tax_invoice": "전자세금계산서", "inspection_confirmation": "납품 검수확인서"}
FIELD_KO = {"supply_amount": "공급가액", "tax_amount": "세액", "total_amount": "합계금액",
            "issue_date": "발행일", "company_name": "상호", "business_registration_no": "사업자등록번호"}

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
def docx_lines(path):
    root = ET.fromstring(zipfile.ZipFile(path).read("word/document.xml"))
    out = []
    for el in root.find(W + "body"):
        if el.tag == W + "p":
            t = "".join(x.text or "" for x in el.iter(W + "t"))
            if t.strip(): out.append(t)
        elif el.tag == W + "tbl":
            for tr in el.iter(W + "tr"):
                out.append(" | ".join("".join(x.text or "" for x in tc.iter(W + "t")) for tc in tr.findall(W + "tc")))
    return out

def make_views(path, stem):
    """Crop page images to the text area so the text displays large on a laptop screen."""
    import io, pymupdf
    from PIL import Image
    vdir = os.path.join(PAGE_DIR, "views"); os.makedirs(vdir, exist_ok=True)
    if path.endswith(".pdf"):
        imgs = [Image.open(io.BytesIO(pg.get_pixmap(dpi=200).tobytes("png"))) for pg in pymupdf.open(path)]
    else:
        imgs = [Image.open(path)]
    out = []
    for n, im in enumerate(imgs):
        im = im.convert("RGB")
        mask = im.convert("L").point(lambda v: 255 if v < 170 else 0)
        box = mask.getbbox() or (0, 0, im.width, im.height)
        m = int(im.width * 0.03)
        box = (max(0, box[0]-m), max(0, box[1]-m), min(im.width, box[2]+m), min(im.height, box[3]+m))
        name = f"{stem}_p{n+1}.png"
        im.crop(box).save(os.path.join(vdir, name))
        out.append("views/" + name)
    return out

def won(v): return f"{int(v):,}원"
def excel_date(v):
    try:
        n = int(float(v))
        if 40000 < n < 60000:
            return (datetime.date(1899, 12, 30) + datetime.timedelta(days=n)).isoformat()
    except (TypeError, ValueError):
        pass
    return v

# ---- per-case context ----
cases = {}
for c in range(1, 11):
    cdir = f"case_{c:02d}"
    rc = json.load(open(os.path.join(BLIND, cdir, "registered_contract.json"), encoding="utf-8"))
    rep = json.load(open(os.path.join(BLIND, "replies", cdir + ".json"), encoding="utf-8"))
    inp = rc["input"]; pol = inp["amount_policy"]
    cmp_total = inp["contract_amount"] + (pol["tax_amount"] or 0) if pol["amount_basis"] == "SUPPLY" else inp["contract_amount"]
    docs = []
    for d in rc["documents"]:
        p = d["path"]; ext = p.rsplit(".", 1)[1]
        entry = {"id": str(d["document_id"]), "src": f"../dataset/dev/{cdir}/{p}", "ext": ext, "name": p,
                 "type": TYPE_KO.get(rep["documents"][str(d["document_id"])]["document_type"], "")}
        if ext == "docx":
            entry["lines"] = docx_lines(os.path.join(DEV, cdir, p))
        if ext in ("pdf", "png"):
            entry["views"] = make_views(os.path.join(DEV, cdir, p), f"{cdir}_{p.rsplit('.',1)[0]}")
        docs.append(entry)
    basis = ("공급가액 기준 %s + 등록 세액 %s = 비교 합계 %s" % (won(inp["contract_amount"]), won(pol["tax_amount"]), won(cmp_total))
             if pol["amount_basis"] == "SUPPLY" else "합계 기준 %s" % won(inp["contract_amount"]))
    cases[str(rc["contract_id"])] = {
        "case": cdir, "vendor": inp["vendor_name"], "bno": inp["business_number"], "basis": basis,
        "cmp": cmp_total, "pay": "분할 지급" if pol["payment_mode"] == "INSTALLMENT" else "일시(전액) 지급",
        "docs": docs, "doctype": {d["id"]: d["type"] for d in docs}}

# ---- questions: "정답 초안이 하는 말" + 볼 곳 + (필요 시) 기준 ----
def Q(claim, rule=None):
    html = '<div class="claimlbl">정답 초안</div><div class="claim">' + claim + '</div>'
    if rule:
        html += '<div class="interp">📌 기준: ' + rule + '</div>'
    return html

def field_q(it, ctx, doc_id, field):
    st, val = it["I"], it.get("J")
    dtype = ctx["doctype"].get(doc_id, "")
    if field == "document_type":
        return Q(f"이 문서는 <b>{TYPE_KO.get(val, val)}</b>다."), "문서 맨 위 제목을 보세요."
    if field == "amount_scope":
        if st == "VALUE" and val == "FULL":
            if dtype == "납품 검수확인서":
                return (Q("이 문서의 금액은 <b>계약 전체 금액</b>이다.",
                          "검수확인서는 청구서가 아니지만, 계약 전체 금액이 적혀 있으면 '전체 금액'으로 봅니다. "
                          "이 기준이 괜찮으면 <b>맞아요</b>. '청구서가 아니니까 해당 없음으로 해야 한다'고 생각하면 <b>아니에요</b>."),
                        "합계금액 줄을 보고, '선금'·'잔금'·'분할' 같은 말이 없는지 보세요.")
            return Q("이 문서의 금액은 <b>계약 전체 금액</b>이다. ('선금·잔금' 같은 일부가 아님)"), "합계금액 줄과 '전액 청구'·'분할 청구' 문구를 보세요."
        if st == "VALUE" and val == "PARTIAL":
            return Q("이 문서의 금액은 <b>일부(선금·잔금 등)</b>다."), "'분할 청구' 문구를 보세요."
        if st == "ABSENT":
            return Q("이 문서에는 <b>금액이 없다</b>."), "금액 줄이 있는지만 보세요."
        return (Q("금액이 전체인지 일부인지 <b>알 수 없다 → 판단 보류</b>.",
                  "'금액의 적용 범위가 표시되지 않음'이라고 적혀 있으면, 견적서라도 '전체'로 추측하지 않습니다. "
                  "그 문구가 원문에 있으면 <b>맞아요</b>."),
                "'금액의 적용 범위가 표시되지 않음' 문구를 찾아보세요.")
    label = FIELD_KO[field]
    if field == "company_name" and st == "VALUE":
        who = {"통장사본": "예금주", "외주용역 계약서": "수급인(을)", "납품 검수확인서": "계약상대자"}.get(dtype, "공급자 상호")
        return Q(f"{who}는 <b>{val}</b>다."), ("'공급받는자'가 아니라 '공급자' 아래 상호를 보세요." if who == "공급자 상호" else f"'{who}' 줄을 보세요.")
    if field == "business_registration_no" and st == "VALUE":
        hint = "'공급받는자'가 아니라 '공급자' 아래 번호를 보세요." if dtype in ("견적서", "전자세금계산서") else "'사업자등록번호' 줄을 보세요."
        return Q(f"사업자등록번호는 <b>{val}</b>다."), hint + " 숫자를 하나씩 비교하세요."
    if field == "issue_date" and st == "VALUE":
        return Q(f"발행일은 <b>{excel_date(val)}</b>다."), "'발행일' 줄을 보세요."
    if field in ("supply_amount", "tax_amount", "total_amount"):
        if st == "VALUE":
            return Q(f"{label}은 <b>{won(val)}</b>이다."), f"'{label}' 줄의 숫자를 보세요."
        if st == "ABSENT":
            return Q(f"이 문서에는 <b>'{label}' 항목이 없다</b>."), "금액 줄이 있는지 보세요."
        return (Q(f"'{label}'이라는 이름의 금액이 없다 → <b>판단 보류</b>.",
                  "'참고값 A/B'처럼 이름 없는 숫자는 계산으로 짐작되더라도 추측해서 넣지 않습니다. "
                  f"원문에 '{label}'이라는 글자가 없으면 <b>맞아요</b>."),
                "금액 줄 앞의 이름(라벨)을 보세요.")
    return Q(f"{label}: {st} {val}"), ""

def check_q(it, ctx, rule, target):
    st = it["I"]; val = it.get("J")
    dtype = ctx["doctype"].get(target, "")
    if rule == "missing_types":
        miss = json.loads(val) if val else []
        if miss:
            return (Q(f"빠진 서류는 <b>{', '.join(TYPE_KO[m] for m in miss)}</b>다. (나머지는 제출됨)"),
                    "왼쪽 위 문서 버튼 목록을 보세요. 6종: 계약서·견적서·사업자등록증·통장사본·세금계산서·검수확인서")
        return Q("6종 서류가 <b>모두 제출됐다</b>."), "왼쪽 위 문서 버튼이 6종(계약서·견적서·사업자등록증·통장사본·세금계산서·검수확인서)인지 보세요."
    if rule == "BUSINESS_STATUS":
        return (Q("실제로 영업 중인 사업자인지는 <b>판단 보류</b>.",
                  "이 평가는 국세청 조회를 하지 않으므로 항상 '판단 보류'로 둡니다. 원문은 안 봐도 되고, 이 기준에 동의하면 <b>맞아요</b>."),
                "")
    if rule == "ORIGINAL_FILE":
        return Q("이 파일은 <b>정상적으로 열린다</b>."), "왼쪽에 문서가 보이면 맞아요."
    if rule == "DOCUMENT_TYPE":
        return Q(f"제목을 보면 <b>무슨 문서인지 알 수 있다</b>. ({dtype})"), "제목을 보세요."
    if rule == "DOCUMENT_PROCESSING":
        return Q("글자가 <b>깨끗해서 읽을 수 있다</b>."), "흐리거나 깨진 곳이 있는지 보세요."
    if rule == "BUSINESS_NO_MATCH":
        if target == "business_registration_no":
            return Q("사업자번호를 대조할 서류(계약서·견적서·세금계산서·사업자등록증)가 <b>있다</b>."), "왼쪽 위 문서 버튼 목록을 보세요."
        return (Q(f"문서의 공급자 사업자번호가 등록 번호 <b>{ctx['bno']}와 같다</b>."),
                "오른쪽 위 '등록 계약' 상자의 번호와 비교하세요." + (" '공급받는자' 번호 말고 '공급자' 번호예요." if dtype in ("견적서", "전자세금계산서") else ""))
    if rule == "AMOUNT_COMPONENTS":
        if st == "FAIL":
            return Q("공급가액 + 세액이 합계금액과 <b>다르다 → 계산이 틀렸다</b>."), "2,000,000 + 200,000 = 2,200,000인데, 합계 줄에 뭐라고 적혀 있는지 보세요."
        return Q("공급가액 + 세액 = 합계금액, <b>계산이 맞다</b>."), "세 줄의 숫자를 더해 보세요."
    if rule == "AMOUNT_EXTRACTION":
        if st == "REVIEW":
            return (Q("금액 이름이 '참고값'뿐이라 <b>공급가액·세액·합계를 확정할 수 없다 → 판단 보류</b>.",
                      "이름 없는 숫자는 계산으로 짐작되더라도 추측해서 넣지 않습니다. 원문 금액 이름이 '참고값'이면 <b>맞아요</b>."),
                    "금액 줄 앞의 이름(라벨)을 보세요.")
        return Q("'합계금액'이라는 이름과 함께 금액이 <b>분명히 적혀 있다</b>."), "합계금액 줄을 보세요."
    if rule == "AMOUNT_MATCH_ESTIMATE":
        return Q(f"견적서 합계금액이 계약 금액 {won(ctx['cmp'])}과 <b>{'같다' if st == 'PASS' else '다르다'}</b>."), "합계금액 줄을 보세요."
    if rule == "AMOUNT_MATCH_TAX_INVOICE":
        if st == "FAIL":
            return (Q(f"세금계산서 합계금액이 계약 금액 {won(ctx['cmp'])}과 <b>다르다 → 불일치</b>.",
                      "'전액 청구'라고 적혀 있으니 '판단 보류'가 아니라 '불일치'로 봅니다. 원문에 '전액 청구'가 있고 합계가 다르면 <b>맞아요</b>."),
                    "합계금액 줄과 '전액 청구' 줄을 보세요.")
        return Q(f"세금계산서 합계금액이 계약 금액 {won(ctx['cmp'])}과 <b>같다</b>."), "합계금액 줄을 보세요."
    if rule == "AMOUNT_BASIS":
        return Q(f"등록 계약의 금액 기준이 <b>분명하다</b>. ({ctx['basis']})"), "오른쪽 위 '등록 계약' 상자를 보세요."
    if rule == "REQUIRED_DOCUMENTS":
        return Q(f"<b>{TYPE_KO.get(target, target)}</b>이 제출되어 있다."), "왼쪽 위 문서 버튼 목록을 보세요."
    if rule == "PAYMENT_SCOPE":
        if target == "tax_invoice":
            return Q(f"이 계약은 <b>{ctx['pay']}</b>이라 분할 청구 경고가 필요 없다."), "오른쪽 위 '등록 계약' 상자의 지급 방식을 보세요."
        return Q("이 세금계산서에 <b>'전액 청구'</b>라고 적혀 있다."), "'전액 청구' 줄을 보세요."
    return Q(f"{rule} {target}: {st}"), ""

items = json.load(open(RAW, encoding="utf-8"))
out = []
for it in items:
    parts = it["A"].split("/")
    cid = parts[0]; ctx = cases[cid]
    if it["sheet"] == "필드확인":
        doc_id, field = parts[1], parts[2]
        q, hint = field_q(it, ctx, doc_id, field)
        kind = "field"
    else:
        doc_id = None
        if parts[2] == "missing_types":
            rule, target = "missing_types", None
        else:
            rule, target = parts[2], parts[3]
            if target.isdigit(): doc_id = target
        q, hint = check_q(it, ctx, rule, target)
        kind = "check"
    val = it.get("J")
    shown = excel_date(val) if val else ""
    out.append({"key": f"{it['sheet']}!{it['row']}", "sheet": it["sheet"], "row": it["row"], "id": it["A"],
                "cid": cid, "doc": doc_id, "label": it["C"], "q": q, "hint": hint,
                "important": it["H"] != "일치 표본", "reason_tag": it["H"],
                "excel": f"{it['I']}" + (f" / {shown}" if shown else ""),
                "kind": kind})

def sort_key(x):
    first_doc = x["doc"] or "0"
    if x["important"]:
        pri = 2 if "BUSINESS_STATUS" in x["id"] else (1 if x["label"].startswith("검수확인서") else 0)
        return (0, pri, x["cid"], first_doc, x["row"])
    return (1, 0, x["cid"], first_doc, x["row"])
out.sort(key=sort_key)

data = {"generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "source_xlsx": "outputs/01a0f640-7f7a-7eb1-8eb2-bb5a189f1850/human_review.xlsx",
        "cases": cases, "items": out}
tpl = open(os.path.join(os.path.dirname(__file__), "review_page_template.html"), encoding="utf-8").read()
html = tpl.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False))
open(os.path.join(PAGE_DIR, "index.html"), "w", encoding="utf-8").write(html)
print("items", len(out), "important", sum(x["important"] for x in out))
