import json
from pathlib import Path

import pytest

from backend import evaluation_predictions as runner
from backend.app.ai.local_llm import LLMSettings, CORE_FIELDS
from backend.prediction_artifacts import ArtifactError, digest, file_hash, load_checkpoint, save_checkpoint, write_json, verify_package
from backend.prediction_scoring import rescore


def fake_client():
    class Client:
        settings = LLMSettings()
        calls = 0

        def model_metadata(self):
            return {"digest": "frozen-model"}

        def extract(self, pages, fields, document_type):
            self.calls += 1
            return {"ok": True, "proposals": {field: {"state": "VALUE", "value": "1100", "page": 1,
                    "line": 2, "quote": "합계금액: 1100원"} for field in fields}, "elapsed_seconds": 2}
    return Client()


def item():
    return {"document_type": "estimate", "pages": [{"page": 1, "location_kind": "page", "text": "견적서\n합계금액: 1100원"}],
            "fields": {"total_amount": None, "amount": None, "amount_basis": "UNKNOWN", "amount_scope": "UNKNOWN"},
            "targets": ["total_amount"], "rule_seconds": .1}


def test_durable_response_is_reused_and_tampering_is_rejected(tmp_path):
    client = fake_client()
    first, key, hit = runner.request_once(client, item(), ["total_amount"], tmp_path, "one")
    second, other_key, other_hit = runner.request_once(client, item(), ["total_amount"], tmp_path, "one")
    assert first == second and key == other_key and not hit and other_hit and client.calls == 1
    response = tmp_path / "responses" / (key + ".json")
    body = json.loads(response.read_text(encoding="utf-8"))
    body["payload"]["run"]["proposals"]["total_amount"]["value"] = "9000"
    response.write_text(json.dumps(body))
    with pytest.raises(ArtifactError, match="CHECKPOINT_CHANGED"):
        runner.request_once(client, item(), ["total_amount"], tmp_path, "one")


def test_pending_request_after_crash_is_not_sent_again(tmp_path):
    client = fake_client()
    def killed(*args):
        client.calls += 1
        raise KeyboardInterrupt()
    client.extract = killed
    with pytest.raises(KeyboardInterrupt):
        runner.request_once(client, item(), ["total_amount"], tmp_path, "one")
    client.extract = lambda *args: pytest.fail("unknown completed request must not be repeated")
    run, _, _ = runner.request_once(client, item(), ["total_amount"], tmp_path, "one")
    assert run["error"] == "INTERRUPTED_RESPONSE_UNKNOWN" and not run["ok"] and client.calls == 1


def test_guard_conditions_share_same_response(tmp_path):
    client = fake_client()
    result = runner.predict_one(client, item(), tmp_path, "one")
    assert client.calls == 2  # All fields, then supplementary fields; each once.
    traces = result["traces"]
    assert traces["hybrid_guarded"]["response_id"] == traces["hybrid_unguarded"]["response_id"]
    assert result["fields"]["hybrid_guarded"]["total_amount"] == 1100


def test_repeat_attempt_rejected_before_preflight_or_heldout_read(tmp_path, monkeypatch):
    write_json(tmp_path / "final_evaluation_attempt.json", {"status": "predictions_frozen"})
    monkeypatch.setattr(runner, "preflight", lambda *a, **kw: pytest.fail("must reject first"))
    with pytest.raises(ValueError, match="HELDOUT_ATTEMPT_EXISTS"):
        runner.run_predictions(tmp_path, tmp_path, tmp_path / "different-output", tmp_path / "release.json")


def test_resume_cannot_change_release_or_output(tmp_path):
    release = tmp_path / "release.json"
    write_json(release, {"frozen": True})
    manifest = {"test": "fixture"}
    write_json(tmp_path / "manifest.json", manifest)
    output = tmp_path / "out"
    runner.reserve(tmp_path, output, release, manifest, {})
    with pytest.raises(ValueError, match="RESUME_MUST_USE_SAME_ATTEMPT"):
        runner.reserve(tmp_path, tmp_path / "new-output", release, manifest, {}, resume=True)
    write_json(release, {"frozen": False})
    with pytest.raises(ValueError, match="RESUME_MUST_USE_SAME_ATTEMPT"):
        runner.reserve(tmp_path, output, release, manifest, {}, resume=True)


def test_active_process_lock_cannot_be_bypassed(tmp_path, monkeypatch):
    write_json(tmp_path / "prediction_process.lock", {"pid": 1})
    monkeypatch.setattr(runner, "preflight", lambda *a, **kw: pytest.fail("must reject first"))
    with pytest.raises(ValueError, match="PREDICTION_PROCESS_ALREADY_RUNNING"):
        runner.run_predictions(tmp_path, tmp_path, tmp_path / "out", tmp_path / "release", resume=True)


