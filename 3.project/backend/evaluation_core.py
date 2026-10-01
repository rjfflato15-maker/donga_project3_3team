"""Offline evaluation against independently reviewed labels; no app/DB imports."""
import hashlib
import json
import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

DOCUMENT_TYPES = ("contract", "estimate", "business_registration", "bank_account", "tax_invoice", "inspection_confirmation")
FIELDS = ("company_name", "business_registration_no", "supply_amount", "tax_amount", "total_amount", "issue_date", "amount_scope")
CHECK_STATUSES = ("PASS", "FAIL", "REVIEW", "MISSING")
FIELD_STATES = ("VALUE", "ABSENT", "REVIEW")


class EvaluationNotReady(ValueError):
    pass


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dataset_file(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise EvaluationNotReady("평가 자료 경로가 잘못되었거나 파일이 없습니다.")
    return path


def verify_dataset(root, manifest):
    seen = set()
    contract_ids = set()
    families = {"dev": set(), "test": set()}
    for contract in manifest["contracts"]:
        if contract["contract_id"] in contract_ids or not contract["documents"]:
            raise EvaluationNotReady("계약 ID 중복 또는 문서가 없는 평가 계약을 확인하세요.")
        contract_ids.add(contract["contract_id"])
        if contract["split"] not in families:
            raise EvaluationNotReady("평가 자료의 dev/test 구분을 확인하세요.")
        families[contract["split"]].add(contract["layout_family"])
        for document in contract["documents"]:
            if document["document_id"] in seen:
                raise EvaluationNotReady("문서 ID가 중복됩니다.")
            seen.add(document["document_id"])
            if file_hash(dataset_file(root, document["path"])) != document["sha256"]:
                raise EvaluationNotReady("평가 서류가 변경되었습니다. 새 자료 버전으로 검수하세요.")
    if families["dev"] & families["test"]:
        raise EvaluationNotReady("같은 서식 계열이 dev와 test에 섞여 있습니다.")


def normalize(field, value):
    if value is None or value == "" or value == "UNKNOWN":
        return None
    if field.endswith("amount"):
        try:
            amount = Decimal(str(value).replace(",", "").replace("원", "").strip())
        except InvalidOperation:
            return None
        return amount if amount.is_finite() and amount >= 0 else None
    if field == "business_registration_no":
        return re.sub(r"[\s-]", "", str(value))
    if field == "issue_date":
        from datetime import date, datetime
        if isinstance(value, (date, datetime)):
            return value.strftime("%Y-%m-%d")
        token = str(value).strip()
        match = re.fullmatch(r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})", token)
        if match:
            try:
                return date(*(int(part) for part in match.groups())).isoformat()
            except ValueError:
                return None
        return None
    return re.sub(r"\s+", " ", str(value)).strip()


