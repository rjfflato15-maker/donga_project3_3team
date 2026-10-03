"""Shared dashboard summaries from stored review data; no OCR or LLM calls."""
from datetime import date

from pydantic import Field
from sqlalchemy import func

from ..db.models import ResubmissionRequest
from ..schemas.contract import ContractListItem
from ..config import NTS_MODE


class ContractDashboardListItem(ContractListItem):
    """Extend the API projection without changing the frozen evaluation schema."""

    action_summary: str
    open_issue_count: int = Field(default=0, ge=0)
    waiting_request_count: int = Field(default=0, ge=0)
    earliest_due_on: date | None = None
    approval_next_step: int | None = Field(default=None, ge=1, le=2)
    llm: dict = {}


def waiting_request_stats(db):
    """Aggregate open requests once for the entire list; MIN ignores NULL dates."""
    rows = (
        db.query(
            ResubmissionRequest.contract_id,
            func.count(ResubmissionRequest.request_id),
            func.min(ResubmissionRequest.due_on),
        )
        .filter(ResubmissionRequest.status == "WAITING_RESPONSE")
        .group_by(ResubmissionRequest.contract_id)
        .all()
    )
    return {contract_id: (count, due_on) for contract_id, count, due_on in rows}


def pending_ai_count(reviews):
    return sum(
        bool(
            isinstance(review, dict)
            and review.get("manual_review_required")
            and not review.get("human_confirmed")
        )
        for review in reviews
    )


def display_issue_counts(checks, *, nts_mode=None):
    """Count displayed issues without changing checks or evaluation summaries."""
    mode = NTS_MODE if nts_mode is None else nts_mode
    counts = {"FAIL": 0, "MISSING": 0, "REVIEW": 0}
    for check in checks:
        if check.status not in counts:
            continue
        if mode == "disabled" and check.rule_id == "BUSINESS_STATUS" and check.status == "REVIEW":
            continue
        counts[check.status] += 1
    return counts


def issue_card_groups(checks, documents, *, nts_mode='disabled'):
    """Same grouping keys as frontend reviewSummary.ts; checks stay unchanged."""
    known = {str(d['document_id']) for d in documents}
    groups = {}
    for check in checks:
        status = getattr(check.status, 'value', check.status)
        if status not in {'FAIL', 'MISSING', 'REVIEW'}:
            continue
        if nts_mode == 'disabled' and check.rule_id == 'BUSINESS_STATUS' and status == 'REVIEW':
            continue
        field = str(check.field)
        key = (f'doc-{field}' if field in known else f'missing-{field}'
               if check.rule_id == 'REQUIRED_DOCUMENTS' else f'contract-{check.rule_id}')
        groups.setdefault(key, []).append({'rule_id': check.rule_id, 'field': check.field, 'status': status})
    return [{'key': key, 'checks': values} for key, values in groups.items()]


def build_action_summary(issue_counts, workflow, approval, waiting_count, ai_pending_count):
    """Keep list and review-context wording consistent for the same snapshot."""
    parts = []
    state = workflow["approval_status"]
    if state == "CONFIRMED":
        parts.append("최종 확인 완료")
    elif state == "STALE":
        parts.append("자료 변경 · 재확인 필요")
    elif state == "RETURNED":
        parts.append("보완 요청 · 재제출 확인 필요")
    elif approval["completed_steps"]:
        parts.append(f"{approval['next_step']}단계 결재 대기")
    if waiting_count:
        parts.append(f"회신 대기 {waiting_count}건")
    for count, label in (
        (issue_counts["MISSING"], "필수 서류 누락"),
        (issue_counts["FAIL"], "불일치"),
        (issue_counts["REVIEW"], "미확인"),
    ):
        if count:
            parts.append(f"{label} {count}건")
    if ai_pending_count:
        parts.append(f"AI 추출 확인 {ai_pending_count}문서")
    return " · ".join(parts) if parts else "자동 검사 완료 · 담당자 최종 확인 필요"
