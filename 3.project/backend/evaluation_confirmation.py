"""Finalize actual human decisions with explicit partial-review provenance."""
import copy
import json
from collections import Counter
from datetime import datetime, timedelta, timezone

from backend.evaluation_core import CHECK_STATUSES, DOCUMENT_TYPES, EvaluationNotReady, FIELDS, normalize, validate_labels
from backend.evaluation_review import valid_field


def apply_human_decisions(manifest, reference, comparison, decisions, reviewer):
    reviewer = reviewer.strip()
    if not reviewer or comparison["review"].get("independent_complete") is not True:
        raise EvaluationNotReady("검수자와 완료된 독립 판독 대조가 필요합니다.")
    required = {row["review_id"] for row in comparison["rows"] if row["human_review_required"]}
    if set(decisions) != required:
        raise EvaluationNotReady("사람 확인 목록의 행이 누락되었거나 선택되지 않은 행이 있습니다.")
    labels = copy.deepcopy(reference)
    for category in ("documents", "contracts"):
        for entry in labels[category].values():
            entry.update(reviewed=False, accepted=True)
    counts = Counter()
    for row in comparison["rows"]:
        rid = row["review_id"]
        if rid in required:
            decision = decisions[rid]
            if decision.get("confirmation") != "확인" or not str(decision.get("evidence", "")).strip():
                raise EvaluationNotReady("사람 직접 확인과 판단 근거가 비어 있습니다.")
            state, value = decision.get("state"), decision.get("value")
            if isinstance(value, str) and value.startswith("="):
                raise EvaluationNotReady("정답 값은 수식 대신 원문에서 확인한 값을 입력하세요.")
            proof = {"method": "human_direct", "confirmed": True, "reviewer": reviewer,
                     "evidence": str(decision["evidence"]).strip(), "selection_reason": row["selection_reason"]}
            counts["human"] += 1
        else:
            if row["comparison"] != "AGREE":
                raise EvaluationNotReady("불일치 또는 미응답을 AI 일치로 확정할 수 없습니다.")
            expected = row["reference"]
            state = expected["state"] if isinstance(expected, dict) else "TYPE" if row["key"] == "document_type" else "MISSING_TYPES" if row["key"] == "missing_types" else expected
            value = expected.get("value") if isinstance(expected, dict) else expected if state in {"TYPE", "MISSING_TYPES"} else None
            proof = {"method": "ai_agreement", "human_reviewed": False, "independent_match": True}
            counts["agreement"] += 1
        cid, did, key = row["contract_id"], row["document_id"], row["key"]
        if did is not None:
            document = labels["documents"][str(did)]
            if key == "document_type":
                if state != "TYPE" or value not in (*DOCUMENT_TYPES, "unknown"):
                    raise EvaluationNotReady("사람이 확인한 문서 유형 값을 점검하세요.")
                document.update(document_type=value, document_type_review=proof)
            else:
                answer = {"state": state, "value": value}
                if not valid_field(key, answer):
                    raise EvaluationNotReady("최종 필드 상태와 값 형식을 점검하세요. ABSENT/REVIEW는 값을 비웁니다.")
                normalized = normalize(key, value)
                if key.endswith("amount") and state == "VALUE":
                    answer["value"] = int(normalized) if normalized == normalized.to_integral_value() else float(normalized)
                elif key == "issue_date" and state == "VALUE":
                    answer["value"] = normalized
                answer["review"] = proof
                document["fields"][key] = answer
        elif key == "missing_types":
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except ValueError as exc:
                    raise EvaluationNotReady("누락 목록은 [] 또는 문서 유형 문자열의 JSON 배열로 입력하세요.") from exc
            if state != "MISSING_TYPES" or not isinstance(value, list) or any(kind not in DOCUMENT_TYPES for kind in value) or len(value) != len(set(value)):
                raise EvaluationNotReady("최종 누락 문서 목록을 확인하세요.")
            labels["contracts"][cid].update(missing_types=value, missing_types_review=proof)
        else:
            if state not in (*CHECK_STATUSES, "N/A") or value not in (None, ""):
                raise EvaluationNotReady("검수 상태를 확인하고 검수의 값 칸은 비워두세요.")
            rule, field = key.split("/", 1)
            matches = [entry for entry in labels["contracts"][cid]["checks"] if entry["rule_id"] == rule and entry["field"] == field]
            if len(matches) != 1:
                raise EvaluationNotReady("사람 확인 목록의 검수 ID가 다릅니다.")
            matches[0].update(status=state, review=proof)
    labels["review"] = {"confirmed": True, "reviewer_type": "human", "reviewer": reviewer,
                       "confirmed_at": datetime.now(timezone(timedelta(hours=9))).isoformat(),
                       "review_method": "independent_reconciliation_with_human_sampling", "human_full_review": counts["human"] == len(comparison["rows"]),
                       "human_direct_count": counts["human"], "ai_agreement_count": counts["agreement"],
                       "required_human_count": len(required), "source_reference_sha256": comparison["hashes"]["reference"],
                       "comparison_sha256": comparison["comparison_sha256"],
                       "independent_reply_sha256": comparison["hashes"]["independent_replies"],
                       "sampling": comparison["sampling"]}
    validate_labels(manifest, labels, "dev")
    return labels
