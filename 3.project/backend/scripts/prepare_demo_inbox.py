"""Create isolated C-company demo inboxes from DEV originals, never customer/test data."""
import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[2]
DEMO_ROOT = PROJECT / "storage/demo"
SCENARIOS = {
    "normal": "정상 제출",
    "missing": "서류 누락",
    "amount_mismatch": "금액 불일치",
    "wrong_business_no": "사업자번호 불일치",
    "ambiguous_amount": "모호한 금액",
}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_output(path):
    root, target = DEMO_ROOT.resolve(), Path(path).resolve()
    if target == root or not target.is_relative_to(root):
        raise ValueError("시연 경로는 storage/demo 아래의 새 하위 폴더여야 합니다.")
    if target.exists():
        raise ValueError("기존 업무함을 덮어쓰지 않습니다. 새 시연 폴더 이름을 지정하세요.")
    return target


def select_dev_cases(dataset):
    dataset = Path(dataset).resolve()
    manifest = read_json(dataset / "manifest.json")
    selected = []
    for scenario in SCENARIOS:
        matches = [r for r in manifest["contracts"] if r.get("split") == "dev" and r.get("scenario") == scenario]
        if len(matches) != 1:
            raise ValueError("시연 시나리오마다 dev 계약이 정확히 하나 필요합니다.")
        case = matches[0]
        for document in case["documents"]:
            relative = Path(document["path"])
            source = (dataset / relative).resolve()
            if (not relative.parts or relative.is_absolute() or relative.parts[0] != "dev"
                    or not source.is_relative_to(dataset / "dev")):
                raise ValueError("dev 밖의 원본은 시연에 사용하지 않습니다.")
            if digest(source) != document["sha256"]:
                raise ValueError("dev 원본 해시가 다릅니다. 시연 자료를 만들지 않았습니다.")
        selected.append(case)
    return selected


def worker_environment(storage):
    env = dict(os.environ)
    env.update(APP_DEPLOYMENT_MODE="pilot", APP_STORAGE_ROOT=str(storage), APP_NTS_MODE="disabled",
               APP_LLM_ENABLED="false", APP_COOKIE_SECURE="false", PYTHONIOENCODING="utf-8")
    return env


def check_worker_root(root):
    root = Path(root).resolve()
    if root == DEMO_ROOT.resolve() or not root.is_relative_to(DEMO_ROOT.resolve()):
        raise ValueError("시연 전용 경로만 준비할 수 있습니다.")
    marker = read_json(root / "demo_manifest.json")
    if marker.get("kind") != "C_COMPANY_DEV_DEMO" or marker.get("status") != "PREPARING":
        raise ValueError("준비 중인 시연 업무함만 처리합니다.")
    return marker


def configure_worker(root, phase):
    marker = check_worker_root(root)
    storage = root / phase / "storage"
    if storage.exists():
        raise ValueError("이미 생성한 시연 업무함을 다시 만들지 않습니다.")
    if phase == "guarded-replay":
        shutil.copytree(root / "rule/storage", storage)
    os.environ.update(worker_environment(storage))
    sys.path.insert(0, str(PROJECT))
    from backend.evaluation_release import verify_release
    release = read_json(PROJECT / "docs/eval/test/preparation/release_lock.json")
    verify_release(PROJECT, release, release["selected_model"])
    if digest(Path(marker["dataset"]) / "manifest.json") != marker["source_manifest_sha256"]:
        raise ValueError("자료 목록이 변경되었습니다.")
    return storage, release


