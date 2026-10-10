"""Dataset-free correctness/timing smoke checks; never a real OCR/LLM accuracy claim."""
import argparse
import contextlib
import copy
import io
import json
import math
import os
import platform
import statistics
import sys
import tempfile
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from time import perf_counter

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))

BASE_TEXT = (
    "견적서\n공급자 상호: 가상회귀상사\n사업자등록번호: 123-45-67891\n"
    "공급가액: 1,000원\n세액: 100원\n합계금액: 1,100원\n발행일: 2026-01-15\n전액 청구"
)
BASE_FIELDS = {
    "company_name": "가상회귀상사", "business_registration_no": "1234567891",
    "supply_amount": 1000, "tax_amount": 100, "total_amount": 1100,
    "issue_date": "2026-01-15", "amount_scope": "FULL",
}


def document_fixtures():
    """Author-written synthetic expectations; no original dataset/labels are read."""
    return [
        {"id": "plain_text", "extension": ".txt", "text": BASE_TEXT, "fields": dict(BASE_FIELDS)},
        {"id": "printed_arithmetic_error", "extension": ".txt",
         "text": BASE_TEXT.replace("합계금액: 1,100원", "합계금액: 1,200원"),
         "fields": {**BASE_FIELDS, "total_amount": 1200}},
        {"id": "zero_tax", "extension": ".txt",
         "text": BASE_TEXT.replace("세액: 100원", "세액: 0원").replace("합계금액: 1,100원", "합계금액: 1,000원"),
         "fields": {**BASE_FIELDS, "tax_amount": 0, "total_amount": 1000}},
        {"id": "native_docx", "extension": ".docx", "text": BASE_TEXT, "fields": dict(BASE_FIELDS)},
    ]


def guard_fixtures():
    def case(name, field, text, value, accepted, *, quote=None, line=1, page=1, dtype="estimate"):
        return {"id": name, "field": field, "text": text, "document_type": dtype, "accepted": accepted,
                "proposal": {"state": "VALUE", "value": value, "page": page, "line": line,
                             "quote": text.splitlines()[line - 1] if quote is None else quote}}
    return [
        case("explicit_total", "total_amount", "합계금액: 1,100원", "1100", True),
        case("fabricated_total", "total_amount", "공급가액: 1,000원\n세액: 100원", "1100", False),
        case("wrong_field", "total_amount", "세액: 1,100원", "1100", False),
        case("wrong_quote", "total_amount", "합계금액: 1,100원", "1100", False, quote="합계금액: 1,200원"),
        case("wrong_page", "total_amount", "합계금액: 1,100원", "1100", False, page=2),
        case("buyer_identity", "business_registration_no",
             "공급자\n사업자등록번호: 123-45-67891\n공급받는자\n사업자등록번호: 111-11-11119",
             "1111111119", False, line=4, dtype="tax_invoice"),
        case("bad_checksum", "business_registration_no", "사업자등록번호: 123-45-67890",
             "1234567890", False, dtype="business_registration"),
        case("negative_amount", "total_amount", "합계금액: -1,100원", "-1100", False),
        case("valid_date", "issue_date", "발행일: 2026-01-15", "2026-01-15", True),
        case("invalid_date", "issue_date", "발행일: 2026-02-30", "2026-02-30", False),
    ]


def timing_summary(samples):
    if not samples:
        return {"sample_count": 0, "mean": None, "p50": None, "p95": None}
    ordered = sorted(samples)
    return {"sample_count": len(samples), "mean": statistics.mean(samples),
            "p50": statistics.median(samples), "p95": ordered[math.ceil(len(ordered) * .95) - 1],
            "min": ordered[0], "max": ordered[-1]}


def source_hashes():
    from backend.evaluation_core import file_hash
    files = list((PROJECT / "backend/app/ai").glob("*.py")) + [
        PROJECT / "backend/evaluation_core.py", PROJECT / "backend/scripts/compare_llm_modes.py", Path(__file__),
    ]
    return {path.relative_to(PROJECT).as_posix(): file_hash(path) for path in sorted(files)}


def check_document(path, fixture):
    from backend.app.ai import analyze_document
    from backend.scripts.compare_llm_modes import field_accuracy
    started = perf_counter()
    analysis, _, _ = analyze_document(str(path), file_name=path.name, use_llm=False)
    elapsed = perf_counter() - started
    actual = analysis.fields.model_dump()
    labels = {"documents": {fixture["id"]: {"fields": {
        name: {"state": "VALUE", "value": value} for name, value in fixture["fields"].items()
    }}}}
    # Reuse the existing benchmark's normalization and denominator semantics.
    metric = field_accuracy([fixture["id"]], labels, {fixture["id"]: actual})
    passed = metric["correct"] == metric["scored"] and analysis.document_type.value == "estimate"
    return elapsed, {"passed": passed, "fields": metric, "document_type": analysis.document_type.value,
                     "expected_type": "estimate", "actual_fields": actual}


