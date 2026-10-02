"""Evaluate frozen human labels or explicitly marked DEV source drafts."""
import argparse
import contextlib
import csv
import io
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))
from backend.evaluation_core import EvaluationNotReady, file_hash, dataset_file, verify_dataset, validate_labels, verify_freeze, score_predictions


def run_rule(root, contracts):
    # Force local evaluation regardless of a customer's .env configuration.
    # Temporary storage avoids touching either pilot.db or evidence_manager.db.
    with tempfile.TemporaryDirectory(prefix="contract-evaluation-") as storage:
        os.environ["APP_DEPLOYMENT_MODE"] = "pilot"
        os.environ["APP_NTS_MODE"] = "disabled"
        os.environ["APP_STORAGE_ROOT"] = storage
        from backend.app.ai import analyze_document
        from backend.app.integrations.nts_client import DisabledNtsClient
        from backend.app.validation.engine import RuleEngine
        engine = RuleEngine()
        engine.nts_client = DisabledNtsClient()
        predictions = {"documents": {}, "contracts": {}}
        durations = []
        for contract in contracts:
            documents = []
            for document in contract["documents"]:
                started = perf_counter()
                try:
                    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                        analysis, raw, _ = analyze_document(str(dataset_file(root, document["path"])), file_name=Path(document["path"]).name)
                    fields = analysis.fields.model_dump()
                    dtype = analysis.document_type.value
                    body = raw.partition("\n")[2] if raw.startswith("[파일명:") else raw
                    failed = not bool(body.strip())
                    error_type = None if not failed else "EMPTY_TEXT"
                except Exception as exc:
                    fields, dtype, failed = {}, "unknown", True
                    error_type = type(exc).__name__
                durations.append(perf_counter() - started)
                predictions["documents"][str(document["document_id"])] = {"document_type": dtype, "fields": fields, "processing_failed": failed, "error_type": error_type}
                documents.append({"document_id": document["document_id"], "document_type": dtype,
                                  "file_name": Path(document["path"]).name, "fields": fields,
                                  "sha256": document["sha256"], "file_available": True,
                                  "processing_status": "FAILED" if failed else "COMPLETED"})
            inputs = contract["input"]
            _, checks = engine.validate_contract_evidence(contract["contract_id"], inputs["title"], inputs["vendor_name"],
                inputs["business_number"], inputs["contract_amount"], documents, amount_policy=inputs["amount_policy"])
            predictions["contracts"][str(contract["contract_id"])] = {"checks": [row.model_dump(mode="json") for row in checks]}
        return predictions, durations


def pct(value):
    return "측정 불가" if value is None else f"{value * 100:.1f}%"


