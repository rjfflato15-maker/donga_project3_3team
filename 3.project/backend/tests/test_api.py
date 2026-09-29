import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

# Create an isolated test engine (using in-memory or test file)
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

from backend.app.main import app
from backend.app.db.database import Base, get_db

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)



def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_contracts_api_and_seed_demo():
    # 1. Trigger demo seed
    res = client.post("/api/contracts/seed-demo")
    assert res.status_code == 200
    contract = res.json()
    assert contract["title"] == "ABC 홈페이지 구축 외주 계약"
    assert contract["vendor_name"] == "ABC 주식회사"
    assert contract["contract_amount"] == 11000000.0
    assert contract["summary"]["completeness_rate"] == 83.3
    assert len(contract["documents"]) == 5

    # 2. Get list of contracts
    list_res = client.get("/api/contracts")
    assert list_res.status_code == 200
    contracts = list_res.json()
    assert len(contracts) >= 1

    # 3. Simulate pipeline
    cid = contract["contract_id"]
    sim_res = client.post(f"/api/pipeline/{cid}/simulate")
    assert sim_res.status_code == 200
    sim_data = sim_res.json()
    assert len(sim_data["steps"]) == 5
    assert sim_data["steps"][0]["step"] == 1
    assert sim_data["steps"][4]["step"] == 5

    # 4. Test Contract Update
    update_res = client.put(f"/api/contracts/{cid}", json={
        "title": "ABC 홈페이지 구축 외주 계약 (수정본)",
        "contract_amount": 10450000.0,
        "vendor_name": "ABC 주식회사 (변경)",
        "business_number": "123-45-67890"
    })
    assert update_res.status_code == 200
    updated_data = update_res.json()
    # 5. Test Contract Delete
    del_res = client.delete(f"/api/contracts/{cid}")
    assert del_res.status_code == 204

    # Verify contract is gone
    get_res = client.get(f"/api/contracts/{cid}")
    assert get_res.status_code == 404


def test_auto_parse_batch_and_create():
    import io
    contract_content = (
        "외주 용역 계약서\n"
        "계약명: AI 계약 검수 시스템 개발 계약\n"
        "계약금액: 금 15,000,000 원\n"
        "발주사: (주)테스트컴퍼니\n"
        "수주사: 앤티그래비티 주식회사\n"
        "사업자등록번호: 220-88-12345\n"
        "계약일자: 2026년 09월 01일\n"
    )

    tax_invoice_content = (
        "전자세금계산서\n"
        "공급자: 앤티그래비티 주식회사\n"
        "사업자등록번호: 220-88-12345\n"
        "총 합계금액: 15,000,000 원\n"
        "발행일자: 2026-09-15\n"
    )

    biz_reg_content = (
        "사업자등록증\n"
        "법인명: 앤티그래비티 주식회사\n"
        "사업자등록번호: 220-88-12345\n"
        "대표자: 홍길동\n"
    )

    files = [
        ("files", ("계약서.txt", io.BytesIO(contract_content.encode("utf-8")), "text/plain")),
        ("files", ("전자세금계산서.txt", io.BytesIO(tax_invoice_content.encode("utf-8")), "text/plain")),
        ("files", ("사업자등록증.txt", io.BytesIO(biz_reg_content.encode("utf-8")), "text/plain")),
    ]

    # 1. Test auto-parse-batch API
    res = client.post("/api/contracts/auto-parse-batch", files=files)
    assert res.status_code == 200
    data = res.json()

    assert data["vendor_name"] == "앤티그래비티 주식회사"
    assert data["business_number"] == "220-88-12345"
    assert data["contract_amount"] == 15000000.0
    assert len(data["documents"]) == 3

    # 2. Test auto-create-batch API
    create_files = [
        ("files", ("계약서.txt", io.BytesIO(contract_content.encode("utf-8")), "text/plain")),
        ("files", ("전자세금계산서.txt", io.BytesIO(tax_invoice_content.encode("utf-8")), "text/plain")),
        ("files", ("사업자등록증.txt", io.BytesIO(biz_reg_content.encode("utf-8")), "text/plain")),
    ]
    form_data = {
        "title": data["title"],
        "vendor_name": data["vendor_name"],
        "business_number": data["business_number"],
        "contract_amount": data["contract_amount"],
    }

    create_res = client.post("/api/contracts/auto-create-batch", data=form_data, files=create_files)
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["title"] == data["title"]
    assert created["vendor_name"] == "앤티그래비티 주식회사"
    assert created["contract_amount"] == 15000000.0
    assert len(created["documents"]) == 3


