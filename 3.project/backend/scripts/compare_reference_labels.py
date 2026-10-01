"""Compare actual independent replies, never simulate a Claude response."""
import argparse
import csv
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))
from backend.evaluation_core import EvaluationNotReady, file_hash, validate_labels, verify_dataset, verify_freeze
from backend.evaluation_review import compare_labels, merge_independent_parts


def main(argv=None):
    parser = argparse.ArgumentParser(description="생성 정보 초안과 Claude 실제 판독의 대조 및 사람 확인 목록")
    parser.add_argument("replies", type=Path, nargs="+", help="계약별 Claude JSON 파일, 중복 ID 없이")
    parser.add_argument("--dataset", type=Path, default=PROJECT / "eval/dataset")
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--output", type=Path, default=PROJECT / "eval/reconciliation")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--sample-rate", type=float, default=0.20)
    parser.add_argument("--human-questions", type=Path, help="일치하더라도 사람이 판단해야 하는 해석 질문 JSON")
    args = parser.parse_args(argv)
    try:
        root = args.dataset.resolve()
        manifest_path = root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        reference_path = args.reference or root / "reference_labels_dev.json"
        reference = json.loads(reference_path.read_text(encoding="utf-8"))
        verify_dataset(root, manifest)
        validate_labels(manifest, reference, "dev", allow_unreviewed=True)
        verify_freeze(manifest_path, reference_path)
        independent = merge_independent_parts([json.loads(path.read_text(encoding="utf-8-sig")) for path in args.replies])
        if len({path.name for path in args.replies}) != len(args.replies):
            raise EvaluationNotReady("독립 판독 파일의 이름이 중복됩니다. 파일별 해시를 구분할 수 없습니다.")
        requests = json.loads(args.human_questions.read_text(encoding="utf-8")) if args.human_questions else []
        comparison = compare_labels(manifest, reference, independent, seed=args.seed, sample_rate=args.sample_rate, review_requests=requests)
        comparison["hashes"] = {"manifest": file_hash(manifest_path), "reference": file_hash(reference_path),
                                 "independent_replies": {path.name: file_hash(path) for path in args.replies}}
        if args.human_questions:
            comparison["hashes"]["human_questions"] = file_hash(args.human_questions)
        if args.output.exists():
            raise EvaluationNotReady("이전 대조 결과를 덮어쓰지 않습니다. 새 --output 경로를 지정하세요.")
        args.output.mkdir(parents=True)
        (args.output / "comparison.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        queue = [row for row in comparison["rows"] if row["human_review_required"]]
        with (args.output / "human_review_queue.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            headers = ["review_id", "source_path", "key", "reference", "independent", "selection_reason", "human_decision", "evidence", "reviewer"]
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            for row in queue:
                entry = {key: row.get(key, "") for key in headers}
                for key in ("reference", "independent"):
                    entry[key] = json.dumps(entry[key], ensure_ascii=False)
                # CSV is a programmatic review queue; prevent formula execution
                # if a returned free-text value starts with a spreadsheet token.
                for key, value in entry.items():
                    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                        entry[key] = "'" + value
                writer.writerow(entry)
        lines = ["# 독립 판독 대조 — 사람 확정 전", "", f"대조 집계: {comparison['counts']}",
                 f"사람 확인 목록: {len(queue)}칸. 실제 확인 완료: 0칸.",
                 "미응답은 일치로 세지 않는다. UNANSWERED가 있으면 Claude 판독을 먼저 보완한다.",
                 f"불일치·모호한 항목을 전부 확인하고 일치 항목에서 무작위 {args.sample_rate:.0%}를 표본 확인한다. 표본 비율은 신뢰도를 보증하지 않는다.",
                 "CSV의 판단·근거·검수자 칸은 사람이 확인한 뒤 작성한다. 이 명령은 정답 확정을 실행하지 않는다."]
        (args.output / "README.md").write_text("\n\n".join(lines) + "\n", encoding="utf-8")
        print(f"독립 판독 대조 완료: {comparison['counts']}. 사람 확인 {len(queue)}칸 대기, 확정하지 않았습니다.")
        return 0
    except (EvaluationNotReady, OSError, ValueError, KeyError, TypeError) as exc:
        print("대조 중단: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
