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



