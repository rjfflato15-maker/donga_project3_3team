import pytest
from backend.app.ai import is_generic_title, extract_contract_title, extract_fields


def test_generic_title_blacklist():
    """Verify generic template names are recognized and filtered."""
    generic_samples = [
        "계약서",
        "[계약서]",
        "표준계약서",
        "[외주 용역 표준 계약서]",
        "용역계약서",
        "외주용역계약서",
        "물품계약서",
        "물품 구매 계약서",
        "위탁계약서",
        "업무위탁계약서",
        "소프트웨어 개발 표준 계약서",
        "비밀유지계약서",
        "NDA",
        "견적서",
        "세금계산서",
    ]
    for sample in generic_samples:
        assert is_generic_title(sample) is True, f"Failed for {sample}"

    specific_samples = [
        "ABC 홈페이지 구축 외주 계약",
        "2026년도 사내 ERP 고도화 사업",
        "스마트 센서 500대 구매 계약",
        "클라우드 인프라 마이그레이션 용역",
        "모바일 앱 UI/UX 디자인 위탁 계약",
    ]
    for sample in specific_samples:
        assert is_generic_title(sample) is False, f"Failed for {sample}"


def test_title_extraction_from_preamble_quote():
    """Requirement 2: Extract quoted task title in intro/preamble."""
    text = """[외주 용역 표준 계약서]

제 1 조 (목적)
본 계약은 발주사 주식회사 한국기업(이하 "갑")과 수주사 ABC 주식회사(이하 "을") 사이에 체결하는 "ABC 홈페이지 구축 외주 계약"에 관한 제반 사항을 규정함을 목적으로 한다.
"""
    title = extract_contract_title(text)
    assert title == "ABC 홈페이지 구축 외주 계약"


def test_title_extraction_from_header_subtitles():
    """Requirement 2: Extract specific title from header parenthesis/subtitle."""
    text = """표준 용역 계약서 (AI 기반 빅데이터 플랫폼 구축)

제 1 조 (목적)
본 계약은 갑과 을 간의 업무를 규정한다.
"""
    title = extract_contract_title(text)
    assert title == "AI 기반 빅데이터 플랫폼 구축"


def test_title_extraction_from_explicit_label():
    """Requirement 2: Extract title from key-value label."""
    text = """[물품 공급 계약서]

- 건명: 2026년도 본사 보안 서버 장비 납품
- 계약금액: 50,000,000 원
"""
    title = extract_contract_title(text)
    assert title == "2026년도 본사 보안 서버 장비 납품"


def test_title_extraction_from_purpose_clause():
    """Requirement 2: Extract task title from Article 1 (Purpose)."""
    text = """[소프트웨어 개발 표준 계약서]

제1조 (목적)
이 계약은 갑이 을에게 스마트 공장 고도화 컨설팅 수행을 위탁함에 따른 목적을 가진다.
"""
    title = extract_contract_title(text)
    assert "스마트 공장 고도화 컨설팅" in title


def test_title_extraction_fallback_core_object():
    """Requirement 3: Fallback combination with core body object when generic title is used."""
    text = """[외주용역계약서]

갑은 을에게 모바일 앱 개발 업무를 위탁하며, 을은 이를 성실히 수행한다.
"""
    title = extract_contract_title(text)
    assert "모바일 앱 개발" in title
    assert is_generic_title(title) is False


def test_extract_fields_incorporation():
    """Verify extract_fields correctly returns non-generic title."""
    text = """[외주 용역 표준 계약서]

- 계약명: 차세대 모빌리티 서비스 구축 외주
- 총계약금액: 금 22,000,000원
- 사업자등록번호: 123-45-67890
"""
    fields = extract_fields(text)
    assert fields.title == "차세대 모빌리티 서비스 구축 외주"
    assert fields.amount == 22000000.0
    assert fields.business_registration_no == "123-45-67890"
