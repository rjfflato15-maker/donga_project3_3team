import json
from datetime import datetime, timedelta

from backend.app.db.models import AuditEvent, Contract, ContractReview, Document
from backend.app.services.workflow_service import policy_for, fingerprint_for
from backend.app.services.pipeline_service import PipelineService


def test_measurements_require_login_and_empty_is_not_zero_savings(client, operator_client):
    operator_client.post("/api/auth/logout")
    assert client.get("/api/pilot/metrics").status_code == 401


def test_empty_measurement_has_no_fabricated_savings(operator_client):
    response = operator_client.get("/api/pilot/metrics")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["contract_count"] == 0
    assert data["timed_contract_count"] == 0
    assert data["mean_elapsed_seconds"] is None
    assert data["median_elapsed_seconds"] is None
    assert "절감시간은 별도 측정" in data["limitation"]
    assert not any("saving" in key for key in data)


def test_elapsed_uses_first_document_and_first_confirmation_only(operator_client, db_factory, separate_client):
    start = datetime(2026, 10, 1, 9, 0, 0)
    with db_factory() as db:
        first = Contract(title="30분 경과 계약", vendor_name="테스트", business_number="123-45-67890", contract_amount=1000)
        second = Contract(title="아직 확인하지 않은 계약", vendor_name="테스트", business_number="123-45-67890", contract_amount=1000)
        db.add_all([first, second])
        db.flush()
        ids = [first.contract_id, second.contract_id]
        db.add_all([
            Document(contract_id=first.contract_id, file_name="first.txt", storage_path="raw/missing.txt", uploaded_at=start),
            Document(contract_id=first.contract_id, file_name="later.txt", storage_path="raw/missing2.txt", uploaded_at=start + timedelta(minutes=5)),
            Document(contract_id=second.contract_id, file_name="pending.txt", storage_path="raw/missing3.txt", uploaded_at=start),
        ])
        db.add(AuditEvent(actor_name="담당자", action="EXTRACT_CORRECTED", contract_id=first.contract_id))
        db.commit()
        for minutes in (30, 60):
            inputs = PipelineService().validation_inputs(db, first)
            snapshot = {"fingerprint": fingerprint_for(db, first, inputs), "policy": policy_for(db, first.contract_id)}
            db.add(ContractReview(contract_id=first.contract_id, revision=1, actor_id=1, actor_name="대표",
                                  decision="CONFIRMED", note="원문 확인", snapshot_json=json.dumps(snapshot),
                                  created_at=start + timedelta(minutes=minutes)))
        # Excluded contracts' retained audit/history must not inflate live metrics.
        db.add(AuditEvent(actor_name="담당자", action="EXTRACT_CORRECTED", contract_id=999999))
        db.add(ContractReview(contract_id=999999, revision=1, actor_id=1, actor_name="대표",
                              decision="CONFIRMED", note="제외한 계약", snapshot_json="{}", created_at=start))
        db.commit()
    representative = separate_client()
    response = representative.get("/api/pilot/metrics")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["contract_count"] == len(ids)
    assert data["timed_contract_count"] == 1
    assert data["mean_elapsed_seconds"] == 1800
    assert data["median_elapsed_seconds"] == 1800
    assert data["document_registration_count"] == 3
    assert data["field_correction_count"] == 1
    assert data["awaiting_confirmation_count"] + data["confirmed_count"] == 2