def seed_rule(root, dataset):
    storage, _ = configure_worker(root, "rule")
    from backend.app.db.database import Base, engine, SessionLocal
    from backend.app.db.models import User, UserProfile, CompanySetting
    from backend.app.security import hash_password
    from backend.app.schemas.contract import ContractCreate
    from backend.app.services.contract_service import ContractService
    from backend.app.services.company_policy_service import CompanyPolicy

    Base.metadata.create_all(engine)
    service = ContractService()
    credentials, cases = [], []
    try:
        with SessionLocal() as db:
            for role, display in (("operator", "시연 담당자"), ("representative", "시연 대표")):
                password = secrets.token_urlsafe(18)
                user = User(email=f"{role}@demo.local", password=hash_password(password))
                db.add(user)
                db.flush()
                db.add(UserProfile(user_id=user.user_id, role=role, display_name=display,
                                   active=True, must_change_password=True))
                if role == "operator":
                    operator_id = user.user_id
                credentials.append(f"{display}\n로그인: {user.email}\n임시 비밀번호: {password}\n")
            policy = CompanyPolicy(company_type="SMALL_BUSINESS")
            for key, value in (("company_name", "C업체 · 시연 전용 · 규칙만"),
                               ("organization_policy", policy.model_dump(mode="json")),
                               ("required_documents", [t.value for t in policy.required_document_types])):
                db.add(CompanySetting(key=key, value=json.dumps(value, ensure_ascii=False)))
            db.commit()
            for case in select_dev_cases(dataset):
                values = case["input"]
                contract = service.create_contract(db, ContractCreate(
                    title=f"[시연 · {SCENARIOS[case['scenario']]}] {values['title']}",
                    vendor_name=values["vendor_name"], business_number=values["business_number"],
                    contract_amount=values["contract_amount"], **values["amount_policy"]), user_id=operator_id)
                entry = {"source_contract_id": case["contract_id"], "app_contract_id": contract.contract_id,
                         "scenario": case["scenario"], "label": SCENARIOS[case["scenario"]], "documents": []}
                for original in case["documents"]:
                    source = dataset / original["path"]
                    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                        doc = service.pipeline_service.process_document_upload(
                            db, contract.contract_id, source.name, source.read_bytes())
                    if doc.processing_status == "FAILED":
                        raise ValueError("dev 원문 인식 실패로 시연 준비를 중단했습니다.")
                    entry["documents"].append({"source_document_id": original["document_id"],
                        "app_document_id": doc.document_id, "source_path": original["path"], "sha256": original["sha256"]})
                cases.append(entry)
        (storage / "initial-accounts.txt").write_text(
            "시연 전용 계정 — 실제 업무에 사용하지 마세요. 첫 로그인 시 비밀번호를 변경하세요.\n\n"
            + "\n".join(credentials), encoding="utf-8")
        save_json(root / "rule/receipt.json", {"mode": "RULE_ONLY", "cases": cases})
    finally:
        engine.dispose()


