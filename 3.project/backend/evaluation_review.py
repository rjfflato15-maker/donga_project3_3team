"""Blind review schemas and reconciliation, without importing the app or oracle."""
import copy
import math
import random
import re
from collections import Counter

from backend.evaluation_core import DOCUMENT_TYPES, FIELDS, FIELD_STATES, CHECK_STATUSES, EvaluationNotReady, normalize


def blind_check_slots(contract):
    # The fixture manifest assigns type-specific rules to the known document
    # types. Giving those assignments to a reviewer would reveal the answers.
    slots = [{"rule_id": "REQUIRED_DOCUMENTS", "field": kind} for kind in DOCUMENT_TYPES]
    slots += [{"rule_id": rule, "field": field} for rule, field in (
        ("BUSINESS_NO_MATCH", "business_registration_no"), ("BUSINESS_STATUS", "business_status"),
        ("AMOUNT_BASIS", "amount_basis"), ("INSTALLMENT_TOTAL", "tax_invoice"),
        ("PAYMENT_SCOPE", "tax_invoice"), ("DUPLICATE_INVOICE", "tax_invoice"))]
    for document in contract["documents"]:
        slots += [{"rule_id": rule, "field": str(document["document_id"])} for rule in (
            "ORIGINAL_FILE", "DOCUMENT_TYPE", "DOCUMENT_PROCESSING", "BUSINESS_NO_MATCH",
            "AMOUNT_EXTRACTION", "AMOUNT_COMPONENTS", "AMOUNT_MATCH_ESTIMATE",
            "AMOUNT_MATCH_TAX_INVOICE", "PAYMENT_SCOPE")]
    return slots


def blank_independent_labels(manifest, contracts):
    splits = {row["split"] for row in contracts}
    if len(splits) != 1 or not splits <= {"dev", "test"}:
        raise EvaluationNotReady("독립 판독 묶음은 한 split만 포함해야 합니다.")
    return {"dataset_version": manifest["dataset_version"], "split": next(iter(splits)),
            "review": {"author": "Claude", "reviewer_type": "ai_independent_review", "confirmed": False,
                       "used_reference_answers": False, "used_app_predictions": False},
            "documents": {str(doc["document_id"]): {
                "document_type": None, "original_read": {"readable": None, "method": None, "notes": ""},
                "fields": {field: {"state": None, "value": None, "evidence": ""} for field in FIELDS}}
                for contract in contracts for doc in contract["documents"]},
            "contracts": {str(contract["contract_id"]): {"missing_types": None,
                "checks": [{**slot, "status": None} for slot in blind_check_slots(contract)]} for contract in contracts}}


def merge_independent_parts(parts, split="dev"):
    merged = None
    for part in parts:
        review = part.get("review", {})
        if (part.get("split") != split or review.get("reviewer_type") != "ai_independent_review"
                or review.get("confirmed") is not False or review.get("used_reference_answers") is not False
                or review.get("used_app_predictions") is not False or not review.get("author")):
            raise EvaluationNotReady("독립 AI 판독의 작성자와 미확정·정답 미참조 기록을 확인하세요.")
        if merged is None:
            merged = {"dataset_version": part.get("dataset_version"), "split": split, "review": dict(review),
                      "documents": {}, "contracts": {}}
        elif part.get("dataset_version") != merged["dataset_version"] or review.get("author") != merged["review"]["author"]:
            raise EvaluationNotReady("독립 판독 파일의 자료 버전 또는 작성자가 다릅니다.")
        for category in ("documents", "contracts"):
            if not isinstance(part.get(category), dict):
                raise EvaluationNotReady("독립 판독의 문서·계약 목록이 없습니다.")
            for key, value in part[category].items():
                if key in merged[category]:
                    raise EvaluationNotReady("독립 판독 파일에서 ID가 중복됩니다. 덮어쓰지 않습니다.")
                merged[category][key] = value
    if merged is None:
        raise EvaluationNotReady("독립 판독 파일이 없습니다.")
    return merged


def valid_field(field, answer):
    if not isinstance(answer, dict) or answer.get("state") not in FIELD_STATES:
        return False
    value = answer.get("value")
    if answer["state"] != "VALUE":
        return value in (None, "")
    token = normalize(field, value)
    if token is None:
        return False
    if field == "business_registration_no":
        return bool(re.fullmatch(r"\d{10}", token))
    return field != "amount_scope" or token in {"FULL", "PARTIAL"}


