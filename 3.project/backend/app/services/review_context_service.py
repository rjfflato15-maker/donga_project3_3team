# Release the read transaction before file hashing, rendering and OCR.
# AI anchors are retained for the proposal, not assigned to a later
# human correction whose current value may differ.
"""Read-only display metadata; never change predictions or fabricate anchors."""
import json
import hashlib
from types import SimpleNamespace
from pathlib import Path
from ..ai.grounding import canonical, candidates, evidence_anchor, source_pages
from ..db.models import AuditEvent, ResubmissionRequest, DocumentFileInfo
from ..schemas.document import AnalysisFields
from .contract_service import ContractService
from .storage_service import read_texts, resolve_path
from .company_policy_service import approval_state
from .review_summary_service import build_action_summary, display_issue_counts, pending_ai_count
from .evidence_geometry_service import attach_coordinates
from .document_version_service import active_documents
SOURCE_NAMES = {'RULE': '규칙', 'AI_SUPPLEMENT': 'AI 보완', 'HUMAN_CONFIRMATION': '사람 확인', 'UNAVAILABLE': '미추출'}


def display_anchor(page, line, quote, allow_text_line=False):
    anchor = evidence_anchor(page, line, quote)
    if anchor or not allow_text_line:
        return anchor
    lines = page['text'].splitlines()
    if type(line) is not int or not 1 <= line <= len(lines) or not quote or quote not in lines[line - 1]:
        return None
    start = sum(len(s) + 1 for s in lines[:line - 1]) + lines[line - 1].index(quote)
    return {'page': None, 'line': line, 'quote': quote, 'start': start, 'end': start + len(quote),
            'location_kind': 'text_line', 'page_layout_verified': False, 'text_verified': True}

def request_response(row):
    return {'request_id': row.request_id, 'contract_id': row.contract_id, 'contact_method': row.contact_method, 'requested_on': row.requested_on, 'due_on': row.due_on, 'memo': row.memo, 'status': row.status, 'actor_name': row.actor_name, 'created_at': row.created_at.isoformat(), 'resolved_at': row.resolved_at.isoformat() if row.resolved_at else None, 'resolution_note': row.resolution_note}

def document_provenance(db, doc):
    fields = json.loads(doc.extract.raw_fields or '{}') if doc.extract else {}
    values = AnalysisFields(**fields).model_dump()
    ai = fields.get('ai_review') or {}
    decisions = {r['field']: r for r in ai.get('decisions', []) if isinstance(r, dict) and r.get('field')}
    manual = bool(doc.extract and doc.extract.extracted_status == 'MANUALLY_CONFIRMED')
    correction = db.query(AuditEvent).filter_by(document_id=doc.document_id, action='EXTRACT_CORRECTED').order_by(AuditEvent.event_id.desc()).first() if manual else None
    confirmation = {'actor_name': correction.actor_name, 'at': correction.created_at.isoformat()} if correction else None
    file_info = db.get(DocumentFileInfo, doc.document_id)
    expected_sha = file_info.sha256 if file_info else None
    doc = SimpleNamespace(document_id=doc.document_id, document_type=doc.document_type, file_name=doc.file_name, storage_path=doc.storage_path, masking=SimpleNamespace(masked_file_path=doc.masking.masked_file_path) if doc.masking else None)
    db.rollback()
    path = resolve_path(doc.storage_path)
    text_only = bool(path and Path(path).suffix.lower() in {'.txt', '.md', '.json', '.csv'})
    raw, _ = read_texts(doc)
    pages = []
    source_error = None
    version_verified = False
    if path and raw:
        try:
            if expected_sha:
                with path.open('rb') as stream:
                    version_verified = hashlib.file_digest(stream, 'sha256').hexdigest() == expected_sha
                if not version_verified:
                    source_error = 'ORIGINAL_VERSION_CHANGED'
            if not source_error:
                pages = source_pages(path, raw)
        except Exception:
            source_error = 'SOURCE_LOCATION_UNAVAILABLE'
    else:
        source_error = 'ORIGINAL_OR_TEXT_UNAVAILABLE'
    results = {}
    for key, value in values.items():
        decision = decisions.get(key)
        derived = decisions.get('total_amount') if key in {'amount', 'amount_basis'} else None
        applied = bool((decision or derived or {}).get('applied'))
        origin = 'AI_SUPPLEMENT' if applied else 'RULE'
        source = 'HUMAN_CONFIRMATION' if manual else origin if value not in (None, 'UNKNOWN', '') else 'UNAVAILABLE'
        anchors = []
        lookup = 'total_amount' if key == 'amount' else key
        options = candidates(pages, lookup, doc.document_type) if lookup in {'company_name', 'business_registration_no', 'supply_amount', 'tax_amount', 'total_amount', 'issue_date', 'amount_scope'} else []
        token = canonical(lookup, value)
        matching = [o for o in options if token is not None and o['value'] == token and (o.get('party') != 'buyer')]
        for option in matching:
            page = next((p for p in pages if p['page'] == option['page']))
            quote = page['text'].splitlines()[option['line'] - 1]
            anchor = display_anchor(page, option['line'], quote, text_only)
            if anchor:
                anchor.update(document_id=doc.document_id, field=key, label=option['label'], party=option['party'], text_verified=True)
                anchors.append(anchor)
        proposal_token = canonical(lookup, (decision or {}).get('proposal', {}).get('value'))
        if not anchors and (not manual) and pages and (token is not None) and (token == proposal_token) and decision and decision.get('applied') and decision.get('anchor'):
            stored_anchor = decision['anchor']
            page = next((p for p in pages if p['page'] == stored_anchor.get('page')), None)
            verified = display_anchor(page, stored_anchor.get('line'), stored_anchor.get('quote'), text_only) if page else None
            if verified:
                anchors = [{**verified, 'document_id': doc.document_id, 'field': key}]
        results[key] = {'value': value, 'source': source, 'source_label': SOURCE_NAMES[source], 'original_source': origin, 'human_confirmation': confirmation, 'evidence': anchors, 'evidence_status': 'AMBIGUOUS' if len(anchors) > 1 else 'AVAILABLE' if anchors else 'UNAVAILABLE', 'evidence_error': None if anchors else source_error or 'SOURCE_LABEL_OR_VALUE_NOT_FOUND', 'ai_decision': decision or derived}
    anchors = [anchor for field in results.values() for anchor in field['evidence']]
    if path and version_verified:
        attach_coordinates(path, anchors, expected_sha)
    else:
        for anchor in anchors:
            anchor.update(bbox=None, bboxes=[], coordinate_space='preview_image_normalized_top_left',
                          source_sha256=expected_sha, coordinate_method=None)
    return {'document_id': doc.document_id, 'file_name': doc.file_name, 'source_version_verified': version_verified, 'source_sha256': expected_sha, 'fields': results, 'ai_review': ai or None}

