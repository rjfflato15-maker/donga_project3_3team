# -*- coding: utf-8 -*-
"""Build a click-through human review page from human_review.xlsx (items) + originals."""
import argparse, datetime, json, os, re, sys, tempfile, zipfile
from pathlib import Path
from html import escape
from xml.etree import ElementTree as ET

PROJ = str(Path(__file__).resolve().parents[2])
sys.path.insert(0, PROJ)
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
    from backend.app.ai.pdf_runtime import open_pdf, open_page, page_count, render_page_image
    from PIL import Image
    vdir = os.path.join(PAGE_DIR, "views"); os.makedirs(vdir, exist_ok=True)
    if path.endswith(".pdf"):
        imgs = []
        with open_pdf(path) as pdf:
            for index in range(page_count(pdf)):
                with open_page(pdf, index) as page:
                    imgs.append(render_page_image(page, 200 / 72))
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
        # Publish a complete new image rather than truncating a preview that
        # a browser or Windows indexer may still have open.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=vdir, suffix=".png", delete=False) as stream:
                temporary = stream.name
                im.crop(box).save(stream, format="PNG")
            os.replace(temporary, os.path.join(vdir, name))
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
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
def load_cases(reference):
    cases = {}
    for cdir in sorted(name for name in os.listdir(BLIND) if name.startswith("case_") and os.path.isdir(os.path.join(BLIND, name))):
        rc = json.load(open(os.path.join(BLIND, cdir, "registered_contract.json"), encoding="utf-8"))
        rep = reference
        inp = rc["input"]; pol = inp["amount_policy"]
        cmp_total = inp["contract_amount"] + (pol["tax_amount"] or 0) if pol["amount_basis"] == "SUPPLY" else inp["contract_amount"]
        docs = []
        for d in rc["documents"]:
            p = d["path"]; ext = p.rsplit(".", 1)[1]
            entry = {"id": str(d["document_id"]), "src": Path(os.path.relpath(os.path.join(DEV, cdir, p), PAGE_DIR)).as_posix(), "ext": ext, "name": p,
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
            "docs": docs, "doctype": {d["id"]: d["type"] for d in docs},
            "fields": {d["id"]: reference["documents"][d["id"]]["fields"] for d in docs}}
    return cases

