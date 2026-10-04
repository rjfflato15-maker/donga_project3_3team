"""Fresh, rule-only measurement inbox; never resets/deletes an existing inbox.

--verify uploads the five synthetic cases and the two replies in a disposable
inbox, through the real pipeline. Normal mode registers one empty contract so
participants' upload and processing time remain part of the measurement.
"""
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))
from backend.scripts.prepare_team_test_materials import BUNDLE, CASES, read_json, save_json, sha256

DEMO_ROOT = PROJECT / "storage/demo/team-test"


def fresh_output(path):
    root, target = DEMO_ROOT.resolve(), Path(path).resolve()
    if target == root or not target.is_relative_to(root) or target.exists():
        raise ValueError("storage/demo/team-test 아래의 새 폴더만 가능합니다. 기존 업무함은 그대로 둡니다.")
    return target


def verify_bundle():
    manifest = read_json(BUNDLE / "facilitator/manifest.json")
    for relative, expected in manifest["file_sha256"].items():
        path = (BUNDLE / relative).resolve()
        if not path.is_relative_to(BUNDLE.resolve()) or sha256(path) != expected:
            raise ValueError("측정 자료 경로 또는 해시가 변경되었습니다.")
    if [e["case_id"] for e in manifest["cases"]] != list(CASES):
        raise ValueError("측정 사례 목록이 다릅니다.")
    return manifest


def isolated_environment(root):
    env = dict(os.environ)
    env.update(APP_DEPLOYMENT_MODE="pilot", APP_STORAGE_ROOT=str(root / "storage"),
               APP_NTS_MODE="disabled", APP_LLM_ENABLED="false", APP_COOKIE_SECURE="false",
               PYTHONIOENCODING="utf-8")
    return env


def prepare(output, case_id="practice", *, verify=False, port=8030, intranet=False):
    if case_id not in CASES:
        raise ValueError("알 수 없는 측정 사례입니다.")
    if not 1024 <= port <= 65535:
        raise ValueError("포트는 1024~65535 범위여야 합니다.")
    root = fresh_output(output)
    verify_bundle()
    root.mkdir(parents=True)
    marker = {"kind": "TEAM_TEST_DEV", "status": "PREPARING", "case_id": case_id,
              "verify": verify, "port": port, "intranet": intranet,
              "manifest_sha256": sha256(BUNDLE / "facilitator/manifest.json")}
    save_json(root / "inbox.json", marker)
    result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", str(root)],
                            cwd=PROJECT, env=isolated_environment(root), capture_output=True,
                            text=True, encoding="utf-8")
    if result.returncode:
        marker["status"] = "FAILED"
        save_json(root / "inbox.json", marker)
        (root / "preparation_error.txt").write_text(result.stderr, encoding="utf-8")
        raise RuntimeError(f"준비 실패. {root / 'preparation_error.txt'} 확인. 기존 업무함은 변경하지 않았습니다.")
    marker["status"] = "READY"
    save_json(root / "inbox.json", marker)
    return root


def install_execution_boundary(*, allow_event_loop_socketpair=False):
    """Fail on forbidden executions/data access even if inherited settings drift."""
    blocked = {"model_guard_calls": 0, "network_attempts": 0, "protected_file_attempts": 0}
    protected = [PROJECT / p for p in ("storage/pilot", "eval/dataset/test", "eval/dataset/test2",
                                      "docs/eval/test", "docs/eval/test2")]

    def audit(event, args):
        # Windows asyncio implements its internal wake-up pipe with socketpair.
        # Permit only that standard-library caller, never arbitrary loopback HTTP.
        if allow_event_loop_socketpair and event == "socket.connect":
            caller = sys._getframe(1)
            if (caller.f_globals.get("__name__") == "socket"
                    and caller.f_code.co_name == "_fallback_socketpair"
                    and args[1][0] in {"127.0.0.1", "::1"}):
                return
        if event in {"socket.connect", "socket.getaddrinfo"}:
            blocked["network_attempts"] += 1
            raise RuntimeError("측정 자료 준비 중 네트워크 호출은 금지합니다.")
        if event == "open" and isinstance(args[0], (str, bytes)):
            path = Path(os.fsdecode(args[0])).resolve()
            if any(path.is_relative_to(p.resolve()) for p in protected):
                blocked["protected_file_attempts"] += 1
                raise RuntimeError("실제 업무·보류 평가 자료는 열지 않습니다.")

    def profile(frame, event, arg):
        if event != "call":
            return
        module = frame.f_globals.get("__name__", "")
        name = frame.f_code.co_name
        if (module in {"backend.app.ai.local_llm", "backend.app.ai.llm_supplement"}
                and name in {"extract", "model_metadata", "build_prompt", "apply_proposals", "supplement_document"}
                or module.startswith("backend.app.ai.grounding") and name.startswith("guard")):
            blocked["model_guard_calls"] += 1
            raise RuntimeError("모델·프롬프트·가드 실행 금지")
    sys.addaudithook(audit)
    sys.setprofile(profile)
    return blocked


