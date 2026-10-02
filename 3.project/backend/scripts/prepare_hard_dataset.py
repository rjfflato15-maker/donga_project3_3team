"""Hard synthetic v2: predeclared gold, disjoint layouts, blind review bundles.

No app extraction, OCR, LLM or validation engine is used to author gold.
"""
import argparse
import copy
import json
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))
from backend.evaluation_core import DOCUMENT_TYPES, FIELDS, file_hash, verify_dataset
from backend.evaluation_review import blank_independent_labels, validate_reference_draft
from backend.prediction_artifacts import write_json
from backend.scripts.generate_evaluation_dataset import fictional_business_number, make_lines, check_slots, TITLES
from backend.scripts.build_reference_labels import reference_checks
from backend.scripts.package_independent_review import PROMPT

CONDITIONS = ("synonyms", "table", "skew", "stamp", "multi_page", "two_column")


def gold_fields(kind, vendor, number, supply, tax, total, date):
    fields = {field: {"state": "ABSENT", "value": None} for field in FIELDS}
    for field, value in (("company_name", vendor), ("business_registration_no", number), ("issue_date", date)):
        fields[field] = {"state": "VALUE", "value": value}
    if kind in {"contract", "estimate", "tax_invoice", "inspection_confirmation"}:
        for field, value in (("supply_amount", supply), ("tax_amount", tax), ("total_amount", total), ("amount_scope", "FULL")):
            fields[field] = {"state": "VALUE", "value": value}
    return fields


def plan():
    manifest = {"dataset_version": "synthetic-hard-v2", "created_for": "local-evaluation", "contracts": []}
    designs = {}
    for split_index, split in enumerate(("dev", "test"), 3):
        name = split + "2"
        for index, condition in enumerate(CONDITIONS, 1):
            cid = split_index * 100 + index
            vendor = f"가상 {'한결' if split == 'dev' else '새봄'}기획 {index}"
            buyer = f"가상 {'북쪽' if split == 'dev' else '남쪽'}연구소 {index}"
            number = fictional_business_number(cid)
            buyer_no = fictional_business_number(cid + 1200)
            supply = (17 + index + split_index * 3) * 137000
            tax, date = supply // 10, f"2026-09-{index + 15:02d}"
            total = supply + tax
            contract = {"contract_id": cid, "split": split, "corpus_split_name": name,
                        "condition": condition, "layout_family": name + "_" + condition,
                        "input": {"title": f"가상 {name} 시스템 구축 {index}", "vendor_name": vendor,
                                  "business_number": number, "contract_amount": total,
                                  "amount_policy": {"amount_basis": "TOTAL", "tax_amount": None, "payment_mode": "FULL"}},
                        "documents": []}
            for position, kind in enumerate(DOCUMENT_TYPES, 1):
                did = cid * 100 + position
                fields = gold_fields(kind, vendor, number, supply, tax, total, date)
                lines = make_lines(kind, vendor, buyer, number, buyer_no, supply, tax, total, date, "normal")
                target = kind == "estimate"
                if target and condition == "synonyms":
                    replacements = {"合計": "합계", "합계금액": "총 청구액" if split == "dev" else "청구 총액",
                                    "공급가액": "세전 대금", "세액": "부가세액"}
                    lines = [next((line.replace(a, b) for a, b in replacements.items() if a in line), line) for line in lines]
                if target and condition == "stamp":
                    fields["total_amount"] = {"state": "REVIEW", "value": None}
                document = {"document_id": did, "path": f"{name}/case_{index:02d}/document_{position:02d}.pdf",
                            "sha256": None}
                contract["documents"].append(document)
                designs[str(did)] = {"document_type": kind, "fields": fields, "lines": lines,
                                     "condition": condition if target else "normal", "split": split,
                                     "gold_policy": "Unreadable total is REVIEW; never reconstruct it from contract or arithmetic."}
            contract["check_slots"] = check_slots(contract["documents"], DOCUMENT_TYPES)
            manifest["contracts"].append(contract)
    return manifest, designs


