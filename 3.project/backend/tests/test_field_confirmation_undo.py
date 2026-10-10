"""One-click confirmation is scoped, reversible, revision-safe, and audited."""
import json
from datetime import datetime, timedelta, timezone
from backend.app.db.models import Document, AuditEvent, User, UserProfile
from conftest import TEST_PASSWORD
from test_api import create_contract
from test_review_workflow_api import upload, configured_contract


def setup_doc(client):
    cid = create_contract(client)['contract_id']
    doc = upload(client, cid)
    revision = client.get(f'/api/contracts/{cid}').json()['workflow']['revision']
    return cid, doc['document_id'], revision


def confirm(client, did, revision, field='total_amount'):
    return client.post(f'/api/documents/{did}/confirm-field', json={'revision': revision, 'field': field})


def undo(client, did, proof):
    return client.post(f'/api/documents/{did}/undo-field-confirmation', json=proof)


def test_confirm_and_undo_keep_values_other_proofs_and_audit(operator_client, db_factory):
    cid, did, revision = setup_doc(operator_client)
    before = operator_client.get(f'/api/documents/{did}').json()['analysis']['fields']
    first = confirm(operator_client, did, revision, 'supply_amount')
    assert first.status_code == 200, first.text
    saved = confirm(operator_client, did, revision + 1)
    assert saved.status_code == 200, saved.text
    assert undo(operator_client, did, saved.json()).status_code == 200
    after = operator_client.get(f'/api/documents/{did}').json()['analysis']['fields']
    assert after == before
    provenance = operator_client.get(f'/api/documents/{did}/provenance').json()
    assert provenance['fields']['total_amount']['human_confirmation'] is None
    assert provenance['fields']['supply_amount']['human_confirmation']
    assert operator_client.get(f'/api/contracts/{cid}').json()['workflow']['revision'] == revision + 3
    with db_factory() as db:
        assert db.query(AuditEvent).filter_by(action='EXTRACT_CORRECTED').count() == 2
        event = db.query(AuditEvent).filter_by(action='FIELD_CONFIRMATION_UNDONE').one()
        assert json.loads(event.details)['field'] == 'total_amount'
    assert undo(operator_client, did, saved.json()).status_code == 409


def test_old_revision_other_actor_or_later_edit_cannot_be_undone(operator_client, separate_client, db_factory, password_hash):
    _, did, revision = setup_doc(operator_client)
    proof = confirm(operator_client, did, revision).json()
    with db_factory() as db:
        other = User(email='other-operator@tests.local', password=password_hash)
        db.add(other)
        db.flush()
        db.add(UserProfile(user_id=other.user_id, role='operator', display_name='다른 담당자', active=True, must_change_password=False))
        db.commit()
    other_client = separate_client('operator')
    other_client.post('/api/auth/logout')
    assert other_client.post('/api/auth/login', json={'email': 'other-operator@tests.local', 'password': TEST_PASSWORD}).status_code == 200
    assert undo(other_client, did, proof).status_code == 409
    assert confirm(operator_client, did, revision + 1).status_code == 409
    assert confirm(operator_client, did, revision, 'tax_amount').status_code == 409
    changed = operator_client.put(f'/api/documents/{did}/fields', json={'fields': {'total_amount': 120},
        'document_type': 'contract', 'revision': revision + 1, 'note': '원문 금액 수정', 'confirmed_fields': ['total_amount']})
    assert changed.status_code == 200
    assert undo(operator_client, did, proof).status_code == 409
    assert undo(operator_client, did, {**proof, 'revision': revision + 2}).status_code == 409
    assert operator_client.get(f'/api/documents/{did}').json()['analysis']['fields']['total_amount'] == 120


def test_missing_invalid_and_expired_confirmation_are_rejected(operator_client, db_factory):
    _, did, revision = setup_doc(operator_client)
    for key in ['unknown_field', 'account_number']:
        assert confirm(operator_client, did, revision, key).status_code == 422
    proof = confirm(operator_client, did, revision).json()
    expired = (datetime.now(timezone.utc) - timedelta(seconds=61)).isoformat()
    with db_factory() as db:
        doc = db.get(Document, did)
        stored = json.loads(doc.extract.raw_fields)
        stored['human_review']['field_confirmations']['total_amount']['at'] = expired
        doc.extract.raw_fields = json.dumps(stored)
        db.commit()
    assert undo(operator_client, did, {**proof, 'confirmed_at': expired}).status_code == 409


def test_undo_restores_pending_ai_review_and_never_revives_approval(operator_client, separate_client, db_factory):
    representative, cid, body = configured_contract(operator_client, separate_client)
    assert operator_client.post(f'/api/pilot/contracts/{cid}/approvals', json={**body, 'step': 1}).status_code == 200
    assert representative.post(f'/api/contracts/{cid}/reviews', json=body).status_code == 200
    did = operator_client.get(f'/api/contracts/{cid}').json()['documents'][0]['document_id']
    with db_factory() as db:
        doc = db.get(Document, did)
        stored = json.loads(doc.extract.raw_fields)
        stored['ai_review'] = {'targets': ['total_amount'], 'manual_review_required': True}
        stored['human_review']['field_confirmations'].pop('total_amount', None)
        doc.extract.raw_fields = json.dumps(stored)
        db.commit()
    proof = confirm(operator_client, did, body['revision']).json()
    with db_factory() as db:
        assert json.loads(db.get(Document, did).extract.raw_fields)['ai_review']['human_confirmed'] is True
    assert undo(operator_client, did, proof).status_code == 200
    detail = operator_client.get(f'/api/contracts/{cid}').json()
    assert detail['workflow']['approval_status'] == 'STALE'
    assert len(detail['workflow']['reviews']) == 1
    with db_factory() as db:
        review = json.loads(db.get(Document, did).extract.raw_fields)['ai_review']
        assert review['human_confirmed'] is False and review['human_unconfirmed_fields'] == ['total_amount']


def test_confirmation_requires_operator_and_current_source(operator_client, separate_client, db_factory):
    _, did, revision = setup_doc(operator_client)
    assert confirm(separate_client('representative'), did, revision).status_code == 403
    with db_factory() as db:
        doc = db.get(Document, did)
        doc.storage_path = 'missing-test-source.txt'
        db.commit()
    assert confirm(operator_client, did, revision).status_code == 409


def test_batch_confirmation_records_only_listed_fields_once(operator_client):
    cid, did, revision = setup_doc(operator_client)
    url = f'/api/documents/{did}/confirm-fields'
    assert operator_client.post(url, json={'revision': revision - 1, 'fields': ['total_amount']}).status_code == 409
    assert operator_client.post(url, json={'revision': revision, 'fields': ['total_amount', 'total_amount']}).status_code == 422
    assert operator_client.post(url, json={'revision': revision, 'fields': []}).status_code == 422
    saved = operator_client.post(url, json={'revision': revision, 'fields': ['supply_amount', 'total_amount']})
    assert saved.status_code == 200, saved.text
    assert saved.json()['revision'] == revision + 1
    fields = operator_client.get(f'/api/documents/{did}/provenance').json()['fields']
    assert fields['supply_amount']['human_confirmation'] and fields['total_amount']['human_confirmation']
    assert fields['tax_amount']['human_confirmation'] is None
    again = operator_client.post(url, json={'revision': revision + 1, 'fields': ['total_amount']})
    assert again.status_code == 409
