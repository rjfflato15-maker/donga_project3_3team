import os
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db.database import Base, engine

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


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