def author_pdf(path, design, font_path):
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from PIL import Image
    from pypdf import PdfReader
    from backend.app.ai.pdf_runtime import open_pdf, open_page, render_page_image
    lines, condition, split = design["lines"], design["condition"], design["split"]
    with tempfile.TemporaryDirectory(prefix="hard-document-") as scratch:
        native = Path(scratch) / "native.pdf"
        canvas = Canvas(str(native), pagesize=A4, invariant=1)
        canvas.setTitle(lines[0])
        canvas.setAuthor("Synthetic hard v2")
        accent = (0.06, .27, .34) if split == "dev" else (.27, .12, .32)
        canvas.setFillColorRGB(*accent)
        if split == "dev":
            canvas.rect(40, 778, 515, 30, fill=1, stroke=0)
        else:
            canvas.rect(35, 738, 8, 70, fill=1, stroke=0)
        canvas.setFillColorRGB(1, 1, 1) if split == "dev" else canvas.setFillColorRGB(*accent)
        canvas.setFont("HardKorean", 16)
        canvas.drawString(52 if split == "dev" else 60, 786, lines[0])
        canvas.setFillColorRGB(0, 0, 0)
        canvas.setFont("HardKorean", 10)
        y = 745 if split == "dev" else 716
        total_box = None
        monetary = [line for line in lines[2:] if any(label in line for label in ("공급가액", "세액", "합계금액", "발행일"))]
        body = [line for line in lines[1:] if line not in monetary] if condition in {"table", "multi_page", "two_column"} else lines[1:]
        if condition == "two_column":
            # Party panels have independent reading order and repeated labels.
            supplier = ["공급자"] + [line for line in body if line.startswith(("상호:", "사업자등록번호:"))][:2]
            buyer = ["공급받는자"] + [line for line in body if line.startswith(("상호:", "사업자등록번호:"))][2:]
            for x, panel in ((52, supplier), (310, buyer)):
                py = y
                canvas.rect(x - 5, py - 100, 235, 115, fill=0, stroke=1)
                for line in panel:
                    canvas.drawString(x, py, line)
                    py -= 27
            y -= 155
        else:
            for line in body:
                if split == "test" and ": " in line:
                    label, value = line.split(": ", 1)
                    canvas.drawString(60, y, label)
                    canvas.drawRightString(520, y, value)
                    value_x = 370
                else:
                    canvas.drawString(52, y, line)
                    value_x = 130
                if line.startswith("합계금액:"):
                    prefix, value = line.split(": ", 1)
                    width = stringWidth(value, "HardKorean", 10)
                    value_x = 520 - width if split == "test" else 52 + stringWidth(prefix + ": ", "HardKorean", 10)
                    total_box = (value_x - 3, y - 5, width + 6, 19)
                y -= 24 if split == "dev" else 29
        if condition == "multi_page":
            canvas.drawString(52, 55, "금액 상세는 다음 쪽에 기재")
            canvas.showPage()
            canvas.setFont("HardKorean", 12)
            canvas.drawString(52, 780, "견적 금액 상세 - 전체 계약 대금")
            y = 732
        if condition == "table":
            canvas.setFont("HardKorean", 11)
            for row in monetary:
                label, value = row.split(": ", 1)
                canvas.rect(52, y - 9, 470, 30)
                canvas.line(265, y - 9, 265, y + 21)
                canvas.drawString(63, y, label)
                canvas.drawRightString(503, y, value)
                y -= 30
        elif condition in {"multi_page", "two_column"}:
            for row in monetary:
                canvas.drawString(52, y, row)
                y -= 28
        if condition == "stamp" and total_box:
            x, y0, width, height = total_box
            canvas.setFillColorRGB(.8, .13, .16)
            canvas.rect(x, y0, width, height, stroke=0, fill=1)
            canvas.setFillColorRGB(1, 1, 1)
            canvas.setFont("HardKorean", 10)
            canvas.drawString(x + 7, y0 + 5, "확 인 인")
        canvas.showPage()
        canvas.save()
        path.parent.mkdir(parents=True, exist_ok=True)
        if condition in {"skew", "stamp"}:
            with open_pdf(native) as pdf, open_page(pdf, 0) as page:
                image = render_page_image(page, 2.5)
            try:
                if condition == "skew":
                    image = image.rotate(2.1 if split == "dev" else -3.2, expand=False, fillcolor="white")
                scan = Path(scratch) / "scan.png"
                image.save(scan)
                target = Canvas(str(path), pagesize=A4, invariant=1)
                target.drawImage(str(scan), 0, 0, width=A4[0], height=A4[1])
                target.showPage()
                target.save()
            finally:
                image.close()
            if any(page.extract_text().strip() for page in PdfReader(path).pages):
                raise ValueError("SCANNED_FIXTURE_MUST_HAVE_NO_HIDDEN_TEXT")
        else:
            path.write_bytes(native.read_bytes())
            text = "\n".join(page.extract_text() for page in PdfReader(path).pages)
            for field, answer in design["fields"].items():
                if answer["state"] != "VALUE" or field == "amount_scope":
                    continue
                value = f"{answer['value']:,}" if field.endswith("amount") else str(answer["value"])
                if value not in text:
                    raise ValueError("DESIGN_VALUE_NOT_IN_INDEPENDENT_PDF_TEXT: " + field)


