"""Freeze the extraction implementation and reserve one heldout evaluation.

No heldout labels or documents are read by release creation/verification.
"""
import json
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from backend.evaluation_core import EvaluationNotReady, file_hash
from backend.app.ai.grounding import GUARD_VERSION
from backend.app.ai.local_llm import LLMSettings, PROMPT_VERSION


def implementation_hashes(project):
    paths = [*project.glob("backend/app/ai/*.py"), *project.glob("backend/app/validation/*.py"),
             *project.glob("backend/app/schemas/*.py")]
    paths += [project / name for name in (
        "backend/app/integrations/nts_client.py",
        "backend/evaluation_core.py", "backend/evaluation_release.py",
        "backend/scripts/compare_llm_modes.py")]
    return {p.relative_to(project).as_posix(): sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            for p in sorted(paths)}


def create_release(project, selection, model, client, dev_receipt):
    chosen = next((r for r in selection["results"] if r["model"] == model), None)
    if (selection.get("selected_model") != model or selection.get("prompt_version") != PROMPT_VERSION
            or not chosen or chosen["model_metadata"]["digest"] != client.model_metadata()["digest"]):
        raise EvaluationNotReady("기존 dev 선택 모델·프롬프트·digest가 달라졌습니다.")
    return {"release_version": "guard-v3-fixed", "frozen": True,
            "frozen_at": datetime.now(timezone.utc).isoformat(),
            "selected_model": model, "results": selection["results"],
            "model_selection_guard_version": selection["guard_version"],
            "selection_basis": selection["selection_basis"],
            "guard_version": GUARD_VERSION, "prompt_version": PROMPT_VERSION,
            "settings": asdict(LLMSettings(model=model)),
            "code_hash_policy": "SHA256 with CRLF normalized to LF",
            "implementation_sha256": implementation_hashes(project),
            "dev_labels_sha256": dev_receipt["labels_sha256"],
            "manifest_sha256": dev_receipt["manifest_sha256"],
            "guard_tuning_disclosure": "가드 v3는 dev 감사 결과로 조정함",
            "docx_policy": "DOCX는 페이지 배치는 미확인, 글자 근거는 확인",
            "test_policy": "one reserved attempt per dataset; no test tuning or repeat runs"}


def verify_release(project, record, model):
    if (record.get("frozen") is not True or record.get("release_version") != "guard-v3-fixed"
            or record.get("implementation_sha256") != implementation_hashes(project)
            or record.get("settings") != asdict(LLMSettings(model=model))):
        raise EvaluationNotReady("고정한 가드 코드 또는 모델 설정과 다릅니다.")


def attempt_path(dataset):
    return Path(dataset) / "final_evaluation_attempt.json"


def check_final_attempt(dataset):
    if attempt_path(dataset).exists():
        raise EvaluationNotReady("이 자료의 최종 평가 시도는 이미 기록되어 있습니다.")


def reserve_final_attempt(dataset, release_path, labels_path, output):
    record = {"status": "started", "started_at": datetime.now(timezone.utc).isoformat(),
              "release_sha256": file_hash(release_path), "labels_sha256": file_hash(labels_path),
              "output": str(output.resolve())}
    try:
        with attempt_path(dataset).open("x", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=False, indent=2)
    except FileExistsError as exc:
        raise EvaluationNotReady("최종 평가가 이미 예약되었습니다.") from exc
    return record


def finish_final_attempt(dataset, record, status):
    record = {**record, "status": status, "finished_at": datetime.now(timezone.utc).isoformat()}
    attempt_path(dataset).write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
