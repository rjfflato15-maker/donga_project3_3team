"""Dashboard projections use temporary records, never dev/test evaluation data."""
import json

import pytest

from backend.app.db.models import Document
from backend.app.schemas.contract import ContractListItem
from backend.app.schemas.validation import ValidationCheck
from backend.app.services.review_summary_service import display_issue_counts
from test_api import create_contract
from test_review_workflow_api import configured_contract, upload


def dashboard(client):
    response = client.get("/api/contracts")
    assert response.status_code == 200, response.text
    return {row["contract_id"]: row for row in response.json()}


def assert_summary_matches(client, contract_id, item):
    context = client.get(f"/api/contracts/{contract_id}/review-context")
    assert context.status_code == 200, context.text
    assert item["action_summary"] == context.json()["action_summary"]
    assert item["approval_next_step"] == context.json()["approval"]["next_step"]
    assert item["open_issue_count"] == sum(
        check['status'] in {'FAIL', 'MISSING', 'REVIEW'} and
        not (check['rule_id'] == 'BUSINESS_STATUS' and check['status'] == 'REVIEW')
        for check in context.json()['checks'])


def test_dashboard_keeps_existing_fields_and_empty_contract_defaults(operator_client):
    assert dashboard(operator_client) == {}
    contract = create_contract(operator_client)
    cid = contract["contract_id"]
    item = dashboard(operator_client)[cid]
    assert set(ContractListItem.model_fields) <= item.keys()
    for key in ("contract_id", "title", "vendor_name", "business_number", "contract_amount", "created_at"):
        assert item[key] == contract[key]
    assert item["review_status"] == "REVIEW"
    assert item["completeness_rate"] == 0
    assert item["submitted_docs_count"] == 0
    assert item["total_docs_count"] == 6
    assert item["submitted_document_types"] == []
    assert item["approval_status"] == "PENDING"
    assert item["revision"] == contract["workflow"]["revision"]
    assert item["missing_original_count"] == 0
    assert item["waiting_request_count"] == 0
    assert item["earliest_due_on"] is None
    assert item["approval_next_step"] == 1
    assert_summary_matches(operator_client, cid, item)


@pytest.mark.parametrize('mode,expected_review', [('disabled', 1), ('api', 2), ('demo', 2)])
def test_issue_counts_exclude_only_disabled_nts_review(mode, expected_review):
    checks = [ValidationCheck(rule_id=rule, field='unit', status=status, message='unit fixture')
              for rule, status in [('BUSINESS_STATUS', 'REVIEW'), ('BUSINESS_STATUS', 'FAIL'),
                                   ('AMOUNT_EXTRACTION', 'REVIEW'), ('REQUIRED_DOCUMENTS', 'MISSING'),
                                   ('BUSINESS_NO_MATCH', 'PASS')]]
    assert display_issue_counts(checks, nts_mode=mode) == {'FAIL': 1, 'MISSING': 1, 'REVIEW': expected_review}


def test_nts_review_remains_in_checks_and_summary_but_not_dashboard_count(operator_client):
    cid = create_contract(operator_client)['contract_id']
    context = operator_client.get(f'/api/contracts/{cid}/review-context').json()
    item = dashboard(operator_client)[cid]
    nts = [check for check in context['checks'] if check['rule_id'] == 'BUSINESS_STATUS']
    assert len(nts) == 1 and nts[0]['status'] == 'REVIEW'
    summary = context['summary']
    assert item['open_issue_count'] == summary['fail_count'] + summary['missing_count'] + summary['review_count'] - 1
    shown_review = summary['review_count'] - 1
    assert (f'미확인 {shown_review}건' in item['action_summary']) == (shown_review > 0)
    assert item['review_status'] == 'REVIEW'
    assert_summary_matches(operator_client, cid, item)


