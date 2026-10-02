"""Four extraction modes, one common rule engine, frozen labels and replay cache."""
import argparse
import contextlib
import csv
import io
import json
import os
import sys
import tempfile
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from time import perf_counter

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))
from backend.evaluation_core import file_hash, dataset_file, verify_dataset, verify_freeze, validate_labels, score_predictions, normalize, EvaluationNotReady
from backend.app.ai.local_llm import OllamaClient, LLMSettings, CORE_FIELDS, PROMPT_VERSION
from backend.app.ai.grounding import source_pages, supplementation_targets, GUARD_VERSION
from backend.app.ai.llm_supplement import apply_proposals

MODES = ("rule", "llm", "hybrid_unguarded", "hybrid_guarded")


def collect_inputs(root, contracts):
    from backend.app.ai import analyze_document
    result = {}
    for contract in contracts:
        for doc in contract["documents"]:
            started = perf_counter()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                analysis, raw, _ = analyze_document(str(dataset_file(root, doc["path"])), file_name=Path(doc["path"]).name, use_llm=False)
                pages = source_pages(dataset_file(root, doc["path"]), raw)
            fields = analysis.fields.model_dump()
            result[str(doc["document_id"])] = {"document": doc, "fields": fields, "pages": pages,
                "document_type": analysis.document_type.value, "processing_failed": not any(p["text"].strip() for p in pages),
                "rule_seconds": perf_counter() - started,
                "targets": supplementation_targets(fields, pages, analysis.document_type.value)}
    return result


