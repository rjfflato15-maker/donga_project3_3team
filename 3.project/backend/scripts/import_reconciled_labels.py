"""Read completed review Excel; never auto-confirm an unreviewed agreement."""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))
from backend.evaluation_core import EvaluationNotReady, file_hash, validate_labels, verify_dataset, verify_freeze
from backend.evaluation_review import compare_labels, merge_independent_parts
from backend.evaluation_confirmation import apply_human_decisions


def import_review(workbook_path, root, comparison_path, replies_directory, reviewer, review_result=None):
    import openpyxl
    output = root / "ground_truth_dev.json"
    if output.with_suffix(".freeze.json").exists() or json.loads(output.read_text(encoding="utf-8")).get("review", {}).get("confirmed"):
        raise EvaluationNotReady("이미 확정한 정답을 덮어쓰지 않습니다. 새 버전으로 검수하세요.")
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    verify_dataset(root, manifest, split="dev")
    reference_path = root / "reference_labels_dev.json"
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    validate_labels(manifest, reference, "dev", allow_unreviewed=True)
    verify_freeze(manifest_path, reference_path)
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    hashes = comparison["hashes"]
    if hashes["manifest"] != file_hash(manifest_path) or hashes["reference"] != file_hash(reference_path):
        raise EvaluationNotReady("대조 이후 원문 목록 또는 초안이 변경되었습니다.")
    parts = []
    for name, digest in hashes["independent_replies"].items():
        if Path(name).name != name:
            raise EvaluationNotReady("독립 판독 파일의 이름 형식을 확인하세요.")
        path = replies_directory / name
        if file_hash(path) != digest:
            raise EvaluationNotReady("대조 이후 Claude 응답이 변경되었습니다.")
        parts.append(json.loads(path.read_text(encoding="utf-8-sig")))
    independent = merge_independent_parts(parts)
    methods = {"random_without_replacement_over_agreed_nonmandatory_cells": "random",
               "stratified_random_by_case_document_type": "case_document_type"}
    recalculated = compare_labels(manifest, reference, independent, seed=comparison["sampling"]["seed"],
                                  sample_rate=comparison["sampling"]["rate"], review_requests=comparison.get("review_requests", []),
                                  sample_method=methods[comparison["sampling"]["method"]])
    if any(recalculated[key] != comparison[key] for key in ("rows", "counts", "sampling", "review_requests", "required_human_count", "review")):
        raise EvaluationNotReady("대조 결과 또는 사람 확인 목록이 재현되지 않습니다.")
    comparison["comparison_sha256"] = file_hash(comparison_path)
    book = openpyxl.load_workbook(workbook_path, read_only=True, data_only=False)
    decisions = {}
    try:
        if (book["안내"]["B2"].value != manifest["dataset_version"]
                or book["안내"]["B3"].value != comparison["comparison_sha256"]
                or book["안내"]["B4"].value != file_hash(manifest_path)):
            raise EvaluationNotReady("Excel과 대조 결과·평가 자료의 버전 또는 해시가 다릅니다.")
        if not reviewer.strip() or str(book["안내"]["B12"].value or "").strip() != reviewer.strip():
            raise EvaluationNotReady("안내 B12의 검수자 별칭과 --reviewer를 일치시키세요.")
        for name in ("필드확인", "검수확인"):
            for row in book[name].iter_rows(min_row=5, values_only=True):
                if not any(value is not None for value in row):
                    continue
                rid = row[0]
                if rid in decisions or not isinstance(rid, str) or len(row) < 12:
                    raise EvaluationNotReady("사람 확인 양식의 중복 ID 또는 행 형식을 확인하세요.")
                decisions[rid] = {"state": row[8], "value": row[9], "confirmation": row[10], "evidence": row[11]}
    finally:
        book.close()
    # Before first freeze, a corrected random sample means the agreement is not
    # trustworthy enough to finalize at this coverage. Expand the review first.
    by_id = {row["review_id"]: row for row in comparison["rows"]}
    for rid, decision in decisions.items():
        row = by_id.get(rid)
        if row is None or row.get("selection_reason") != "RANDOM_SAMPLE":
            continue
        expected = row["reference"]
        if isinstance(expected, dict):
            from backend.evaluation_core import normalize
            matches = decision["state"] == expected["state"] and normalize(row["key"], decision["value"]) == normalize(row["key"], expected["value"])
        elif row["key"] == "document_type":
            matches = decision["state"] == "TYPE" and decision["value"] == expected
        elif row["key"] == "missing_types":
            try:
                actual = json.loads(decision["value"]) if isinstance(decision["value"], str) else decision["value"]
                matches = decision["state"] == "MISSING_TYPES" and sorted(actual) == expected
            except (ValueError, TypeError):
                matches = False
        else:
            matches = decision["state"] == expected and decision["value"] in (None, "")
        if not matches and comparison["required_human_count"] < len(comparison["rows"]):
            raise EvaluationNotReady("무작위 표본에서 수정이 발견됐습니다. --sample-rate 1.0으로 나머지 항목까지 확인한 새 대조 결과와 양식으로 검수하세요.")
    labels = apply_human_decisions(manifest, reference, comparison, decisions, reviewer)
    if review_result is not None:
        source = json.loads(review_result.read_text(encoding="utf-8-sig"))
        items = source.get("items", [])
        if source.get("reviewer") != reviewer or len(items) != len(decisions) or {item["id"] for item in items} != set(decisions):
            raise EvaluationNotReady("원본 사람 검수 기록의 검수자 또는 확인 목록이 다릅니다.")
        times = []
        for item in items:
            decision = decisions[item["id"]]
            if item.get("reviewer") != reviewer or item.get("decision") != decision["confirmation"] or item.get("reason") != decision["evidence"]:
                raise EvaluationNotReady("원본 검수 기록과 Excel의 확인·근거가 다릅니다.")
            timestamp = datetime.fromisoformat(item["reviewed_at"].replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                raise EvaluationNotReady("사람 확인 시각에 시간대가 필요합니다.")
            times.append(timestamp)
            cid, did, key = item["id"].split("/", 2)
            if did != "contract":
                proof = labels["documents"][did]["document_type_review"] if key == "document_type" else labels["documents"][did]["fields"][key]["review"]
            elif key == "missing_types":
                proof = labels["contracts"][cid]["missing_types_review"]
            else:
                rule, field = key.split("/", 1)
                proof = next(check["review"] for check in labels["contracts"][cid]["checks"] if check["rule_id"] == rule and check["field"] == field)
            proof.update(reviewed_at=item["reviewed_at"], source_sheet=item["sheet"], source_row=item["row"])
        labels["review"].update(human_result_sha256=file_hash(review_result), human_result_file=review_result.name,
                               reviewed_from=min(times).isoformat(), reviewed_until=max(times).isoformat())
    output.write_text(json.dumps(labels, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    receipt = {"labels_sha256": file_hash(output), "manifest_sha256": file_hash(manifest_path),
               "workbook_sha256": file_hash(workbook_path), **labels["review"]}
    output.with_suffix(".freeze.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return labels


def main(argv=None):
    parser = argparse.ArgumentParser(description="독립 AI 판독 대조 후 사람의 직접·표본 검수 결과 확정")
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--dataset", type=Path, default=PROJECT / "eval/dataset")
    parser.add_argument("--comparison", type=Path, default=PROJECT / "eval/reconciliation-v3/comparison.json")
    parser.add_argument("--replies", type=Path, default=PROJECT / "eval/claude_blind_review/replies")
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--review-result", type=Path, help="원본 사람 확인 JSON의 시각·근거 출처 보존")
    parser.add_argument("--confirmed", action="store_true", required=True, help="필수 항목을 실제로 확인했음을 명시")
    args = parser.parse_args(argv)
    try:
        labels = import_review(args.workbook, args.dataset.resolve(), args.comparison, args.replies, args.reviewer, args.review_result)
        print(f"dev 정답 확정: 사람 직접 확인 {labels['review']['human_direct_count']}칸, AI 일치 {labels['review']['ai_agreement_count']}칸. 전수 사람 검수로 기록하지 않았습니다.")
        return 0
    except (EvaluationNotReady, OSError, ValueError, KeyError, TypeError) as exc:
        print("대조 정답 가져오기 중단: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
