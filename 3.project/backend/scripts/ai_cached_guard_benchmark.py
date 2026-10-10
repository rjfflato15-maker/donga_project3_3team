"""Read-only archived score reproduction and explicitly exploratory cached guard replay.

No original document extraction, OCR, Ollama request, or archived Python execution.
Run each trusted code checkout in a separate process with --code-root.
"""
import argparse
import contextlib
import io
import json
import os
import platform
import statistics
import sys
import tempfile
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from time import perf_counter

PROJECT = Path(__file__).resolve().parents[2]


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def compare_existing(expected, actual, prefix=""):
    """Compare every historical field; allow newly added diagnostic fields."""
    differences = []
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key, value in expected.items():
            location = f"{prefix}.{key}" if prefix else key
            if key not in actual:
                differences.append(location)
            else:
                differences.extend(compare_existing(value, actual[key], location))
    elif expected != actual:
        differences.append(prefix)
    return differences


def implementation_hashes(code_root):
    paths = list((code_root / "backend/app/ai").glob("*.py")) + [
        code_root / "backend/evaluation_core.py", code_root / "backend/prediction_scoring.py",
        code_root / "backend/prediction_artifacts.py", code_root / "backend/scripts/compare_llm_modes.py",
    ]
    return {path.relative_to(code_root).as_posix(): sha256(path.read_bytes()).hexdigest() for path in sorted(paths)}


def load_heldout(archive_root, split):
    from backend import evaluation_core as core
    from backend import prediction_scoring as scorer
    from backend.prediction_artifacts import load_checkpoint, verify_package
    policy = "v3" if split == "test" else "v4"
    package = archive_root / f"docs/eval/{split}/{policy}_predictions"
    dataset = archive_root / ("eval/dataset" if split == "test" else "eval/dataset-v2")
    receipt = verify_package(package)
    labels_path = dataset / "ground_truth_test.json"
    freeze = core.verify_freeze(dataset / "manifest.json", labels_path)
    manifest = load_checkpoint(package / "manifest.json")
    if manifest != read_json(dataset / "manifest.json"):
        raise ValueError("FROZEN_MANIFEST_MISMATCH")
    labels = read_json(labels_path)
    core.validate_labels(manifest, labels, "test")
    predictions, traces = (load_checkpoint(package / name) for name in ("predictions.json", "traces.json"))
    metrics = scorer.score(core, manifest, labels, predictions, traces)
    archived_scores = sorted((package.parent / f"{policy}_scores").glob("human_confirmed_rescore_*.json"))
    archived_scores = [path for path in archived_scores if read_json(path).get("metadata", {}).get("labels_sha256") == freeze["labels_sha256"]]
    if len(archived_scores) != 1:
        raise ValueError("EXPECTED_ONE_MATCHING_ARCHIVED_SCORE")
    archived_score = read_json(archived_scores[0])
    differences = compare_existing(archived_score["metrics"], metrics)
    official = {"comparison": "all_existing_metric_fields", "reproduced": not differences,
                "differing_metric_paths": differences, "metrics": metrics,
                "archived_score_sha256": core.file_hash(archived_scores[0]),
                "prediction_receipt_sha256": core.file_hash(package / "receipt.json"),
                "labels_sha256": freeze["labels_sha256"], "manifest_sha256": freeze["manifest_sha256"],
                "review_method": labels["review"].get("review_method"),
                "human_full_review": labels["review"].get("human_full_review"),
                "frozen_package_files_verified": len(receipt["files_sha256"])}
    return package, labels, traces, official, policy


