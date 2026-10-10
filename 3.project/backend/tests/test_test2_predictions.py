import json
from dataclasses import asdict
from pathlib import Path

import pytest

from backend import test2_predictions as runner
from backend.app.ai.local_llm import LLMSettings
from backend.prediction_artifacts import file_hash, write_json, verify_package


PROJECT = Path(__file__).resolve().parents[2]


class Client:
    settings = LLMSettings()
    calls = 0

    def model_metadata(self):
        return {"digest": "fixture-model"}

    def extract(self, pages, fields, document_type):
        self.calls += 1
        return {"ok": True, "elapsed_seconds": 2,
            "proposals": {field: {"state": "VALUE", "value": "1100", "page": 1,
                "line": 2, "quote": "합계금액: 1100원"} for field in fields}}


def fixture_policy(tmp_path):
    project = tmp_path / "project"
    dataset = project / "eval/dataset-v2"
    write_json(dataset / "manifest.json", {"dataset_version": "synthetic-hard-v2", "created_for": "local-evaluation",
        "contracts": [{"contract_id": 401, "split": "test", "documents": []}]})
    names = ("backend/app/config.py", "backend/app/integrations/nts_client.py", "backend/app/schemas/common.py",
        "backend/app/schemas/document.py", "backend/app/schemas/validation.py", "backend/evaluation_core.py",
        "backend/scripts/compare_llm_modes.py")
    (project / "backend/app/ai").mkdir(parents=True)
    (project / "backend/app/validation").mkdir(parents=True)
    for name in names:
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# fixture\n", encoding="utf-8")
    release = {"release_version": "guard-v4-test2-fixed", "frozen": True, "guard_policy": "v4",
        "nts_mode": "disabled", "guard_version": "grounding-v4-dev2", "prompt_version": "grounded-fields-v3",
        "code_hash_policy": "SHA256 with CRLF normalized to LF", "test2_sources_used_for_tuning": False,
        "implementation_sha256": {name: runner.normalized_hash(project / name) for name in names},
        "manifest_sha256": file_hash(dataset / "manifest.json"), "settings": asdict(Client.settings),
        "model_digest": "fixture-model"}
    release_path = project / "release.json"
    write_json(release_path, release)
    return project, dataset, release_path


def test_missing_human_review_blocks_before_source_or_model_work(tmp_path, monkeypatch):
    project, dataset, release = fixture_policy(tmp_path)
    monkeypatch.setattr(runner, "verify_dataset", lambda *a, **kw: pytest.fail("heldout originals must remain unopened"))
    client = Client()
    client.model_metadata = lambda: pytest.fail("model work must not start before human gate")
    with pytest.raises(ValueError, match="TEST2_HUMAN_REVIEW_PENDING"):
        runner.preflight(project, dataset, release, client=client)
    assert client.calls == 0


def test_check_mode_uses_receipts_without_reading_originals_or_extracting(tmp_path, monkeypatch):
    project, dataset, release = fixture_policy(tmp_path)
    # This test exercises the historical locked policy's receipts. Current
    # production guard revisions must not masquerade as that frozen release.
    monkeypatch.setattr("backend.app.ai.grounding_v4.GUARD_VERSION", "grounding-v4-dev2")
    monkeypatch.setattr("backend.app.ai.local_llm.PROMPT_VERSION", "grounded-fields-v3")
    monkeypatch.setattr(runner, "verify_dataset", lambda *a, **kw: pytest.fail("check must not open sources"))
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "user")
    write_json(tmp_path / "user/.ollama/server.json", {"disable_ollama_cloud": True})
    client = Client()
    client.extract = lambda *a: pytest.fail("check must not invoke extraction")
    report = runner.preflight(project, dataset, release, client=client, check_only=True)[3]
    assert report["human_review_ready"] is False and report["new_extraction_calls"] == 0
    assert report["answer_values_read"] is False and report["heldout_originals_opened"] is False
    # The human gate hashes label bytes without parsing any answer values.
    labels = dataset / "ground_truth_test.json"
    labels.write_text("fixture: answer values deliberately unavailable as JSON")
    result = project / "eval/human_reviews/test2/fixture.json"
    write_json(result, {"fixture": True})
    proof = {"labels_sha256": file_hash(labels), "manifest_sha256": file_hash(dataset / "manifest.json"),
        "confirmed": True, "reviewer_type": "human", "reviewer": "fixture", "confirmed_at": "fixture",
        "human_direct_count": 81, "required_human_count": 81, "ai_agreement_count": 459,
        "human_result_file": "fixture.json", "human_result_sha256": file_hash(result)}
    write_json(labels.with_suffix(".freeze.json"), proof)
    assert runner.preflight(project, dataset, release, client=client, check_only=True)[3]["human_review_ready"] is True
    result.write_text("changed")
    with pytest.raises(ValueError, match="TEST2_HUMAN_RESULT_PROVENANCE_CHANGED"):
        runner.preflight(project, dataset, release, client=client, check_only=True)


