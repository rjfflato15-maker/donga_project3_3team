import hashlib

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app import security


def test_unicode_password_and_unique_salt():
    password = "사내망 테스트 암호 🔐 2026!"
    first = security.hash_password(password)
    second = security.hash_password(password)
    assert first != second
    assert security.verify_password(password, first)
    assert not security.verify_password("잘못된 암호", first)
    assert not security.verify_password(first, first)


@pytest.mark.parametrize("stored", [
    "plain-text-password", hashlib.sha256(b"plain-text-password").hexdigest(), "", None,
    "pbkdf2_sha256$1$" + "a" * 32 + "$" + "b" * 64,
    "pbkdf2_sha256$599999$" + "a" * 32 + "$" + "b" * 64,
    "pbkdf2_sha256$2000001$" + "a" * 32 + "$" + "b" * 64,
    "pbkdf2_sha256$999999999999999999999$" + "a" * 32 + "$" + "b" * 64,
    "pbkdf2_sha256$600000$aa$" + "b" * 64,
    "pbkdf2_sha256$600000$" + "a" * 32 + "$bb",
    "pbkdf2_sha256$600000$" + "z" * 32 + "$" + "b" * 64,
    "pbkdf2_sha256$600000$" + "a" * 32 + "$" + "b" * 64 + "$extra",
])
def test_invalid_records_rejected_before_expensive_hash(stored, monkeypatch):
    def must_not_run(*_, **__):
        pytest.fail("Malformed/legacy records must be rejected before PBKDF2.")
    monkeypatch.setattr(security.hashlib, "pbkdf2_hmac", must_not_run)
    assert not security.verify_password("plain-text-password", stored)
    if isinstance(stored, str):
        assert not security.verify_password(stored, stored)


def test_migration_helper_discards_all_legacy_credentials():
    import manage_pilot as pilot
    old = [
        {"user_id": 1, "email": "plain@tests.local", "password": "old-plain-password"},
        {"user_id": 2, "email": "hash@tests.local", "password": hashlib.sha256(b"old-password").hexdigest()},
        {"user_id": 3, "email": "pbkdf@tests.local", "password": security.hash_password("Old-password-2026!")},
    ]
    original = [dict(row) for row in old]
    changed = pilot.prepare_legacy_rows("app_users", old)
    assert old == original
    assert changed is not old
    for before, after in zip(old, changed):
        assert after["user_id"] == before["user_id"]
        assert after["email"] == before["email"]
        assert after["password"].startswith("pbkdf2_sha256$600000$")
        assert after["password"] != before["password"]
        assert not security.verify_password(before["password"], after["password"])
    other = [{"contract_id": 1, "title": "ownership preserved"}]
    assert pilot.prepare_legacy_rows("contracts", other) is other


def test_migrate_local_fixture_keeps_imported_users_inactive(tmp_path, monkeypatch):
    import manage_pilot as pilot
    source_path = tmp_path / "legacy-fixture.db"
    target_root = tmp_path / "new-company"
    target_root.mkdir()
    (target_root / "masked").mkdir()
    source = create_engine("sqlite:///" + str(source_path))
    pilot.Base.metadata.create_all(source)
    with Session(source) as db:
        user = pilot.User(email="legacy-owner@tests.local", password="source-password-must-not-survive")
        db.add(user)
        db.flush()
        db.add(pilot.Contract(user_id=user.user_id, title="이주한 계약", vendor_name="테스트 업체",
                              business_number="123-45-67890", contract_amount=1000))
        db.commit()
    source.dispose()
    monkeypatch.setattr(pilot, "STORAGE_DIR", target_root)
    monkeypatch.setattr(pilot, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(pilot, "source_url", lambda: "sqlite:///" + str(source_path))
    pilot.migrate(empty=False)
    destination = create_engine("sqlite:///" + str(target_root / "pilot.db"))
    try:
        with Session(destination) as db:
            imported = db.query(pilot.User).filter_by(email="legacy-owner@tests.local").one()
            profile = db.get(pilot.UserProfile, imported.user_id)
            assert profile.active is False
            assert profile.must_change_password is True
            assert imported.password.startswith("pbkdf2_sha256$600000$")
            assert not security.verify_password("source-password-must-not-survive", imported.password)
            for email in ("operator@company.local", "representative@company.local"):
                new_user = db.query(pilot.User).filter_by(email=email).one()
                new_profile = db.get(pilot.UserProfile, new_user.user_id)
                assert new_profile.active is True
                assert new_profile.must_change_password is True
            assert db.query(pilot.Contract).count() == 1
    finally:
        destination.dispose()
    assert (target_root / "initial-accounts.txt").is_file()