def check_guard(fixture, policy):
    from backend.app.ai.llm_supplement import apply_proposals
    field = fixture["field"]
    pages = [{"page": 1, "location_kind": "page", "text": fixture["text"]}]
    run = {"ok": True, "proposals": {field: copy.deepcopy(fixture["proposal"])}}
    started = perf_counter()
    _, review = apply_proposals({field: None}, run, pages, fixture["document_type"], [field], guard_policy=policy)
    elapsed = perf_counter() - started
    decision = review["decisions"][0]
    passed = decision["accepted"] == fixture["accepted"] and not review["human_confirmed"]
    return elapsed, {"passed": passed, "expected_acceptance": fixture["accepted"],
                     "actual_acceptance": decision["accepted"], "reasons": decision["reasons"],
                     "guard_version": review["guard_version"], "human_confirmed": review["human_confirmed"]}


def _measure(stage, name, callback, repeat, warmup):
    samples, observations = [], []
    # Warmups still check correctness; errors are never discarded to improve the result.
    for iteration in range(warmup + repeat):
        try:
            elapsed, observed = callback()
        except Exception as exc:
            elapsed, observed = None, {"passed": False, "error_type": type(exc).__name__}
        observations.append({"iteration": iteration + 1, "warmup": iteration < warmup, **observed})
        if iteration >= warmup and elapsed is not None:
            samples.append(elapsed)
    return {"id": name, "stage": stage, "passed": all(item["passed"] for item in observations),
            "seconds": timing_summary(samples), "samples_seconds": samples, "observations": observations}


def run_benchmark(*, repeat=3, warmup=1):
    if not 1 <= repeat <= 1000 or not 0 <= warmup <= 100:
        raise ValueError("repeat must be 1..1000 and warmup 0..100")
    previous = dict(os.environ)
    cases = []
    try:
        with tempfile.TemporaryDirectory(prefix="cpilot-ai-synthetic-") as directory:
            os.environ.update(APP_DEPLOYMENT_MODE="pilot", APP_NTS_MODE="disabled",
                              APP_LLM_ENABLED="false", APP_VLM_ENABLED="false", APP_STORAGE_ROOT=directory)
            before = source_hashes()
            for index, fixture in enumerate(document_fixtures(), 1):
                path = Path(directory) / (f"input_{index:02}" + fixture["extension"])
                if fixture["extension"] == ".docx":
                    from docx import Document
                    doc = Document()
                    for line in fixture["text"].splitlines():
                        doc.add_paragraph(line)
                    doc.save(path)
                else:
                    path.write_text(fixture["text"], encoding="utf-8")
                cases.append(_measure("native_file_rules", fixture["id"],
                                      lambda f=fixture, p=path: check_document(p, f), repeat, warmup))
            for policy in ("v3", "v4"):
                for fixture in guard_fixtures():
                    cases.append(_measure("fixed_proposal_guard", f"{policy}/{fixture['id']}",
                                          lambda f=fixture, p=policy: check_guard(f, p), repeat, warmup))
            unchanged = before == source_hashes()
    finally:
        os.environ.clear()
        os.environ.update(previous)
    dependencies = {}
    for name in ("pydantic", "python-docx", "pypdf", "pypdfium2", "pillow", "winocr", "requests"):
        try:
            dependencies[name] = version(name)
        except PackageNotFoundError:
            dependencies[name] = None
    return {
        "schema_version": "cpilot-ai-synthetic-v1", "created_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Hand-authored synthetic correctness checks; not OCR/model accuracy or end-to-end latency.",
        "label_status": "synthetic_author_expectations_not_independent_human_evaluation",
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "machine": platform.machine(), "packages": dependencies},
        "repeat": repeat, "warmup": warmup, "source_sha256": before,
        "source_unchanged_during_run": unchanged,
        "timing_definition": "perf_counter around each native-file analysis or fixed-proposal guard call; excludes imports, fixture creation and warmups; p95 is nearest-rank. Each call is timed independently.",
        "stages": {
            "native_file_rules": {"status": "executed", "real_file_parser": True, "ocr": False, "model": False},
            "fixed_proposal_guard": {"status": "executed", "proposals": "fixed_synthetic", "model": False},
            "real_ocr": {"status": "not_run", "reason": "No raster input or OCR engine is invoked by this smoke runner."},
            "real_llm": {"status": "not_run", "reason": "No Ollama request is made; use the existing frozen-label evaluator."},
            "real_vlm": {"status": "not_run", "reason": "Image re-reading is not covered."},
        },
        "summary": {"case_count": len(cases), "passed": sum(c["passed"] for c in cases),
                    "failed": sum(not c["passed"] for c in cases),
                    "result": "passed" if unchanged and all(c["passed"] for c in cases) else "failed"},
        "cases": cases,
    }


def write_result(path, payload):
    path = Path(path).resolve()
    if path.suffix.lower() != ".json":
        raise ValueError("Output must be a new .json file")
    for protected in (PROJECT / "eval", PROJECT / "docs/eval", PROJECT / "storage"):
        if path.is_relative_to(protected.resolve()):
            raise ValueError("Output cannot be inside datasets, frozen reports, or customer storage")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--output", type=Path, help="New JSON file only; never overwrites an existing result")
    args = parser.parse_args(argv)
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = run_benchmark(repeat=args.repeat, warmup=args.warmup)
        if args.output:
            write_result(args.output, result)
        print(json.dumps(result if args.output is None else {"output": str(args.output), **result["summary"]},
                         ensure_ascii=False, indent=2))
        return 0 if result["summary"]["result"] == "passed" else 1
    except (OSError, ValueError, ImportError) as exc:
        print(f"Synthetic benchmark could not run: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