def test_current_guard_revision_cannot_use_historical_test2_lock(tmp_path, monkeypatch):
    project, dataset, release = fixture_policy(tmp_path)
    monkeypatch.setattr("backend.app.ai.grounding_v4.GUARD_VERSION", "grounding-v4-coverage-20261009")
    client = Client()
    with pytest.raises(ValueError, match="TEST2_MODEL_PROMPT_OR_SETTINGS_CHANGED"):
        runner.preflight(project, dataset, release, client=client, check_only=True)
    assert client.calls == 0


def test_changed_policy_cannot_start_test2(tmp_path):
    project, dataset, release = fixture_policy(tmp_path)
    (project / "backend/app/config.py").write_text("# changed after lock\n")
    with pytest.raises(ValueError, match="TEST2_POLICY_IMPLEMENTATION_CHANGED"):
        runner.preflight(project, dataset, release, client=Client())


def test_v4_is_explicit_and_guarded_modes_share_one_response(tmp_path, monkeypatch):
    from backend.app.ai import llm_supplement
    policies = []
    def apply(fields, response, pages, kind, targets, **kwargs):
        policies.append((kwargs["guard_policy"], kwargs["guarded"]))
        return fields, {"targets": list(targets)}
    monkeypatch.setattr(llm_supplement, "apply_proposals", apply)
    client = Client()
    item = {"pages": [{"page": 1, "location_kind": "page", "text": "견적서\n합계금액: 1100원"}],
        "document_type": "estimate", "fields": {}, "targets": ["total_amount"], "rule_seconds": .1}
    output = runner.predict_one(client, item, tmp_path, "fixture")
    assert client.calls == 2 and policies == [("v4", False), ("v4", False), ("v4", True)]
    assert output["traces"]["hybrid_guarded"]["response_id"] == output["traces"]["hybrid_unguarded"]["response_id"]


@pytest.mark.parametrize("changed_during_run", [False, True])
def test_v4_package_seals_once_and_sealed_resume_uses_no_ocr_or_model(tmp_path, monkeypatch, changed_during_run):
    dataset = tmp_path / "dataset"
    document = {"document_id": 40101, "path": "test2/document.txt", "sha256": "fixture"}
    contract = {"contract_id": 401, "split": "test", "documents": [document], "input": {
        "title": "fixture", "vendor_name": "가상회사", "business_number": "0000000000", "contract_amount": 1100,
        "amount_policy": {"amount_basis": "TOTAL", "tax_amount": None, "payment_mode": "FULL"}}}
    manifest = {"dataset_version": "synthetic-hard-v2", "contracts": [contract]}
    write_json(dataset / "manifest.json", manifest)
    release = tmp_path / "release.json"
    definition = {"implementation_sha256": {}, "release_version": "guard-v4-test2-fixed", "guard_policy": "v4"}
    write_json(release, definition)
    client = Client()
    monkeypatch.setattr(runner, "preflight", lambda *a, **kw: (manifest, definition, client, {}))
    def postflight(*a):
        if changed_during_run:
            raise runner.EvaluationNotReady("TEST2_POLICY_IMPLEMENTATION_CHANGED")
    monkeypatch.setattr(runner, "postflight", postflight)
    def collector(*a):
        return {"document": document, "pages": [{"page": 1, "location_kind": "page", "text": "견적서\n합계금액: 1100원"}],
            "document_type": "estimate", "fields": {"total_amount": None, "amount": None, "amount_basis": "UNKNOWN",
                "amount_scope": "UNKNOWN"}, "targets": ["total_amount"], "rule_seconds": .1, "processing_failed": False}
    output = tmp_path / "frozen"
    if changed_during_run:
        with pytest.raises(ValueError, match="TEST2_POLICY_IMPLEMENTATION_CHANGED"):
            runner.run(PROJECT, dataset, output, release, client=client, collector=collector)
        assert not (output / "receipt.json").exists() and client.calls == 2
        assert json.loads((dataset / "final_evaluation_attempt.json").read_text())["status"] == "interrupted"
        return
    receipt = runner.run(PROJECT, dataset, output, release, client=client, collector=collector)
    assert receipt["guard_policy"] == "v4" and receipt["labels_read"] is False and client.calls == 2
    assert verify_package(output) == receipt
    with pytest.raises(ValueError, match="HELDOUT_ATTEMPT_EXISTS"):
        runner.run(PROJECT, dataset, tmp_path / "different", release)
    # Recover only the marker after a crash, never repeat any inference.
    marker = dataset / "final_evaluation_attempt.json"
    attempt = json.loads(marker.read_text(encoding="utf-8"))
    attempt["status"] = "started"
    write_json(marker, attempt)
    monkeypatch.setattr(runner, "preflight", lambda *a, **kw: pytest.fail("sealed resume must run nothing"))
    assert runner.run(PROJECT, dataset, output, release, resume=True) == receipt
    assert client.calls == 2
