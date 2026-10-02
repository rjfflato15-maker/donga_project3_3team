"""Run all tests against local, disposable data, never the configured customer DB."""
import importlib
import os
import sys
import tempfile
from pathlib import Path

# Pytest loads this file before importing any test/application modules. Pilot
# mode ignores legacy PostgreSQL settings from .env, and this separate directory
# ensures even an accidental default-engine connection cannot touch pilot.db.
IMPORT_STORAGE = Path(tempfile.mkdtemp(prefix="c-pilot-pytest-import-"))
os.environ["APP_DEPLOYMENT_MODE"] = "pilot"
os.environ["APP_NTS_MODE"] = "disabled"
os.environ["APP_LLM_ENABLED"] = "false"
os.environ["APP_STORAGE_ROOT"] = str(IMPORT_STORAGE)
os.environ["APP_COOKIE_SECURE"] = "false"
os.environ["APP_ALLOWED_ORIGINS"] = "http://testserver"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.app.db.database import Base, get_db
from backend.app.db.models import User, UserProfile
from backend.app.main import app
from backend.app.security import hash_password

TEST_PASSWORD = "Test-only-password-2026!"


@pytest.fixture(scope="session")
def password_hash():
    return hash_password(TEST_PASSWORD)


@pytest.fixture
def db_factory(tmp_path, monkeypatch):
    """One file-backed DB/storage per test; usable by independent HTTP threads."""
    test_root = tmp_path / "isolated-company"
    test_root.mkdir()
    engine = create_engine("sqlite:///" + str(test_root / "test.db"),
                           connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def sqlite_policy(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")

    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(engine)
    for module_name in ("backend.app.config", "backend.app.services.storage_service",
                        "backend.app.services.pipeline_service", "backend.app.services.backup_service",
                        "backend.app.api.pilot"):
        module = importlib.import_module(module_name)
        for name, value in (("STORAGE_DIR", test_root), ("RAW_STORAGE_DIR", test_root / "raw"),
                            ("MASKED_STORAGE_DIR", test_root / "masked"),
                            ("DB_PATH", test_root / "test.db"),
                            ("DATABASE_URL", "sqlite:///" + str(test_root / "test.db")),
                            ("PROJECT_ROOT", tmp_path)):
            if hasattr(module, name):
                monkeypatch.setattr(module, name, value)
    main = importlib.import_module("backend.app.main")
    database = importlib.import_module("backend.app.db.database")
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(main, "SessionLocal", factory)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", factory)

    def override_db():
        with factory() as db:
            yield db

    old_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_db
    auth = importlib.import_module("backend.app.api.auth")
    auth._attempts.clear()
    yield factory
    app.dependency_overrides.clear()
    app.dependency_overrides.update(old_overrides)
    engine.dispose()


@pytest.fixture
def accounts(db_factory, password_hash):
    records = {}
    with db_factory() as db:
        for role in ("operator", "representative"):
            user = User(email=f"{role}@tests.local", password=password_hash)
            db.add(user)
            db.flush()
            db.add(UserProfile(user_id=user.user_id, role=role, display_name=f"테스트 {role}",
                               active=True, must_change_password=False))
            records[role] = {"user_id": user.user_id, "email": user.email, "password": TEST_PASSWORD}
        db.commit()
    return records


@pytest.fixture
def client(db_factory):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def operator_client(client, accounts):
    account = accounts["operator"]
    response = client.post("/api/auth/login", json={"email": account["email"], "password": account["password"]})
    assert response.status_code == 200, response.text
    yield client


@pytest.fixture
def separate_client(client, accounts):
    """A second browser cookie jar; main fixture owns the application lifespan."""
    clients = []

    def create(role="representative"):
        other = TestClient(app)
        account = accounts[role]
        response = other.post("/api/auth/login", json={"email": account["email"], "password": account["password"]})
        assert response.status_code == 200, response.text
        clients.append(other)
        return other

    yield create
    for other in clients:
        other.close()
