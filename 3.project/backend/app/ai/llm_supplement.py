import copy
from .local_llm import OllamaClient
from .grounding import canonical, guard_proposal, source_pages, supplementation_targets, GUARD_VERSION


def apply_proposals(rule_fields, run, pages, document_type, targets, *, guarded=True, llm_only=False):
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
        decision = guard_proposal(field, proposal, pages, document_type)
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
    return fields, {"status": "COMPLETED" if run.get("ok") else "FAILED", "error": run.get("error"),
                    "model": run.get("model"), "model_metadata": run.get("model_metadata"),
                    "elapsed_seconds": run.get("elapsed_seconds", 0), "attempts": run.get("attempts", 0),
                    "targets": list(targets), "decisions": decisions, "manual_review_required": bool(targets),
                    "human_confirmed": False, "prompt_version": run.get("prompt_version"), "guard_version": GUARD_VERSION,
                    "settings": run.get("settings")}


def supplement_document(file_path, raw_text, fields, document_type, client=None):
    try:
        pages = source_pages(file_path, raw_text)
        targets = supplementation_targets(fields, pages, document_type)
        if not targets:
            return fields, {"status": "NOT_NEEDED", "targets": [], "decisions": [], "manual_review_required": False}
        client = client or OllamaClient()
        run = client.extract(pages, targets, document_type)
        return apply_proposals(fields, run, pages, document_type, targets)
    except Exception:
        return fields, {"status": "FAILED", "error": "LOCAL_LLM_OR_SOURCE_UNAVAILABLE", "decisions": [],
                        "manual_review_required": True, "human_confirmed": False}
