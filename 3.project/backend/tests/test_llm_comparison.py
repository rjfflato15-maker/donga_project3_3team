import json
from types import SimpleNamespace

import pytest

from backend.evaluation_core import EvaluationNotReady
from backend.scripts.compare_llm_modes import check_accuracy, main, request_cached, verify_final_selection, guard_outcomes
from backend.app.ai.local_llm import LLMSettings, PROMPT_VERSION
from backend.app.ai.grounding import GUARD_VERSION


def test_shared_cache_reuses_one_response_and_rejects_tampering(tmp_path):
    class Client:
        settings = LLMSettings()
        calls = 0
        def model_metadata(self):
            return {"digest": "local-digest"}
        def extract(self, *args):
            self.calls += 1
            return {"ok": True, "proposals": {}, "elapsed_seconds": 7.5}
    client = Client()
    item = {"pages": [{"page": 1, "text": "합계금액: 110", "location_kind": "page"}], "document_type": "estimate"}
    first, key, hit, _ = request_cached(client, item, ["total_amount"], tmp_path)
    replay, same_key, second_hit, _ = request_cached(client, item, ["total_amount"], tmp_path)
    assert first == replay and key == same_key and not hit and second_hit and client.calls == 1
    path = tmp_path / (key + ".json")
    saved = json.loads(path.read_text(encoding="utf-8"))
    saved["run"]["elapsed_seconds"] = 0
    path.write_text(json.dumps(saved), encoding="utf-8")
    with pytest.raises(EvaluationNotReady):
        request_cached(client, item, ["total_amount"], tmp_path)


def test_check_accuracy_counts_missing_and_extra_but_excludes_both_na():
    labels = {"contracts": {"1": {"checks": [
        {"rule_id": "A", "field": "x", "status": "PASS"},
        {"rule_id": "B", "field": "x", "status": "FAIL"},
        {"rule_id": "C", "field": "x", "status": "N/A"}]}}}
    predictions = {"contracts": {"1": {"checks": [
        {"rule_id": "A", "field": "x", "status": "PASS"},
        {"rule_id": "D", "field": "x", "status": "PASS"}]}}}
    assert check_accuracy(labels, predictions) == {"correct": 1, "scored": 3, "both_not_applicable": 1, "accuracy": 1 / 3}


@pytest.mark.parametrize("args", [["--split", "test"], ["--split", "test", "--final"],
                                  ["--split", "test", "--final", "--selected-model", "gemma3:latest", "--benchmark-only"]])
def test_final_gates_precede_any_heldout_read(args, monkeypatch):
    from backend.scripts import compare_llm_modes
    monkeypatch.setattr(compare_llm_modes.Path, "read_text", lambda *a, **kw: pytest.fail("read before final gate"))
    assert main(args) == 2


def test_final_selection_rejects_changed_model_or_digest():
    record = {"selected_model": "qwen3:latest", "prompt_version": PROMPT_VERSION, "guard_version": GUARD_VERSION,
              "results": [{"model": "qwen3:latest", "model_metadata": {"digest": "fixed"}}]}
    client = SimpleNamespace(model_metadata=lambda: {"digest": "fixed"})
    verify_final_selection("qwen3:latest", record, client)
    with pytest.raises(EvaluationNotReady):
        verify_final_selection("gemma3:latest", record, client)
    client = SimpleNamespace(model_metadata=lambda: {"digest": "changed"})
    with pytest.raises(EvaluationNotReady):
        verify_final_selection("qwen3:latest", record, client)


def test_guard_precision_and_referral_do_not_count_rejected_correct_values_as_errors():
    def decision(field, value, applied, state="VALUE"):
        return {"field": field, "applied": applied, "proposal": {"state": state, "value": value}}
    traces = {"1": {"review": {"targets": ["total_amount", "supply_amount", "tax_amount"], "decisions": [
        decision("total_amount", "110", True), decision("supply_amount", "100", False), decision("tax_amount", "11", False)]}},
        "2": {"review": {"targets": ["total_amount"], "decisions": [decision("total_amount", None, True, "REVIEW")]}},
        "3": {"review": {"targets": [], "decisions": []}}}
    labels = {"documents": {"1": {"fields": {"total_amount": {"state": "VALUE", "value": 110},
        "supply_amount": {"state": "VALUE", "value": 100}, "tax_amount": {"state": "VALUE", "value": 10}}},
        "2": {"fields": {"total_amount": {"state": "REVIEW", "value": None}}}}}
    result = guard_outcomes(traces, labels)
    assert result["accepted_value_precision"] == 1
    assert result["rejected_gold_matching"] == result["rejected_gold_mismatching"] == 1
    assert result["human_referral_field_count"] == 3 and result["human_referral_field_rate"] == 3 / 4
    assert result["human_referral_document_rate"] == 2 / 3


def test_docx_guard_metadata_does_not_change_prompt_response_cache(tmp_path):
    client = SimpleNamespace(settings=LLMSettings(), model_metadata=lambda: {"digest": "local"},
        extract=lambda *args: {"ok": True, "proposals": {}, "elapsed_seconds": 2})
    item = {"document_type": "estimate", "pages": [{"page": None, "location_kind": "document_block", "text": "합계금액: 110원"}]}
    _, key, _, _ = request_cached(client, item, ["total_amount"], tmp_path)
    item["pages"][0].update(document_format="docx", line_locations={"1": [{"paragraph": 1}]})
    client.extract = lambda *args: pytest.fail("replay must not call model")
    _, replay_key, hit, _ = request_cached(client, item, ["total_amount"], tmp_path, replay_only=True)
    assert hit and replay_key == key
    with pytest.raises(EvaluationNotReady):
        request_cached(client, item, ["tax_amount"], tmp_path, replay_only=True)


def test_release_rejects_changed_code_or_settings_before_heldout_read(monkeypatch):
    from dataclasses import asdict
    from backend import evaluation_release
    monkeypatch.setattr(evaluation_release, "implementation_hashes", lambda project: {"guard.py": "fixed"})
    record = {"frozen": True, "release_version": "guard-v3-fixed", "implementation_sha256": {"guard.py": "fixed"},
              "settings": asdict(LLMSettings())}
    evaluation_release.verify_release(None, record, "qwen3:latest")
    record["implementation_sha256"]["guard.py"] = "changed"
    with pytest.raises(EvaluationNotReady):
        evaluation_release.verify_release(None, record, "qwen3:latest")
    record["implementation_sha256"]["guard.py"] = "fixed"
    record["settings"]["temperature"] = 1
    with pytest.raises(EvaluationNotReady):
        evaluation_release.verify_release(None, record, "qwen3:latest")


def test_final_attempt_cannot_be_repeated_with_different_output(tmp_path, monkeypatch):
    from backend.evaluation_release import reserve_final_attempt, finish_final_attempt
    release, labels = tmp_path / "release.json", tmp_path / "labels.json"
    release.write_text("{}")
    labels.write_text("{}")
    record = reserve_final_attempt(tmp_path, release, labels, tmp_path / "out1")
    finish_final_attempt(tmp_path, record, "failed_or_interrupted")
    with pytest.raises(EvaluationNotReady):
        reserve_final_attempt(tmp_path, release, labels, tmp_path / "out2")
    monkeypatch.setattr(type(tmp_path), "read_text", lambda *a, **kw: pytest.fail("repeat must stop before heldout read"))
    assert main(["--dataset", str(tmp_path), "--split", "test", "--final", "--selected-model", "qwen3:latest"]) == 2