def write_report(output, metadata, metrics):
    output.mkdir(parents=True, exist_ok=True)
    preliminary = metadata.get("preliminary", False)
    stem = "preliminary_rule" if preliminary else "baseline_rule"
    payload = {"metadata": metadata, "metrics": metrics}
    (output / (stem + ".json")).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = [("분류 Macro F1", metrics["classification_macro_f1"], 0.90),
            ("핵심 필드 정확도", metrics["field_accuracy"], 0.90),
            ("누락 Recall", metrics["missing_recall"], 0.95),
            ("교차검증 Macro F1", metrics["cross_validation_macro_f1"], 0.90)]
    title = "# 규칙 예비 성능 보고서" if preliminary else "# 규칙 기준 성능 보고서"
    notice = ("생성 정보와 파일을 대조해 만든 Codex 정답 초안을 사용했다. 사람 검수와 Claude 독립 검토는 아직 완료하지 않았다. 이 결과는 개발용 예비 측정이며 최종 발표의 검증된 성능 수치로 사용하지 않는다."
              if preliminary else "사람이 확정한 정답표를 사용한 규칙 기준 성능이다.")
    review = metadata.get("label_review", {})
    if not preliminary and review.get("review_method") == "independent_reconciliation_with_human_sampling":
        notice = (f"생성 설계 초안과 Claude 독립 판독을 대조하고 사람이 필수 항목과 무작위 표본 {review['human_direct_count']}칸을 직접 확인하여 확정했다. "
                  f"나머지 {review['ai_agreement_count']}칸은 두 AI 초안의 일치에 따른 정답이다. 사람 전수 검수로 해석하지 않는다.")
        if review.get("human_full_review"):
            notice = f"생성 설계 초안과 Claude 독립 판독을 대조한 뒤 사람이 전체 {review['human_direct_count']}칸을 직접 확인하여 정답을 확정했다."
    lines = [title, "", notice, "", f"평가 구분은 {metadata['split']}이며 모델을 사용하지 않은 규칙 기준 성능이다.", "",
             f"실행 일시: {metadata['evaluated_at']}", f"자료 버전: {metadata['dataset_version']}",
             f"정답 SHA256: {metadata['labels_sha256']}", f"자료 목록 SHA256: {metadata['manifest_sha256']}",
             f"계약 {metrics['contract_count']}건, 문서 {metrics['document_count']}개", "",
             "| 지표 | 측정값 | 목표 | 달성 여부 |", "| --- | --- | --- | --- |"]
    for name, value, target in rows:
        result = "측정 불가" if value is None else (("예비 기준 충족" if value >= target else "예비 기준 미충족") if preliminary else ("달성" if value >= target else "미달"))
        lines.append(f"| {name} | {pct(value)} | {pct(target)} | {result} |")
    lines += ["", f"문제가 있는 항목에서 잘못된 PASS 비율: {pct(metrics['wrong_pass_rate'])}",
              f"PASS 결과 중 잘못된 PASS 비율: {pct(metrics['wrong_pass_among_passes'])}",
              f"자동 추출값 제공 비율: {pct(metrics['extraction_coverage'])}",
              f"확인 필요 검수 비율: {pct(metrics['check_review_rate'])}",
              f"존재하는 필드의 정확도: {pct(metrics['present_field_accuracy'])}",
              f"모호한 필드의 보류 정확도: {pct(metrics['ambiguous_field_accuracy'])}",
              f"없는 필드에 값을 만든 비율: {pct(metrics['false_extraction_on_absent_rate'])}",
              f"문서당 평균 분류·추출 시간: {metrics['mean_document_seconds']:.3f}초 (규칙 검수와 사람 확인 시간 제외)", "",
              "## 측정 조건과 한계", "",
              "핵심 필드 정확도의 분모는 VALUE와 REVIEW 정답이다. 값이 존재하는데 추출을 거절한 경우는 오답이며 분모에서 빼지 않는다. ABSENT는 정답이 쉽게 늘어나는 것을 막기 위해 별도 거짓 추출 비율로 보고한다. 처리율은 값 제공 여부이고 담당자 또는 대표의 승인율이 아니다.", "",
              "모든 실행에서 국세청 외부 API를 호출하지 않는다. BUSINESS_STATUS는 미연동에 따른 확인 필요로 평가한다. 이 수치는 합성 자료에서의 결과이며 실제 회사 서류의 성능이나 검수 시간 절감을 보장하지 않는다.", "",
              "분류는 사용자 유형 힌트 없이 수행한다. 파일명은 문서 유형을 담지 않은 이름을 사용한다. 분류 점수는 정확도 지표에 넣지 않는다. Macro F1은 분류 6종과 검수 상태 4종을 고정하여 평균하며, 정답과 예측이 모두 없는 클래스의 F1은 0으로 기록한다.", "",
              "개발용 결과는 모델 선택과 개선에만 사용한다. 최종 발표 수치는 구현과 설정을 고정한 뒤 별도 test 자료로 평가해야 한다.", "",
              "## 오류 사례", ""]
    lines.extend(f"- {json.dumps(row, ensure_ascii=False)}" for row in metrics["failures"][:10])
    if not metrics["failures"]:
        lines.append("평가한 정답 범위에서 발견한 오류가 없다.")
    (output / (stem + ".md")).write_text("\n".join(lines) + "\n", encoding="utf-8")
    with (output / ("preliminary_metrics.csv" if preliminary else "baseline_metrics.csv")).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["metric", "value", "split", "labels_sha256"])
        for key, value in metrics.items():
            if isinstance(value, (int, float)) or value is None:
                writer.writerow([key, value, metadata["split"], metadata["labels_sha256"]])