def validate_labels(manifest, labels, split, *, allow_unreviewed=False):
    review = labels.get("review", {})
    preliminary = allow_unreviewed and review.get("reviewer_type") == "source_reference"
    if allow_unreviewed and (split != "dev" or not preliminary):
        raise EvaluationNotReady("예비 측정은 생성 정보에서 작성한 dev 정답 초안만 사용할 수 있습니다.")
    if not preliminary and (review.get("reviewer_type", "human") != "human"
                            or not review.get("confirmed") or not review.get("reviewer") or not review.get("confirmed_at")):
        raise EvaluationNotReady("사람이 검수하고 확정한 정답표가 필요합니다. 성능 수치를 계산하지 않았습니다.")
    if preliminary and (review.get("confirmed") or not review.get("author") or not review.get("created_at")):
        raise EvaluationNotReady("AI 초안은 작성자를 기록하고 사람 확정 상태는 false로 유지하세요.")
    if labels.get("dataset_version") != manifest.get("dataset_version") or labels.get("split") != split:
        raise EvaluationNotReady("정답표와 자료 버전이 다릅니다.")
    contracts = [row for row in manifest["contracts"] if row["split"] == split]
    if not contracts:
        raise EvaluationNotReady("평가할 계약이 없습니다.")
    missing = []
    for contract in contracts:
        cid = str(contract["contract_id"])
        truth_contract = labels.get("contracts", {}).get(cid, {})
        checked = truth_contract.get("source_checked") if preliminary else truth_contract.get("reviewed")
        if not checked or not isinstance(truth_contract.get("missing_types"), list):
            missing.append("계약 " + cid)
        elif any(value not in DOCUMENT_TYPES for value in truth_contract["missing_types"]):
            raise EvaluationNotReady("누락 문서 정답 유형을 확인하세요.")
        expected_keys = {(row["rule_id"], row["field"]) for row in contract["check_slots"]}
        checks = truth_contract.get("checks", [])
        keys = [(row.get("rule_id"), row.get("field")) for row in checks]
        if len(keys) != len(set(keys)) or set(keys) != expected_keys:
            missing.append("검수 항목 " + cid)
        if any(row.get("status") not in (*CHECK_STATUSES, "N/A") for row in checks):
            missing.append("검수 정답 " + cid)
        labeled_missing = {row.get("field") for row in checks
                           if row.get("rule_id") == "REQUIRED_DOCUMENTS" and row.get("status") == "MISSING"}
        if isinstance(truth_contract.get("missing_types"), list) and labeled_missing != set(truth_contract["missing_types"]):
            raise EvaluationNotReady("누락 문서 목록과 REQUIRED_DOCUMENTS 정답이 다릅니다.")
        for document in contract["documents"]:
            did = str(document["document_id"])
            truth = labels.get("documents", {}).get(did, {})
            checked = truth.get("source_checked") if preliminary else truth.get("reviewed")
            if not checked or truth.get("document_type") not in (*DOCUMENT_TYPES, "unknown"):
                missing.append("문서 " + did)
            for field in FIELDS:
                answer = truth.get("fields", {}).get(field, {})
                state, value = answer.get("state"), answer.get("value")
                if state not in FIELD_STATES:
                    missing.append(did + "/" + field)
                elif state == "VALUE":
                    normalized = normalize(field, value)
                    if normalized is None or (field == "business_registration_no" and not re.fullmatch(r"\d{10}", normalized)):
                        missing.append(did + "/" + field)
                    if field == "amount_scope" and value not in {"FULL", "PARTIAL"}:
                        missing.append(did + "/" + field)
                elif value not in (None, ""):
                    raise EvaluationNotReady("ABSENT/REVIEW 정답 값은 비워두세요.")
    if missing:
        raise EvaluationNotReady(f"미작성 또는 미확인 정답 {len(missing)}개가 있습니다. 성능 수치를 계산하지 않았습니다.")
    return contracts


def verify_freeze(manifest_path, labels_path):
    receipt_path = Path(labels_path).with_suffix(".freeze.json")
    if not receipt_path.is_file():
        raise EvaluationNotReady("정답표 확정 기록이 없습니다. 사람이 검수한 양식을 먼저 가져오세요.")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("labels_sha256") != file_hash(labels_path) or receipt.get("manifest_sha256") != file_hash(manifest_path):
        raise EvaluationNotReady("확정 이후 정답 또는 자료 목록이 변경되었습니다. 검수 후 새 버전으로 확정하세요.")
    return receipt


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def macro_f1(pairs, classes):
    rows = {}
    for label in classes:
        tp = sum(expected == actual == label for expected, actual in pairs)
        fp = sum(expected != label and actual == label for expected, actual in pairs)
        fn = sum(expected == label and actual != label for expected, actual in pairs)
        rows[label] = {"support": tp + fn, "tp": tp, "fp": fp, "fn": fn,
                       "f1": 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else 0.0}
    return sum(row["f1"] for row in rows.values()) / len(classes), rows


