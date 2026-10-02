import json
from types import SimpleNamespace

import pytest

from backend.evaluation_core import EvaluationNotReady
from backend.scripts.compare_llm_modes import check_accuracy, main, request_cached, verify_final_selection
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
