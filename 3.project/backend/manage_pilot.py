"""C업체 시범환경 준비/백업/복원. 원격 원본 DB에는 읽기만 수행한다."""
import argparse
import hashlib
import json
import os
import secrets
import sqlite3
import stat
import sys
import tempfile
import uuid
import zipfile
from contextlib import closing
from datetime import datetime
from pathlib import Path, PurePosixPath

os.environ["APP_DEPLOYMENT_MODE"] = "pilot"
os.environ.setdefault("APP_NTS_MODE", "disabled")

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session
from app.config import PROJECT_ROOT, STORAGE_DIR
from app.db.database import Base
from app.db.models import (User, UserProfile, Contract, ContractWorkflow, Document, DocumentMasking,
                           DocumentFileInfo, CompanySetting, AuthSession, AuditEvent)
from app.security import hash_password

LEGACY_TABLES = ("app_users", "email_verifications", "contracts", "documents", "document_maskings",
                 "document_extracts", "business_verification", "validation_results")


def source_url():
    configured = os.getenv("DATABASE_URL")
    if configured:
        return configured
    if all(os.getenv(key) for key in ("DB_USER", "DB_PASSWORD", "DB_HOST")):
        return URL.create("postgresql+psycopg2", username=os.getenv("DB_USER"), password=os.getenv("DB_PASSWORD"),
                          host=os.getenv("DB_HOST"), port=int(os.getenv("DB_PORT", "6543")),
                          database=os.getenv("DB_NAME", "postgres"))
    legacy = PROJECT_ROOT / "evidence_manager.db"
    if not legacy.exists():
        raise RuntimeError("기존 DB 설정이 없습니다. 빈 시범환경은 --empty 옵션으로 준비하세요.")
    return "sqlite:///" + str(legacy)


def legacy_file(value):
    if not value:
        return None
    roots = [(PROJECT_ROOT / "storage").resolve(), STORAGE_DIR.resolve()]
    path = Path(value)
    candidates = [path] if path.is_absolute() else [PROJECT_ROOT / path, PROJECT_ROOT / "storage" / path]
    basename = value.replace("\\", "/").rsplit("/", 1)[-1]
    candidates.extend(root / folder / basename for root in roots for folder in ("raw", "masked"))
    for candidate in candidates:
        resolved = candidate.resolve()
        if any(resolved.is_relative_to(root) for root in roots) and resolved.is_file():
            return resolved
    return None


def prepare_legacy_rows(name, rows):
    """Retain ownership history without retaining reusable source credentials."""
    if name != "app_users":
        return rows
    return [{**row, "password": hash_password(secrets.token_urlsafe(24))} for row in rows]