def review_context(db, contract_id):
    detail = ContractService().get_contract_detail(db, contract_id)
    if not detail:
        return None
    from ..db.models import Contract
    contract = db.get(Contract, contract_id)
    current_docs = active_documents(contract)
    documents = [document_provenance(db, d) for d in current_docs]
    by_id = {str(d['document_id']): d for d in documents}
    keys = {'BUSINESS_NO_MATCH': ['business_registration_no'], 'AMOUNT_COMPONENTS': ['supply_amount', 'tax_amount', 'total_amount'], 'AMOUNT_EXTRACTION': ['supply_amount', 'tax_amount', 'total_amount', 'amount'], 'AMOUNT_MATCH_ESTIMATE': ['total_amount', 'amount'], 'AMOUNT_MATCH_TAX_INVOICE': ['total_amount', 'amount_scope'], 'PAYMENT_SCOPE': ['amount_scope', 'total_amount'], 'INSTALLMENT_TOTAL': ['total_amount', 'amount_scope']}
    checks = []
    for check in detail.checks:
        targets = [by_id[check.field]] if check.field in by_id else [by_id[str(d.document_id)] for d in current_docs if d.document_type == 'tax_invoice'] if check.rule_id in {'INSTALLMENT_TOTAL', 'PAYMENT_SCOPE'} else []
        evidence = [a for doc in targets for field in keys.get(check.rule_id, []) for a in doc['fields'][field]['evidence']]
        checks.append({**check.model_dump(mode='json'), 'reason': check.message, 'evidence': evidence, 'evidence_status': 'AVAILABLE' if evidence else 'UNAVAILABLE' if targets else 'NOT_APPLICABLE'})
    requests = db.query(ResubmissionRequest).filter_by(contract_id=contract_id).order_by(ResubmissionRequest.request_id.desc()).all()
    waiting = sum((r.status == 'WAITING_RESPONSE' for r in requests))
    summary = detail.summary
    approval = approval_state(db, contract_id, detail.workflow['revision'], detail.workflow['fingerprint'])
    ai_pending = pending_ai_count(d['ai_review'] for d in documents)
    action_summary = build_action_summary(display_issue_counts(detail.checks), detail.workflow, approval, waiting, ai_pending)
    return {'contract_id': contract_id, 'revision': detail.workflow['revision'], 'fingerprint': detail.workflow['fingerprint'], 'action_summary': action_summary, 'summary': summary.model_dump(), 'checks': checks, 'documents': documents, 'workflow': detail.workflow, 'follow_up': {'status': 'WAITING_RESPONSE' if waiting else 'NO_PENDING_REQUEST', 'waiting_count': waiting, 'requests': [request_response(r) for r in requests]}, 'approval': approval}
