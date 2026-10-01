"""Import human-entered Excel labels without deriving answers from extraction."""
import argparse
import copy
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))
from backend.evaluation_core import FIELDS, EvaluationNotReady, file_hash, validate_labels, verify_dataset


def read_rows(sheet):
    for row in sheet.iter_rows(min_row=5, values_only=True):
        if any(value is not None for value in row):
            yield row


def import_workbook(workbook_path, root, split, reviewer, output=None):
    import openpyxl
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    verify_dataset(root, manifest)
    template = json.loads((root / f"ground_truth_{split}.json").read_text(encoding="utf-8"))
    if template.get("review", {}).get("confirmed"):
        raise EvaluationNotReady("이 자료의 정답표는 이미 확정되어 있습니다. 새 자료 버전으로 검수하세요.")
    truth = copy.deepcopy(template)
    selected = [row for row in manifest["contracts"] if row["split"] == split]
    document_ids = {str(doc["document_id"]) for row in selected for doc in row["documents"]}
    contract_ids = {str(row["contract_id"]) for row in selected}
    book = openpyxl.load_workbook(workbook_path, read_only=True, data_only=False)
    try:
        if (book["안내"]["B2"].value != manifest["dataset_version"]
                or book["안내"]["B3"].value != file_hash(manifest_path)):
            raise EvaluationNotReady("Excel 양식과 평가 자료 버전 또는 해시가 다릅니다.")
        prefix = split.upper()
        seen_documents, seen_fields, seen_checks = set(), set(), set()
        for row in read_rows(book[prefix + "_유형"]):
            did, answer = str(row[0]), row[4]
            if did not in document_ids or did in seen_documents:
                raise EvaluationNotReady("문서 유형 양식의 ID 또는 중복 행을 확인하세요.")
            seen_documents.add(did)
            truth["documents"][did].update(document_type=answer, reviewed=row[5] == "확인")
        for row in read_rows(book[prefix + "_필드"]):
            did, field, state, value = str(row[0]), row[2], row[4], row[5]
            key = (did, field)
            if did not in document_ids or field not in FIELDS or key in seen_fields:
                raise EvaluationNotReady("필드 양식의 ID와 필드명 또는 중복 행을 확인하세요.")
            if isinstance(value, str) and value.startswith("="):
                raise EvaluationNotReady("정답 값에 수식 대신 원문에서 확인한 값을 입력하세요.")
            if hasattr(value, "strftime"):
                value = value.strftime("%Y-%m-%d")
            seen_fields.add(key)
            truth["documents"][did]["fields"][field] = {"state": state, "value": value}
        for row in read_rows(book[prefix + "_검수"]):
            cid, rule, field, status, reviewed = str(row[0]), row[2], str(row[3]), row[4], row[5]
            key = (cid, rule, field)
            if cid not in contract_ids or key in seen_checks or reviewed != "확인":
                raise EvaluationNotReady("검수 양식의 ID, 중복 행, 확인 여부를 점검하세요.")
            seen_checks.add(key)
            candidates = [entry for entry in truth["contracts"][cid]["checks"] if entry["rule_id"] == rule and entry["field"] == field]
            if len(candidates) != 1:
                raise EvaluationNotReady("검수 항목이 원본 양식과 다릅니다.")
            candidates[0]["status"] = status
        if seen_documents != document_ids or seen_fields != {(did, field) for did in document_ids for field in FIELDS}:
            raise EvaluationNotReady("정답 양식에서 문서 또는 필드 행이 누락되었습니다.")
        expected_checks = {(str(row["contract_id"]), slot["rule_id"], slot["field"]) for row in selected for slot in row["check_slots"]}
        if seen_checks != expected_checks:
            raise EvaluationNotReady("정답 양식에서 검수 행이 누락되었습니다.")
    finally:
        book.close()
    for cid in contract_ids:
        entry = truth["contracts"][cid]
        entry["missing_types"] = [row["field"] for row in entry["checks"] if row["rule_id"] == "REQUIRED_DOCUMENTS" and row["status"] == "MISSING"]
        entry["reviewed"] = True
    truth["review"] = {"confirmed": True, "reviewer_type": "human", "reviewer": reviewer.strip(),
                       "confirmed_at": datetime.now(timezone(timedelta(hours=9))).isoformat()}
    validate_labels(manifest, truth, split)
    output = output or root / f"ground_truth_{split}.json"
    output.write_text(json.dumps(truth, ensure_ascii=False, indent=2), encoding="utf-8")
    receipt = {"labels_sha256": file_hash(output), "manifest_sha256": file_hash(manifest_path),
               "workbook_sha256": file_hash(workbook_path), **truth["review"]}
    output.with_suffix(".freeze.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    return truth


def main(argv=None):
    parser = argparse.ArgumentParser(description="사람이 작성한 Excel 정답표 확정")
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--dataset", type=Path, default=PROJECT / "eval" / "dataset")
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    parser.add_argument("--reviewer", required=True, help="검수자 별칭")
    parser.add_argument("--confirmed", action="store_true", required=True, help="모델 출력 전에 사람이 검수 완료했음을 명시")
    args = parser.parse_args(argv)
    try:
        import_workbook(args.workbook, args.dataset.resolve(), args.split, args.reviewer)
        print("사람 입력 정답 확정 완료: " + args.split + ". 정답과 자료 해시를 저장했습니다.")
        return 0
    except (EvaluationNotReady, OSError, ValueError, KeyError) as exc:
        print("정답 가져오기 중단: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