def replay(package, labels, traces, policy, *, repeat):
    from backend import evaluation_core as core
    from backend.app.ai.llm_supplement import apply_proposals
    from backend.prediction_artifacts import load_checkpoint, digest
    from backend.scripts.compare_llm_modes import field_accuracy, guard_outcomes
    inputs = {path.stem: load_checkpoint(path) for path in sorted((package / "inputs").glob("*.json"))}
    if set(inputs) != set(traces["hybrid_guarded"]):
        raise ValueError("CACHED_INPUT_COVERAGE_MISMATCH")
    fields, current_traces, changes, timings = {}, {}, [], []
    replay_definition = []
    for did, item in inputs.items():
        original_trace = traces["hybrid_guarded"][did]
        key = original_trace["response_id"]
        if key is None:
            if item["targets"]:
                raise ValueError("TARGETS_WITHOUT_CACHED_RESPONSE")
            run = {"ok": True, "proposals": {}, "elapsed_seconds": 0}
        else:
            cached = load_checkpoint(package / "responses" / (key + ".json"))
            request = load_checkpoint(package / "requests" / (key + ".json"))
            if cached["request_sha256"] != key or request["request_sha256"] != key:
                raise ValueError("CACHED_RESPONSE_ID_MISMATCH")
            expected_request = request["request"]
            visible_pages = [{k: page[k] for k in ("page", "location_kind", "text")} for page in item["pages"]]
            if (digest(expected_request) != key or expected_request["pages"] != visible_pages
                    or expected_request["targets"] != item["targets"]
                    or expected_request["document_type"] != item["document_type"]):
                raise ValueError("CACHED_REQUEST_INPUT_MISMATCH")
            run = cached["run"]
        replay_definition.append({"document_id": did, "pages": item["pages"], "fields": item["fields"],
                                  "targets": item["targets"], "document_type": item["document_type"], "run": run})
        prior_result = None
        for _ in range(repeat):
            started = perf_counter()
            values, review = apply_proposals(item["fields"], run, item["pages"], item["document_type"],
                                             item["targets"], guard_policy=policy)
            timings.append(perf_counter() - started)
            result = digest({"fields": values, "review": review})
            if prior_result is not None and result != prior_result:
                raise ValueError("NONDETERMINISTIC_GUARD_REPLAY")
            prior_result = result
        fields[did] = values
        current_traces[did] = {"review": review, "response_id": key}
        old = {row["field"]: row for row in original_trace["review"]["decisions"]}
        new_fields = {row["field"] for row in review["decisions"]}
        for missing in sorted(set(old) - new_fields):
            changes.append({"document_id": did, "field": missing, "old_applied": old[missing]["applied"],
                            "new_applied": None, "old_reasons": old[missing]["reasons"],
                            "new_reasons": ["DECISION_MISSING"]})
        for decision in review["decisions"]:
            previous = old.get(decision["field"])
            if previous is None or previous["proposal"] != decision["proposal"]:
                raise ValueError("CACHED_PROPOSAL_CHANGED")
            if previous["applied"] != decision["applied"] or previous["reasons"] != decision["reasons"]:
                changes.append({"document_id": did, "field": decision["field"],
                                "old_applied": previous["applied"], "new_applied": decision["applied"],
                                "old_reasons": previous["reasons"], "new_reasons": decision["reasons"]})
    ordered = sorted(timings)
    return {"scope": "Exploratory held-out reuse; not a fresh independent final evaluation.",
            "policy": policy, "document_count": len(inputs), "repeat": repeat,
            "same_inputs_sha256": digest(replay_definition), "decision_trace_sha256": digest(current_traces),
            "decisions_sha256": digest({did: row["review"]["decisions"] for did, row in current_traces.items()}),
            "field_predictions_sha256": digest(fields), "field_metrics": field_accuracy(inputs, labels, fields),
            "guard_outcomes": guard_outcomes(current_traces, labels), "changes_from_archived_decisions": changes,
            "new_ocr_calls": 0, "new_model_calls": 0, "new_rule_extraction_calls": 0,
            "contract_checks": "not_recomputed_for_exploratory_fields",
            "guard_call_seconds": {"samples": len(timings), "mean": statistics.mean(timings),
                                   "p50": statistics.median(timings),
                                   "p95": ordered[max(0, (95 * len(ordered) + 99) // 100 - 1)]},
            "timing_definition": "Local apply_proposals only, includes empty-target calls and first-call costs; no import/OCR/model/contract-check time. No hardware speedup claim."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-root", required=True, type=Path)
    parser.add_argument("--code-root", type=Path, default=PROJECT)
    parser.add_argument("--split", choices=("test", "test2"), required=True)
    parser.add_argument("--replay", action="store_true", help="Explicit exploratory reuse of held-out cached inputs after code is fixed")
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    root, code, output = args.archive_root.resolve(), args.code_root.resolve(), args.output.resolve()
    protected = [root, code / "eval", code / "docs/eval", code / "storage"]
    if any(output.is_relative_to(path.resolve()) for path in protected) or output.exists() or output.suffix.lower() != ".json":
        parser.error("Output must be a new JSON outside immutable datasets/reports and customer storage")
    if not 1 <= args.repeat <= 100:
        parser.error("repeat must be 1..100")
    sys.path.insert(0, str(code))
    before = implementation_hashes(code)
    try:
        with tempfile.TemporaryDirectory(prefix="cpilot-cached-benchmark-") as storage:
            os.environ.update(APP_DEPLOYMENT_MODE="pilot", APP_NTS_MODE="disabled", APP_LLM_ENABLED="false",
                              APP_VLM_ENABLED="false", APP_STORAGE_ROOT=storage)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                package, labels, traces, official, policy = load_heldout(root, args.split)
                explored = replay(package, labels, traces, policy, repeat=args.repeat) if args.replay else None
                # Revalidate the exact frozen package and label artifacts after all reads.
                _, _, _, rechecked, _ = load_heldout(root, args.split)
                if rechecked != official:
                    raise ValueError("FROZEN_INPUTS_CHANGED_DURING_RUN")
        unchanged = before == implementation_hashes(code)
        payload = {"schema_version": "cpilot-cached-benchmark-v1", "created_at": datetime.now(timezone.utc).isoformat(),
                   "split": args.split, "python": platform.python_version(), "platform": platform.platform(),
                   "source_sha256": before, "source_unchanged_during_run": unchanged,
                   "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
                   "archive_python_executed": False, "frozen_package_and_labels_reverified_after_run": True,
                   "original_documents_opened_for_extraction": False,
                   "official_frozen_scores": official, "exploratory_cached_replay": explored}
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        print(json.dumps({"output": str(output), "split": args.split, "official_scores_reproduced": official["reproduced"],
                          "source_unchanged": unchanged, "exploratory_replay": explored is not None}, indent=2))
        return 0 if unchanged and official["reproduced"] else 1
    except (OSError, ValueError, KeyError, ImportError) as exc:
        print(f"Cached benchmark stopped: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
