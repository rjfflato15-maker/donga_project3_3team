"""Pure scoring of frozen predictions. No OCR, model, guard, DB or source reads."""
import importlib.util
import json
from collections import Counter
from pathlib import Path


def load_frozen_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_draft(core, manifest, labels):
    review = labels.get("review", {})
    if (review.get("reviewer_type") != "source_reference" or review.get("confirmed") is not False
            or not review.get("author") or not review.get("created_at")
            or labels.get("split") != "test" or labels.get("dataset_version") != manifest["dataset_version"]):
        raise core.EvaluationNotReady("UNCONFIRMED_SOURCE_REFERENCE_REQUIRED")
    contracts = [row for row in manifest["contracts"] if row["split"] == "test"]
    for contract in contracts:
        truth = labels["contracts"][str(contract["contract_id"])]
        slots = {(row["rule_id"], row["field"]) for row in contract["check_slots"]}
        rows = truth["checks"]
        if (not truth.get("source_checked") or not isinstance(truth.get("missing_types"), list)
                or len(rows) != len(slots) or {(r["rule_id"], r["field"]) for r in rows} != slots
                or any(row["status"] not in (*core.CHECK_STATUSES, "N/A") for row in rows)):
            raise core.EvaluationNotReady("INCOMPLETE_DRAFT_CONTRACT")
        for document in contract["documents"]:
            truth = labels["documents"][str(document["document_id"])]
            if not truth.get("source_checked") or truth["document_type"] not in (*core.DOCUMENT_TYPES, "unknown"):
                raise core.EvaluationNotReady("INCOMPLETE_DRAFT_DOCUMENT")
            for field in core.FIELDS:
                answer = truth["fields"][field]
                if answer["state"] not in core.FIELD_STATES:
                    raise core.EvaluationNotReady("INVALID_DRAFT_FIELD_STATE")
                if answer["state"] == "VALUE":
                    if core.normalize(field, answer["value"]) is None:
                        raise core.EvaluationNotReady("INVALID_DRAFT_FIELD_VALUE")
                elif answer["value"] is not None:
                    raise core.EvaluationNotReady("REVIEW_OR_ABSENT_MUST_HAVE_NO_VALUE")
    return contracts


def check_accuracy(labels, prediction):
    correct = scored = not_applicable = 0
    for cid, contract in prediction["contracts"].items():
        expected = {(row["rule_id"], row["field"]): row["status"] for row in labels["contracts"][cid]["checks"]}
        actual = {(row["rule_id"], row["field"]): row["status"] for row in contract["checks"]}
        for key in expected.keys() | actual.keys():
            want, got = expected.get(key, "N/A"), actual.get(key, "N/A")
            if want == got == "N/A":
                not_applicable += 1
            else:
                scored += 1
                correct += want == got
    return {"correct": correct, "scored": scored, "both_not_applicable": not_applicable,
            "accuracy": correct / scored if scored else None}


def guard_outcomes(core, traces, labels):
    counts = Counter()
    referrals = []
    for did, trace in traces.items():
        review = trace.get("review", {})
        targets = review.get("targets", [])
        unresolved = set(targets)
        counts["called_document_count"] += bool(targets)
        for decision in review.get("decisions", []):
            field, proposal = decision["field"], decision["proposal"]
            truth = labels["documents"][did]["fields"][field]
            correct = proposal["state"] == truth["state"] and (proposal["state"] != "VALUE" or
                core.normalize(field, proposal["value"]) == core.normalize(field, truth["value"]))
            disposition = "accepted" if decision["applied"] else "rejected"
            counts[disposition + ("_gold_matching" if correct else "_gold_mismatching")] += 1
            if decision["applied"] and proposal["state"] == "VALUE":
                counts["accepted_value_count"] += 1
                counts["accepted_value_correct"] += correct
            if decision["applied"] and proposal["state"] != "REVIEW":
                unresolved.discard(field)
        counts["requested_field_count"] += len(targets)
        counts["human_referral_field_count"] += len(unresolved)
        if unresolved:
            referrals.append(did)
    counts["accepted_value_precision"] = core.ratio(counts["accepted_value_correct"], counts["accepted_value_count"])
    counts["human_referral_field_rate"] = core.ratio(counts["human_referral_field_count"], counts["requested_field_count"])
    counts["human_referral_document_count"] = len(referrals)
    counts["document_count"] = len(traces)
    counts["human_referral_document_rate"] = core.ratio(len(referrals), len(traces))
    counts["definition"] = "Machine grounding/referral only; human confirmation and measured time savings are separate."
    return dict(counts)


def score(core, manifest, labels, predictions, traces, *, preliminary=False):
    contracts = validate_draft(core, manifest, labels) if preliminary else core.validate_labels(manifest, labels, "test")
    metrics = {}
    for mode, prediction in predictions.items():
        result = core.score_predictions(contracts, labels, prediction)
        checks = check_accuracy(labels, prediction)
        result.update(check_state_accuracy=checks["accuracy"], check_state_counts=checks,
                      mean_document_seconds=sum(row["effective_seconds"] for row in traces[mode].values()) / len(traces[mode]),
                      llm_failure_count=sum(row.get("review", {}).get("status") == "FAILED" for row in traces[mode].values()),
                      unexpected_pass_on_not_applicable=sum(row["kind"] == "check" and row["expected"] == "N/A"
                          and row["actual"] == "PASS" for row in result["failures"]))
        if mode == "hybrid_guarded":
            result["guard_outcomes"] = guard_outcomes(core, traces[mode], labels)
        metrics[mode] = result
    return metrics


def rescore(package, labels_path, *, preliminary=False):
    from backend.prediction_artifacts import verify_package, load_checkpoint
    package, labels_path = Path(package), Path(labels_path)
    receipt = verify_package(package)
    core = load_frozen_module(package / "implementation/backend/evaluation_core.py", "frozen_evaluation_core")
    scorer = load_frozen_module(package / "implementation/backend/prediction_scoring.py", "frozen_prediction_scorer")
    manifest = load_checkpoint(package / "manifest.json")
    predictions = load_checkpoint(package / "predictions.json")
    traces = load_checkpoint(package / "traces.json")
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    freeze = json.loads(labels_path.with_suffix(".freeze.json").read_text(encoding="utf-8"))
    if (freeze.get("labels_sha256") != core.file_hash(labels_path)
            or freeze.get("manifest_sha256") != core.file_hash(package / "source_manifest.json")
            or json.loads((package / "source_manifest.json").read_text(encoding="utf-8")) != manifest):
        raise core.EvaluationNotReady("LABEL_FREEZE_CHANGED")
    metrics = scorer.score(core, manifest, labels, predictions, traces, preliminary=preliminary)
    return {"metadata": {"phase": "preliminary_unconfirmed" if preliminary else "human_confirmed_rescore",
                         "preliminary": preliminary, "prediction_attempt_id": receipt["attempt_id"],
                         "prediction_receipt_sha256": core.file_hash(package / "receipt.json"),
                         "labels_sha256": core.file_hash(labels_path), "label_review": labels["review"],
                         "scoring_code_sha256": core.file_hash(package / "implementation/backend/prediction_scoring.py"),
                         "new_inference_calls": 0, "new_guard_runs": 0}, "metrics": metrics}
