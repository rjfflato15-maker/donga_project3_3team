import copy
import os
from .local_llm import OllamaClient
from .grounding import (canonical, guard_proposal, source_pages, source_evidence_complete,
                        supplementation_targets, GUARD_VERSION)


def apply_proposals(rule_fields, run, pages, document_type, targets, *, guarded=True, llm_only=False, guard_policy="v3"):
    if guard_policy == "v4":
        from .grounding_v4 import guard_proposal as policy_guard, GUARD_VERSION as policy_version
    elif guard_policy == "v3":
        policy_guard, policy_version = guard_proposal, GUARD_VERSION
    else:
        raise ValueError("UNKNOWN_GUARD_POLICY")
    fields = copy.deepcopy(rule_fields)
    if llm_only:
        fields["amount"], fields["amount_basis"] = None, "UNKNOWN"
        for field in targets:
            fields[field] = "UNKNOWN" if field == "amount_scope" else None
    decisions = []
    for field in targets:
        proposal = run.get("proposals", {}).get(field)
        if not run.get("ok") or not proposal:
            continue
        decision = policy_guard(field, proposal, pages, document_type)
        decision["applied"] = decision["accepted"] if guarded else True
        if decision["applied"]:
            value = canonical(field, proposal.get("value")) if proposal.get("state") == "VALUE" else None
            if field.endswith("amount") and value is not None:
                value = float(value)
            fields[field] = "UNKNOWN" if field == "amount_scope" and value is None else value
        decisions.append(decision)
    if any(d["applied"] and d["field"] in {"supply_amount", "tax_amount", "total_amount"} for d in decisions):
        fields["amount"] = fields.get("total_amount")
        fields["amount_basis"] = "TOTAL" if fields.get("total_amount") is not None else "UNKNOWN"
    unresolved = [field for field in targets if not any(
        d["field"] == field and d["applied"] and d["proposal"]["state"] != "REVIEW" for d in decisions)]
    return fields, {"status": "COMPLETED" if run.get("ok") else "FAILED", "error": run.get("error"),
                    "model": run.get("model"), "model_metadata": run.get("model_metadata"),
                    "elapsed_seconds": run.get("elapsed_seconds", 0), "attempts": run.get("attempts", 0),
                    "targets": list(targets), "decisions": decisions, "manual_review_required": bool(targets),
                    "guard_review_required": bool(unresolved), "unresolved_fields": unresolved,
                    "human_confirmed": False, "prompt_version": run.get("prompt_version"), "guard_version": policy_version,
                    "settings": run.get("settings")}


def supplement_document(file_path, raw_text, fields, document_type, client=None):
    # Empty evidence selects the bounded expected field set without scanning
    # unsafe/incomplete candidates. Keep failures resolvable by field review.
    targets = supplementation_targets(fields, [], document_type)
    try:
        pages = source_pages(file_path, raw_text)
        if not source_evidence_complete(pages):
            return fields, {"status": "FAILED", "error": "SOURCE_EVIDENCE_UNAVAILABLE", "decisions": [],
                            "targets": list(targets), "unresolved_fields": list(targets), "attempts": 0,
                            "manual_review_required": True, "guard_review_required": True,
                            "human_confirmed": False}
        targets = supplementation_targets(fields, pages, document_type)
        if not targets:
            return fields, {"status": "NOT_NEEDED", "targets": [], "decisions": [], "manual_review_required": False}
        client = client or OllamaClient()
        run = client.extract(pages, targets, document_type)
        return apply_proposals(fields, run, pages, document_type, targets,
                               guard_policy=os.getenv("APP_LLM_GUARD_POLICY", "v3"))
    except Exception:
        return fields, {"status": "FAILED", "error": "LOCAL_LLM_OR_SOURCE_UNAVAILABLE", "decisions": [],
                        "targets": list(targets), "unresolved_fields": list(targets),
                        "manual_review_required": True, "guard_review_required": True, "human_confirmed": False}