def make_scoring_package(tmp_path):
    package = tmp_path / "frozen"
    package.mkdir()
    manifest = {"dataset_version": "test-fixture", "contracts": [{"contract_id": 1, "split": "test",
                "documents": [{"document_id": 2}], "check_slots": []}]}
    save_checkpoint(package / "manifest.json", manifest)
    write_json(package / "source_manifest.json", manifest)
    save_checkpoint(package / "release.json", {})
    values = {field: None for field in CORE_FIELDS}
    values.update(company_name="가상회사", amount_scope="UNKNOWN")
    predictions = {mode: {"documents": {"2": {"document_type": "estimate", "fields": values}},
                         "contracts": {"1": {"checks": []}}} for mode in runner.MODES}
    traces = {mode: {"2": {"effective_seconds": 1, "review": {"targets": [], "decisions": []}}} for mode in runner.MODES}
    save_checkpoint(package / "predictions.json", predictions)
    save_checkpoint(package / "traces.json", traces)
    root = Path(__file__).resolve().parents[2]
    for name in ("evaluation_core.py", "prediction_scoring.py"):
        target = package / "implementation/backend" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((root / "backend" / name).read_bytes())
    receipt = {"format": "heldout-predictions-v1", "attempt_id": "one", "files_sha256": {
        path.relative_to(package).as_posix(): file_hash(path) for path in package.rglob("*") if path.is_file()}}
    write_json(package / "receipt.json", receipt)
    labels = {"dataset_version": "test-fixture", "split": "test",
              "review": {"reviewer_type": "source_reference", "confirmed": False, "author": "fixture", "created_at": "fixture"},
              "documents": {"2": {"document_type": "estimate", "source_checked": True,
                            "fields": {field: {"state": "ABSENT", "value": None} for field in CORE_FIELDS}}},
              "contracts": {"1": {"source_checked": True, "missing_types": [], "checks": []}}}
    labels["documents"]["2"]["fields"]["company_name"] = {"state": "VALUE", "value": "가상회사"}
    path = tmp_path / "labels.json"
    write_labels(package, path, labels)
    return package, path, labels


def write_labels(package, path, labels):
    write_json(path, labels)
    write_json(path.with_suffix(".freeze.json"), {"labels_sha256": file_hash(path),
               "manifest_sha256": file_hash(package / "source_manifest.json")})


def test_rescore_uses_frozen_values_and_never_calls_live_model_or_guard(tmp_path, monkeypatch):
    package, path, labels = make_scoring_package(tmp_path)
    monkeypatch.setattr(runner, "apply_proposals", lambda *a, **kw: pytest.fail("guard must not execute"))
    monkeypatch.setattr(runner, "collect_one", lambda *a, **kw: pytest.fail("OCR must not execute"))
    monkeypatch.setattr(runner.OllamaClient, "extract", lambda *a, **kw: pytest.fail("LLM must not execute"))
    before = file_hash(package / "receipt.json")
    first = rescore(package, path, preliminary=True)
    assert first["metrics"]["rule"]["field_accuracy"] == 1
    labels["documents"]["2"]["fields"]["company_name"]["value"] = "사람이 고친 회사"
    write_labels(package, path, labels)
    second = rescore(package, path, preliminary=True)
    assert second["metrics"]["rule"]["field_accuracy"] == 0
    assert second["metadata"]["new_inference_calls"] == 0 and file_hash(package / "receipt.json") == before


def test_unconfirmed_labels_cannot_be_called_final(tmp_path):
    package, path, _ = make_scoring_package(tmp_path)
    with pytest.raises(ValueError):
        rescore(package, path)


def test_frozen_prediction_and_label_receipt_tampering_are_detected(tmp_path):
    package, path, labels = make_scoring_package(tmp_path)
    path.write_text(json.dumps({**labels, "split": "dev"}))
    with pytest.raises(ValueError, match="LABEL_FREEZE_CHANGED"):
        rescore(package, path, preliminary=True)
    (package / "predictions.json").write_text("{}")
    with pytest.raises(ArtifactError, match="FROZEN_PACKAGE_CHANGED"):
        verify_package(package)


def test_exclusive_publication_does_not_overwrite_previous_checkpoint(tmp_path):
    path = tmp_path / "input.json"
    save_checkpoint(path, {"value": 1})
    with pytest.raises(FileExistsError):
        save_checkpoint(path, {"value": 2})
    assert load_checkpoint(path) == {"value": 1}


def test_full_prediction_attempt_reads_no_labels_and_resume_after_sealing_calls_nothing(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    document = {"document_id": 2, "path": "test/document.txt", "sha256": "fixture"}
    contract = {"contract_id": 1, "split": "test", "documents": [document], "input": {
        "title": "가상 계약", "vendor_name": "가상회사", "business_number": "0000000000", "contract_amount": 1100,
        "amount_policy": {"amount_basis": "TOTAL", "tax_amount": None, "payment_mode": "FULL"}}}
    manifest = {"dataset_version": "synthetic-v1", "contracts": [contract]}
    write_json(tmp_path / "manifest.json", manifest)
    release = tmp_path / "release.json"
    write_json(release, {"implementation_sha256": {}})
    client = fake_client()
    monkeypatch.setattr(runner, "preflight", lambda *a, **kw: (manifest, {"implementation_sha256": {}}, client, {}))
    def collect(*args):
        return {**item(), "document": document, "processing_failed": False}
    output = tmp_path / "out"
    receipt = runner.run_predictions(root, tmp_path, output, release, collector=collect)
    assert client.calls == 2 and receipt["labels_read"] is False and receipt["document_count"] == 1
    assert verify_package(output)["attempt_id"] == receipt["attempt_id"]
    # Recover a crash between publishing the sealed receipt and finishing its marker.
    marker = tmp_path / "final_evaluation_attempt.json"
    attempt = json.loads(marker.read_text(encoding="utf-8"))
    attempt["status"] = "started"
    write_json(marker, attempt)
    monkeypatch.setattr(runner, "preflight", lambda *a, **kw: pytest.fail("sealed resume must call nothing"))
    assert runner.run_predictions(root, tmp_path, output, release, resume=True) == receipt
    assert client.calls == 2
