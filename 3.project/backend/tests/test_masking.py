import pytest
from backend.app.ai.masking import mask_sensitive_information


def test_rrn_masking():
    text = "대표자 홍길동 주민번호: 800101-1234567 등록"
    masked, count, cats, token_map = mask_sensitive_information(text)
    assert "[RRN_001]" in masked
    assert "800101-1234567" not in masked
    assert "RRN" in cats
    assert count >= 1


def test_phone_and_email_masking():
    text = "담당자 연락처: 010-1234-5678, 이메일: user@example.com"
    masked, count, cats, token_map = mask_sensitive_information(text)
    assert "[PHONE_001]" in masked
    assert "010-1234-5678" not in masked
    assert "[EMAIL_001]" in masked
    assert "user@example.com" not in masked
    assert "PHONE" in cats
    assert "EMAIL" in cats


def test_biz_no_preservation_vs_account_masking():
    text = "사업자등록번호: 123-45-67890, 입금계좌: 110-123-456789 (신한은행)"
    masked, count, cats, token_map = mask_sensitive_information(text)
    # Business registration number must be PRESERVED
    assert "123-45-67890" in masked
    # Bank account number must be MASKED
    assert "[ACCOUNT_001]" in masked
    assert "110-123-456789" not in masked
    assert "ACCOUNT" in cats