def migrate(empty=False):
    target = STORAGE_DIR / "pilot.db"
    if target.exists():
        raise RuntimeError("시범 DB가 이미 있습니다. 기존 자료를 덮어쓰지 않았습니다.")
    records = {}
    if not empty:
        source = create_engine(source_url(), connect_args={"connect_timeout": 15} if str(source_url()).startswith("postgresql") else {})
        try:
            with source.connect() as connection:
                if source.dialect.name == "postgresql":
                    connection = connection.execution_options(isolation_level="REPEATABLE READ")
                with connection.begin():
                    if source.dialect.name == "postgresql":
                        connection.exec_driver_sql("SET TRANSACTION READ ONLY")
                    available = set(inspect(connection).get_table_names())
                    for name in LEGACY_TABLES:
                        if name in available:
                            table = Base.metadata.tables[name]
                            # Existing passwords are not needed for ownership
                            # history and should not be read from the source DB.
                            columns = [column for column in table.columns if name != "app_users" or column.name != "password"]
                            records[name] = [dict(row) for row in connection.execute(select(*columns)).mappings()]
        finally:
            source.dispose()
    stage = STORAGE_DIR / (".migration-" + uuid.uuid4().hex + ".db")
    destination = create_engine("sqlite:///" + str(stage))
    Base.metadata.create_all(destination)
    copied = 0
    credentials = []
    try:
        with destination.begin() as connection:
            for name in LEGACY_TABLES:
                rows = records.get(name, [])
                if rows:
                    connection.execute(Base.metadata.tables[name].insert(), prepare_legacy_rows(name, rows))
        with Session(destination) as db:
            # Imported owners remain for history; their old demo passwords cannot log in.
            for user in db.query(User).all():
                db.add(UserProfile(user_id=user.user_id, role="operator", display_name="이전 자료 소유자",
                                   active=False, must_change_password=True))
            for contract in db.query(Contract).all():
                db.add(ContractWorkflow(contract_id=contract.contract_id, amount_basis="UNKNOWN"))
            for document in db.query(Document).all():
                original = legacy_file(document.storage_path)
                if not original:
                    continue
                content = original.read_bytes()
                stem = uuid.uuid4().hex
                key = f"raw/{document.contract_id}/{stem}{original.suffix.lower()}"
                new_file = STORAGE_DIR / key
                new_file.parent.mkdir(parents=True, exist_ok=True)
                new_file.write_bytes(content)
                document.storage_path = key
                db.add(DocumentFileInfo(document_id=document.document_id, sha256=hashlib.sha256(content).hexdigest(), byte_size=len(content)))
                raw_text = original.parent / ("extracted_raw_" + original.name + ".txt")
                if not raw_text.is_file() and original.suffix.lower() in {".txt", ".md", ".json", ".csv"}:
                    raw_text = original
                if raw_text.is_file():
                    text_target = STORAGE_DIR / "text" / (stem + ".txt")
                    text_target.parent.mkdir(parents=True, exist_ok=True)
                    text_target.write_text(raw_text.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
                mask = db.query(DocumentMasking).filter_by(document_id=document.document_id).first()
                old_mask = legacy_file(mask.masked_file_path) if mask else None
                if old_mask:
                    mask_key = "masked/" + stem + ".txt"
                    (STORAGE_DIR / mask_key).write_text(old_mask.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
                    mask.masked_file_path = mask_key
                copied += 1
            for role, email, display in (("operator", "operator@company.local", "C업체 담당자"),
                                          ("representative", "representative@company.local", "C업체 대표")):
                password = secrets.token_urlsafe(18)
                existing = db.query(User).filter_by(email=email).first()
                user = existing or User(email=email)
                user.password = hash_password(password)
                db.add(user); db.flush()
                profile = db.get(UserProfile, user.user_id)
                if not profile:
                    profile = UserProfile(user_id=user.user_id)
                    db.add(profile)
                profile.role, profile.display_name = role, display
                profile.active, profile.must_change_password = True, True
                credentials.append(f"{display}\n로그인: {email}\n임시 비밀번호: {password}\n")
            db.add(CompanySetting(key="company_name", value=json.dumps("C업체 시범환경", ensure_ascii=False)))
            db.add(AuditEvent(actor_name="시스템", action="PILOT_DATA_IMPORTED", details=json.dumps({
                "contracts": len(records.get("contracts", [])), "documents": len(records.get("documents", [])), "originals_copied": copied})))
            db.commit()
        destination.dispose()
        os.replace(stage, target)
        # File is deliberately excluded from Git and backup exports. Never print secrets.
        (STORAGE_DIR / "initial-accounts.txt").write_text(
            "C업체 시범환경 초기 계정 (외부 공유 금지)\n처음 로그인하면 12자 이상의 새 비밀번호로 변경해야 합니다.\n"
            "변경 후 이 안내 파일은 안전하게 정리하세요.\n\n" + "\n".join(credentials), encoding="utf-8")
        print(json.dumps({"result": "prepared", "contracts": len(records.get("contracts", [])),
                          "documents": len(records.get("documents", [])), "originals_copied": copied,
                          "missing_originals": len(records.get("documents", [])) - copied}, ensure_ascii=False))
    finally:
        destination.dispose()
        if stage.exists():
            stage.unlink()


def backup(destination):
    if not (STORAGE_DIR / "pilot.db").is_file():
        raise RuntimeError("시범 DB를 먼저 준비하세요.")
    target = Path(destination).resolve()
    if target.exists():
        raise RuntimeError("백업 파일이 이미 있습니다. 새 파일 이름을 지정하세요.")
    target.parent.mkdir(parents=True, exist_ok=True)
    from app.services.backup_service import create_backup
    create_backup(target)
    print(json.dumps({"result": "backup_created", "file_name": target.name}, ensure_ascii=False))


MAX_BACKUP_MEMBERS = 100_000
MAX_BACKUP_EXPANDED_BYTES = 10 * 1024**3
MAX_BACKUP_MANIFEST_BYTES = 64 * 1024
_WINDOWS_DEVICES = {"CON", "PRN", "AUX", "NUL", "CLOCK$", "CONIN$", "CONOUT$"} | {
    prefix + str(number) for prefix in ("COM", "LPT") for number in range(1, 10)}


def restore(archive, destination):
    root = Path(destination).resolve()
    if root.exists():
        raise RuntimeError("복원 대상은 아직 존재하지 않는 새 폴더여야 합니다. 기존 DB는 덮어쓰지 않습니다.")
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        names = [member.filename for member in members]
        if names.count("pilot.db") != 1 or names.count("manifest.json") != 1:
            raise RuntimeError("백업에는 DB와 백업 설명 파일이 각각 하나씩 있어야 합니다.")
        if len({name.casefold() for name in names}) != len(names):
            raise RuntimeError("백업에 중복된 파일 경로가 있습니다.")
        if len(members) > MAX_BACKUP_MEMBERS or sum(item.file_size for item in members) > MAX_BACKUP_EXPANDED_BYTES:
            raise RuntimeError("백업 크기 제한(10GB)을 초과했습니다. 운영 담당자의 복원 절차가 필요합니다.")
        if bundle.getinfo("manifest.json").file_size > MAX_BACKUP_MANIFEST_BYTES:
            raise RuntimeError("백업 설명 파일의 크기 제한을 초과했습니다.")
        for member in members:
            path = PurePosixPath(member.filename)
            # Windows ZipInfo may normalize backslashes in filename; inspect
            # the original archive name as well, before creating any files.
            original_name = getattr(member, "orig_filename", member.filename)
            if (not path.parts or path.is_absolute() or ".." in path.parts
                    or any(character in original_name for character in ('\\', ':', '\x00'))
                    or path.as_posix() != member.filename.rstrip('/')
                    or any(part.endswith((' ', '.')) or part.split('.')[0].upper() in _WINDOWS_DEVICES
                           or any(character < ' ' or character in '<>"|?*' for character in part)
                           for part in path.parts)
                    or stat.S_ISLNK(member.external_attr >> 16) or member.flag_bits & 1):
                raise RuntimeError("백업에 허용되지 않는 경로가 있습니다.")
            if path.parts[0] not in {"pilot.db", "manifest.json", "raw", "masked", "text"}:
                raise RuntimeError("백업에 허용되지 않는 파일이 있습니다.")
            if path.parts[0] in {"pilot.db", "manifest.json"} and len(path.parts) != 1:
                raise RuntimeError("DB와 백업 설명 파일의 경로가 올바르지 않습니다.")
            if path.parts[0] in {"pilot.db", "manifest.json"} and member.is_dir():
                raise RuntimeError("DB와 백업 설명 파일은 일반 파일이어야 합니다.")
            if not (root / member.filename).resolve().is_relative_to(root):
                raise RuntimeError("백업 경로가 복원 폴더를 벗어납니다.")
        file_names = {member.filename.casefold() for member in members if not member.is_dir()}
        for member in members:
            if any(parent.as_posix().casefold() in file_names for parent in PurePosixPath(member.filename).parents):
                raise RuntimeError("백업에 파일과 폴더가 충돌하는 경로가 있습니다.")
        try:
            manifest = json.loads(bundle.read("manifest.json"))
        except (ValueError, UnicodeError) as error:
            raise RuntimeError("백업 설명 파일을 읽을 수 없습니다.") from error
        if not isinstance(manifest, dict) or manifest.get("format") != "c-pilot-v1" or manifest.get("database") != "pilot.db":
            raise RuntimeError("지원하는 시범환경 백업 형식이 아닙니다.")
        root.mkdir(parents=True)
        for member in members:
            if member.is_dir():
                (root / member.filename).mkdir(parents=True, exist_ok=True)
            else:
                target = root / member.filename
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(member) as source, target.open("wb") as output:
                    while chunk := source.read(1024 * 1024):
                        output.write(chunk)
    with closing(sqlite3.connect(str(root / "pilot.db"))) as database:
        with database:
            if database.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise RuntimeError("복원한 DB의 무결성을 확인하지 못했습니다. 복원 폴더를 사용하지 마세요.")
            database.execute("DELETE FROM pilot_auth_sessions")
            for key, expected in database.execute("SELECT storage_path, sha256 FROM documents JOIN pilot_document_files USING(document_id)"):
                path = (root / key).resolve()
                if not path.is_relative_to(root):
                    raise RuntimeError("원본 경로가 복원 폴더를 벗어납니다.")
                if path.is_file():
                    digest = hashlib.sha256()
                    with path.open('rb') as source:
                        while chunk := source.read(1024 * 1024):
                            digest.update(chunk)
                    if digest.hexdigest() != expected:
                        raise RuntimeError("복원한 원본 내용이 저장 당시와 다릅니다. 복원 폴더를 사용하지 마세요.")
    print(json.dumps({"result": "restored", "sessions": "expired", "next": "APP_STORAGE_ROOT를 복원 폴더로 지정하고 실행하세요."}, ensure_ascii=False))


def recover_account(email):
    if not (STORAGE_DIR / "pilot.db").is_file():
        raise RuntimeError("시범 DB가 없습니다.")
    engine = create_engine("sqlite:///" + str(STORAGE_DIR / "pilot.db"))
    try:
        with Session(engine) as db:
            user = db.query(User).filter_by(email=email.strip().lower()).first()
            profile = db.get(UserProfile, user.user_id) if user else None
            if not user or not profile or not profile.active:
                raise RuntimeError("사용 중인 계정이 아닙니다. 계정 주소를 확인하세요.")
            password = secrets.token_urlsafe(18)
            user.password = hash_password(password)
            profile.must_change_password = True
            db.query(AuthSession).filter_by(user_id=user.user_id).delete()
            db.add(AuditEvent(actor_name="서버 운영자", action="ACCOUNT_RECOVERY", details=json.dumps({"user_id": user.user_id})))
            db.commit()
            (STORAGE_DIR / "account-recovery.txt").write_text(
                f"계정 복구 안내 · 외부 공유 금지\n로그인: {user.email}\n임시 비밀번호: {password}\n첫 로그인 후 변경해야 합니다. 변경 후 이 파일을 안전하게 정리하세요.\n", encoding="utf-8")
        print(json.dumps({"result": "account_recovered", "credentials_file": "account-recovery.txt"}, ensure_ascii=False))
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="C업체 내부 DB 준비 · 백업 · 안전한 새 폴더 복원")
    commands = parser.add_subparsers(dest="command", required=True)
    migration = commands.add_parser("migrate")
    migration.add_argument("--empty", action="store_true", help="기존 자료 없이 새로운 시범환경 시작")
    export = commands.add_parser("backup")
    export.add_argument("--output", required=True)
    recovery = commands.add_parser("restore")
    recovery.add_argument("--archive", required=True)
    recovery.add_argument("--destination", required=True)
    account = commands.add_parser("recover-account")
    account.add_argument("--email", required=True, help="서버 운영자가 로그인 계정을 복구")
    args = parser.parse_args()
    try:
        if args.command == "migrate": migrate(args.empty)
        elif args.command == "backup": backup(args.output)
        elif args.command == "restore": restore(args.archive, args.destination)
        else: recover_account(args.email)
    except Exception as error:
        # Driver errors can contain connection secrets. Print safe actionable errors only.
        if isinstance(error, RuntimeError):
            print(str(error), file=sys.stderr)
        else:
            print(f"작업 실패 ({type(error).__name__}). DB 연결·파일 접근 설정을 확인하세요. 연결 정보는 출력하지 않았습니다.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
