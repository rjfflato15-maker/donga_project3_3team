import hashlib
import io
from datetime import datetime, timedelta

from backend.app.db.models import AuthSession, User, UserProfile
from backend.app.security import COOKIE_NAME
from conftest import TEST_PASSWORD


CONTRACT_BODY = {
    "title": "AI 계약 검수 시스템 개발 계약", "vendor_name": "앤티그래비티 주식회사",
    "business_number": "220-88-12345", "contract_amount": 15000000.0,
    "amount_basis": "TOTAL", "payment_mode": "FULL",
}


def create_contract(client, **overrides):
    response = client.post("/api/contracts", json={**CONTRACT_BODY, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


def text_files():
    contents = [
        ("계약서.txt", "외주 용역 계약서\n계약명: AI 계약 검수 시스템 개발 계약\n계약금액: 금 15,000,000 원\n"
         "발주사: (주)테스트컴퍼니\n수주사: 앤티그래비티 주식회사\n사업자등록번호: 220-88-12345\n계약일자: 2026년 09월 01일\n"),
        ("전자세금계산서.txt", "전자세금계산서\n공급자: 앤티그래비티 주식회사\n사업자등록번호: 220-88-12345\n"
         "총 합계금액: 15,000,000 원\n발행일자: 2026-09-15\n"),
        ("사업자등록증.txt", "사업자등록증\n법인명: 앤티그래비티 주식회사\n사업자등록번호: 220-88-12345\n대표자: 홍길동\n"),
    ]
    return [("files", (name, io.BytesIO(text.encode("utf-8")), "text/plain")) for name, text in contents]


def test_health_and_protected_api(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert client.get("/api/contracts").status_code == 401
    assert client.post("/api/contracts", json=CONTRACT_BODY).status_code == 401


def test_contract_crud_revision_and_pilot_seed(operator_client):
    assert operator_client.post("/api/contracts/seed-demo").status_code == 403
    contract = create_contract(operator_client)
    cid = contract["contract_id"]
    assert contract["summary"]["completeness_rate"] == 0
    assert len(contract["documents"]) == 0
    assert len([check for check in contract["checks"] if check["rule_id"] == "REQUIRED_DOCUMENTS"]) == 6
    assert contract["workflow"]["amount_basis"] == "TOTAL"
    assert len(operator_client.get("/api/contracts").json()) == 1
    simulation = operator_client.post(f"/api/pipeline/{cid}/simulate")
    assert simulation.status_code == 200, simulation.text
    assert len(simulation.json()["steps"]) == 5
    revision = contract["workflow"]["revision"]
    update = operator_client.put(f"/api/contracts/{cid}", json={
        "title": "계약 수정본", "contract_amount": 16500000.0,
        "revision": revision, "change_note": "원본 계약 합계금액 정정",
    })
    assert update.status_code == 200, update.text
    updated = update.json()
    assert updated["title"] == "계약 수정본"
    assert updated["workflow"]["revision"] > revision
    stale = operator_client.put(f"/api/contracts/{cid}", json={
        "title": "오래된 화면 수정", "revision": revision, "change_note": "동시 수정 충돌 확인",
    })
    assert stale.status_code == 409
    assert operator_client.delete(f"/api/contracts/{cid}").status_code == 204
    assert operator_client.get(f"/api/contracts/{cid}").status_code == 404


def test_auto_parse_batch_and_create(operator_client):
    response = operator_client.post("/api/contracts/auto-parse-batch", files=text_files())
    assert response.status_code == 200, response.text
    parsed = response.json()
    assert parsed["vendor_name"] == "앤티그래비티 주식회사"
    assert parsed["business_number"] == "220-88-12345"
    assert parsed["contract_amount"] == 15000000.0
    assert len(parsed["documents"]) == 3
    response = operator_client.post("/api/contracts/auto-create-batch", files=text_files(), data={
        key: parsed[key] for key in ("title", "vendor_name", "business_number", "contract_amount")
    })
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["title"] == parsed["title"]
    assert created["vendor_name"] == "앤티그래비티 주식회사"
    assert created["contract_amount"] == 15000000.0
    assert len(created["documents"]) == 3
    assert all(document["file_available"] for document in created["documents"])
    assert created["review_status"] == "REVIEW"


def test_document_masking_preview_download_and_exclusion(operator_client):
    contract = create_contract(operator_client)
    cid = contract["contract_id"]
    raw = ("[외주 용역 계약서]\n- 상호: ABC 주식회사\n- 사업자등록번호: 123-45-67890\n"
           "- 주민등록번호: 800101-1234567\n- 입금계좌: 신한은행 110-123-456789\n"
           "- 사업장소재지: 서울특별시 중구 세종대로 100\n")
    response = operator_client.post(f"/api/contracts/{cid}/documents", files=[
        ("files", ("01_계약서_테스트.txt", raw.encode("utf-8"), "text/plain"))
    ])
    assert response.status_code == 200, response.text
    doc_id = response.json()[0]["document_id"]
    response = operator_client.get(f"/api/documents/{doc_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["file_available"] is True
    assert "800101-1******" in data["masked_text"]
    assert "123-**-*****" in data["masked_text"]
    assert "110-***-456789" in data["masked_text"]
    assert "중구 세종대로 100" not in data["masked_text"]
    assert "800101-1234567" in data["raw_text"]
    masked = operator_client.get(f"/api/documents/{doc_id}/text-preview")
    assert masked.status_code == 200
    assert "800101-1234567" not in masked.json()["text"]
    download = operator_client.get(f"/api/documents/{doc_id}/download", params={"masked": False})
    assert download.status_code == 200
    assert download.content == raw.encode("utf-8")
    assert "attachment" in download.headers["content-disposition"]
    assert download.headers["cache-control"] == "no-store"
    assert operator_client.delete(f"/api/documents/{doc_id}").status_code == 204
    assert operator_client.get(f"/api/documents/{doc_id}").status_code == 404


def test_initial_password_change_sessions_and_retired_reset(client, accounts, db_factory):
    operator = accounts["operator"]
    with db_factory() as db:
        db.get(UserProfile, operator["user_id"]).must_change_password = True
        db.commit()
    login = client.post("/api/auth/login", json={"email": operator["email"], "password": TEST_PASSWORD})
    assert login.status_code == 200, login.text
    assert login.json()["user"]["must_change_password"] is True
    assert "HttpOnly" in login.headers["set-cookie"]
    assert "SameSite=lax" in login.headers["set-cookie"]
    old_token = client.cookies.get(COOKIE_NAME)
    with db_factory() as db:
        session = db.get(AuthSession, hashlib.sha256(old_token.encode()).hexdigest())
        assert session is not None
        assert session.token_hash != old_token
    assert client.get("/api/auth/me").status_code == 200
    assert client.get("/api/contracts").status_code == 403
    wrong_current = client.post("/api/auth/password", json={"current_password": "wrong", "new_password": "Updated-password-2026!"})
    assert wrong_current.status_code == 400
    change = client.post("/api/auth/password", json={"current_password": TEST_PASSWORD, "new_password": "Updated-password-2026!"})
    assert change.status_code == 200, change.text
    assert change.json()["must_change_password"] is False
    assert client.cookies.get(COOKIE_NAME) != old_token
    assert client.get("/api/contracts").status_code == 200
    with db_factory() as db:
        assert db.get(AuthSession, hashlib.sha256(old_token.encode()).hexdigest()) is None
    for endpoint in ("send-verification-code", "verify-code", "change-password"):
        assert client.post(f"/api/auth/{endpoint}", json={}).status_code == 410
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/contracts").status_code == 401
    assert client.post("/api/auth/login", json={"email": operator["email"], "password": TEST_PASSWORD}).status_code == 401
    assert client.post("/api/auth/login", json={"email": operator["email"], "password": "Updated-password-2026!"}).status_code == 200


def test_expired_session_and_inactive_account(operator_client, accounts, db_factory):
    token = operator_client.cookies.get(COOKIE_NAME)
    with db_factory() as db:
        db.get(AuthSession, hashlib.sha256(token.encode()).hexdigest()).expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()
    assert operator_client.get("/api/contracts").status_code == 401
    with db_factory() as db:
        db.get(UserProfile, accounts["operator"]["user_id"]).active = False
        db.commit()
    assert operator_client.post("/api/auth/login", json={"email": accounts["operator"]["email"], "password": TEST_PASSWORD}).status_code == 403


def test_legacy_password_records_cannot_login(client, db_factory):
    legacy = hashlib.sha256(TEST_PASSWORD.encode()).hexdigest()
    with db_factory() as db:
        user = User(email="legacy@tests.local", password=legacy)
        db.add(user)
        db.flush()
        db.add(UserProfile(user_id=user.user_id, role="operator", display_name="기존 계정", active=True, must_change_password=True))
        db.commit()
    for candidate in (TEST_PASSWORD, legacy):
        response = client.post("/api/auth/login", json={"email": "legacy@tests.local", "password": candidate})
        assert response.status_code == 401


def test_roles_origin_and_file_validation(operator_client, separate_client):
    representative = separate_client()
    assert representative.post("/api/contracts", json=CONTRACT_BODY).status_code == 403
    assert operator_client.get("/api/pilot/users").status_code == 403
    assert representative.get("/api/pilot/users").status_code == 200
    assert operator_client.post("/api/contracts", json=CONTRACT_BODY, headers={"Origin": "https://untrusted.invalid"}).status_code == 403
    contract = create_contract(operator_client)
    cid = contract["contract_id"]
    assert operator_client.post(f"/api/contracts/{cid}/documents", files=[("files", ("fake.pdf", b"not a pdf", "application/pdf"))]).status_code == 400
    assert operator_client.post(f"/api/contracts/{cid}/documents", files=[("files", ("empty.txt", b"", "text/plain"))]).status_code == 413


def test_representative_confirmation_snapshot_and_stale(operator_client, separate_client):
    representative = separate_client()
    policy = representative.put("/api/pilot/settings", json={"company_name": "격리된 C 테스트", "required_document_types": ["contract"]})
    assert policy.status_code == 200, policy.text
    contract = create_contract(operator_client)
    cid = contract["contract_id"]
    response = operator_client.post(f"/api/contracts/{cid}/documents", files=text_files()[:1])
    assert response.status_code == 200, response.text
    from submission_helpers import submit_ready
    detail = submit_ready(operator_client, cid)
    request = {"decision": "CONFIRMED", "note": "국세청 미연동 항목과 원문을 직접 확인했습니다.",
               "revision": detail["workflow"]["revision"], "fingerprint": detail["workflow"]["fingerprint"],
               "acknowledge_unverified": True}
    assert operator_client.post(f"/api/contracts/{cid}/reviews", json=request).status_code == 403
    response = representative.post(f"/api/contracts/{cid}/reviews", json=request)
    assert response.status_code == 200, response.text
    confirmed = response.json()
    assert confirmed["workflow"]["approval_status"] == "CONFIRMED"
    assert any(check["status"] == "REVIEW" for check in confirmed["checks"])
    response = operator_client.put(f"/api/contracts/{cid}", json={
        "contract_amount": 16500000, "revision": confirmed["workflow"]["revision"], "change_note": "추가 과업 합계금액 반영"})
    assert response.status_code == 200, response.text
    assert response.json()["workflow"]["approval_status"] == "STALE"
    assert representative.post(f"/api/contracts/{cid}/reviews", json=request).status_code == 409
    audits = representative.get("/api/pilot/audit", params={"contract_id": cid})
    assert audits.status_code == 200
    assert any(record["action"] == "REPRESENTATIVE_CONFIRMED" for record in audits.json())


def test_missing_required_document_and_original_block_final_confirmation(operator_client, separate_client, db_factory):
    representative = separate_client()
    contract = create_contract(operator_client)
    cid = contract["contract_id"]
    workflow = contract["workflow"]
    request = {"decision": "CONFIRMED", "note": "원문을 직접 확인했다는 충분한 길이의 근거",
               "revision": workflow["revision"], "fingerprint": workflow["fingerprint"], "acknowledge_unverified": True}
    assert representative.post(f"/api/contracts/{cid}/reviews", json=request).status_code == 400
    assert representative.put("/api/pilot/settings", json={"company_name": "격리된 C 테스트", "required_document_types": ["contract"]}).status_code == 200
    from backend.app.db.models import Document
    with db_factory() as db:
        db.add(Document(contract_id=cid, file_name="원본없는_계약서.txt", storage_path="raw/unavailable.txt", document_type="contract"))
        db.commit()
    detail = representative.get(f"/api/contracts/{cid}").json()
    request.update(revision=detail["workflow"]["revision"], fingerprint=detail["workflow"]["fingerprint"])
    assert detail["summary"]["missing_count"] == 0
    assert representative.post(f"/api/contracts/{cid}/reviews", json=request).status_code == 400


def test_reference_edit_preserves_extracted_evidence_and_correction_is_audited(operator_client):
    contract = create_contract(operator_client)
    cid = contract["contract_id"]
    response = operator_client.post(f"/api/contracts/{cid}/documents", files=text_files()[:1])
    assert response.status_code == 200, response.text
    document = response.json()[0]
    doc_id = document["document_id"]
    original_fields = document["analysis"]["fields"]
    detail = operator_client.get(f"/api/contracts/{cid}").json()
    update = operator_client.put(f"/api/contracts/{cid}", json={"contract_amount": 16500000,
        "revision": detail["workflow"]["revision"], "change_note": "계약 기준 합계 변경"})
    assert update.status_code == 200, update.text
    assert operator_client.get(f"/api/documents/{doc_id}").json()["analysis"]["fields"] == original_fields
    request = {"fields": {**original_fields, "total_amount": 16500000, "amount": 16500000, "amount_basis": "TOTAL"},
               "document_type": "contract", "revision": update.json()["workflow"]["revision"], "note": ""}
    assert operator_client.put(f"/api/documents/{doc_id}/fields", json=request).status_code == 400
    request["note"] = "원본 계약 합계금액을 직접 확인하고 OCR 추출값을 보완"
    corrected = operator_client.put(f"/api/documents/{doc_id}/fields", json=request)
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["analysis"]["fields"]["total_amount"] == 16500000
    assert operator_client.put(f"/api/documents/{doc_id}/fields", json=request).status_code == 409
    audit = operator_client.get("/api/pilot/audit", params={"contract_id": cid}).json()
    event = next(event for event in audit if event["action"] == "EXTRACT_CORRECTED")
    assert event["details"]["before"] == original_fields
    assert event["details"]["after"]["total_amount"] == 16500000