def request_cached(client, item, targets, cache, refresh=False):
    # Keys depend on the exact OCR source, target fields, prompt and model digest.
    metadata = client.model_metadata()
    request = {"pages": item["pages"], "targets": list(targets), "document_type": item["document_type"],
               "settings": asdict(client.settings), "model_digest": metadata["digest"], "prompt_version": PROMPT_VERSION}
    key = sha256(json.dumps(request, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    path = cache / (key + ".json")
    started = perf_counter()
    if path.exists() and not refresh:
        saved = json.loads(path.read_text(encoding="utf-8"))
        if saved["request_sha256"] != key or sha256(json.dumps(saved["run"], ensure_ascii=False, sort_keys=True).encode()).hexdigest() != saved["run_sha256"]:
            raise EvaluationNotReady("LLM 응답 캐시가 변경되었습니다.")
        return saved["run"], key, True, perf_counter() - started
    run = client.extract(item["pages"], targets, item["document_type"])
    cache.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"request_sha256": key, "run_sha256": sha256(json.dumps(run, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
                               "run": run}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return run, key, False, perf_counter() - started


def field_accuracy(items, labels, fields_by_id):
    correct, scored, false_absent, absent = 0, 0, 0, 0
    for did in items:
        for field in CORE_FIELDS:
            truth = labels["documents"][did]["fields"][field]
            value = fields_by_id[did].get(field)
            provided = value not in (None, "", "UNKNOWN")
            if truth["state"] == "ABSENT":
                absent += 1
                false_absent += provided
            else:
                scored += 1
                correct += (provided and normalize(field, value) == normalize(field, truth["value"])) if truth["state"] == "VALUE" else not provided
    return {"correct": correct, "scored": scored, "accuracy": correct / scored if scored else None,
            "absent": absent, "false_extraction_on_absent": false_absent}


def candidate_benchmark(inputs, labels, models, output, cache, labels_path, limit=8):
    # Predeclared DEV coverage: six formats/types from the first contract,
    # then ambiguous-label and printed-arithmetic cases. No gold values enter prompts.
    ids = sorted(inputs)[:6] + [did for did in ("10902", "11005") if did in inputs]
    ids = list(dict.fromkeys(ids))[:limit]
    if len(ids) < limit:
        ids += [did for did in sorted(inputs) if did not in ids][:limit - len(ids)]
    results = []
    for model in models:
        client = OllamaClient(LLMSettings(model=model))
        raw, guarded, times, errors = {}, {}, [], []
        for did in ids:
            print(f"모델 비교: {model} 문서 {did}", flush=True)
            run, _, hit, _ = request_cached(client, inputs[did], CORE_FIELDS, cache)
            raw[did], _ = apply_proposals(inputs[did]["fields"], run, inputs[did]["pages"], inputs[did]["document_type"], CORE_FIELDS, guarded=False, llm_only=True)
            guarded[did], _ = apply_proposals(inputs[did]["fields"], run, inputs[did]["pages"], inputs[did]["document_type"], CORE_FIELDS, llm_only=True)
            times.append(run["elapsed_seconds"])
            if not run["ok"]:
                errors.append({"document_id": did, "reason": run["error"]})
        results.append({"model": model, "model_metadata": client.model_metadata(), "document_ids": ids,
                        "raw_fields": field_accuracy(ids, labels, raw), "guarded_fields": field_accuracy(ids, labels, guarded),
                        "mean_original_call_seconds": sum(times) / len(times), "errors": errors})
    selected = max(results, key=lambda r: (r["guarded_fields"]["accuracy"] or 0, r["raw_fields"]["accuracy"] or 0, -r["mean_original_call_seconds"]))["model"]
    payload = {"selection_basis": "DEV 8-document guarded field accuracy, raw field accuracy, then original call time",
               "label_status": "confirmed", "labels_sha256": file_hash(labels_path), "prompt_version": PROMPT_VERSION, "guard_version": GUARD_VERSION,
               "results": results, "selected_model": selected}
    output.mkdir(parents=True, exist_ok=True)
    (output / "model_comparison.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return selected, payload


def validate_mode_contracts(contracts, inputs, fields_by_id):
    from backend.app.validation.engine import RuleEngine
    from backend.app.integrations.nts_client import DisabledNtsClient
    engine = RuleEngine()
    engine.nts_client = DisabledNtsClient()
    predictions = {"documents": {}, "contracts": {}}
    for contract in contracts:
        docs = []
        for doc in contract["documents"]:
            did, item = str(doc["document_id"]), inputs[str(doc["document_id"])]
            predictions["documents"][did] = {"document_type": item["document_type"], "fields": fields_by_id[did]}
            docs.append({"document_id": doc["document_id"], "document_type": item["document_type"], "fields": fields_by_id[did],
                         "file_name": Path(doc["path"]).name, "sha256": doc["sha256"], "file_available": True,
                         "processing_status": "FAILED" if item["processing_failed"] else "COMPLETED"})
        ref = contract["input"]
        _, checks = engine.validate_contract_evidence(contract["contract_id"], ref["title"], ref["vendor_name"], ref["business_number"],
                                                     ref["contract_amount"], docs, amount_policy=ref["amount_policy"])
        predictions["contracts"][str(contract["contract_id"])] = {"checks": [c.model_dump(mode="json") for c in checks]}
    return predictions


def check_accuracy(labels, predictions):
    correct = scored = not_applicable = 0
    for cid, contract in labels["contracts"].items():
        expected = {(r["rule_id"], r["field"]): r["status"] for r in contract["checks"]}
        actual = {(r["rule_id"], r["field"]): r["status"] for r in predictions["contracts"][cid]["checks"]}
        for key in expected.keys() | actual.keys():
            want, got = expected.get(key, "N/A"), actual.get(key, "N/A")
            if want == got == "N/A":
                not_applicable += 1
                continue
            scored += 1
            correct += want == got
    return {"correct": correct, "scored": scored, "both_not_applicable": not_applicable,
            "accuracy": correct / scored if scored else None}


def verify_final_selection(model, record, client):
    if (model != record.get("selected_model") or record.get("prompt_version") != PROMPT_VERSION
            or record.get("guard_version") != GUARD_VERSION):
        raise EvaluationNotReady("test 모델과 프롬프트는 dev 선택 기록과 같아야 합니다.")
    selected = next((r for r in record["results"] if r["model"] == model), None)
    if not selected or selected["model_metadata"]["digest"] != client.model_metadata()["digest"]:
        raise EvaluationNotReady("설치 모델 digest가 dev 선택 때와 다릅니다.")


def run_four_modes(inputs, contracts, labels, model, cache):
    client = OllamaClient(LLMSettings(model=model))
    fields_by_mode = {mode: {} for mode in MODES}
    traces = {mode: {} for mode in MODES}
    for did, item in inputs.items():
        fields_by_mode["rule"][did] = item["fields"]
        traces["rule"][did] = {"effective_seconds": item["rule_seconds"], "guard_seconds": 0, "cache_execution_seconds": 0}
        print(f"네 조건 평가: {model} 문서 {did}", flush=True)
        raw_run, key, hit, executed = request_cached(client, item, CORE_FIELDS, cache)
        fields_by_mode["llm"][did], review = apply_proposals(item["fields"], raw_run, item["pages"], item["document_type"], CORE_FIELDS, guarded=False, llm_only=True)
        traces["llm"][did] = {"review": review, "response_id": key, "cache_hit": hit, "guard_seconds": 0,
                               "effective_seconds": item["rule_seconds"] + raw_run["elapsed_seconds"], "cache_execution_seconds": executed}
        if item["targets"]:
            hybrid_run, hybrid_key, hybrid_hit, hybrid_executed = request_cached(client, item, item["targets"], cache)
        else:
            hybrid_run, hybrid_key, hybrid_hit, hybrid_executed = {"ok": True, "proposals": {}, "elapsed_seconds": 0}, None, False, 0
        for mode in ("hybrid_unguarded", "hybrid_guarded"):
            started = perf_counter()
            fields, review = apply_proposals(item["fields"], hybrid_run, item["pages"], item["document_type"], item["targets"], guarded=mode == "hybrid_guarded")
            guard_seconds = perf_counter() - started if mode == "hybrid_guarded" else 0
            fields_by_mode[mode][did] = fields
            traces[mode][did] = {"review": review, "response_id": hybrid_key, "cache_hit": hybrid_hit, "guard_seconds": guard_seconds,
                "effective_seconds": item["rule_seconds"] + hybrid_run["elapsed_seconds"] + guard_seconds,
                "cache_execution_seconds": hybrid_executed if mode == "hybrid_unguarded" else 0, "shared_response_replay": mode == "hybrid_guarded"}
    metrics = {}
    for mode in MODES:
        predictions = validate_mode_contracts(contracts, inputs, fields_by_mode[mode])
        result = score_predictions(contracts, labels, predictions)
        reasons, source_warnings = Counter(), Counter()
        for trace in traces[mode].values():
            for decision in trace.get("review", {}).get("decisions", []):
                if mode == "hybrid_guarded" and not decision["applied"]:
                    reasons.update(decision["reasons"])
                source_warnings.update(decision["warnings"])
        check_counts = check_accuracy(labels, predictions)
        result.update(check_state_accuracy=check_counts["accuracy"], check_state_counts=check_counts,
                      guard_rejected_count=sum(not d["applied"] for trace in traces[mode].values() for d in trace.get("review", {}).get("decisions", [])) if mode == "hybrid_guarded" else 0,
                      guard_rejection_reasons=dict(reasons), source_warnings=dict(source_warnings),
                      mean_document_seconds=sum(t["effective_seconds"] for t in traces[mode].values()) / len(inputs),
                      mean_guard_seconds=sum(t["guard_seconds"] for t in traces[mode].values()) / len(inputs),
                      mean_cache_execution_seconds=sum(t["cache_execution_seconds"] for t in traces[mode].values()) / len(inputs),
                      llm_failure_count=sum(t.get("review", {}).get("status") == "FAILED" for t in traces[mode].values()))
        metrics[mode] = result
    return metrics, traces


def write_comparison(output, metadata, metrics, traces):
    output.mkdir(parents=True, exist_ok=True)
    payload = {"metadata": metadata, "metrics": metrics}
    (output / "four_modes.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "extraction_evidence.json").write_text(json.dumps(traces, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    review = metadata["label_review"]
    review_summary = {key: review.get(key) for key in ("reviewer", "human_full_review", "human_direct_count", "ai_agreement_count", "confirmed_at")}
    lines = [f"# 확정 정답 기준 {metadata['split']} 네 조건 비교", "",
             "test 최종 평가다." if metadata["final_test"] else "dev 개발용 평가이며 별도 test 최종 성능이 아니다.",
             "분류는 네 조건 모두 같은 규칙 분류기를 사용한다. LLM만은 필드 추출만 LLM이라는 뜻이다.",
             "", f"정답 검수 출처: {json.dumps(review_summary, ensure_ascii=False)}", "사람 표본 확인과 AI 일치 확인을 구분하며 사람 전수 검수로 해석하지 않는다.",
             "", "| 조건 | 필드 정확도 | 검수 상태 정확도 | 검수 Macro F1 | 잘못된 PASS | 가드 거부 | 문서 평균 시간 |", "|---|---:|---:|---:|---:|---:|---:|"]
    with (output / "four_modes.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["mode", "field_accuracy", "check_state_accuracy", "cross_validation_macro_f1", "wrong_pass", "guard_rejected", "mean_document_seconds", "mean_guard_seconds", "mean_cache_execution_seconds", "labels_sha256"])
        for mode, m in metrics.items():
            lines.append(f"| {mode} | {m['field_accuracy']:.2%} | {m['check_state_accuracy']:.2%} | {m['cross_validation_macro_f1']:.4f} | {m['wrong_pass_counts']['wrong_pass']} | {m['guard_rejected_count']} | {m['mean_document_seconds']:.3f}초 |")
            writer.writerow([mode, m["field_accuracy"], m["check_state_accuracy"], m["cross_validation_macro_f1"], m["wrong_pass_counts"]["wrong_pass"], m["guard_rejected_count"], m["mean_document_seconds"], m["mean_guard_seconds"], m["mean_cache_execution_seconds"], metadata["labels_sha256"]])
    lines += ["", "③과 ④는 문서별 response_id가 같은 LLM 응답을 재사용한다. 시간은 최초 실제 호출시간과 공통 분류·OCR 시간, 가드 시간을 합친 값이며 캐시 실행시간은 별도로 기록한다. 조건별 규칙 검수 시간과 사람 확인 시간은 포함하지 않는다.",
              "", "검수 상태 정확도의 분모는 정답 또는 출력에 적용되는 항목의 합집합이다. 양쪽 모두 N/A인 항목은 분모에서 제외하며 누락·추가 출력은 오답에 포함한다. 핵심 필드 정확도는 VALUE+REVIEW 정답을 분모로 유지하고 ABSENT 거짓 추출률은 별도 집계한다.",
              "", "DOCX 등 물리 페이지를 확인할 수 없는 형식은 PAGE_UNVERIFIED로 LLM 제안을 거부하고 규칙 결과와 수동 검토 필요 기록을 유지한다. 원문 자체의 산술 불일치는 SOURCE_ARITHMETIC_MISMATCH로 기록하고 표시값을 계산값으로 고치지 않는다.",
              "", f"모델: {metadata['model']}. 정답 SHA256: {metadata['labels_sha256']}", "", "가드 거부 이유(한 제안에 여러 이유가 있을 수 있음):", json.dumps(metrics["hybrid_guarded"]["guard_rejection_reasons"], ensure_ascii=False),
              "", "근거 검증은 특정 형식·라벨·당사자 오류 위험을 줄이는 장치이며 원문 OCR 오류와 모든 의미 오류를 해결하지 않는다. 개선 여부는 조건별 실제 수치로 판단한다."]
    (output / "four_modes.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=PROJECT / "eval/dataset")
    parser.add_argument("--models", nargs="+", default=["qwen3:latest", "gemma3:latest"])
    parser.add_argument("--selected-model")
    parser.add_argument("--benchmark-only", action="store_true")
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    parser.add_argument("--final", action="store_true")
    parser.add_argument("--selection-record", type=Path, default=PROJECT / "docs/eval/dev/comparison/model_comparison.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        # Reject before reading heldout labels or documents. Model selection is DEV only.
        if args.split == "test" and (not args.final or not args.selected_model or args.benchmark_only):
            raise EvaluationNotReady("test는 --final 및 dev에서 선택한 --selected-model이 필요합니다.")
        if args.final and args.split != "test":
            raise EvaluationNotReady("--final은 test에만 허용합니다.")
        if args.final:
            record = json.loads(args.selection_record.read_text(encoding="utf-8"))
            verify_final_selection(args.selected_model, record, OllamaClient(LLMSettings(model=args.selected_model)))
        args.output = args.output or PROJECT / f"docs/eval/{args.split}/{'final' if args.final else 'comparison'}"
        root = args.dataset.resolve()
        manifest_path, labels_path = root / "manifest.json", root / f"ground_truth_{args.split}.json"
        manifest, labels = (json.loads(p.read_text(encoding="utf-8")) for p in (manifest_path, labels_path))
        # Refuse raw proposal persistence outside this known synthetic corpus.
        if manifest.get("dataset_version") != "synthetic-v1" or manifest.get("created_for") != "local-evaluation":
            raise EvaluationNotReady("LLM 응답 캐시는 현재 합성 평가 자료에서만 저장합니다.")
        contracts = validate_labels(manifest, labels, args.split)
        verify_dataset(root, manifest, split=args.split)
        receipt = verify_freeze(manifest_path, labels_path)
        with tempfile.TemporaryDirectory(prefix="llm-dev-evaluation-") as storage:
            os.environ.update(APP_DEPLOYMENT_MODE="pilot", APP_NTS_MODE="disabled", APP_STORAGE_ROOT=storage)
            inputs = collect_inputs(root, contracts)
            cache = args.output / "llm_cache"
            selected = args.selected_model
            if not selected:
                selected, _ = candidate_benchmark(inputs, labels, args.models, args.output, cache, labels_path)
            if args.benchmark_only:
                print("모델 개발 비교 완료: " + selected)
                return 0
            metrics, traces = run_four_modes(inputs, contracts, labels, selected, cache)
            metadata = {"split": args.split, "preliminary": False, "final_test": args.final, "model": selected,
                        "evaluated_at": datetime.now(timezone(timedelta(hours=9))).isoformat(), "settings": asdict(LLMSettings(model=selected)),
                        "labels_sha256": receipt["labels_sha256"], "manifest_sha256": receipt["manifest_sha256"],
                        "label_review": labels["review"], "prompt_version": PROMPT_VERSION, "guard_version": GUARD_VERSION, "same_hybrid_response": True,
                        "nts_mode": "disabled", "classification": "common_rule_classifier"}
            write_comparison(args.output, metadata, metrics, traces)
            print(f"확정 정답 기준 {args.split} 네 조건 비교 완료: " + selected)
        return 0
    except (EvaluationNotReady, ValueError, KeyError, OSError) as exc:
        print("비교 중단: " + type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