def test_dashboard_counts_only_open_requests_and_earliest_non_null_deadline(operator_client):
    ids = [create_contract(operator_client)["contract_id"] for _ in range(3)]
    a, b, c = ids

    def record(cid, due_on):
        response = operator_client.post(
            f"/api/pilot/contracts/{cid}/resubmission-requests",
            json={"contact_method": "EMAIL", "requested_on": "2026-10-02", "due_on": due_on, "memo": "가상 요청 기록"},
        )
        assert response.status_code == 201, response.text
        return response.json()["request_id"]

    def resolve(cid, request_id, status):
        response = operator_client.patch(
            f"/api/pilot/contracts/{cid}/resubmission-requests/{request_id}",
            json={"status": status, "note": "가상 회신·취소 확인"},
        )
        assert response.status_code == 200, response.text

    later = record(a, "2026-10-07")
    earlier = record(a, "2026-10-05")
    undated = record(a, None)
    resolve(a, record(a, "2026-10-03"), "RECEIVED")
    resolve(a, record(a, "2026-10-04"), "CANCELLED")
    record(b, None)

    items = dashboard(operator_client)
    assert items[a]["waiting_request_count"] == 3
    assert items[a]["earliest_due_on"] == "2026-10-05"
    assert "회신 대기 3건" in items[a]["action_summary"]
    assert items[b]["waiting_request_count"] == 1 and items[b]["earliest_due_on"] is None
    assert items[c]["waiting_request_count"] == 0 and items[c]["earliest_due_on"] is None
    for cid in ids:
        assert_summary_matches(operator_client, cid, items[cid])

    resolve(a, earlier, "RECEIVED")
    item = dashboard(operator_client)[a]
    assert item["waiting_request_count"] == 2 and item["earliest_due_on"] == "2026-10-07"
    resolve(a, later, "CANCELLED")
    item = dashboard(operator_client)[a]
    assert item["waiting_request_count"] == 1 and item["earliest_due_on"] is None
    resolve(a, undated, "RECEIVED")
    item = dashboard(operator_client)[a]
    assert item["waiting_request_count"] == 0 and item["earliest_due_on"] is None
    assert "회신 대기" not in item["action_summary"]
    assert_summary_matches(operator_client, a, item)


def test_dashboard_tracks_two_stage_confirmation_and_stale_data(operator_client, separate_client):
    representative, cid, body = configured_contract(operator_client, separate_client)
    assert dashboard(operator_client)[cid]["approval_next_step"] == 1
    first = operator_client.post(f"/api/pilot/contracts/{cid}/approvals", json={**body, "step": 1})
    assert first.status_code == 200, first.text
    item = dashboard(operator_client)[cid]
    assert item["approval_next_step"] == 2 and "2단계 결재 대기" in item["action_summary"]
    assert_summary_matches(operator_client, cid, item)

    final = representative.post(f"/api/pilot/contracts/{cid}/approvals", json={**body, "step": 2})
    assert final.status_code == 200, final.text
    item = dashboard(operator_client)[cid]
    assert item["approval_next_step"] is None and "최종 확인 완료" in item["action_summary"]
    assert_summary_matches(operator_client, cid, item)

    edited = operator_client.put(
        f"/api/contracts/{cid}",
        json={"title": "새 자료가 반영된 계약", "revision": body["revision"], "change_note": "자료 변경 후 결재 재확인"},
    )
    assert edited.status_code == 200, edited.text
    item = dashboard(operator_client)[cid]
    assert item["approval_status"] == "STALE"
    assert item["approval_next_step"] == 1 and "자료 변경 · 재확인 필요" in item["action_summary"]
    assert_summary_matches(operator_client, cid, item)


@pytest.mark.parametrize("human_confirmed", [False, True])
def test_dashboard_uses_stored_ai_status_without_detail_or_source_processing(
    operator_client, db_factory, monkeypatch, human_confirmed
):
    from backend.app.services import review_context_service, storage_service
    from backend.app.services.contract_service import ContractService

    contract = create_contract(operator_client)
    cid = contract["contract_id"]
    doc = upload(operator_client, cid)
    with db_factory() as db:
        row = db.get(Document, doc["document_id"])
        fields = json.loads(row.extract.raw_fields)
        fields["ai_review"] = {"manual_review_required": True, "human_confirmed": human_confirmed, "decisions": []}
        row.extract.raw_fields = json.dumps(fields)
        db.commit()
    context = operator_client.get(f"/api/contracts/{cid}/review-context").json()

    def forbidden(*args, **kwargs):
        raise AssertionError("계약 목록은 상세 조회·원문 읽기·OCR을 실행하면 안 됩니다.")

    monkeypatch.setattr(ContractService, "get_contract_detail", forbidden)
    monkeypatch.setattr(review_context_service, "document_provenance", forbidden)
    monkeypatch.setattr(review_context_service, "source_pages", forbidden)
    monkeypatch.setattr(storage_service, "read_texts", forbidden)
    item = dashboard(operator_client)[cid]
    assert item["action_summary"] == context["action_summary"]
    assert ("AI 추출 확인 1문서" in item["action_summary"]) is (not human_confirmed)