# ---- questions: "정답 초안이 하는 말" + 볼 곳 + (필요 시) 기준 ----
def Q(claim, rule=None):
    html = '<div class="claimlbl">정답 초안:</div><div class="claim">' + claim + '</div>'
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
            return (Q("이 문서의 금액은 <b>일부(선금·잔금 등)</b>다.",
                      "'분할 청구 선금 또는 잔금'이면 선금인지 잔금인지 몰라도 일부 청구입니다. 그 문구가 있으면 <b>맞아요</b>."),
                    "'분할 청구'·'선금 또는 잔금' 문구를 보세요.")
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
    if st == "N/A" and rule in {"AMOUNT_MATCH_ESTIMATE", "AMOUNT_MATCH_TAX_INVOICE"}:
        expected_type = "견적서" if rule == "AMOUNT_MATCH_ESTIMATE" else "전자세금계산서"
        if dtype != expected_type:
            return (Q(f"이 문서는 {dtype}이므로 <b>{expected_type} 금액 대조의 대상이 아니다</b>.",
                      "계약서·검수확인서에 금액이 있어도 문서 종류가 다르면 이 검사는 적용하지 않습니다. 문서 제목이 맞으면 <b>맞아요</b>."),
                    "문서 제목을 보세요. '대상 아님'은 '읽지 못함'과 달라요.")
        if ctx["pay"] == "분할 지급" and rule == "AMOUNT_MATCH_TAX_INVOICE":
            return (Q("분할 청구를 계약 전체 금액과 <b>건별로 비교하지 않는다</b>.",
                      "분할 지급에서는 청구 금액을 합쳐 비교합니다. 일부 청구라면 <b>맞아요</b>."), "지급 방식과 '분할 청구' 문구를 보세요.")
        return (Q("금액을 확정할 수 없어 <b>일치·불일치 대조는 하지 않는다</b>.",
                  "참고값을 임의로 합계로 정하지 않습니다. 금액 뜻이 모호하면 <b>맞아요</b>."), "금액 이름과 적용 범위 문구를 보세요.")
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
        if st == "N/A":
            return Q(f"{dtype}은 <b>사업자번호 대조 검사의 대상이 아니다</b>."), "이 검사는 계약서·견적서·세금계산서·사업자등록증에 적용해요. 문서 제목을 보세요."
        return (Q(f"문서의 공급자 사업자번호가 등록 번호 <b>{ctx['bno']}와 {'다르다' if st == 'FAIL' else '같다'}</b>."),
                "오른쪽 위 '등록 계약' 상자의 번호와 비교하세요." + (" '공급받는자' 번호 말고 '공급자' 번호예요." if dtype in ("견적서", "전자세금계산서") else ""))
    if rule == "AMOUNT_COMPONENTS":
        values = ctx.get("fields", {}).get(target, {})
        if st == "N/A" and any(values.get(k, {}).get("state") != "VALUE" for k in ("supply_amount", "tax_amount", "total_amount")):
            return Q("세 금액이 모두 있는 문서가 아니므로 <b>금액 계산 오류 검사를 적용하지 않는다</b>."), "공급가액·세액·합계 세 항목이 모두 적혀 있는지 보세요."
        if st == "FAIL":
            supply = values.get("supply_amount", {}).get("value")
            tax = values.get("tax_amount", {}).get("value")
            hint = (f"{won(supply)} + {won(tax)} = {won(int(supply) + int(tax))}인데, 합계 줄의 숫자와 비교하세요."
                    if supply is not None and tax is not None else "공급가액과 세액을 더한 값이 합계 줄과 다른지 보세요.")
            return Q("공급가액 + 세액이 합계금액과 <b>다르다 → 계산이 틀렸다</b>."), hint
        return Q("공급가액 + 세액 = 합계금액, <b>계산이 맞다</b>."), "세 줄의 숫자를 더해 보세요."
    if rule == "AMOUNT_EXTRACTION":
        if st == "N/A" and dtype in ("통장사본", "사업자등록증"):
            return Q(f"{dtype}은 <b>금액 추출 검사의 대상이 아니다</b>."), "청구 금액을 비교하는 증빙이 아닌지 문서 제목을 보세요."
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
        return Q(f"<b>{TYPE_KO.get(target, target)}</b>이 {'빠져 있다' if st == 'MISSING' else '제출되어 있다'}."), "왼쪽 위 문서 버튼 목록을 보세요."
    if rule == "INSTALLMENT_TOTAL":
        if st == "N/A":
            return Q("이 계약은 일시 지급이므로 <b>분할 청구 합계 검사를 적용하지 않는다</b>."), "등록 계약의 지급 방식이 '일시(전액) 지급'인지 보세요."
        return (Q(f"분할 청구 금액을 모두 더하면 계약 금액 {won(ctx['cmp'])}과 <b>{'같다' if st == 'PASS' else '다르다'}</b>."),
                "세금계산서 두 장의 합계금액을 더해 등록 계약 금액과 비교하세요.")
    if rule == "DUPLICATE_INVOICE":
        return Q("분할 청구에 <b>같은 세금계산서가 중복으로 들어 있지 않다</b>."), "세금계산서 금액·내용과 파일을 비교하세요."
    if rule == "PAYMENT_SCOPE":
        if target == "tax_invoice":
            return Q(f"이 계약은 <b>{ctx['pay']}</b>이라 분할 청구 경고가 필요 없다."), "오른쪽 위 '등록 계약' 상자의 지급 방식을 보세요."
        if dtype != "전자세금계산서":
            return Q(f"{dtype}은 <b>세금계산서 청구 범위 검사의 대상이 아니다</b>."), "문서 제목을 보세요."
        if ctx["pay"] == "분할 지급":
            return Q("분할 지급 계약의 일부 청구라 <b>전액 지급 경고가 필요 없다</b>."), "등록 지급 방식과 세금계산서의 '분할 청구' 문구를 보세요."
        return Q("이 세금계산서에 <b>'전액 청구'</b>라고 적혀 있다."), "'전액 청구' 줄을 보세요."
    return Q(f"{rule} {target}: {st}"), ""

