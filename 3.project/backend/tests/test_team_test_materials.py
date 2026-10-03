"""Measurement fixtures are DEV-only, isolated, and do not reveal answers in ZIPs."""
import csv
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from pypdf import PdfReader

from backend.scripts import prepare_team_test_materials as materials
from backend.scripts import prepare_team_test_inbox as inbox


@pytest.mark.parametrize("location", ["root", "existing", "outside", "traversal"])
def test_inbox_refuses_existing_or_outside_data(tmp_path, monkeypatch, location):
    root = tmp_path / "demo"
    (root / "existing").mkdir(parents=True)
    monkeypatch.setattr(inbox, "DEMO_ROOT", root)
    outside = tmp_path / "customer"
    outside.mkdir()
    sentinel = outside / "important.txt"
    sentinel.write_text("keep")
    paths = {"root": root, "existing": root / "existing", "outside": outside,
             "traversal": root / ".." / "customer" / "new"}
    with pytest.raises(ValueError):
        inbox.fresh_output(paths[location])
    assert sentinel.read_text() == "keep"
    assert inbox.fresh_output(root / "fresh") == root / "fresh"


def test_participant_zip_is_allowlist_even_with_extra_answers(tmp_path):
    folder = tmp_path / "participant"
    (folder / "originals").mkdir(parents=True)
    for name in ("registered_contract.json", "registered_contract.pdf", "business_rules.md", "blank_record.csv",
                 "originals/document_01.pdf", "answers.md", "verification.json", "originals/corrected.pdf"):
        (folder / name).write_text("sample")
    archive = tmp_path / "participant.zip"
    materials.archive_participant(folder, archive)
    with zipfile.ZipFile(archive) as z:
        assert sorted(z.namelist()) == sorted(["registered_contract.json", "registered_contract.pdf",
            "business_rules.md", "blank_record.csv", "originals/document_01.pdf"])


def test_frozen_materials_hashes_and_blanks():
    manifest = inbox.verify_bundle()
    assert len(manifest["dev_source_sha256"]) == 6
    assert all(p.startswith("eval/dataset/dev/") for p in manifest["dev_source_sha256"])
    for case in manifest["cases"]:
        folder = materials.BUNDLE / "participants" / case["case_id"]
        with (folder / "blank_record.csv").open(encoding="utf-8-sig", newline="") as f:
            assert list(csv.reader(f)) == [materials.RECORD_COLUMNS, [""] * len(materials.RECORD_COLUMNS)]
        with zipfile.ZipFile(materials.BUNDLE / "packages" / (case["case_id"] + ".zip")) as z:
            assert set(z.namelist()) == {p.relative_to(folder).as_posix() for p in materials.participant_files(folder)}
            for name in z.namelist():
                assert z.read(name) == (folder / name).read_bytes()


def test_ab_structure_amounts_and_pdf_positions_are_equal():
    cases = {c["case_id"]: c for c in inbox.verify_bundle()["cases"]}
    for task in ("task_1", "task_2"):
        a, b = [cases[f"{task}_{v}"] for v in ("A", "B")]
        assert [d["kind"] for d in a["documents"]] == [d["kind"] for d in b["documents"]]
        assert a["expected_issue"] == b["expected_issue"]
        assert len(a["documents"]) == (5 if task == "task_1" else 6)
        for case in (a, b):
            registration = case["registration"]
            assert len(str(registration["contract_amount"])) == 7
            assert len(str(registration["tax_amount"])) == 6
            assert registration["amount_basis"] == "TOTAL"
        for doc_a, doc_b in zip(a["documents"], b["documents"]):
            positions = []
            for doc in (doc_a, doc_b):
                reader = PdfReader(materials.BUNDLE / doc["path"])
                assert len(reader.pages) == 1
                rows = []
                reader.pages[0].extract_text(visitor_text=lambda text, cm, tm, font, size:
                    rows.append((tm[4], tm[5], size)) if text.strip() else None)
                positions.append(rows)
            assert positions[0] == positions[1]
        if task == "task_1":
            assert {d["kind"] for d in a["documents"]} == set(materials.DOCUMENT_TYPES) - {"bank_account"}
        else:
            for case in (a, b):
                replacement = case["replacement"]
                assert replacement["initial_total"] - replacement["correct_total"] == 110000
                assert replacement["correct_total"] == case["registration"]["contract_amount"]
                assert replacement["path"].startswith("facilitator/replies/")


def test_inherited_live_settings_cannot_enable_llm_or_nts(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_LLM_ENABLED", "true")
    monkeypatch.setenv("APP_NTS_MODE", "api")
    result = inbox.isolated_environment(tmp_path)
    assert result["APP_LLM_ENABLED"] == "false"
    assert result["APP_NTS_MODE"] == "disabled"
    assert result["APP_DEPLOYMENT_MODE"] == "pilot"
    assert result["APP_STORAGE_ROOT"] == str(tmp_path / "storage")


def test_failed_preparation_cannot_be_reused(tmp_path, monkeypatch):
    monkeypatch.setattr(inbox, "DEMO_ROOT", tmp_path)
    monkeypatch.setattr(inbox.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1, stderr="failed"))
    target = tmp_path / "new"
    with pytest.raises(RuntimeError, match="준비 실패"):
        inbox.prepare(target)
    assert materials.read_json(target / "inbox.json")["status"] == "FAILED"
    with pytest.raises(ValueError):
        inbox.prepare(target)


def test_tampered_material_is_rejected_before_creating_inbox(tmp_path, monkeypatch):
    bundle = tmp_path / "bundle"
    (bundle / "facilitator").mkdir(parents=True)
    (bundle / "document.pdf").write_bytes(b"modified")
    materials.save_json(bundle / "facilitator/manifest.json", {
        "file_sha256": {"document.pdf": "incorrect"}})
    monkeypatch.setattr(inbox, "BUNDLE", bundle)
    monkeypatch.setattr(inbox, "DEMO_ROOT", tmp_path / "demo")
    with pytest.raises(ValueError, match="해시"):
        inbox.prepare(tmp_path / "demo" / "new")
    assert not (tmp_path / "demo").exists()


def test_extra_issue_and_wrong_issue_fail_verification():
    missing = {"rule_id": "REQUIRED_DOCUMENTS", "status": "MISSING", "field": "bank_account"}
    mismatch = {"rule_id": "AMOUNT_MATCH_ESTIMATE", "status": "FAIL"}
    inbox.require_issue([missing], missing)
    with pytest.raises(AssertionError):
        inbox.require_issue([missing, mismatch], missing)
    with pytest.raises(AssertionError):
        inbox.require_issue([mismatch], missing)
    with pytest.raises(AssertionError):
        inbox.require_issue([missing], None)
