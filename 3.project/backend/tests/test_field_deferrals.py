import json
from backend.app.db.models import Document, DocumentFileInfo
from test_field_confirmation_undo import setup_doc, confirm


def defer(client, did, revision, field='total_amount', note='계약 담당자에게 금액 확인'):
    return client.post(f'/api/documents/{did}/defer-field', json={'field': field, 'revision': revision, 'note': note})


def test_deferral_survives_reads_without_confirming_values_or_changing_revision(operator_client):
    cid, did, revision = setup_doc(operator_client)
    before = operator_client.get(f'/api/contracts/{cid}').json()
    result = defer(operator_client, did, revision)
    assert result.status_code == 200, result.text
    for _ in range(2):
        proof = operator_client.get(f'/api/documents/{did}/provenance').json()
        assert proof['deferrals']['total_amount']['note'] == '계약 담당자에게 금액 확인'
        assert proof['fields']['total_amount']['human_confirmation'] is None
    after = operator_client.get(f'/api/contracts/{cid}').json()
    assert after['workflow']['revision'] == before['workflow']['revision']
    assert after['documents'][0]['analysis']['fields'] == before['documents'][0]['analysis']['fields']


def test_deferral_requires_operator_valid_field_note_and_live_revision(operator_client, separate_client):
    _, did, revision = setup_doc(operator_client)
    assert defer(separate_client('representative'), did, revision).status_code == 403
    assert defer(operator_client, did, revision - 1).status_code == 409
    assert defer(operator_client, did, revision, field='not_a_field').status_code == 422
    assert defer(operator_client, did, revision, note='  ').status_code == 422
    assert defer(operator_client, did, revision, field='__document__').status_code == 200


def test_confirmation_resolves_its_deferral_but_not_other_fields(operator_client):
    _, did, revision = setup_doc(operator_client)
    assert defer(operator_client, did, revision).status_code == 200
    assert defer(operator_client, did, revision, field='supply_amount').status_code == 200
    assert confirm(operator_client, did, revision).status_code == 200
    pending = operator_client.get(f'/api/documents/{did}/provenance').json()['deferrals']
    assert 'total_amount' not in pending and 'supply_amount' in pending


def test_clear_checks_latest_deferral_and_source_change_invalidates_note(operator_client, db_factory):
    _, did, revision = setup_doc(operator_client)
    old = defer(operator_client, did, revision).json()['deferral']
    latest = defer(operator_client, did, revision, note='수정된 확인 사유').json()['deferral']
    body = {'field': 'total_amount', 'revision': revision, 'deferred_at': old['at']}
    assert operator_client.post(f'/api/documents/{did}/clear-field-deferral', json=body).status_code == 409
    body['deferred_at'] = latest['at']
    assert operator_client.post(f'/api/documents/{did}/clear-field-deferral', json=body).status_code == 200
    assert not operator_client.get(f'/api/documents/{did}/provenance').json()['deferrals']
    assert defer(operator_client, did, revision).status_code == 200
    with db_factory() as db:
        db.get(DocumentFileInfo, did).sha256 = 'changed-source'
        db.commit()
    assert not operator_client.get(f'/api/documents/{did}/provenance').json()['deferrals']


def test_no_issue_judgement_is_separate_from_deferral_and_keeps_values(operator_client):
    cid, did, revision = setup_doc(operator_client)
    before = operator_client.get(f'/api/contracts/{cid}').json()
    body = {'field': 'total_amount', 'revision': revision, 'note': '잔금 문구지만 일시 지급 합의 확인', 'kind': 'NO_ISSUE'}
    assert operator_client.post(f'/api/documents/{did}/defer-field', json={**body, 'note': ' '}).status_code == 422
    assert operator_client.post(f'/api/documents/{did}/defer-field', json={**body, 'kind': 'APPROVE'}).status_code == 422
    result = operator_client.post(f'/api/documents/{did}/defer-field', json=body)
    assert result.status_code == 200, result.text
    proof = operator_client.get(f'/api/documents/{did}/provenance').json()
    assert 'total_amount' not in proof['deferrals']
    assert proof['no_issue']['total_amount']['note'] == '잔금 문구지만 일시 지급 합의 확인'
    after = operator_client.get(f'/api/contracts/{cid}').json()
    assert after['checks'] == before['checks'] and after['workflow']['revision'] == before['workflow']['revision']
    clear = {'field': 'total_amount', 'revision': revision, 'deferred_at': proof['no_issue']['total_amount']['at']}
    assert operator_client.post(f'/api/documents/{did}/clear-field-deferral', json=clear).status_code == 200
    assert not operator_client.get(f'/api/documents/{did}/provenance').json()['no_issue']
