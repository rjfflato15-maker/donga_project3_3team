"""One heldout inference attempt with immutable, label-free checkpoints.

The v3 extractor/guard/evaluator remain unchanged. A pending request without a
durable response is recorded as interrupted; it is NEVER sent again on resume.
"""
import contextlib
import importlib.metadata
import io
import json
import os
import platform
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from backend.evaluation_core import EvaluationNotReady, file_hash, verify_dataset
from backend.evaluation_release import verify_release
from backend.scripts.compare_llm_modes import MODES, verify_final_selection, validate_mode_contracts
from backend.app.ai.local_llm import CORE_FIELDS, LLMSettings, OllamaClient, PROMPT_VERSION
from backend.app.ai.llm_supplement import apply_proposals
from backend.prediction_artifacts import digest, write_json, save_checkpoint, load_checkpoint, verify_package


def now():
    return datetime.now(timezone.utc).isoformat()


def environment_receipt():
    packages = {}
    for name in ("winocr", "Pillow", "pypdfium2", "python-docx", "pytesseract", "pydantic", "requests"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return {"python": platform.python_version(), "platform": platform.platform(), "packages": packages}


def preflight(project, dataset, release_path, *, smoke=True, client=None):
    """Validate the frozen runtime and synthetic sources, never read labels."""
    release = json.loads(Path(release_path).read_text(encoding="utf-8"))
    model = release["selected_model"]
    client = client or OllamaClient(LLMSettings(model=model))
    verify_release(Path(project), release, model)
    verify_final_selection(model, release, client)
    manifest_path = Path(dataset) / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("created_for") != "local-evaluation" or manifest.get("dataset_version") != "synthetic-v1":
        raise EvaluationNotReady("ONLY_SYNTHETIC_V1_HELDOUT")
    if file_hash(manifest_path) != release["manifest_sha256"]:
        raise EvaluationNotReady("MANIFEST_CHANGED")
    verify_dataset(dataset, manifest, split="test")
    config = Path.home() / ".ollama/server.json"
    if not config.is_file() or json.loads(config.read_text(encoding="utf-8-sig")).get("disable_ollama_cloud") is not True:
        raise EvaluationNotReady("CLOUD_DISABLE_CONFIG_REQUIRED")
    report = {"checked_at": now(), "environment": environment_receipt(),
              "settings": asdict(client.settings), "model_metadata": client.model_metadata(),
              "nts_mode": "disabled", "labels_read": False, "cloud_disable_config": True}
    if smoke:
        # This tiny artificial DEV input warms the model; no heldout page enters it.
        run = client.extract([{"page": 1, "location_kind": "page", "text": "견적서\n합계금액: 1100원"}],
                             ["total_amount"], "estimate")
        proposal = run.get("proposals", {}).get("total_amount", {})
        if not run.get("ok") or proposal.get("state") != "VALUE" or str(proposal.get("value")) != "1100":
            raise EvaluationNotReady("DEV_SMOKE_FAILED")
        report["dev_smoke"] = {"ok": True, "elapsed_seconds": run["elapsed_seconds"], "run_sha256": digest(run)}
    return manifest, release, client, report


def reserve(dataset, output, release_path, manifest, report, *, resume=False):
    marker = Path(dataset) / "final_evaluation_attempt.json"
    output = Path(output).resolve()
    if resume:
        if not marker.is_file():
            raise EvaluationNotReady("NO_ATTEMPT_TO_RESUME")
        attempt = json.loads(marker.read_text(encoding="utf-8"))
        if (attempt.get("mode") != "predictions-only-v1" or attempt.get("output") != str(output)
                or attempt.get("release_sha256") != file_hash(release_path)
                or attempt.get("manifest_sha256") != digest(manifest)
                or attempt.get("status") not in {"started", "interrupted"}):
            raise EvaluationNotReady("RESUME_MUST_USE_SAME_ATTEMPT")
        attempt["status"] = "started"
        attempt["resumed_at"] = now()
        write_json(marker, attempt)
        return attempt
    if marker.exists() or output.exists():
        raise EvaluationNotReady("HELDOUT_ATTEMPT_OR_OUTPUT_EXISTS")
    attempt = {"mode": "predictions-only-v1", "attempt_id": str(uuid4()), "status": "started",
               "started_at": now(), "output": str(output), "release_sha256": file_hash(release_path),
               "manifest_sha256": digest(manifest), "labels_read": False,
               "recovery_policy": "Reuse durable inputs/responses; pending response becomes INTERRUPTED_RESPONSE_UNKNOWN without a new call."}
    write_json(marker, attempt, exclusive=True)
    output.mkdir(parents=True, exist_ok=False)
    save_checkpoint(output / "manifest.json", manifest)
    with (output / "source_manifest.json").open("xb") as stream:
        stream.write((Path(dataset) / "manifest.json").read_bytes())
    save_checkpoint(output / "release.json", json.loads(Path(release_path).read_text(encoding="utf-8")))
    save_checkpoint(output / "preflight.json", report)
    return attempt


def request_once(client, item, targets, output, attempt_id):
    visible = [{key: page[key] for key in ("page", "location_kind", "text")} for page in item["pages"]]
    request = {"pages": visible, "targets": list(targets), "document_type": item["document_type"],
               "settings": asdict(client.settings), "model_digest": client.model_metadata()["digest"],
               "prompt_version": PROMPT_VERSION}
    key = digest(request)
    response_path = Path(output) / "responses" / (key + ".json")
    pending_path = Path(output) / "requests" / (key + ".json")
    if response_path.exists():
        saved = load_checkpoint(response_path)
        if saved["request_sha256"] != key or saved["attempt_id"] != attempt_id:
            raise EvaluationNotReady("RESPONSE_BELONGS_TO_OTHER_ATTEMPT")
        return saved["run"], key, True
    if pending_path.exists():
        pending = load_checkpoint(pending_path)
        if pending["attempt_id"] != attempt_id or pending["request_sha256"] != key:
            raise EvaluationNotReady("REQUEST_BELONGS_TO_OTHER_ATTEMPT")
        run = {"ok": False, "error": "INTERRUPTED_RESPONSE_UNKNOWN", "proposals": {},
               "elapsed_seconds": 0, "attempts": 0, "model": client.settings.model,
               "prompt_version": PROMPT_VERSION, "settings": asdict(client.settings),
               "model_metadata": client.model_metadata()}
    else:
        save_checkpoint(pending_path, {"attempt_id": attempt_id, "request_sha256": key,
                                     "started_at": now(), "request": request})
        run = client.extract(item["pages"], targets, item["document_type"])
    save_checkpoint(response_path, {"attempt_id": attempt_id, "request_sha256": key, "run": run})
    return run, key, False


def collect_one(dataset, contract, document):
    from backend.app.ai import analyze_document
    from backend.app.ai.grounding import source_pages, supplementation_targets
    from backend.evaluation_core import dataset_file
    started = perf_counter()
    source = dataset_file(dataset, document["path"])
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        analysis, raw, _ = analyze_document(str(source), file_name=source.name, use_llm=False)
        pages = source_pages(source, raw)
    fields = analysis.fields.model_dump()
    return {"document": document, "contract_id": contract["contract_id"], "fields": fields,
            "pages": pages, "document_type": analysis.document_type.value,
            "processing_failed": not any(page["text"].strip() for page in pages),
            "rule_seconds": perf_counter() - started,
            "targets": supplementation_targets(fields, pages, analysis.document_type.value)}


def predict_one(client, item, output, attempt_id):
    fields = {"rule": item["fields"]}
    traces = {"rule": {"effective_seconds": item["rule_seconds"], "guard_seconds": 0}}
    run, key, hit = request_once(client, item, CORE_FIELDS, output, attempt_id)
    fields["llm"], review = apply_proposals(item["fields"], run, item["pages"], item["document_type"],
                                          CORE_FIELDS, guarded=False, llm_only=True)
    traces["llm"] = {"review": review, "response_id": key, "cache_hit": hit, "guard_seconds": 0,
                     "effective_seconds": item["rule_seconds"] + run["elapsed_seconds"]}
    if item["targets"]:
        run, key, hit = request_once(client, item, item["targets"], output, attempt_id)
    else:
        run, key, hit = {"ok": True, "proposals": {}, "elapsed_seconds": 0}, None, False
    for mode in ("hybrid_unguarded", "hybrid_guarded"):
        started = perf_counter()
        fields[mode], review = apply_proposals(item["fields"], run, item["pages"], item["document_type"],
                                              item["targets"], guarded=mode == "hybrid_guarded")
        seconds = perf_counter() - started if mode == "hybrid_guarded" else 0
        traces[mode] = {"review": review, "response_id": key, "cache_hit": hit,
                        "shared_response_replay": mode == "hybrid_guarded", "guard_seconds": seconds,
                        "effective_seconds": item["rule_seconds"] + run["elapsed_seconds"] + seconds}
    return {"fields": fields, "traces": traces}


def preserve_implementation(project, output, release):
    project, output = Path(project), Path(output)
    paths = set(release["implementation_sha256"])
    paths.update(path.relative_to(project).as_posix() for path in (project / "backend/app").rglob("*.py"))
    paths.update({"backend/evaluation_core.py", "backend/evaluation_predictions.py",
                  "backend/prediction_scoring.py", "backend/prediction_artifacts.py"})
    for relative in sorted(paths):
        source = project / relative
        target = output / "implementation" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if file_hash(target) != file_hash(source):
                raise EvaluationNotReady("SNAPSHOT_IMPLEMENTATION_CHANGED")
        else:
            with target.open("xb") as stream:
                stream.write(source.read_bytes())


def run_predictions(project, dataset, output, release_path, *, resume=False, client=None, collector=None, progress=print):
    project, dataset, output = Path(project), Path(dataset), Path(output)
    if not resume and (dataset / "final_evaluation_attempt.json").exists():
        raise EvaluationNotReady("HELDOUT_ATTEMPT_EXISTS")
    # Also serialize process-level execution of the SAME resumed attempt.
    lock = dataset / "prediction_process.lock"
    try:
        with lock.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps({"pid": os.getpid(), "started_at": now()}))
    except FileExistsError as exc:
        raise EvaluationNotReady("PREDICTION_PROCESS_ALREADY_RUNNING_OR_LOCK_NEEDS_AUDIT") from exc
    attempt = None
    try:
        if resume and (output / "receipt.json").exists():
            receipt = verify_package(output)
            marker = dataset / "final_evaluation_attempt.json"
            attempt = json.loads(marker.read_text(encoding="utf-8"))
            if (attempt.get("mode") != "predictions-only-v1" or attempt["attempt_id"] != receipt["attempt_id"]
                    or attempt["output"] != str(output.resolve()) or attempt["release_sha256"] != receipt["release_sha256"]):
                raise EvaluationNotReady("SEALED_RECEIPT_BELONGS_TO_OTHER_ATTEMPT")
            attempt.update(status="predictions_frozen", finished_at=receipt["frozen_at"], receipt_sha256=file_hash(output / "receipt.json"))
            write_json(marker, attempt)
            return receipt
        manifest, release, client, report = preflight(project, dataset, release_path, client=client)
        attempt = reserve(dataset, output, release_path, manifest, report, resume=resume)
        preserve_implementation(project, output, release)
        contracts = [row for row in manifest["contracts"] if row["split"] == "test"]
        collector = collector or collect_one
        inputs, by_mode = {}, {mode: {} for mode in MODES}
        traces = {mode: {} for mode in MODES}
        with tempfile.TemporaryDirectory(prefix="heldout-predictions-") as storage:
            # The prediction runner never opens the operational DB.
            previous = {key: os.environ.get(key) for key in ("APP_DEPLOYMENT_MODE", "APP_NTS_MODE", "APP_STORAGE_ROOT")}
            os.environ.update(APP_DEPLOYMENT_MODE="pilot", APP_NTS_MODE="disabled", APP_STORAGE_ROOT=storage)
            try:
                total = sum(len(row["documents"]) for row in contracts)
                processed = 0
                for contract in contracts:
                    for document in contract["documents"]:
                        did = str(document["document_id"])
                        input_path = output / "inputs" / (did + ".json")
                        if not input_path.exists():
                            save_checkpoint(input_path, collector(dataset, contract, document))
                        inputs[did] = load_checkpoint(input_path)
                        prediction_path = output / "documents" / (did + ".json")
                        if not prediction_path.exists():
                            save_checkpoint(prediction_path, predict_one(client, inputs[did], output, attempt["attempt_id"]))
                        prediction = load_checkpoint(prediction_path)
                        for mode in MODES:
                            by_mode[mode][did] = prediction["fields"][mode]
                            traces[mode][did] = prediction["traces"][mode]
                        processed += 1
                        progress(f"예측 보존 {processed}/{total} · 정답 미사용", flush=True)
            finally:
                for key, value in previous.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value
        predictions = {mode: validate_mode_contracts(contracts, inputs, by_mode[mode]) for mode in MODES}
        for name, value in (("predictions.json", predictions), ("traces.json", traces)):
            path = output / name
            if path.exists():
                if load_checkpoint(path) != value:
                    raise EvaluationNotReady("SEALED_PREDICTIONS_CHANGED")
            else:
                save_checkpoint(path, value)
        files = {path.relative_to(output).as_posix(): file_hash(path)
                 for path in sorted(output.rglob("*")) if path.is_file() and path.name != "receipt.json" and not path.name.endswith(".tmp")}
        receipt = {"format": "heldout-predictions-v1", "attempt_id": attempt["attempt_id"],
                   "frozen_at": now(), "release_sha256": attempt["release_sha256"],
                   "manifest_sha256": attempt["manifest_sha256"], "document_count": len(inputs),
                   "modes": list(MODES), "labels_read": False, "files_sha256": files}
        write_json(output / "receipt.json", receipt, exclusive=True)
        attempt.update(status="predictions_frozen", finished_at=now(), receipt_sha256=file_hash(output / "receipt.json"))
        write_json(dataset / "final_evaluation_attempt.json", attempt)
        return receipt
    finally:
        if attempt and attempt["status"] == "started":
            attempt.update(status="interrupted", interrupted_at=now())
            write_json(dataset / "final_evaluation_attempt.json", attempt)
        lock.unlink(missing_ok=True)
