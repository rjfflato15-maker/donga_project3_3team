"""Execute the locked v4 test2 policy once, using the existing durable runner.

Preflight checks only human receipts and file hashes, never answer values.
The --check path opens no heldout originals and performs no model extraction.
"""
import json
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from time import perf_counter

from backend import evaluation_predictions as durable
from backend.evaluation_core import EvaluationNotReady, verify_dataset, verify_freeze
from backend.prediction_artifacts import file_hash


def normalized_hash(path):
    return sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def human_receipt(project, dataset, manifest_path):
    labels = dataset / "ground_truth_test.json"
    frozen = labels.with_suffix(".freeze.json")
    if not labels.is_file() or not frozen.is_file():
        return None
    receipt = verify_freeze(manifest_path, labels)
    if (receipt.get("confirmed") is not True or receipt.get("reviewer_type") != "human"
            or not receipt.get("reviewer") or not receipt.get("confirmed_at")
            or receipt.get("human_direct_count", 0) <= 0
            or receipt.get("human_direct_count") != receipt.get("required_human_count")
            or not receipt.get("human_result_sha256")):
        raise EvaluationNotReady("TEST2_ACTUAL_HUMAN_CONFIRMATION_REQUIRED")
    name = str(receipt.get("human_result_file", ""))
    source = (project / "eval/human_reviews/test2" / name).resolve()
    human_root = (project / "eval/human_reviews/test2").resolve()
    if (not name or not source.is_relative_to(human_root) or not source.is_file()
            or file_hash(source) != receipt["human_result_sha256"]):
        raise EvaluationNotReady("TEST2_HUMAN_RESULT_PROVENANCE_CHANGED")
    return {key: receipt[key] for key in ("labels_sha256", "human_result_sha256", "reviewer",
        "confirmed_at", "human_direct_count", "ai_agreement_count")}