def main(argv=None):
    parser = argparse.ArgumentParser(description="사람이 확정한 정답으로 로컬 성능 측정")
    parser.add_argument("--dataset", type=Path, default=PROJECT / "eval" / "dataset")
    parser.add_argument("--labels", type=Path)
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    parser.add_argument("--mode", choices=["rule", "llm", "hybrid_unguarded", "hybrid_guarded"], default="rule")
    parser.add_argument("--final", action="store_true", help="구현과 모델 설정을 고정한 후의 최종 평가")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--preliminary", action="store_true", help="생성 정보 기반의 미확정 dev 정답 초안으로 예비 측정")
    parser.add_argument("--save-predictions", action="store_true", help="가상 자료의 추출 결과를 로컬 평가 파일에 저장")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.mode != "rule":
            raise EvaluationNotReady("현재는 2A 규칙 기준 측정 단계입니다. LLM 비교 모드는 1번 구현 후 연결합니다.")
        if args.split == "test" and not args.final:
            raise EvaluationNotReady("test는 최종 평가 전용입니다. 개발 중에는 dev를 사용하세요.")
        if args.preliminary and args.split != "dev":
            raise EvaluationNotReady("예비 측정은 dev만 사용합니다. test는 최종 평가 전용으로 유지하세요.")
        root = args.dataset.resolve()
        manifest_path = root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if args.save_predictions and (manifest.get("dataset_version") != "synthetic-v1" or manifest.get("created_for") != "local-evaluation"):
            raise EvaluationNotReady("추출 결과 저장은 현재 가상 자료 버전에서만 허용합니다.")
        labels_path = args.labels or root / ("reference_labels_dev.json" if args.preliminary else f"ground_truth_{args.split}.json")
        labels = json.loads(labels_path.read_text(encoding="utf-8"))
        verify_dataset(root, manifest, split=args.split)
        contracts = validate_labels(manifest, labels, args.split, allow_unreviewed=args.preliminary)
        receipt = verify_freeze(manifest_path, labels_path)
        if args.preliminary:
            source = receipt.get("source_files", {})
            if not source:
                raise EvaluationNotReady("정답 초안을 작성한 생성 코드와 라벨 기준 해시가 없습니다.")
            for relative, digest in source.items():
                if file_hash(dataset_file(PROJECT, relative)) != digest:
                    raise EvaluationNotReady("정답 초안 작성 후 생성 코드 또는 라벨 기준이 변경되었습니다.")
        if args.validate_only:
            print(f"정답 검증 통과: {args.split} 계약 {len(contracts)}건. 추출과 성능 측정은 실행하지 않았습니다.")
            return 0
        predictions, durations = run_rule(root, contracts)
        metrics = score_predictions(contracts, labels, predictions)
        metrics["mean_document_seconds"] = sum(durations) / len(durations)
        metadata = {"split": args.split, "mode": "rule", "dataset_version": manifest["dataset_version"],
                    "evaluated_at": datetime.now(timezone(timedelta(hours=9))).isoformat(),
                    "labels_sha256": receipt["labels_sha256"], "manifest_sha256": receipt["manifest_sha256"],
                    "preliminary": args.preliminary, "label_review": labels["review"],
                    "nts_mode": "disabled", "classification_hint": False, "model": None,
                    "command": ["evaluate.py", "--split", args.split, "--mode", args.mode] + (["--preliminary"] if args.preliminary else [])}
        output = args.output or PROJECT / "docs" / "eval" / args.split / ("preliminary" if args.preliminary else "baseline")
        write_report(output, metadata, metrics)
        if args.save_predictions:
            (output / "rule_predictions.json").write_text(json.dumps(predictions, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"규칙 {'예비' if args.preliminary else '기준'} 측정 완료: {args.split} 계약 {len(contracts)}건. 보고서와 CSV를 저장했습니다.")
        return 0
    except (EvaluationNotReady, OSError, ValueError, KeyError) as exc:
        print("측정 대기: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
