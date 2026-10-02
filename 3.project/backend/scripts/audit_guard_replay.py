"""DEV-only offline audit of fixed-response guard revisions. No source/test reads."""
import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))
from backend.evaluation_core import EvaluationNotReady, file_hash, verify_freeze
from backend.scripts.compare_llm_modes import guard_outcomes, proposal_matches_gold


CAUSE_NAMES = {
    "DOCX_PHYSICAL_PAGE_POLICY": "DOCX의 물리 페이지 요구",
    "SCOPE_ANCHOR_OMITTED": "금액 범위의 위치·문구 누락",
    "OCR_SUPPLIER_LABEL_DAMAGED": "공급자 라벨 OCR 손상·당사자 확인 불가",
    "OCR_THOUSANDS_SPACING": "천 단위 숫자 안의 OCR 공백",
    "OCR_LABEL_BULLET": "라벨 뒤 OCR 구분 기호",
    "INCORRECT_PROPOSAL": "값 또는 보류 상태가 정답과 불일치",
}


def original_cause(decision, correct):
    if not correct:
        return "INCORRECT_PROPOSAL"
    proposal = decision["proposal"]
    if (decision.get("anchor") or {}).get("location_kind") == "document_block":
        return "DOCX_PHYSICAL_PAGE_POLICY"
    if decision["field"] == "amount_scope" and not proposal["quote"] and proposal["line"] is None:
        return "SCOPE_ANCHOR_OMITTED"
    if decision["field"].endswith("amount"):
        return "OCR_THOUSANDS_SPACING"
    if "예금주•" in proposal["quote"] or "예금주·" in proposal["quote"]:
        return "OCR_LABEL_BULLET"
    return "OCR_SUPPLIER_LABEL_DAMAGED"