def verify_policy(project, dataset, release_path):
    project, dataset, release_path = Path(project), Path(dataset), Path(release_path)
    release = json.loads(release_path.read_text(encoding="utf-8"))
    if (release.get("release_version") != "guard-v4-test2-fixed" or release.get("frozen") is not True
            or release.get("guard_policy") != "v4" or release.get("nts_mode") != "disabled"
            or release.get("guard_version") != "grounding-v4-dev2"
            or release.get("code_hash_policy") != "SHA256 with CRLF normalized to LF"
            or release.get("test2_sources_used_for_tuning") is not False):
        raise EvaluationNotReady("LOCKED_V4_TEST2_POLICY_REQUIRED")
    expected_paths = {*(p.relative_to(project).as_posix() for p in (project / "backend/app/ai").glob("*.py")),
                      *(p.relative_to(project).as_posix() for p in (project / "backend/app/validation").glob("*.py")),
        "backend/app/config.py", "backend/app/integrations/nts_client.py", "backend/app/schemas/common.py",
        "backend/app/schemas/document.py", "backend/app/schemas/validation.py", "backend/evaluation_core.py",
        "backend/scripts/compare_llm_modes.py"}
    hashes = release.get("implementation_sha256", {})
    if set(hashes) != expected_paths:
        raise EvaluationNotReady("TEST2_POLICY_COVERAGE_CHANGED")
    for name, expected in hashes.items():
        source = (project / name).resolve()
        if not source.is_relative_to(project.resolve()) or normalized_hash(source) != expected:
            raise EvaluationNotReady("TEST2_POLICY_IMPLEMENTATION_CHANGED: " + name)
    manifest_path = dataset / "manifest.json"
    if file_hash(manifest_path) != release["manifest_sha256"]:
        raise EvaluationNotReady("TEST2_MANIFEST_CHANGED")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    contracts = [c for c in manifest.get("contracts", []) if c.get("split") == "test"]
    if (manifest.get("dataset_version") != "synthetic-hard-v2" or manifest.get("created_for") != "local-evaluation"
            or not contracts or any(c["contract_id"] // 100 != 4 for c in contracts)):
        raise EvaluationNotReady("ONLY_HARD_V2_TEST2_ALLOWED")
    return manifest, release


def preflight(project, dataset, release_path, *, client=None, check_only=False):
    project, dataset = Path(project), Path(dataset)
    manifest, release = verify_policy(project, dataset, release_path)
    human = human_receipt(project, dataset, dataset / "manifest.json")
    if not check_only and human is None:
        raise EvaluationNotReady("TEST2_HUMAN_REVIEW_PENDING")
    from backend.app.ai.local_llm import LLMSettings, OllamaClient, PROMPT_VERSION
    from backend.app.ai.grounding_v4 import GUARD_VERSION
    client = client or OllamaClient(LLMSettings(**release["settings"]))
    if (asdict(client.settings) != release["settings"] or PROMPT_VERSION != release["prompt_version"]
            or GUARD_VERSION != release["guard_version"] or client.model_metadata()["digest"] != release["model_digest"]):
        raise EvaluationNotReady("TEST2_MODEL_PROMPT_OR_SETTINGS_CHANGED")
    cloud = Path.home() / ".ollama/server.json"
    if not cloud.is_file() or json.loads(cloud.read_text(encoding="utf-8-sig")).get("disable_ollama_cloud") is not True:
        raise EvaluationNotReady("CLOUD_DISABLE_CONFIG_REQUIRED")
    report = {"checked_at": durable.now(), "environment": durable.environment_receipt(),
        "settings": asdict(client.settings), "model_metadata": client.model_metadata(),
        "release_version": release["release_version"], "guard_policy": "v4", "nts_mode": "disabled",
        "labels_read": False, "answer_values_read": False, "human_confirmation": human,
        "human_review_ready": human is not None, "cloud_disable_config": True,
        "heldout_originals_opened": not check_only, "new_extraction_calls": 0}
    if check_only:
        return manifest, release, client, report
    verify_dataset(dataset, manifest, split="test")
    # A small artificial input is independent of both evaluation corpora.
    run = client.extract([{"page": 1, "location_kind": "page", "text": "견적서\n합계금액: 1100원"}],
                         ["total_amount"], "estimate")
    proposal = run.get("proposals", {}).get("total_amount", {})
    if not run.get("ok") or proposal.get("state") != "VALUE" or str(proposal.get("value")) != "1100":
        raise EvaluationNotReady("DEV_SMOKE_FAILED")
    report["dev_smoke"] = {"ok": True, "run_sha256": durable.digest(run), "elapsed_seconds": run["elapsed_seconds"]}
    report["new_extraction_calls"] = 1
    return manifest, release, client, report


def predict_one(client, item, output, attempt_id):
    from backend.app.ai.local_llm import CORE_FIELDS
    from backend.app.ai.llm_supplement import apply_proposals
    fields = {"rule": item["fields"]}
    traces = {"rule": {"effective_seconds": item["rule_seconds"], "guard_seconds": 0}}
    run, key, hit = durable.request_once(client, item, CORE_FIELDS, output, attempt_id)
    fields["llm"], review = apply_proposals(item["fields"], run, item["pages"], item["document_type"],
                                          CORE_FIELDS, guarded=False, llm_only=True, guard_policy="v4")
    traces["llm"] = {"review": review, "response_id": key, "cache_hit": hit, "guard_seconds": 0,
                     "effective_seconds": item["rule_seconds"] + run["elapsed_seconds"]}
    if item["targets"]:
        run, key, hit = durable.request_once(client, item, item["targets"], output, attempt_id)
    else:
        run, key, hit = {"ok": True, "proposals": {}, "elapsed_seconds": 0}, None, False
    for mode in ("hybrid_unguarded", "hybrid_guarded"):
        started = perf_counter()
        fields[mode], review = apply_proposals(item["fields"], run, item["pages"], item["document_type"],
            item["targets"], guarded=mode == "hybrid_guarded", guard_policy="v4")
        seconds = perf_counter() - started if mode == "hybrid_guarded" else 0
        traces[mode] = {"review": review, "response_id": key, "cache_hit": hit, "guard_seconds": seconds,
            "shared_response_replay": mode == "hybrid_guarded",
            "effective_seconds": item["rule_seconds"] + run["elapsed_seconds"] + seconds}
    return {"fields": fields, "traces": traces}


def postflight(project, dataset, release_path, client):
    _, release = verify_policy(project, dataset, release_path)
    if client.model_metadata()["digest"] != release["model_digest"]:
        raise EvaluationNotReady("TEST2_MODEL_CHANGED_DURING_RUN")


def run(project, dataset, output, release_path, *, resume=False, **kwargs):
    result = durable.run_predictions(project, dataset, output, release_path, resume=resume,
        preflight_fn=preflight, predictor=predict_one,
        snapshot_paths=("backend/test2_predictions.py", "backend/scripts/predict_test2_locked.py"),
        postflight_fn=postflight, snapshot_all_app=False, **kwargs)
    if result.get("release_version") != "guard-v4-test2-fixed" or result.get("guard_policy") != "v4":
        raise EvaluationNotReady("SEALED_PACKAGE_IS_NOT_V4_TEST2")
    return result
