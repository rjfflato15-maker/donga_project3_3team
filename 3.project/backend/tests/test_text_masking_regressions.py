from types import SimpleNamespace

import pytest

from backend.app.ai.masking import mask_sensitive_information
from backend.app.services import storage_service


@pytest.mark.parametrize("corporate_number", ["110111-9345210", "110111-0345210"])
def test_labeled_corporate_registration_is_masked_for_zero_and_nine(corporate_number):
    raw = f"법 인 등 록 번 호 : {corporate_number}\n합계금액: 38,500,000원\n작성일자: 2026-12-15\n"
    protected, count, categories, _ = mask_sensitive_information(raw)
    assert corporate_number not in protected
    assert count >= 1
    assert categories
    assert "38,500,000원" in protected
    assert "2026-12-15" in protected
    assert corporate_number in raw


@pytest.mark.parametrize("label,name", [
    ("대표 이 사", "한 도 윤"), ("대 표 자", "최 강 민"),
    ("대표자", "홍길동"),
])
def test_explicit_representative_label_masks_spaced_names(label, name):
    raw = f"{label}: {name} (인)\n계약금액: 38,500,000원\n"
    protected, _, _, _ = mask_sensitive_information(raw)
    assert name not in protected
    assert "38,500,000원" in protected
    assert name in raw


@pytest.mark.parametrize("label,company", [
    ("상 호", "주식회사 한빛솔루션"), ("법 인 명", "주식회사 테스트산업"),
])
def test_explicit_company_labels_mask_legal_company_names(label, company):
    raw = f"{label}: {company}\n공급가액: 35,000,000원\n세액: 3,500,000원\n"
    protected, _, _, _ = mask_sensitive_information(raw)
    assert company not in protected
    assert "35,000,000원" in protected
    assert "3,500,000원" in protected
    assert company in raw


def test_read_texts_refreshes_old_masked_sidecar_without_mutating_original(db_factory):
    raw = "법인등록번호: 110111-9345210\n대표 이 사: 한 도 윤\n상호: 주식회사 한빛솔루션\n합계금액: 38,500,000원\n"
    key, path, _ = storage_service.store_original(1, "계약서.txt", raw.encode("utf-8"))
    old_mask_key = storage_service.store_text(key, raw, raw)
    document = SimpleNamespace(storage_path=key, masking=SimpleNamespace(masked_file_path=old_mask_key))
    original_before = path.read_bytes()
    read_raw, protected = storage_service.read_texts(document)
    assert read_raw == raw
    assert "110111-9345210" not in protected
    assert "한 도 윤" not in protected
    assert "주식회사 한빛솔루션" not in protected
    assert "38,500,000원" in protected
    assert path.read_bytes() == original_before


def test_current_masking_failure_never_reuses_potentially_unprotected_old_sidecar(db_factory, monkeypatch):
    from backend.app.ai import masking
    raw = "법인등록번호: 110111-9345210\n대표 이 사: 한 도 윤\n"
    key, _, _ = storage_service.store_original(1, "계약서.txt", raw.encode("utf-8"))
    old_mask_key = storage_service.store_text(key, raw, raw)
    document = SimpleNamespace(storage_path=key, masking=SimpleNamespace(masked_file_path=old_mask_key))
    def fail(*_, **__):
        raise RuntimeError("privacy filter unavailable")
    monkeypatch.setattr(masking, "mask_sensitive_information", fail)
    read_raw, protected = storage_service.read_texts(document)
    assert read_raw == raw
    assert "110111-9345210" not in protected
    assert "한 도 윤" not in protected
    assert "마스킹" in protected
