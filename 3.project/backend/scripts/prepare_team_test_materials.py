"""Build Tuesday usability materials from the DEV linear template only.

Does not import the app, open an evaluation manifest, or run any model/guard.
Participant archives are an explicit allowlist; answers and replies stay separate.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))
from backend.scripts.generate_evaluation_dataset import (
    DOCUMENT_TYPES, fictional_business_number, make_lines, write_pdf,
)

BUNDLE = PROJECT / "sample-data/team-test-dev-v1"
VERSION = "team-test-dev-v1"
CASES = {
    "practice": ("연습", 1100000, 701, None),
    "task_1_A": ("과제 1 · A", 2100000, 702, "missing"),
    "task_1_B": ("과제 1 · B", 2300000, 703, "missing"),
    "task_2_A": ("과제 2 · A", 3100000, 704, "reissue"),
    "task_2_B": ("과제 2 · B", 3300000, 705, "reissue"),
}
RULES = """# 업무 기준표 (모든 과제·방식에 동일)

필수 서류: 외주용역 계약서, 견적서, 사업자등록증, 통장사본, 전자세금계산서, 납품 검수확인서.
계약서·검수확인서는 회사 내부 서류이며 나머지 네 종류는 거래처에게 받습니다.
등록 계약 정보표의 사업자번호는 거래처(공급자) 번호입니다. 공급받는자 번호와 혼동하지 마세요.
등록 금액은 세금 포함 총액이며 일시(전액) 지급입니다. 견적서·세금계산서 합계와 비교합니다.
공급가액과 세액의 합도 확인합니다. 국세청 조회는 미연동이며 이번 처리 대상이 아닙니다.
이 자료는 가상 자료입니다. 실제 연락·송금은 하지 않습니다.