def compare_labels(manifest, reference, independent, *, seed=42, sample_rate=0.20, review_requests=(), sample_method="random"):
    if not 0 <= sample_rate <= 1:
        raise EvaluationNotReady("표본 비율은 0과 1 사이여야 합니다.")
    if sample_method not in {"random", "case_document_type"}:
        raise EvaluationNotReady("표본 방식은 random 또는 case_document_type이어야 합니다.")
    split = reference.get("split")
    if split not in {"dev", "test"} or independent.get("split") != split or reference.get("dataset_version") != independent.get("dataset_version") or reference.get("dataset_version") != manifest.get("dataset_version"):
        raise EvaluationNotReady("대조할 자료 버전과 split 구분을 확인하세요.")
    contracts = [row for row in manifest["contracts"] if row["split"] == split]
    allowed_documents = {str(doc["document_id"]) for row in contracts for doc in row["documents"]}
    allowed_contracts = {str(row["contract_id"]) for row in contracts}
    if set(independent["documents"]) - allowed_documents or set(independent["contracts"]) - allowed_contracts:
        raise EvaluationNotReady("독립 판독에 선택한 split 목록에 없는 ID가 있습니다.")
    rows = []

    def add(cid, key, expected, actual, valid, *, document=None, ambiguous=False, blocked=False):
        state = "UNANSWERED" if not valid else ("AGREE" if expected == actual else "DISAGREE")
        rows.append({"review_id": f"{cid}/{document['document_id'] if document else 'contract'}/{key}",
                     "contract_id": cid, "document_id": document["document_id"] if document else None,
                     "source_path": document["path"] if document else None,
                     "key": key, "reference": expected, "independent": actual,
                     "comparison": state, "ambiguous": ambiguous, "source_unread": blocked,
                     "human_review_required": False, "human_review_completed": False})

    for contract in contracts:
        cid = str(contract["contract_id"])
        ref_contract = reference["contracts"][cid]
        other_contract = independent["contracts"].get(cid, {})
        all_read = all(independent["documents"].get(str(doc["document_id"]), {}).get("original_read", {}).get("readable") is True
                       and independent["documents"].get(str(doc["document_id"]), {}).get("original_read", {}).get("method") in {"visual", "text_content", "visual_and_text"}
                       for doc in contract["documents"])
        missing = other_contract.get("missing_types")
        valid = isinstance(missing, list) and all(kind in DOCUMENT_TYPES for kind in missing) and len(missing) == len(set(missing))
        add(cid, "missing_types", sorted(ref_contract["missing_types"]), sorted(missing) if valid else missing, valid and all_read, blocked=not all_read)
        checks = other_contract.get("checks", [])
        if not isinstance(checks, list) or any(not isinstance(row, dict) for row in checks):
            raise EvaluationNotReady("독립 판독의 검수 항목 형식을 확인하세요.")
        allowed = {(row["rule_id"], row["field"]) for row in blind_check_slots(contract)}
        other_checks = {}
        for row in checks:
            key = (row.get("rule_id"), row.get("field"))
            if key not in allowed or key in other_checks:
                raise EvaluationNotReady("독립 판독의 알 수 없거나 중복된 검수 항목을 확인하세요.")
            other_checks[key] = row.get("status")
        for row in ref_contract["checks"]:
            actual = other_checks.get((row["rule_id"], row["field"]))
            add(cid, row["rule_id"] + "/" + row["field"], row["status"], actual,
                actual in (*CHECK_STATUSES, "N/A") and all_read, ambiguous=row["status"] == "REVIEW", blocked=not all_read)
        for doc in contract["documents"]:
            did = str(doc["document_id"])
            expected = reference["documents"][did]
            actual = independent["documents"].get(did, {})
            read = actual.get("original_read", {})
            readable = read.get("readable") is True and read.get("method") in {"visual", "text_content", "visual_and_text"}
            add(cid, "document_type", expected["document_type"], actual.get("document_type"),
                readable and actual.get("document_type") in (*DOCUMENT_TYPES, "unknown"), document=doc, blocked=not readable)
            for field in FIELDS:
                ref_answer = expected["fields"][field]
                answer = actual.get("fields", {}).get(field)
                valid = readable and valid_field(field, answer)
                normalized_reference = {"state": ref_answer["state"], "value": str(normalize(field, ref_answer["value"])) if ref_answer["state"] == "VALUE" else None}
                normalized_actual = ({"state": answer["state"], "value": str(normalize(field, answer["value"])) if answer["state"] == "VALUE" else None} if valid else answer)
                add(cid, field, normalized_reference, normalized_actual, valid, document=doc,
                    ambiguous=ref_answer["state"] == "REVIEW" or isinstance(answer, dict) and answer.get("state") == "REVIEW", blocked=not readable)
    by_id = {row["review_id"]: row for row in rows}
    requested = set()
    for request in review_requests:
        rid, reason = request.get("review_id"), request.get("reason")
        if rid not in by_id or rid in requested or not isinstance(reason, str) or not reason.strip():
            raise EvaluationNotReady("추가 사람 확인 요청의 ID, 중복, 이유를 확인하세요.")
        requested.add(rid)
        by_id[rid]["human_question"] = reason
    mandatory = [row for row in rows if row["comparison"] == "DISAGREE" or (row["ambiguous"] or row.get("human_question")) and row["comparison"] != "UNANSWERED"]
    for row in mandatory:
        reason = "DISAGREEMENT" if row["comparison"] == "DISAGREE" else "INTERPRETATION" if row.get("human_question") else "AMBIGUITY"
        row.update(human_review_required=True, selection_reason=reason)
    agreements = sorted([row for row in rows if row["comparison"] == "AGREE" and not row["human_review_required"]], key=lambda row: row["review_id"])
    target = math.ceil(len(agreements) * sample_rate)
    rng = random.Random(seed)
    strata = []
    if sample_method == "case_document_type":
        groups = {}
        for row in agreements:
            did = str(row["document_id"] or row["key"].split("/")[-1])
            kind = reference["documents"].get(did, {}).get("document_type", "contract_checks")
            groups.setdefault((row["contract_id"], kind), []).append(row)
        keys = sorted(groups)
        # Guarantee one cell per case/type group when the requested total
        # permits it. Allocate the remainder proportionally, then sample
        # randomly within each group without changing the total sample size.
        quotas = {key: int(target >= len(keys)) for key in keys}
        while sum(quotas.values()) < target:
            key = max((key for key in keys if quotas[key] < len(groups[key])),
                      key=lambda key: target * len(groups[key]) / len(agreements) - quotas[key])
            quotas[key] += 1
        sample = []
        for key in keys:
            sample.extend(rng.sample(groups[key], quotas[key]))
            strata.append({"contract_id": key[0], "document_type": key[1],
                           "eligible_count": len(groups[key]), "sampled_count": quotas[key]})
    else:
        sample = rng.sample(agreements, target)
    for row in sample:
        row.update(human_review_required=True, selection_reason="RANDOM_SAMPLE")
    coverage = [{"contract_id": row["contract_id"], "scenario": row.get("scenario"),
                 "selected_document_ids": sorted({item["document_id"] for item in rows if item["contract_id"] == str(row["contract_id"]) and item["human_review_required"] and item["document_id"] is not None})}
                for row in contracts]
    counts = Counter(row["comparison"] for row in rows)
    result = {"dataset_version": reference["dataset_version"], "split": split, "review": {"confirmed": False,
            "human_review_completed_count": 0, "independent_complete": counts["UNANSWERED"] == 0},
            "sampling": {"seed": seed, "rate": sample_rate, "method": "random_without_replacement_over_agreed_nonmandatory_cells",
                         "eligible_agreements": len(agreements), "sampled_count": len(sample), "coverage": coverage},
            "review_requests": list(review_requests),
            "counts": dict(counts), "required_human_count": sum(row["human_review_required"] for row in rows), "rows": rows}
    if sample_method == "case_document_type":
        result["sampling"].update(method="stratified_random_by_case_document_type", strata=strata)
    return result


def validate_reference_draft(manifest, reference, split):
    """Validate draft structure only; never authorize heldout predictions.

    The frozen scoring validator deliberately rejects test preliminary scoring.
    Project one split into its draft-only structural check, without changing
    originals or marking any item human-confirmed.
    """
    from backend.evaluation_core import validate_labels
    if split not in {"dev", "test"} or reference.get("split") != split:
        raise EvaluationNotReady("정답 초안의 split이 다릅니다.")
    projected_manifest = copy.deepcopy(manifest)
    projected_manifest["contracts"] = [row for row in projected_manifest["contracts"] if row["split"] == split]
    for row in projected_manifest["contracts"]:
        row["split"] = "dev"
    projected = copy.deepcopy(reference)
    projected["split"] = "dev"
    validate_labels(projected_manifest, projected, "dev", allow_unreviewed=True)
