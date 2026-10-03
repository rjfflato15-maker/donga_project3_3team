"""Record only changed or explicitly reviewed fields, never the whole PUT body."""
import json
from datetime import datetime, timezone
from ..db.models import AuditEvent
from ..schemas.document import AnalysisFields


def current_confirmations(db, document_id, stored):
    values = AnalysisFields(**stored).model_dump()
    metadata = stored.get('human_review')
    metadata = metadata if isinstance(metadata, dict) else {}
    if isinstance(metadata.get('field_confirmations'), dict):
        candidates = metadata['field_confirmations']
    else:
        # Legacy saves had no explicit field scope. Recover actual changes only.
        candidates = {}
        events = db.query(AuditEvent).filter_by(document_id=document_id, action='EXTRACT_CORRECTED').order_by(AuditEvent.event_id).all()
        for event in events:
            try:
                details = json.loads(event.details)
                before, after = details.get('before'), details.get('after')
                if not isinstance(before, dict) or not isinstance(after, dict):
                    continue
                old, new = AnalysisFields(**before).model_dump(), AnalysisFields(**after).model_dump()
                named = details.get('confirmed_fields')
                keys = named if isinstance(named, list) else [key for key in new if new[key] != old[key]]
                for key in keys:
                    if key in new:
                        candidates[key] = {'actor_name': event.actor_name, 'at': event.created_at.isoformat(),
                            'value': new[key], 'method': 'RECORDED_FIELD_SCOPE' if isinstance(named, list) else 'LEGACY_CHANGED_VALUE'}
            except (ValueError, TypeError):
                continue
    return {key: dict(proof) for key, proof in candidates.items() if key in values and isinstance(proof, dict)
            and 'value' in proof and proof['value'] == values[key]}


def confirm_fields(db, document_id, before, after, actor, explicit=None):
    old = AnalysisFields(**before).model_dump()
    changed = [key for key in after if old[key] != after[key]]
    named = list(explicit or [])
    if any(key not in after for key in named) or len(named) != len(set(named)):
        raise ValueError('확인할 필드 이름이 올바르지 않거나 중복됩니다.')
    selected = sorted(set(changed) | set(named))
    proofs = current_confirmations(db, document_id, before)
    at = datetime.now(timezone.utc).isoformat()
    for key in selected:
        proofs[key] = {'actor_name': actor.display_name, 'at': at, 'value': after[key],
            'method': 'CHANGED_VALUE' if key in changed else 'EXPLICIT_CONFIRMATION'}
    return {'field_confirmations': proofs, 'confirmed_fields': sorted(proofs)}, changed, selected


def reviewed_ai(review, proofs):
    result = dict(review)
    known = set(proofs)
    targets = set(review.get('targets') or [])
    if not targets:
        targets = {item['field'] for item in review.get('decisions', []) if isinstance(item, dict) and item.get('field')}
    pending = sorted(targets - known)
    complete = bool(targets) and not pending
    result.update(human_confirmed=complete, human_confirmed_fields=sorted(targets & known),
        human_unconfirmed_fields=pending,
        manual_review_required=bool(pending) if targets else bool(review.get('manual_review_required')))
    result['decisions'] = [{**item, 'human_confirmed': item.get('field') in known}
        for item in review.get('decisions', []) if isinstance(item, dict)]
    return result