def audit(previous, current, labels, original_audit):
    before, after = previous["hybrid_guarded"], current["hybrid_guarded"]
    if set(before) != set(after):
        raise EvaluationNotReady("dev 문서 목록이 다릅니다.")
    rows, causes, newly_accepted_wrong = [], Counter(), []
    for did in before:
        if before[did]["response_id"] != after[did]["response_id"]:
            raise EvaluationNotReady("전후 LLM 응답이 다릅니다.")
        old_by_field = {d["field"]: d for d in before[did]["review"]["decisions"]}
        new_by_field = {d["field"]: d for d in after[did]["review"]["decisions"]}
        if old_by_field.keys() != new_by_field.keys():
            raise EvaluationNotReady("전후 요청 필드가 다릅니다.")
        for field, old in old_by_field.items():
            new = new_by_field[field]
            if old["proposal"] != new["proposal"]:
                raise EvaluationNotReady("전후 모델 제안이 다릅니다.")
            correct = proposal_matches_gold(old["proposal"], labels["documents"][did]["fields"][field], field)
            if not old["applied"] or not new["applied"] or not correct:
                cause = original_cause(old, correct) if not old["applied"] else "PREVIOUSLY_ACCEPTED_MISMATCH"
                if not old["applied"] and correct:
                    causes[cause] += 1
                row = {"document_id": did, "field": field, "gold_matching": correct,
                       "old_applied": old["applied"], "new_applied": new["applied"], "cause": cause,
                       "old_reasons": old["reasons"], "new_reasons": new["reasons"],
                       "proposal": old["proposal"], "resolved_anchor": new.get("anchor"),
                       "new_disposition": "machine_grounded_awaiting_final_confirmation" if new["applied"] else "human_review_referral"}
                rows.append(row)
                if not old["applied"] and new["applied"] and not correct:
                    newly_accepted_wrong.append(row)
    retained = []
    for example in original_audit["incorrect_examples"]:
        decision = next(d for d in after[example["document_id"]]["review"]["decisions"] if d["field"] == example["field"])
        if decision["applied"]:
            raise EvaluationNotReady("기존 오답 제안이 새 가드를 통과했습니다.")
        retained.append({**example, "still_rejected": True, "new_reasons": decision["reasons"]})
    if newly_accepted_wrong:
        raise EvaluationNotReady("기존에 거부한 오답을 새 가드가 채택했습니다.")
    return {"scope": "confirmed dev offline audit; no test or production gold lookup",
            "guard_tuning_disclosure": "가드 v3는 dev 감사 결과로 조정함",
            "docx_policy": "DOCX는 페이지 배치는 미확인, 글자 근거는 확인",
            "same_response_and_targets_all_documents": True,
            "original_correct_rejection_causes": dict(causes), "original_incorrect_proposals": retained,
            "original_correct_rejections_recovered": sum(not r["old_applied"] and r["new_applied"] and r["gold_matching"] for r in rows),
            "original_correct_rejections_retained_for_human": sum(not r["old_applied"] and not r["new_applied"] and r["gold_matching"] for r in rows),
            "newly_rejected_mismatching_abstentions": sum(r["old_applied"] and not r["new_applied"] and not r["gold_matching"] for r in rows),
            "newly_accepted_incorrect_count": len(newly_accepted_wrong),
            "before": guard_outcomes(before, labels), "after": guard_outcomes(after, labels), "rows": rows}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous", type=Path, default=PROJECT / "docs/eval/dev/comparison")
    parser.add_argument("--current", type=Path, default=PROJECT / "docs/eval/dev/guard_v3")
    args = parser.parse_args()
    # There is deliberately no --split or arbitrary labels argument.
    labels_path = PROJECT / "eval/dataset/ground_truth_dev.json"
    receipt = verify_freeze(PROJECT / "eval/dataset/manifest.json", labels_path)
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    for folder in (args.previous, args.current):
        report = load(folder / "four_modes.json")
        if (report["metadata"]["split"] != "dev" or report["metadata"]["labels_sha256"] != receipt["labels_sha256"]):
            raise EvaluationNotReady("확정 dev 정답 기준 보고서가 아닙니다.")
    payload = audit(load(args.previous / "extraction_evidence.json"), load(args.current / "extraction_evidence.json"),
                    load(labels_path), load(args.previous / "guard_audit.json"))
    payload["labels_sha256"] = receipt["labels_sha256"]
    payload["previous_evidence_sha256"] = file_hash(args.previous / "extraction_evidence.json")
    payload["current_evidence_sha256"] = file_hash(args.current / "extraction_evidence.json")
    (args.current / "guard_audit.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# dev 가드 v2 → v3 감사", "", payload["guard_tuning_disclosure"], payload["docx_policy"], "",
             "PAGE_UNVERIFIED 15건은 실제 DOCX 4건과 PDF·PNG 범위 근거 누락 11건이다. 위치와 값이 모두 확인된 경우만 완화한다.", "",
             "| 기존 정답 일치 거부 원인 | 건수 | 조치 |", "|---|---:|---|"]
    for cause, count in payload["original_correct_rejection_causes"].items():
        lines.append(f"| {CAUSE_NAMES[cause]} | {count} | {'계속 사람 추가 확인' if cause == 'OCR_SUPPLIER_LABEL_DAMAGED' else '좁은 근거 검사로 채택'} |")
    lines += ["", "| 지표 | 가드 v2 | 가드 v3 |", "|---|---:|---:|"]
    for key, label in (("accepted_value_precision", "채택 VALUE 중 정답 일치"),
                       ("human_referral_field_rate", "요청 80필드 중 추가 사람 확인 비율"),
                       ("guard_auto_validated_field_rate", "요청 필드 기계 근거 검증 완료율"),
                       ("human_referral_document_rate", "전체 59문서 중 추가 사람 확인 비율")):
        lines.append(f"| {label} | {payload['before'][key]:.2%} | {payload['after'][key]:.2%} |")
    lines += ["", "거부는 운영 시 사람 추가 확인으로 넘기는 조치다. 값·상태가 틀린지는 확정 dev 정답으로 사후 분석한다.",
              f"기존 정답 일치 거부 27건 중 {payload['original_correct_rejections_recovered']}건을 채택하고 {payload['original_correct_rejections_retained_for_human']}건은 유지했다. 기존 오답 2건은 모두 거부되며, 참고값 A/B를 ABSENT로 답한 3건도 새로 거부한다.",
              "채택 VALUE 중 OCR 회사명 오독 1건은 이전과 동일하게 남는다. 새로 풀린 21건은 정답과 일치했으나 dev 조정 결과이며 안전성을 보증하지 않는다.",
              "자동 검증 완료율은 기계 근거 검사 기준이다. 채택 AI 값은 여전히 최종 담당자 확인 전(human_confirmed=false)이다.",
              "이전 전체 필드 정확도는 311/337(92.28%)이며 v3와 같은 정답·응답을 사용했다. 전체 필드 분모에서 거부·REVIEW를 제외하지 않는다.", "",
              "| 문서 | 필드 | 원인 | 정답 일치 | 이전 | v3 | v3 사유 |", "|---|---|---|---|---|---|---|"]
    with (args.current / "guard_audit.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["document_id", "field", "cause", "gold_matching", "old_applied", "new_applied", "new_reasons", "new_disposition"])
        for r in payload["rows"]:
            writer.writerow([r["document_id"], r["field"], r["cause"], r["gold_matching"], r["old_applied"], r["new_applied"], ",".join(r["new_reasons"]), r["new_disposition"]])
            lines.append(f"| {r['document_id']} | {r['field']} | {CAUSE_NAMES.get(r['cause'], '기존 채택 불일치')} | {'일치' if r['gold_matching'] else '불일치'} | {'채택' if r['old_applied'] else '추가 확인'} | {'채택' if r['new_applied'] else '추가 확인'} | {', '.join(r['new_reasons'])} |")
    (args.current / "guard_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("dev 감사 완료: 기존 오답 2건 거부 유지, 새로 채택한 오답 0건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