def make_items(items, cases):
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
        note = it.get('M')
        if note:
            q = re.sub(r'<div class="interp">.*?</div>', '', q, flags=re.S)
            q += '<div class="interp">📌 기준: ' + escape(note) + ' 이 기준대로면 <b>맞아요</b>.</div>'
        elif '📌 기준:' not in q:
            q += '<div class="interp">📌 기준: ' + escape(hint or "원문과 등록 계약을 비교하세요.") + ' 설명대로면 <b>맞아요</b>.</div>'
        val = it.get("J")
        shown = excel_date(val) if val else ""
        out.append({"key": f"{it['sheet']}!{it['row']}", "sheet": it["sheet"], "row": it["row"], "id": it["A"],
                    "cid": cid, "doc": doc_id, "label": it["C"], "q": q, "hint": hint,
                    "important": it["H"] != "일치 표본", "reason_tag": it["H"],
                    "excel": f"{it['I']}" + (f" / {shown}" if shown else ""),
                    "kind": kind})
    out.sort(key=sort_key)
    return out

def sort_key(x):
    first_doc = x["doc"] or "0"
    if x["important"]:
        pri = 2 if "BUSINESS_STATUS" in x["id"] else (1 if x["label"].startswith("검수확인서") else 0)
        return (0, pri, x["cid"], first_doc, x["row"])
    return (1, 0, x["cid"], first_doc, x["row"])
def build_page(*, split="dev", dataset=None, blind=None, output=None, workbook=None):
    global PAGE_DIR, BLIND, DEV, RAW
    dataset = Path(dataset or Path(PROJ)/"eval/dataset").resolve()
    BLIND = str(Path(blind or Path(PROJ)/("eval/claude_blind_review" + ("_test" if split == "test" else ""))).resolve())
    PAGE_DIR = str(Path(output or Path(PROJ)/("eval/human_review_page" + ("_test" if split == "test" else ""))).resolve())
    DEV = str(dataset/split)
    Path(PAGE_DIR).mkdir(parents=True, exist_ok=True)
    reference = json.loads((dataset/f"reference_labels_{split}.json").read_text(encoding="utf-8"))
    cases = load_cases(reference)
    items = []
    if workbook:
        import openpyxl
        book = openpyxl.load_workbook(workbook,read_only=True,data_only=False)
        try:
            for name in ("필드확인", "검수확인"):
                for n, row in enumerate(book[name].iter_rows(min_row=5,values_only=True),5):
                    if row[0] is not None:
                        items.append({**{chr(65+i): value for i,value in enumerate(row[:13])}, "sheet":name,"row":n})
        finally:
            book.close()
    out = make_items(items,cases)
    from hashlib import sha256
    data = {"generated":datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(timespec="seconds"),
            "split":split, "ready":bool(workbook), "cases":cases, "items":out,
            "source_xlsx":Path(os.path.relpath(workbook,PROJ)).as_posix() if workbook else None,
            "source_xlsx_sha256":sha256(Path(workbook).read_bytes()).hexdigest() if workbook else None}
    tpl = Path(__file__).with_name("review_page_template.html").read_text(encoding="utf-8")
    html = tpl.replace("/*__DATA__*/null",json.dumps(data,ensure_ascii=False).replace("<","\\u003c"))
    Path(PAGE_DIR,"index.html").write_text(html,encoding="utf-8",newline="\n")
    return data


def main():
    parser=argparse.ArgumentParser(description="기존 원문 확인 화면으로 dev/test 검수 페이지 생성")
    parser.add_argument("--split",choices=["dev","test"],default="dev")
    parser.add_argument("--dataset",type=Path)
    parser.add_argument("--blind",type=Path)
    parser.add_argument("--output",type=Path)
    parser.add_argument("--workbook",type=Path)
    args=parser.parse_args()
    data=build_page(split=args.split,dataset=args.dataset,blind=args.blind,output=args.output,workbook=args.workbook)
    print("검수 페이지:",args.split,"확인 목록",len(data["items"]),"칸 /", "사람 확인 대기" if data["ready"] else "Claude 독립 판독 대기; 확정 불가")


if __name__ == "__main__":
    main()