def seed_guarded_replay(root):
    _, release = configure_worker(root, "guarded-replay")
    from backend.app.db.database import engine, SessionLocal
    from backend.app.db.models import Document, CompanySetting
    from backend.app.ai.local_llm import LLMSettings
    from backend.app.ai.grounding import source_pages, supplementation_targets
    from backend.app.ai.llm_supplement import apply_proposals
    from backend.app.services.storage_service import read_texts, resolve_path
    from backend.app.services.workflow_service import touch_contract
    from backend.app.services.contract_service import ContractService
    from backend.scripts.compare_llm_modes import request_cached

    class OfflineReplayClient:
        settings = LLMSettings(model=release["selected_model"])

        def model_metadata(self):
            return next(r["model_metadata"] for r in release["results"] if r["model"] == release["selected_model"])

        def extract(self, *args, **kwargs):
            raise RuntimeError("시연 캐시 재생은 새 LLM 호출을 하지 않습니다.")

    receipt = read_json(root / "rule/receipt.json")
    changed_fields, replayed_documents = 0, 0
    try:
        with SessionLocal() as db:
            for case in receipt["cases"]:
                for entry in case["documents"]:
                    doc = db.get(Document, entry["app_document_id"])
                    path = resolve_path(doc.storage_path)
                    if not path or digest(path) != entry["sha256"]:
                        raise ValueError("시연 원본이 변경되었습니다.")
                    raw, _ = read_texts(doc)
                    fields = json.loads(doc.extract.raw_fields)
                    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                        pages = source_pages(path, raw)
                    targets = supplementation_targets(fields, pages, doc.document_type)
                    if targets:
                        item = {"pages": pages, "document_type": doc.document_type}
                        run, response_id, _, _ = request_cached(OfflineReplayClient(), item, targets,
                            PROJECT / "docs/eval/dev/comparison/llm_cache", replay_only=True)
                        if not run.get("ok"):
                            raise ValueError("성공한 기존 dev LLM 응답이 필요합니다.")
                        updated, review = apply_proposals(fields, run, pages, doc.document_type, targets)
                        review.update(demo_cache_replay=True, response_id=response_id)
                        replayed_documents += 1
                    else:
                        updated = dict(fields)
                        review = {"status": "NOT_NEEDED", "targets": [], "decisions": [],
                                  "manual_review_required": False, "demo_cache_replay": True}
                    changed_fields += sum(updated.get(k) != v for k, v in fields.items())
                    doc.extract.raw_fields = json.dumps({**updated, "ai_review": review}, ensure_ascii=False)
                    doc.extract.extracted_vendor_name = updated.get("company_name")
                    doc.extract.extracted_vendor_reg_no = updated.get("business_registration_no")
                    doc.extract.extracted_amount = updated.get("amount")
                    doc.extract.extracted_date = updated.get("issue_date")
                touch_contract(db, case["app_contract_id"])
            db.get(CompanySetting, "company_name").value = json.dumps("C업체 · 시연 전용 · AI 보완(캐시 재생)", ensure_ascii=False)
            db.commit()
            for case in receipt["cases"]:
                ContractService().pipeline_service.revalidate_contract(db, case["app_contract_id"])
        save_json(root / "guarded-replay/receipt.json", {**receipt, "mode": "GUARDED_CACHE_REPLAY",
            "replayed_documents": replayed_documents, "changed_fields": changed_fields,
            "live_llm_calls": 0, "human_confirmed": False, "model": release["selected_model"],
            "prompt_version": release["prompt_version"], "guard_version": release["guard_version"]})
    finally:
        engine.dispose()


