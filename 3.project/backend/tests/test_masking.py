import pytest
from backend.app.ai.masking import mask_sensitive_information


def test_rrn_masking():
    # 주민번호 뒷 성별 구분 제외 *표시
    text = "대표자 홍길동 주민번호: 800101-1234567 등록"
    masked, count, cats, token_map = mask_sensitive_information(text)
    assert "800101-1******" in masked
    assert "800101-1234567" not in masked
    assert "RRN" in cats
    assert count >= 1


def test_phone_and_email_masking():
    text = "담당자 연락처: 010-1234-5678, 이메일: user@example.com"
    masked, count, cats, token_map = mask_sensitive_information(text)
    assert "010-****-5678" in masked
    assert "010-1234-5678" not in masked
    assert "us***@example.com" in masked
    assert "PHONE" in cats
    assert "EMAIL" in cats


def test_biz_no_and_account_and_address_masking():
    # 사업자등록번호 앞 3자리 표시 가운데 * 표시 끝에 번호 * 표시 -> 123-**-*****
    # 계좌번호 앞에 3자리 가운데 *표시 -> 110-***-456789
    # 주소지 지역만 표시 하고 나머지 *로 표시 -> 주소: 서울특별시 ** **** ***
    text = (
        "사업자등록번호: 123-45-67890\n"
        "입금계좌: 110-123-456789 (신한은행)\n"
        "주소: 서울특별시 중구 세종대로 100"
    )
    masked, count, cats, token_map = mask_sensitive_information(text)

    # Business registration number masked as 123-**-*****
    assert "123-**-*****" in masked
    assert "123-45-67890" not in masked
    assert "BIZ_REG_NO" in cats

    # Bank account number masked as 110-***-456789
    assert "110-***-456789" in masked
    assert "110-123-456789" not in masked
    assert "ACCOUNT" in cats

    # Address masked with region kept and details as *
    assert "서울특별시" in masked
    assert "중구 세종대로 100" not in masked
    assert "*" in masked
    assert "ADDRESS" in cats


def test_rrn_gender_preservation():
    # 주민번호 뒷 성별 구분(1, 2, 3, 4) 제외 *표시
    samples = [
        ("800101-1234567", "800101-1******"),
        ("900202-2345678", "900202-2******"),
        ("010303-3456789", "010303-3******"),
        ("020404-4567890", "020404-4******"),
    ]
    for raw, expected in samples:
        text = f"주민등록번호: {raw}"
        masked, count, cats, token_map = mask_sensitive_information(text)
        assert expected in masked
        assert raw not in masked
        assert "RRN" in cats


def test_bank_account_masking_variations():
    # 계좌번호 앞에 3자리 가운데 *표시
    text = "신한은행 110-123-456789 입금계좌: 352-0123-4567-89 국민은행 123-456789012"
    masked, count, cats, token_map = mask_sensitive_information(text)
    assert "110-***-456789" in masked
    assert "352-****-****-89" in masked
    assert "ACCOUNT" in cats


def test_address_masking_variations():
    # 주소지 지역만 표시 하고 나머지 *로 표시
    text1 = "사업장소재지: 서울특별시 강남구 테헤란로 123, 4층"
    masked1, _, cats1, _ = mask_sensitive_information(text1)
    assert "서울특별시" in masked1
    assert "강남구 테헤란로 123, 4층" not in masked1
    assert "*" in masked1
    assert "ADDRESS" in cats1

    text2 = "본점 소재지: 부산광역시 해운대구 센텀중앙로 90"
    masked2, _, cats2, _ = mask_sensitive_information(text2)
    assert "부산광역시" in masked2
    assert "해운대구 센텀중앙로 90" not in masked2
    assert "*" in masked2
    assert "ADDRESS" in cats2


def test_masking_off_preserves_full_raw_text():
    # 마스킹 처리 off 일 때 전체 보이도록 raw_text는 원본 그대로 유지되어야 함
    raw_contract = (
        "[을 - 수주사]\n"
        "- 상호: ABC 주식회사\n"
        "- 사업자등록번호: 123-45-67890\n"
        "- 주민등록번호: 800101-1234567\n"
        "- 입금계좌: 신한은행 110-123-456789\n"
        "- 사업장소재지: 서울특별시 강남구 테헤란로 123, 4층"
    )
    # Masking ON produces masked text
    masked, count, cats, token_map = mask_sensitive_information(raw_contract)
    assert "123-**-*****" in masked
    assert "800101-1******" in masked
    assert "110-***-456789" in masked
    assert "서울특별시" in masked

    # Masking OFF view: The original raw_contract has all numbers in full
    assert "123-45-67890" in raw_contract
    assert "800101-1234567" in raw_contract
    assert "110-123-456789" in raw_contract
    assert "강남구 테헤란로 123, 4층" in raw_contract


