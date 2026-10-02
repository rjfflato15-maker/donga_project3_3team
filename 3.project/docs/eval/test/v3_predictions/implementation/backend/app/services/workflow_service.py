import json
import hashlib
from datetime import datetime
from ..db.models import CompanySetting, ContractWorkflow, ContractReview, AuditEvent
from ..schemas.common import CORE_6_DOCUMENT_TYPES, DocumentType
from ..config import NTS_MODE


def required_types(db):
    setting = db.get(CompanySetting, "required_documents")
    values = json.loads(setting.value) if setting else [t.value for t in CORE_6_DOCUMENT_TYPES]
    return [DocumentType(v) for v in values]


def policy_for(db, contract_id: int):
    row = db.get(ContractWorkflow, contract_id)
    return {"revision": row.revision if row else 1, "amount_basis": row.amount_basis if row else "UNKNOWN",
            "tax_amount": row.tax_amount if row else None, "payment_mode": row.payment_mode if row else "FULL"}


def touch_contract(db, contract_id: int):
    row = db.get(ContractWorkflow, contract_id)
    if row is None:
        db.add(ContractWorkflow(contract_id=contract_id, revision=2))
    else:
        db.query(ContractWorkflow).filter(ContractWorkflow.contract_id == contract_id).update(
            {ContractWorkflow.revision: ContractWorkflow.revision + 1}, synchronize_session="fetch")
    db.flush()


def fingerprint_for(db, contract, documents):
    payload = {"contract": [contract.title, contract.vendor_name, contract.business_number, contract.contract_amount],
               "nts_mode": NTS_MODE,
               "policy": policy_for(db, contract.contract_id),
               "required_documents": [t.value for t in required_types(db)],
               "documents": sorted(documents, key=lambda d: d["document_id"])}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def review_state(db, contract_id: int, fingerprint=None):
    policy = policy_for(db, contract_id)
    reviews = db.query(ContractReview).filter(ContractReview.contract_id == contract_id).order_by(ContractReview.review_id.desc()).limit(30).all()
    latest = reviews[0] if reviews else None
    status = "PENDING"
    if latest:
        status = latest.decision if latest.revision == policy["revision"] else "STALE"
        if fingerprint and json.loads(latest.snapshot_json).get("fingerprint") != fingerprint:
            status = "STALE"
    return {**policy, "approval_status": status,
            "fingerprint": fingerprint,
            "reviews": [{"review_id": r.review_id, "revision": r.revision, "actor_name": r.actor_name,
                         "decision": r.decision, "note": r.note, "created_at": r.created_at.isoformat()}
                        for r in reviews]}


def audit(db, actor, action: str, contract_id=None, document_id=None, details=None):
    db.add(AuditEvent(actor_id=actor.user_id if actor else None,
                      actor_name=actor.display_name if actor else "시스템", action=action,
                      contract_id=contract_id, document_id=document_id,
                      details=json.dumps(details or {}, ensure_ascii=False, default=str),
                      created_at=datetime.utcnow()))
    db.commit()