def write_launch_files(root, modes):
    for mode, port in (("rule", 8020), ("guarded-replay", 8021)):
        if mode not in modes:
            continue
        launcher = root / mode / "launcher"
        launcher.mkdir()
        save_json(launcher / "settings.json", {"storage_root": str(root / mode / "storage"),
            "port": port, "intranet": False, "backup_directory": str(root / "backups" / mode)})
    project_literal = str(PROJECT).replace("'", "''")
    script = """$ErrorActionPreference = 'Stop'
$demoExe = Join-Path '__PROJECT__' 'C-Pilot.exe'
if (-not (Test-Path -LiteralPath $demoExe)) { throw 'C-Pilot.exe가 필요합니다.' }
Write-Host '시연 전용: 1 규칙만 / 2 AI 보완 결과(캐시 재생) / 0 시연 서버 모두 종료'
$demoChoice = Read-Host '번호'
if ($demoChoice -eq '0') {
  foreach ($demoMode in @('rule','guarded-replay')) {
    $demoSettings = Join-Path $PSScriptRoot "$demoMode/launcher/settings.json"
    if (Test-Path -LiteralPath $demoSettings) { & $demoExe stop --settings-file $demoSettings }
  }
} elseif ($demoChoice -in @('1','2')) {
  $demoMode = if ($demoChoice -eq '1') { 'rule' } else { 'guarded-replay' }
  $demoSettings = Join-Path $PSScriptRoot "$demoMode/launcher/settings.json"
  if (-not (Test-Path -LiteralPath $demoSettings)) { throw '이 비교 업무함은 아직 준비되지 않았습니다.' }
  & $demoExe start --settings-file $demoSettings --no-browser
  if ($LASTEXITCODE -ne 0) { throw '포트와 시연 서버 상태를 확인하세요.' }
  $demoUrl = if ($demoChoice -eq '1') { 'http://127.0.0.1:8020/' } else { 'http://localhost:8021/' }
  Start-Process $demoUrl
}
""".replace("__PROJECT__", project_literal)
    (root / "run_demo.ps1").write_text(script, encoding="utf-8-sig")
    (root / "Run-demo.bat").write_text('@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_demo.ps1"\r\npause\r\n', encoding="ascii", newline="")
    shutil.copyfile(root / "rule/storage/initial-accounts.txt", root / "initial-accounts.txt")
    (root / "README.md").write_text(
        "# C업체 시연 전용 업무함\n\nRun-demo.bat에서 1 또는 2를 선택하세요. 초기 계정은 initial-accounts.txt에 있습니다.\n"
        "규칙만: http://127.0.0.1:8020/ · AI 보완 결과: http://localhost:8021/\n\n"
        "두 업무함의 로그인 쿠키가 겹치지 않도록 주소의 호스트를 구분합니다. 실제 업무 서버 8000은 변경하지 않습니다.\n"
        "AI 보완은 기존 dev 응답을 가드 v3로 재생한 결과입니다. 실행 중 새 LLM 호출은 기본적으로 꺼져 있습니다.\n"
        "국세청 조회는 APP_NTS_MODE=disabled(미연동)로 고정합니다. 가상 사업자번호를 외부로 조회하지 않습니다.\n"
        "시연에서 바꾼 값·회신 기록은 해당 업무함에만 저장됩니다. 원본과 비교 상태를 다시 준비할 때는 새 폴더를 사용하세요.\n",
        encoding="utf-8")


def prepare(output, dataset, rule_only=False):
    root = validate_output(output)
    cases = select_dev_cases(dataset)
    root.mkdir(parents=True)
    marker = {"kind": "C_COMPANY_DEV_DEMO", "status": "PREPARING", "dataset": str(dataset),
        "source_manifest_sha256": digest(dataset / "manifest.json"), "company_type": "SMALL_BUSINESS",
        "approval_steps": 1, "case_count": len(cases), "document_count": sum(len(c["documents"]) for c in cases),
        "test_used": False, "live_llm_calls": 0, "nts_mode": "disabled"}
    save_json(root / "demo_manifest.json", marker)
    modes = ["rule"] if rule_only else ["rule", "guarded-replay"]
    try:
        for mode in modes:
            print(f"시연 업무함 준비: {mode}", flush=True)
            command = [sys.executable, str(Path(__file__).resolve()), "--output", str(root),
                       "--dataset", str(dataset), "--worker", mode]
            result = subprocess.run(command, cwd=PROJECT, env=worker_environment(root / mode / "storage"),
                stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            if result.returncode:
                raise ValueError(f"{mode} 준비 실패. 기존 업무 자료는 변경하지 않았습니다. 새 폴더에서 재시도하세요.")
        write_launch_files(root, modes)
        save_json(root / "demo_manifest.json", {**marker, "status": "READY", "modes": modes})
    except Exception:
        save_json(root / "demo_manifest.json", {**marker, "status": "FAILED"})
        raise
    return root


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEMO_ROOT / "c-company-v1")
    parser.add_argument("--dataset", type=Path, default=PROJECT / "eval/dataset")
    parser.add_argument("--rule-only", action="store_true")
    parser.add_argument("--worker", choices=("rule", "guarded-replay"), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        root, dataset = args.output.resolve(), args.dataset.resolve()
        if args.worker == "rule":
            check_worker_root(root)
            seed_rule(root, dataset)
        elif args.worker == "guarded-replay":
            check_worker_root(root)
            seed_guarded_replay(root)
        else:
            print("시연 준비 완료: " + str(prepare(root, dataset, args.rule_only)))
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print("시연 준비 중단: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