연락 방법은 카카오톡, 회신 기한은 2026-10-08로 기록하세요(모든 과제 동일).
요청할 대상·서류·이유를 적고 회신 대기로 기록합니다. 올바른 요청이면 진행자가 준비한 회신을 줍니다.
회신을 받으면 이전 파일을 보존하고 새 파일을 현재본으로 구분한 뒤 결과를 다시 확인합니다.
마지막에 대표에게 전달할 한 줄을 남깁니다. 대표의 최종 결재는 시간 과제에 포함하지 않습니다.
파일 열기·업로드부터 기록까지 재며, 과제 하나·방식 하나당 10분입니다.
앱에서도 제공받은 원문을 직접 업로드합니다. 로그인·비밀번호 변경은 시작 전에 끝냅니다.
"""
RECORD_COLUMNS = ["과제", "자료", "확인 결과", "근거 서류와 내용", "요청 대상", "요청 문구",
                  "연락 방법", "요청일", "회신 기한", "처리 상태", "회신 메모",
                  "이전본 경로", "현재본 경로", "대표에게 전달할 한 줄"]


def save_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def participant_files(folder):
    """Never include arbitrary recursively discovered files (including an answer)."""
    names = ["registered_contract.json", "registered_contract.pdf", "business_rules.md", "blank_record.csv"]
    return [folder / n for n in names] + sorted((folder / "originals").glob("document_??.pdf"))


def archive_participant(folder, output):
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        for path in participant_files(folder):
            z.write(path, path.relative_to(folder).as_posix())


def build(output=BUNDLE, font=Path("C:/Windows/Fonts/malgun.ttf")):
    output = Path(output).resolve()
    allowed = (PROJECT / "sample-data").resolve()
    if output == allowed or not output.is_relative_to(allowed) or output.exists():
        raise ValueError("sample-data 아래의 새 폴더만 사용합니다. 기존 자료는 덮어쓰지 않습니다.")
    if not font.is_file():
        raise ValueError("한글 폰트가 필요합니다.")
    # Read only DEV originals for provenance. Never open the mixed dev/test manifest.
    dev = PROJECT / "eval/dataset/dev/case_01"
    source_hashes = {p.relative_to(PROJECT).as_posix(): sha256(p) for p in sorted(dev.glob("document_*"))}
    if len(source_hashes) != 6:
        raise ValueError("dev 기본 사례의 6개 원문 출처를 확인할 수 없습니다.")
    guide_path = "3.project/docs/operations/team_test_participant_guide.md"
    guide = subprocess.check_output(["git", "show", f"feat/ui-polish:{guide_path}"], cwd=PROJECT,
                                    encoding="utf-8")
    guide_commit = subprocess.check_output(["git", "rev-parse", "feat/ui-polish"], cwd=PROJECT,
                                          encoding="utf-8").strip()
    guide = guide.split("## 진행자 체크", 1)[0].rstrip("\n- ") + "\n"
    guide = "\n".join(line for line in guide.splitlines() if not line.startswith("> 진행자 문서:")) + "\n"
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    pdfmetrics.registerFont(TTFont("TeamKorean", str(font)))
    facilitator = output / "facilitator"
    facilitator.mkdir(parents=True)
    (output / "packages").mkdir()
    (output / "participant_guide.md").write_text(guide, encoding="utf-8")
    manifest = {"version": VERSION, "derivation": "dev_linear template; fresh fictional values",
                "dev_source_sha256": source_hashes, "guide_commit": guide_commit,
                "guide_source": guide_path, "llm_enabled": False, "nts_mode": "disabled", "cases": []}
    for case_id, (label, supply, serial, scenario) in CASES.items():
        folder = output / "participants" / case_id
        (folder / "originals").mkdir(parents=True)
        vendor, buyer = f"가상 솔빛제작소 {serial}", "가상 파랑운영사 700"
        bno, buyer_no = fictional_business_number(serial), fictional_business_number(1700)
        tax, total = supply // 10, supply * 11 // 10
        registration = {"title": label + " · 가상 업무지원 시스템 구축", "vendor_name": vendor,
                        "business_number": bno, "contract_amount": total, "amount_basis": "TOTAL",
                        "tax_amount": tax, "payment_mode": "FULL"}
        save_json(folder / "registered_contract.json", registration)
        write_pdf(folder / "registered_contract.pdf", ["등록 계약 정보표", label,
            "평가용 가상 자료입니다. 실제 거래에 사용할 수 없습니다.",
            "계약명: " + registration["title"], "거래처(공급자): " + vendor,
            "사업자등록번호: " + bno, f"등록 계약 금액(세금 포함): {total:,}원",
            f"공급가액: {supply:,}원", f"세액: {tax:,}원", "지급 방식: 일시(전액) 지급",
            "담당자는 서류를 확인하고, 대표가 최종 확인합니다."], "dev_linear", "TeamKorean")
        (folder / "business_rules.md").write_text(RULES, encoding="utf-8")
        with (folder / "blank_record.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(RECORD_COLUMNS)
            writer.writerow([""] * len(RECORD_COLUMNS))
        entry = {"case_id": case_id, "label": label, "registration": registration, "documents": [],
                 "expected_issue": None, "replacement": None}
        kinds = [kind for kind in DOCUMENT_TYPES if not (scenario == "missing" and kind == "bank_account")]
        for number, kind in enumerate(kinds, 1):
            actual_supply = supply + (100000 if scenario == "reissue" and kind == "estimate" else 0)
            lines = make_lines(kind, vendor, buyer, bno, buyer_no, actual_supply,
                               actual_supply // 10, actual_supply * 11 // 10, "2026-10-01", "normal")
            target = folder / "originals" / f"document_{number:02d}.pdf"
            write_pdf(target, lines, "dev_linear", "TeamKorean")
            entry["documents"].append({"path": target.relative_to(output).as_posix(), "kind": kind,
                                       "sha256": sha256(target)})
        if scenario == "missing":
            entry["expected_issue"] = {"rule_id": "REQUIRED_DOCUMENTS", "status": "MISSING",
                                       "field": "bank_account"}
        if scenario == "reissue":
            entry["expected_issue"] = {"rule_id": "AMOUNT_MATCH_ESTIMATE", "status": "FAIL"}
            target = facilitator / "replies" / case_id / "received_document.pdf"
            target.parent.mkdir(parents=True)
            lines = make_lines("estimate", vendor, buyer, bno, buyer_no, supply, tax, total,
                               "2026-10-02", "normal")
            write_pdf(target, lines, "dev_linear", "TeamKorean")
            entry["replacement"] = {"path": target.relative_to(output).as_posix(), "sha256": sha256(target),
                                     "initial_total": total + 110000, "correct_total": total, "difference": 110000}
        manifest["cases"].append(entry)
        archive_participant(folder, output / "packages" / f"{case_id}.zip")
    # Freeze participant artifacts and reply PDFs; facilitator prose is not a scored input.
    manifest["file_sha256"] = {p.relative_to(output).as_posix(): sha256(p)
                               for p in sorted(output.rglob("*")) if p.is_file()}
    save_json(facilitator / "manifest.json", manifest)
    answers = ["# 진행자 전용 — 참가자에게 배포하지 마세요", "",
               "과제 1 — 서류 확인과 요청 / 과제 2 — 다시 받은 서류 처리. 연습은 측정 제외.", "",
               "| 자료 | 정답·제공할 회신 |", "| --- | --- |",
               "| 연습 | 필수 6종 모두 제출, 번호·금액 일치 |",
               "| 과제 1 A·B | 통장사본만 없음. 거래처에 통장사본 요청, 카카오톡·10/8 기한·회신 대기 기록 |"]
    for entry in manifest["cases"]:
        rep = entry["replacement"]
        if rep:
            answers.append(f"| {entry['label']} | 견적 {rep['initial_total']:,}원 → 등록 {rep['correct_total']:,}원. "
                           f"차이 110,000원. 올바른 정정 요청 직후 replies/{entry['case_id']}/received_document.pdf 제공 |")
    answers += ["", "재발행: 이전본 보존, 수정본을 현재본으로 반영, 재확인·회신 처리·대표 전달까지 확인합니다.",
                "NTS 미연동 REVIEW는 안내이며 과제 오류로 세지 않습니다. 앱의 자동 결재를 의미하지 않습니다.",
                "정답표는 설계 기준입니다. 실제 규칙 검증 결과는 docs/operations/team_test_materials.md를 보세요."]
    (facilitator / "answers.md").write_text("\n".join(answers) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=BUNDLE)
    parser.add_argument("--font", type=Path, default=Path("C:/Windows/Fonts/malgun.ttf"))
    args = parser.parse_args()
    result = build(args.output, args.font)
    print(f"{result['version']}: 5 cases, 5 participant ZIPs, 35 PDFs (including registration sheets)")
