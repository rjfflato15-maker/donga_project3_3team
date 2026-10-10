"""Keep shared review behavior out of HTTP routers without changing its contract."""
import ast
import inspect
import json
from pathlib import Path

import pytest

from backend.app.api import documents, pilot, vlm_reread, workflow
from backend.app.db.models import AuditEvent, ContractReview, EmailVerification
from backend.app.schemas.document import Correction
from backend.app.schemas.review import ReviewRequest
from backend.app.services import contract_review_service, document_correction_service
from test_review_workflow_api import configured_contract


@pytest.mark.parametrize('module', [
    workflow, vlm_reread, contract_review_service, document_correction_service,
])
def test_shared_review_modules_do_not_import_http_routers(module):
    tree = ast.parse(inspect.getsource(module))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module not in {'pilot', 'documents'}
            assert 'api' not in (node.module or '').split('.')
        elif isinstance(node, ast.Import):
            assert all('api' not in alias.name.split('.') for alias in node.names)


def test_moved_schemas_and_correction_helper_keep_existing_import_aliases():
    assert pilot.ReviewRequest is workflow.ReviewRequest is ReviewRequest
    assert documents.Correction is vlm_reread.Correction is Correction
    assert documents.apply_correction is vlm_reread.apply_correction is document_correction_service.apply_correction
    assert documents.pipeline_service is document_correction_service.pipeline_service
    assert Correction(fields={'total_amount': None}, document_type='estimate',
                      revision=1, note='clear unreadable total').fields.model_dump(exclude_unset=True) == {'total_amount': None}


@pytest.mark.parametrize('entrypoint', ['reviews', 'approvals'])
def test_final_review_entrypoints_keep_snapshot_audit_and_publication_order(
        operator_client, separate_client, db_factory, monkeypatch, entrypoint):
    representative, cid, body = configured_contract(operator_client, separate_client)
    first = operator_client.post(f'/api/pilot/contracts/{cid}/approvals', json={**body, 'step': 1})
    assert first.status_code == 200, first.text

    events = []
    original_lock = contract_review_service.STORAGE_LOCK
    original_detail = contract_review_service.ContractService.get_contract_detail
    original_audit = contract_review_service.audit

    class ReviewLock:
        def __enter__(self):
            original_lock.acquire()
            events.append('lock')

        def __exit__(self, *args):
            events.append('unlock')
            original_lock.release()

    def detail(service, db, contract_id):
        events.append('detail')
        return original_detail(service, db, contract_id)

    def audit(db, *args, **kwargs):
        events.append('audit')
        # The review is already committed before the separately committed audit.
        with db_factory() as observer:
            assert observer.query(ContractReview).filter_by(contract_id=cid).count() == 1
        return original_audit(db, *args, **kwargs)

    monkeypatch.setattr(contract_review_service, 'STORAGE_LOCK', ReviewLock())
    monkeypatch.setattr(contract_review_service.ContractService, 'get_contract_detail', detail)
    monkeypatch.setattr(contract_review_service, 'audit', audit)
    if entrypoint == 'reviews':
        response = representative.post(f'/api/contracts/{cid}/reviews', json=body)
    else:
        response = representative.post(f'/api/pilot/contracts/{cid}/approvals', json={**body, 'step': 2})
    assert response.status_code == 200, response.text
    assert events == ['detail', 'lock', 'audit', 'unlock', 'detail']
    result = response.json()
    assert result['workflow']['approval_status'] == 'CONFIRMED'
    assert result['workflow']['revision'] == body['revision']
    assert result['workflow']['fingerprint'] == body['fingerprint']
    with db_factory() as db:
        review = db.query(ContractReview).filter_by(contract_id=cid).one()
        snapshot = json.loads(review.snapshot_json)
        assert review.note == body['note']
        assert review.revision == body['revision']
        assert snapshot['fingerprint'] == body['fingerprint']
        assert snapshot['summary'] == result['summary']
        assert snapshot['checks'] == result['checks']
        assert len(snapshot['documents']) == len(result['documents']) == 1
        event = db.query(AuditEvent).filter_by(contract_id=cid, action='REPRESENTATIVE_CONFIRMED').one()
        assert event.actor_id == review.actor_id
        assert json.loads(event.details) == {
            'revision': body['revision'], 'fingerprint': body['fingerprint'],
            'review_id': review.review_id, 'note': body['note'],
        }


@pytest.mark.parametrize('endpoint', [
    'send-verification-code', 'send-code', 'verify-code', 'change-password',
])
def test_retired_email_reset_routes_and_legacy_table_remain(client, db_factory, endpoint):
    response = client.post(f'/api/auth/{endpoint}')
    assert response.status_code == 410
    assert response.json() == {
        'detail': '사내망에서는 로그인 후 비밀번호를 변경하거나 대표에게 초기화를 요청하세요.',
    }
    with db_factory() as db:
        assert db.query(EmailVerification).count() == 0
    services_dir = Path(document_correction_service.__file__).parent
    assert not (services_dir / 'auth_service.py').exists()
    assert not (services_dir / 'email_service.py').exists()