def score_predictions(contracts, labels, predictions):
    classification = []
    field_counts = {field: Counter() for field in FIELDS}
    check_pairs, failures = [], []
    missing_tp = missing_fn = missing_fp = unsafe_total = unsafe_pass = pass_total = review_total = 0
    for contract in contracts:
        cid = str(contract["contract_id"])
        for document in contract["documents"]:
            did = str(document["document_id"])
            truth = labels["documents"][did]
            prediction = predictions["documents"][did]
            classification.append((truth["document_type"], prediction["document_type"]))
            if truth["document_type"] != prediction["document_type"]:
                failures.append({"kind": "classification", "document_id": did})
            for field in FIELDS:
                answer = truth["fields"][field]
                raw_value = prediction["fields"].get(field)
                provided = raw_value is not None and raw_value != "" and raw_value != "UNKNOWN"
                actual = normalize(field, raw_value)
                counts = field_counts[field]
                counts["all"] += 1
                counts["provided"] += provided
                if answer["state"] == "ABSENT":
                    counts["absent"] += 1
                    counts["false_extraction"] += provided
                    correct = not provided
                else:
                    counts["scored"] += 1
                    correct = provided and actual == normalize(field, answer["value"]) if answer["state"] == "VALUE" else not provided
                    counts["correct"] += correct
                    if answer["state"] == "VALUE":
                        counts["present"] += 1
                        counts["present_correct"] += correct
                    else:
                        counts["ambiguous"] += 1
                        counts["ambiguous_correct"] += correct
                if not correct:
                    failures.append({"kind": "field", "document_id": did, "field": field, "expected_state": answer["state"]})
        truth_contract = labels["contracts"][cid]
        actual_checks = predictions["contracts"][cid]["checks"]
        expected_missing = set(truth_contract["missing_types"])
        actual_missing = {row["field"] for row in actual_checks if row["rule_id"] == "REQUIRED_DOCUMENTS" and row["status"] == "MISSING"}
        missing_tp += len(expected_missing & actual_missing)
        missing_fn += len(expected_missing - actual_missing)
        missing_fp += len(actual_missing - expected_missing)
        expected = {(row["rule_id"], row["field"]): row["status"] for row in truth_contract["checks"]}
        actual = {}
        for row in actual_checks:
            key = (row["rule_id"], row["field"])
            if key in actual:
                raise EvaluationNotReady("검수 결과의 동일 항목이 중복되어 채점 기준을 확인해야 합니다.")
            actual[key] = row["status"]
        for key in sorted(expected.keys() | actual.keys()):
            want, got = expected.get(key, "N/A"), actual.get(key, "N/A")
            if want == got == "N/A":
                continue
            check_pairs.append((want, got))
            unsafe = want in {"FAIL", "REVIEW", "MISSING"}
            unsafe_total += unsafe
            unsafe_pass += unsafe and got == "PASS"
            pass_total += got == "PASS"
            review_total += got == "REVIEW"
            if want != got:
                failures.append({"kind": "check", "contract_id": cid, "rule_id": key[0], "field": key[1], "expected": want, "actual": got})
    classification_f1, class_rows = macro_f1(classification, DOCUMENT_TYPES)
    cross_f1, check_rows = macro_f1(check_pairs, CHECK_STATUSES)
    totals = sum(field_counts.values(), Counter())
    return {
        "contract_count": len(contracts), "document_count": len(classification),
        "classification_macro_f1": classification_f1, "classification_by_type": class_rows,
        "field_accuracy": ratio(totals["correct"], totals["scored"]),
        "present_field_accuracy": ratio(totals["present_correct"], totals["present"]),
        "ambiguous_field_accuracy": ratio(totals["ambiguous_correct"], totals["ambiguous"]),
        "false_extraction_on_absent_rate": ratio(totals["false_extraction"], totals["absent"]),
        "field_counts": dict(totals), "fields": {key: dict(value) for key, value in field_counts.items()},
        "extraction_coverage": ratio(totals["provided"], totals["all"]),
        "missing_recall": ratio(missing_tp, missing_tp + missing_fn),
        "missing_precision": ratio(missing_tp, missing_tp + missing_fp),
        "missing_counts": {"tp": missing_tp, "fn": missing_fn, "fp": missing_fp},
        "cross_validation_macro_f1": cross_f1, "checks_by_status": check_rows,
        "wrong_pass_rate": ratio(unsafe_pass, unsafe_total),
        "wrong_pass_among_passes": ratio(unsafe_pass, pass_total),
        "wrong_pass_counts": {"unsafe_expected": unsafe_total, "wrong_pass": unsafe_pass, "predicted_pass": pass_total},
        "check_review_rate": ratio(review_total, len(check_pairs)),
        "failures": failures,
    }