def test_document_masking_on_off_api():
    import io
    # 1. Create a contract first
    contract_res = client.post("/api/contracts", json={
        "title": "개인정보 마스킹 테스트 계약",
        "vendor_name": "ABC 주식회사",
        "business_number": "123-45-67890",
        "contract_amount": 10000000.0,
    })
    assert contract_res.status_code == 201
    cid = contract_res.json()["contract_id"]

    # 2. Upload document containing sensitive information
    doc_content = (
        "[외주 용역 계약서]\n"
        "- 상호: ABC 주식회사\n"
        "- 사업자등록번호: 123-45-67890\n"
        "- 주민등록번호: 800101-1234567\n"
        "- 입금계좌: 신한은행 110-123-456789\n"
        "- 사업장소재지: 서울특별시 중구 세종대로 100\n"
    )
    files = [
        ("files", ("01_계약서_테스트.txt", io.BytesIO(doc_content.encode("utf-8")), "text/plain")),
    ]
    upload_res = client.post(f"/api/contracts/{cid}/documents", files=files)
    assert upload_res.status_code == 200
    docs = upload_res.json()
    assert len(docs) == 1
    doc_id = docs[0]["document_id"]

    # 3. Retrieve document via GET /api/documents/{doc_id}
    get_res = client.get(f"/api/documents/{doc_id}")
    assert get_res.status_code == 200
    doc_data = get_res.json()

    # Verify masked_text (for Masking ON)
    masked_text = doc_data["masked_text"]
    assert "800101-1******" in masked_text  # RRN: gender preserved, rest *
    assert "123-**-*****" in masked_text    # Biz reg no: front 3 kept, middle/end *
    assert "110-***-456789" in masked_text  # Account: front 3 kept, middle *, end kept
    assert "서울특별시" in masked_text      # Address: region preserved
    assert "중구 세종대로 100" not in masked_text

    # Verify raw_text (for Masking OFF - full visibility)
    raw_text = doc_data["raw_text"]
    assert "800101-1234567" in raw_text
    assert "123-45-67890" in raw_text
    assert "110-123-456789" in raw_text
    assert "중구 세종대로 100" in raw_text


def test_auth_login_and_password_reset():
    # 1. Login with seeded demo credentials
    login_res = client.post(
        "/api/auth/login",
        json={"email": "nj445325@gmail.com", "password": "admin123!"},
    )
    assert login_res.status_code == 200
    data = login_res.json()
    assert data["success"] is True
    assert data["user"]["email"] == "nj445325@gmail.com"

    # 2. Login with wrong password
    bad_login = client.post(
        "/api/auth/login",
        json={"email": "nj445325@gmail.com", "password": "wrong_password"},
    )
    assert bad_login.status_code == 401

    # 3. Request verification code
    code_res = client.post(
        "/api/auth/send-verification-code",
        json={"email": "nj445325@gmail.com", "password": "admin123!"},
    )
    assert code_res.status_code == 200
    code_data = code_res.json()
    assert code_data["success"] is True
    demo_code = code_data["demo_code"]
    assert demo_code is not None

    # 4. Verify the code
    verify_res = client.post(
        "/api/auth/verify-code",
        json={"email": "nj445325@gmail.com", "code": demo_code},
    )
    assert verify_res.status_code == 200
    verify_data = verify_res.json()
    assert verify_data["success"] is True
    verif_token = verify_data["verification_token"]
    assert verif_token is not None

    # 5. Change password
    change_res = client.post(
        "/api/auth/change-password",
        json={
            "email": "nj445325@gmail.com",
            "verification_token": verif_token,
            "new_password": "new_secret_password_123!",
        },
    )
    assert change_res.status_code == 200
    assert change_res.json()["success"] is True

    # 6. Verify new password login succeeds, old fails
    old_login = client.post(
        "/api/auth/login",
        json={"email": "nj445325@gmail.com", "password": "admin123!"},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/auth/login",
        json={"email": "nj445325@gmail.com", "password": "new_secret_password_123!"},
    )
    assert new_login.status_code == 200
    assert new_login.json()["success"] is True





