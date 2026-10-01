import hashlib
import json
import sqlite3
import zipfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta
from threading import Event

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.db.database import Base
from backend.app.db.models import User, Contract, Document, DocumentFileInfo, AuthSession
from backend.app.services import backup_service, storage_service


@pytest.fixture
def backup_source(tmp_path, monkeypatch, password_hash):
    root = tmp_path / "backup-source"
    root.mkdir()
    (root / "raw" / "1").mkdir(parents=True)
    original = b"contract original fixture"
    (root / "raw" / "1" / "original.txt").write_bytes(original)
    (root / "raw" / "1" / ".pending-not-published.txt").write_bytes(b"must not be included")
    (root / "initial-accounts.txt").write_text("must not be included", encoding="utf-8")
    engine = create_engine("sqlite:///" + str(root / "pilot.db"))
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(User(user_id=1, email="backup@tests.local", password=password_hash))
        db.flush()
        db.add(Contract(contract_id=1, user_id=1, title="백업 테스트", vendor_name="테스트", business_number="123-45-67890", contract_amount=1000))
        db.flush()
        db.add(Document(document_id=1, contract_id=1, file_name="original.txt", storage_path="raw/1/original.txt"))
        db.flush()
        db.add(DocumentFileInfo(document_id=1, sha256=hashlib.sha256(original).hexdigest(), byte_size=len(original)))
        db.add(AuthSession(token_hash="a" * 64, user_id=1, expires_at=datetime(2026, 10, 1) + timedelta(days=1)))
        db.commit()
    engine.dispose()
    monkeypatch.setattr(backup_service, "STORAGE_DIR", root)
    return root


def test_backup_and_fresh_folder_restore_keep_originals_and_expire_sessions(backup_source, tmp_path):
    import manage_pilot as pilot
    archive = tmp_path / "backup.zip"
    backup_service.create_backup(archive)
    with zipfile.ZipFile(archive) as bundle:
        names = set(bundle.namelist())
        assert {"pilot.db", "manifest.json", "raw/1/original.txt"} <= names
        assert not any(".pending-" in name or "initial-accounts" in name for name in names)
        assert json.loads(bundle.read("manifest.json"))["format"] == "c-pilot-v1"
    destination = tmp_path / "fresh-restore"
    pilot.restore(archive, destination)
    assert (destination / "raw" / "1" / "original.txt").read_bytes() == (backup_source / "raw" / "1" / "original.txt").read_bytes()
    with closing(sqlite3.connect(str(destination / "pilot.db"))) as db:
        assert db.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert db.execute("SELECT count(*) FROM contracts").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM pilot_auth_sessions").fetchone()[0] == 0
    with pytest.raises(RuntimeError):
        pilot.restore(archive, destination)


def test_zip_compression_does_not_hold_publication_lock(backup_source, tmp_path, monkeypatch):
    started, finish = Event(), Event()
    write = backup_service._write_bundle
    def slow_zip(*args):
        started.set()
        assert finish.wait(10)
        return write(*args)
    monkeypatch.setattr(backup_service, "_write_bundle", slow_zip)
    with ThreadPoolExecutor(max_workers=1) as workers:
        future = workers.submit(backup_service.create_backup, tmp_path / "background-backup.zip")
        try:
            assert started.wait(2)
            acquired = storage_service.STORAGE_LOCK.acquire(timeout=1)
            assert acquired, "ZIP work is holding the DB publication lock."
            storage_service.STORAGE_LOCK.release()
            assert not future.done()
        finally:
            finish.set()
        future.result(timeout=10)


@pytest.mark.parametrize("entry", ["../escape.txt", "raw/../../escape.txt", "C:/escape.txt", "raw\\escape.txt", "initial-accounts.txt"])
def test_restore_rejects_unsafe_or_credential_paths_before_creating_folder(entry, tmp_path):
    import manage_pilot as pilot
    archive = tmp_path / "unsafe.zip"
    # Windows zipfile normalizes backslashes while writing. Replace a same-size
    # placeholder in both ZIP headers to preserve the untrusted input bytes.
    archived_entry = entry.replace("\\", "!")
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("manifest.json", json.dumps({"format": "c-pilot-v1", "database": "pilot.db"}))
        bundle.writestr("pilot.db", b"unreachable database placeholder")
        bundle.writestr(archived_entry, b"unsafe")
    if archived_entry != entry:
        archive.write_bytes(archive.read_bytes().replace(archived_entry.encode(), entry.encode()))
    destination = tmp_path / "must-not-exist"
    with pytest.raises(RuntimeError):
        pilot.restore(archive, destination)
    assert not destination.exists()


@pytest.mark.parametrize("missing", ["pilot.db", "manifest.json"])
def test_restore_requires_database_and_manifest_before_creating_folder(missing, tmp_path):
    import manage_pilot as pilot
    archive = tmp_path / "missing-required.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        if missing != "manifest.json":
            bundle.writestr("manifest.json", json.dumps({"format": "c-pilot-v1", "database": "pilot.db"}))
        if missing != "pilot.db":
            bundle.writestr("pilot.db", b"unreachable database placeholder")
    destination = tmp_path / "must-not-exist"
    with pytest.raises(RuntimeError):
        pilot.restore(archive, destination)
    assert not destination.exists()


def test_restore_rejects_changed_original_hash(backup_source, tmp_path):
    import manage_pilot as pilot
    archive = tmp_path / "valid.zip"
    changed = tmp_path / "changed-original.zip"
    backup_service.create_backup(archive)
    with zipfile.ZipFile(archive) as source, zipfile.ZipFile(changed, "w") as target:
        for entry in source.infolist():
            content = source.read(entry)
            if entry.filename == "raw/1/original.txt":
                content = b"not the backed-up original"
            target.writestr(entry, content)
    with pytest.raises(RuntimeError):
        pilot.restore(changed, tmp_path / "unusable-restore")
    assert (backup_source / "raw" / "1" / "original.txt").read_bytes() == b"contract original fixture"