def issues(detail):
    return [{"rule_id": c.rule_id, "status": c.status.value, "field": c.field,
             "expected": c.expected, "actual": c.actual}
            for c in detail.checks if c.status.value in {"FAIL", "MISSING", "REVIEW"}
            and c.rule_id != "BUSINESS_STATUS"]


def require_issue(actual, expected):
    if expected is None:
        assert actual == [], f"추가 문제: {actual}"
    else:
        assert len(actual) == 1, f"문제가 정확히 1건이어야 합니다: {actual}"
        assert all(actual[0].get(k) == v for k, v in expected.items()), (actual, expected)


def worker(root):
    root = Path(root).resolve()
    if root == DEMO_ROOT.resolve() or not root.is_relative_to(DEMO_ROOT.resolve()):
        raise ValueError("측정 전용 하위 폴더만 가능합니다.")
    marker = read_json(root / "inbox.json")
    if marker.get("kind") != "TEAM_TEST_DEV" or marker.get("status") != "PREPARING" or (root / "storage").exists():
        raise ValueError("새로 준비 중인 측정 업무함만 가능합니다.")
    if marker["manifest_sha256"] != sha256(BUNDLE / "facilitator/manifest.json"):
        raise ValueError("자료 목록 해시가 변경되었습니다.")
    manifest = verify_bundle()
    os.environ.update(isolated_environment(root))
    blocked = install_execution_boundary()
    from backend.app.db.database import Base, engine, SessionLocal
    from backend.app.db.models import User, UserProfile, CompanySetting, DocumentVersion, Document
    from backend.app.security import hash_password
    from backend.app.schemas.contract import ContractCreate
    from backend.app.services.contract_service import ContractService
    from backend.app.services.company_policy_service import CompanyPolicy
    from backend.app.services.workflow_service import policy_for
    from backend.app.services.storage_service import resolve_path

    Base.metadata.create_all(engine)
    service, credentials, records = ContractService(), [], []
    try:
        with SessionLocal() as db:
            for role, display in (("operator", "테스트 담당자"), ("representative", "테스트 대표")):
                password = secrets.token_urlsafe(18)
                user = User(email=f"{role}@team.local", password=hash_password(password))
                db.add(user)
                db.flush()
                db.add(UserProfile(user_id=user.user_id, role=role, display_name=display,
                                   active=True, must_change_password=True))
                if role == "operator":
                    operator_id = user.user_id
                credentials.append(f"{display}: {user.email}\n임시 비밀번호: {password}\n")
            policy = CompanyPolicy(company_type="SMALL_BUSINESS")
            for key, value in (("company_name", "C업체 · 팀원 테스트"),
                               ("organization_policy", policy.model_dump(mode="json")),
                               ("required_documents", [t.value for t in policy.required_document_types])):
                db.add(CompanySetting(key=key, value=json.dumps(value, ensure_ascii=False)))
            db.commit()
            selected = manifest["cases"] if marker["verify"] else [e for e in manifest["cases"] if e["case_id"] == marker["case_id"]]
            for case in selected:
                contract = service.create_contract(db, ContractCreate(**case["registration"]), user_id=operator_id)
                entry = {"case_id": case["case_id"], "app_contract_id": contract.contract_id,
                         "uploaded_documents": 0}
                if marker["verify"]:
                    previous_id = None
                    for source in case["documents"]:
                        path = BUNDLE / source["path"]
                        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                            doc = service.pipeline_service.process_document_upload(db, contract.contract_id, path.name, path.read_bytes())
                        assert doc.processing_status != "FAILED"
                        assert doc.document_type == source["kind"], (case["case_id"], source["kind"], doc.document_type)
                        if doc.document_type == "estimate":
                            previous_id = doc.document_id
                        entry["uploaded_documents"] += 1
                    detail = service.get_contract_detail(db, contract.contract_id)
                    entry["initial_issues"] = issues(detail)
                    entry["nts_advisories"] = [c.model_dump(mode="json") for c in detail.checks if c.rule_id == "BUSINESS_STATUS"]
                    require_issue(entry["initial_issues"], case["expected_issue"])
                    if case["replacement"]:
                        path = BUNDLE / case["replacement"]["path"]
                        revision = policy_for(db, contract.contract_id)["revision"]
                        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                            new = service.pipeline_service.process_document_upload(db, contract.contract_id, path.name, path.read_bytes(),
                                replaces_document_id=previous_id, expected_contract_revision=revision, change_note="가상 회신 반영")
                        entry["after_reply_issues"] = issues(service.get_contract_detail(db, contract.contract_id))
                        require_issue(entry["after_reply_issues"], None)
                        old_version = db.query(DocumentVersion).filter_by(document_id=previous_id).one()
                        new_version = db.query(DocumentVersion).filter_by(document_id=new.document_id).one()
                        assert not old_version.is_current and new_version.is_current
                        assert new_version.previous_document_id == previous_id
                        initial_source = next(d for d in case["documents"] if d["kind"] == "estimate")
                        old_document = db.get(Document, previous_id)
                        assert sha256(resolve_path(old_document.storage_path)) == initial_source["sha256"]
                        assert sha256(resolve_path(new.storage_path)) == case["replacement"]["sha256"]
                        entry["old_preserved_and_new_current"] = True
                records.append(entry)
        sys.setprofile(None)
        assert not any(blocked.values()), blocked
        save_json(root / "verification.json", {"dataset_version": manifest["version"],
            "manifest_sha256": marker["manifest_sha256"], "mode": "RULE_ONLY", "nts_mode": "disabled",
            "cache_used": False, "runtime_boundary": blocked,
            "purpose": "material_verification" if marker["verify"] else "empty_measurement_inbox",
            "cases": records, "passed": True})
        (root / "storage/initial-accounts.txt").write_text(
            "가상 테스트 전용. 로그인 및 임시 비밀번호 변경은 시간 측정 전에 끝내세요.\n\n"
            + "\n".join(credentials), encoding="utf-8")
        launcher = root / "launcher"
        launcher.mkdir()
        save_json(launcher / "settings.json", {"storage_root": str(root / "storage"), "port": marker["port"],
            "intranet": marker["intranet"], "backup_directory": str(root / "backups")})
        for action in ("start", "stop"):
            command = f'@echo off\r\nchcp 65001 >nul\r\n"{PROJECT / "C-Pilot.exe"}" {action} --settings-file "%~dp0launcher\\settings.json"'
            if action == "start":
                command += " --no-browser"
            (root / f"{action}.bat").write_bytes((command + "\r\npause\r\n").encode("utf-8"))
    finally:
        sys.setprofile(None)
        engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--case", choices=CASES, default="practice")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--port", type=int, default=8030)
    parser.add_argument("--intranet", action="store_true")
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker(args.worker)
    else:
        if not args.output:
            parser.error("--output storage/demo/team-test/<새 이름> 필수")
        root = prepare(args.output, args.case, verify=args.verify, port=args.port, intranet=args.intranet)
        print(f"준비 완료: {root}\n결과: verification.json / 로그인: storage/initial-accounts.txt")
