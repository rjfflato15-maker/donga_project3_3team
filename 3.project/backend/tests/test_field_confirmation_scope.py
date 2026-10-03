import json

from backend.app.db.models import Document, AuditEvent
from test_api import create_contract
from test_review_workflow_api import upload


def correct(client, cid, did, *, changes=None, confirmed=None):
    fields = client.get(f'/api/documents/{did}').json()['analysis']['fields']
    fields.update(changes or {})
    revision = client.get(f'/api/contracts/{cid}').json()['workflow']['revision']
    body = {'fields': fields, 'document_type': 'estimate', 'revision': revision, 'note': 'unit fixture field-scoped review'}
    if confirmed is not None:
        body['confirmed_fields'] = confirmed
    return client.put(f'/api/documents/{did}/fields', json=body)


def test_partial_correction_does_not_confirm_unchanged_ai_and_explicit_review_can_finish_it(operator_client, db_factory):
    cid = create_contract(operator_client)['contract_id']
    did = upload(operator_client, cid, 'estimate')['document_id']
    with db_factory() as db:
        doc = db.get(Document, did)
        stored = json.loads(doc.extract.raw_fields)
        stored.update(company_name='UNIT-FIXTURE', total_amount=110)
        stored['ai_review'] = {'status': 'COMPLETED', 'targets': ['company_name', 'total_amount'],
            'manual_review_required': True, 'human_confirmed': False, 'decisions': [
                {'field': 'company_name', 'applied': True, 'proposal': {'state': 'VALUE', 'value': 'UNIT-FIXTURE'}}]}
        doc.extract.raw_fields = json.dumps(stored)
        db.commit()
    response = correct(operator_client, cid, did, changes={'total_amount': 121})
    assert response.status_code == 200, response.text
    ai = response.json()['analysis']['ai_review']
    assert ai['human_confirmed'] is False and ai['manual_review_required'] is True
    assert ai['human_unconfirmed_fields'] == ['company_name']
    result = operator_client.get(f'/api/documents/{did}/provenance').json()
    assert result['human_confirmed_fields'] == ['total_amount']
    assert result['fields']['total_amount']['source'] == 'HUMAN_CONFIRMATION'
    assert result['fields']['company_name']['source'] == 'AI_SUPPLEMENT'
    assert result['fields']['company_name']['human_confirmation'] is None
    total_proof = result['fields']['total_amount']['human_confirmation']
    response = correct(operator_client, cid, did, confirmed=['company_name'])
    assert response.status_code == 200, response.text
    assert response.json()['analysis']['ai_review']['human_confirmed'] is True
    result = operator_client.get(f'/api/documents/{did}/provenance').json()
    assert result['human_confirmed_fields'] == ['company_name', 'total_amount']
    assert result['fields']['total_amount']['human_confirmation'] == total_proof
    assert result['fields']['company_name']['human_confirmation']['method'] == 'EXPLICIT_CONFIRMATION'


def test_full_unchanged_body_does_not_imply_review_and_unknown_confirmation_scope_is_rejected(operator_client):
    cid = create_contract(operator_client)['contract_id']
    did = upload(operator_client, cid, 'estimate')['document_id']
    response = correct(operator_client, cid, did)
    assert response.status_code == 200
    result = operator_client.get(f'/api/documents/{did}/provenance').json()
    assert result['human_confirmed_fields'] == []
    assert all(field['source'] != 'HUMAN_CONFIRMATION' for field in result['fields'].values())
    revision = operator_client.get(f'/api/contracts/{cid}').json()['workflow']['revision']
    assert correct(operator_client, cid, did, confirmed=['not_a_field']).status_code == 400
    assert operator_client.get(f'/api/contracts/{cid}').json()['workflow']['revision'] == revision


def test_legacy_save_recovers_changed_fields_without_claiming_full_review(operator_client, db_factory):
    cid = create_contract(operator_client)['contract_id']
    did = upload(operator_client, cid, 'estimate')['document_id']
    with db_factory() as db:
        doc = db.get(Document, did)
        before = json.loads(doc.extract.raw_fields)
        before.update(company_name='UNIT-FIXTURE', total_amount=110)
        after = {**before, 'total_amount': 121}
        doc.extract.raw_fields = json.dumps(after)
        doc.extract.extracted_status = 'MANUALLY_CONFIRMED'
        db.add(AuditEvent(document_id=did, contract_id=cid, actor_name='unit legacy reviewer', action='EXTRACT_CORRECTED',
            details=json.dumps({'before': before, 'after': after})))
        db.commit()
    result = operator_client.get(f'/api/documents/{did}/provenance').json()
    assert result['legacy_confirmation_scope_unknown'] is True
    assert result['human_confirmed_fields'] == ['total_amount']
    assert result['fields']['company_name']['source'] == 'RULE'
    assert result['fields']['total_amount']['human_confirmation']['method'] == 'LEGACY_CHANGED_VALUE'
