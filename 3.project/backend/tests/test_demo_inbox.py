"""Demo preparation must not cross into customer/heldout data or enable external calls."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.scripts import prepare_demo_inbox as demo
from backend.launcher import environment, settings as launcher_settings


@pytest.fixture
def synthetic_dataset(tmp_path):
    dataset = tmp_path / "dataset"
    cases = []
    for number, scenario in enumerate(demo.SCENARIOS, 1):
        source = dataset / f"dev/case_{number}/original.txt"
        source.parent.mkdir(parents=True)
        source.write_text(f"synthetic document {number}", encoding="utf-8")
        cases.append({"split": "dev", "scenario": scenario, "contract_id": number,
                      "documents": [{"path": source.relative_to(dataset).as_posix(),
                                     "sha256": demo.digest(source)}]})
    # Heldout rows deliberately reference unreadable/missing originals. No access is allowed.
    cases.append({"split": "test", "scenario": "normal", "contract_id": 99,
                  "documents": [{"path": "test/must-not-be-opened.pdf", "sha256": "missing"}]})
    demo.save_json(dataset / "manifest.json", {"contracts": cases})
    return dataset


@pytest.mark.parametrize("location", ["root", "existing", "customer"])
def test_output_cannot_overwrite_or_leave_demo_area(tmp_path, monkeypatch, location):
    root = tmp_path / "demo"
    root.mkdir()
    existing = root / "existing"
    existing.mkdir()
    customer = tmp_path / "customer"
    customer.mkdir()
    sentinel = customer / "pilot.db"
    sentinel.write_bytes(b"customer data")
    monkeypatch.setattr(demo, "DEMO_ROOT", root)
    target = {"root": root, "existing": existing, "customer": customer}[location]
    with pytest.raises(ValueError):
        demo.validate_output(target)
    assert sentinel.read_bytes() == b"customer data"
    assert demo.validate_output(root / "new") == root / "new"


def test_dev_selection_never_opens_test_originals(synthetic_dataset):
    cases = demo.select_dev_cases(synthetic_dataset)
    assert len(cases) == 5
    assert {case["split"] for case in cases} == {"dev"}
    assert not (synthetic_dataset / "test").exists()


@pytest.mark.parametrize("bad_path", ["test/must-not-be-opened.pdf", "dev/../../customer.db", ""])
def test_dev_manifest_cannot_redirect_to_other_sources(synthetic_dataset, bad_path):
    manifest = demo.read_json(synthetic_dataset / "manifest.json")
    manifest["contracts"][0]["documents"][0]["path"] = bad_path
    demo.save_json(synthetic_dataset / "manifest.json", manifest)
    with pytest.raises(ValueError, match="dev 밖"):
        demo.select_dev_cases(synthetic_dataset)


def test_source_hash_mismatch_stops_before_creating_demo(synthetic_dataset, tmp_path, monkeypatch):
    root = tmp_path / "demo"
    monkeypatch.setattr(demo, "DEMO_ROOT", root)
    (synthetic_dataset / "dev/case_1/original.txt").write_bytes(b"modified")
    with pytest.raises(ValueError, match="해시"):
        demo.prepare(root / "new", synthetic_dataset)
    assert not root.exists()


@pytest.mark.parametrize("status", ["READY", "FAILED"])
def test_worker_cannot_reseed_an_existing_inbox(tmp_path, monkeypatch, status):
    root = tmp_path / "demo"
    target = root / "existing"
    target.mkdir(parents=True)
    monkeypatch.setattr(demo, "DEMO_ROOT", root)
    demo.save_json(target / "demo_manifest.json", {"kind": "C_COMPANY_DEV_DEMO", "status": status})
    with pytest.raises(ValueError, match="준비 중"):
        demo.check_worker_root(target)
    with pytest.raises(ValueError, match="전용 경로"):
        demo.check_worker_root(tmp_path / "customer")


def test_demo_and_launcher_disable_nts_even_when_parent_enables_api(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_NTS_MODE", "api")
    monkeypatch.setenv("APP_LLM_ENABLED", "true")
    storage = tmp_path / "demo/storage"
    worker = demo.worker_environment(storage)
    assert worker["APP_STORAGE_ROOT"] == str(storage)
    assert worker["APP_DEPLOYMENT_MODE"] == "pilot"
    assert worker["APP_NTS_MODE"] == "disabled"
    assert worker["APP_LLM_ENABLED"] == "false"
    runtime = environment.pilot_environment({"storage_root": str(storage), "port": 8020, "intranet": False})
    assert runtime["APP_NTS_MODE"] == "disabled"
    assert runtime["APP_LLM_ENABLED"] == "false"


def test_failed_worker_stops_next_mode_without_exposing_output(synthetic_dataset, tmp_path, monkeypatch, capsys):
    root = tmp_path / "demo"
    target = root / "new"
    monkeypatch.setattr(demo, "DEMO_ROOT", root)
    calls = []

    def failed_worker(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=2, stdout="private password", stderr="private original text")

    monkeypatch.setattr(demo.subprocess, "run", failed_worker)
    with pytest.raises(ValueError, match="rule 준비 실패"):
        demo.prepare(target, synthetic_dataset)
    assert len(calls) == 1
    assert calls[0][1]["env"]["APP_NTS_MODE"] == "disabled"
    assert demo.read_json(target / "demo_manifest.json")["status"] == "FAILED"
    output = capsys.readouterr()
    assert "private" not in output.out + output.err
    assert not (target / "guarded-replay").exists()


def test_generated_launch_settings_keep_each_inbox_separate(tmp_path):
    root = tmp_path / "demo"
    for mode in ("rule", "guarded-replay"):
        (root / mode / "storage").mkdir(parents=True)
    (root / "rule/storage/initial-accounts.txt").write_text("private demo credential", encoding="utf-8")
    demo.write_launch_files(root, ["rule", "guarded-replay"])
    for mode, port in (("rule", 8020), ("guarded-replay", 8021)):
        settings = launcher_settings.load_settings(root / mode / "launcher/settings.json")
        assert settings["storage_root"] == str(root / mode / "storage")
        assert settings["port"] == port
        assert not Path(settings["backup_directory"]).is_relative_to(Path(settings["storage_root"]))
        assert environment.pilot_environment(settings)["APP_NTS_MODE"] == "disabled"
    assert (root / "Run-demo.bat").exists()
    assert "APP_NTS_MODE=disabled" in (root / "README.md").read_text(encoding="utf-8")