def blind_bundle(root, manifest, split, destination):
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "CLAUDE_PROMPT.md").write_text(PROMPT + "\n스캔에서 가려져 읽을 수 없는 값은 REVIEW입니다. 등록 금액이나 산술로 복원하지 마세요.\n", encoding="utf-8")
    (destination / "LABELING_GUIDE.md").write_bytes((PROJECT / "eval/LABELING_GUIDE.md").read_bytes())
    for position, contract in enumerate((row for row in manifest["contracts"] if row["split"] == split), 1):
        folder = destination / f"case_{position:02d}"
        folder.mkdir()
        docs = []
        for document in contract["documents"]:
            name = Path(document["path"]).name
            (folder / name).write_bytes((root / document["path"]).read_bytes())
            docs.append({**document, "path": name})
        write_json(folder / "registered_contract.json", {"dataset_version": manifest["dataset_version"], "split": split,
                   "contract_id": contract["contract_id"], "input": contract["input"], "documents": docs})
        write_json(folder / "reply_template.json", blank_independent_labels(manifest, [contract]))
    write_json(destination / "package_receipt.json", {"dataset_version": manifest["dataset_version"], "split": split,
               "files": {path.relative_to(destination).as_posix(): file_hash(path) for path in destination.rglob("*") if path.is_file()},
               "contains_reference_answers": False, "contains_app_predictions": False, "review_completed": False})
    (destination / "replies").mkdir()
    with zipfile.ZipFile(destination.with_suffix(".zip"), "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in destination.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(destination).as_posix())


def generate(root, font):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    if root.exists():
        raise ValueError("HARD_DATASET_EXISTS; never overwrite gold or heldout files")
    root.mkdir(parents=True)
    pdfmetrics.registerFont(TTFont("HardKorean", str(font)))
    manifest, designs = plan()
    # Commit the complete intended field answers BEFORE creating any document or prediction.
    write_json(root / "predeclared_design.json", {"declared_at": datetime.now(timezone.utc).isoformat(),
               "documents": designs, "used_app_predictions": False})
    for contract in manifest["contracts"]:
        for document in contract["documents"]:
            path = root / document["path"]
            author_pdf(path, designs[str(document["document_id"])], font)
            document["sha256"] = file_hash(path)
    write_json(root / "manifest.json", manifest)
    verify_dataset(root, manifest)
    for split in ("dev", "test"):
        draft = {"dataset_version": manifest["dataset_version"], "split": split,
                 "reference_version": "hard-design-v2", "review": {"confirmed": False,
                 "reviewer_type": "source_reference", "author": "Codex", "created_at": datetime.now(timezone.utc).isoformat(),
                 "human_reviewed": False, "claude_reviewed": False}, "documents": {}, "contracts": {}}
        for contract in (row for row in manifest["contracts"] if row["split"] == split):
            rows = {}
            for document in contract["documents"]:
                did = str(document["document_id"])
                rows[did] = {"document_type": designs[did]["document_type"], "fields": designs[did]["fields"]}
                draft["documents"][did] = {**rows[did], "source_checked": True, "reviewed": False,
                    "source_check_method": "independent_pdf_text_or_raster_design; human_visual_pending", "source_sha256": document["sha256"]}
            missing, checks = reference_checks(contract, rows)
            draft["contracts"][str(contract["contract_id"])] = {"source_checked": True, "reviewed": False,
                                                                 "missing_types": missing, "checks": checks}
        validate_reference_draft(manifest, draft, split)
        reference = root / f"reference_labels_{split}.json"
        write_json(reference, draft)
        write_json(reference.with_suffix(".freeze.json"), {"labels_sha256": file_hash(reference),
                   "manifest_sha256": file_hash(root / "manifest.json"), "human_confirmed": False,
                   "predeclared_design_sha256": file_hash(root / "predeclared_design.json")})
        write_json(root / f"ground_truth_{split}.json", {"dataset_version": manifest["dataset_version"], "split": split,
                   "review": {"confirmed": False}, "documents": {}, "contracts": {}})
        blind_bundle(root, manifest, split, root.parent / ("claude_blind_review_" + split + "2"))
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=PROJECT / "eval/dataset-v2")
    parser.add_argument("--font", type=Path, default=Path("C:/Windows/Fonts/malgun.ttf"))
    args = parser.parse_args()
    manifest = generate(args.output, args.font)
    print(f"hard v2 정답 초안·독립 판독 묶음 준비: 계약 {len(manifest['contracts'])}개, PDF 72개. 모델 실행·사람 확정 없음.")


if __name__ == "__main__":
    main()
