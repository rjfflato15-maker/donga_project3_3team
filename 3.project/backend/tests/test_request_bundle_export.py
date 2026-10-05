"""Structured request history survives export and restore of disposable data."""
import copy
import hashlib
import io
import json
import sqlite3
import zipfile
from contextlib import closing
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from backend.app.db.database import Base
from backend.app.db.models import (Document, DocumentFileInfo, DocumentVersion,
    RequestBundle, RequestBundleItem, ResubmissionRequest)
from backend.app.services import backup_service
from test_api import create_contract
from test_document_versions import reissue
from test_review_workflow_api import upload


VENDOR = '가상 검증업체'
BUSINESS_NO = '220-88-12345'
BUSINESS_DIGITS = '2208812345'
PARTIAL_COUNTS = {'waiting': 1, 'received': 1, 'cancelled': 0, 'total': 2}


@pytest.fixture
def partial_bundle(operator_client, db_factory):
    cid = create_contract(operator_client, vendor_name=VENDOR, contract_amount=220)['contract_id']
    old = upload(operator_client, cid, 'estimate')
    old_id = old['document_id']
    workflow = operator_client.get(f'/api/contracts/{cid}').json()['workflow']
    issue_key = f"document:{old['version']['logical_document_id']}"
    created = operator_client.post(f'/api/pilot/contracts/{cid}/resubmission-bundles', json={
        'revision': workflow['revision'], 'fingerprint': workflow['fingerprint'],
        'idempotency_key': 'request-bundle-export-unit', 'contact_method': 'KAKAO',
        'requested_on': '2026-10-05', 'due_on': '2026-10-08',
        'memo': f'{VENDOR}의 견적 정정과 통장사본 요청 기록',
        'items': [{'issue_key': issue_key, 'reviewed_original': True},
                  {'issue_key': 'missing:bank_account', 'reviewed_original': False}],
    })
    assert created.status_code == 201, created.text
    request = created.json()
    rid = request['request_id']
    item = next(item for item in request['bundle']['items'] if item['issue_key'] == issue_key)
    snapshot = copy.deepcopy(item['snapshot'])
    assert snapshot['document']['document_id'] == old_id
    assert snapshot['document']['version']['version_number'] == 1
    assert snapshot['document']['source_version_verified'] is True
    assert any(check['status'] == 'FAIL' for check in snapshot['checks'])
    resolved = operator_client.patch(f'/api/pilot/contracts/{cid}/resubmission-bundles/{rid}/items', json={
        'revision': workflow['revision'], 'fingerprint': workflow['fingerprint'],
        'request_revision': request['bundle']['request_revision'],
        'items': [{'item_id': item['item_id'], 'status': 'RECEIVED',
                   'note': f'{VENDOR} {BUSINESS_DIGITS} 정정 견적서 합계 220원 회신 확인'}],
    })
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()['status'] == 'WAITING_RESPONSE'
    assert resolved.json()['bundle']['counts'] == PARTIAL_COUNTS
    replacement = reissue(operator_client, cid, old_id, workflow['revision'],
        text=f'견적서\n상호: {VENDOR}\n사업자등록번호: {BUSINESS_NO}\n'
             '공급가액: 200원\n세액: 20원\n합계금액: 220원\n전액 청구',
        target_document_type='estimate')
    assert replacement.status_code == 200, replacement.text
    new_id = replacement.json()[0]['document_id']
    current = operator_client.get(f'/api/pilot/contracts/{cid}/resubmission-requests')
    assert current.status_code == 200, current.text
    request = next(row for row in current.json() if row['request_id'] == rid)
    assert next(row for row in request['bundle']['items'] if row['item_id'] == item['item_id'])['snapshot'] == snapshot
    with db_factory() as db:
        source_db = Path(db.get_bind().url.database)
    return {'cid': cid, 'rid': rid, 'old_id': old_id, 'new_id': new_id,
            'item_id': item['item_id'], 'snapshot': snapshot, 'workflow': workflow,
            'request': request, 'source_db': source_db}


def export_metadata(client, case, masked):
    revision = client.get(f"/api/contracts/{case['cid']}").json()['workflow']['revision']
    response = client.get(f"/api/contracts/{case['cid']}/export",
        params={'masked': masked, 'revision': revision})
    assert response.status_code == 200, response.text
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert archive.testzip() is None
        return {name: json.loads(archive.read(name)) for name in ('history.json', 'manifest.json', 'contract.json')}


def exported_request(metadata, case):
    return next(row for row in metadata['history.json']['requests'] if row['request_id'] == case['rid'])


def test_unmasked_zip_keeps_partial_request_and_original_document_snapshot(operator_client, partial_bundle):
    case = partial_bundle
    metadata = export_metadata(operator_client, case, masked=False)
    request = exported_request(metadata, case)
    expected = {key: value for key, value in case['request']['bundle'].items() if key != 'idempotency_key'}
    assert request['status'] == 'WAITING_RESPONSE'
    assert request['resolved_at'] is None
    assert request['bundle'] == expected
    assert request['bundle']['request_revision'] == 2
    assert request['bundle']['contract_revision'] == case['workflow']['revision']
    assert request['bundle']['contract_fingerprint'] == case['workflow']['fingerprint']
    assert metadata['contract.json']['revision'] > request['bundle']['contract_revision']
    assert 'idempotency_key' not in request['bundle']
    assert request['bundle']['counts'] == PARTIAL_COUNTS
    item = next(row for row in request['bundle']['items'] if row['item_id'] == case['item_id'])
    assert item['snapshot'] == case['snapshot']
    assert item['document_id'] == case['old_id'] and item['status'] == 'RECEIVED'
    documents = {row['document_id']: row for row in metadata['manifest.json']['documents']}
    assert documents[case['old_id']]['is_current'] is False
    assert documents[case['old_id']]['entry'].startswith('documents/previous/')
    assert documents[case['new_id']]['is_current'] is True
    assert documents[case['new_id']]['version_number'] == 2
    assert documents[case['new_id']]['entry'].startswith('documents/current/')
    assert documents[case['old_id']]['source_sha256'] == case['snapshot']['document']['source_sha256']


def test_masked_zip_masks_item_titles_reasons_receipt_notes_and_preserves_money(operator_client, db_factory, partial_bundle):
    case = partial_bundle
    # Persisted history can contain identifiers even when today's generated
    # candidate title is short. Exercise all three public free-text fields.
    with db_factory() as db:
        item = db.get(RequestBundleItem, case['item_id'])
        item.title = f'{VENDOR} {BUSINESS_NO} 견적서 220원'
        item.reason = f'{VENDOR} 사업자번호 {BUSINESS_NO} 견적 합계 110원, 계약 기준 220원'
        db.commit()
    original = exported_request(export_metadata(operator_client, case, masked=False), case)
    masked_metadata = export_metadata(operator_client, case, masked=True)
    masked = exported_request(masked_metadata, case)
    original_item = next(row for row in original['bundle']['items'] if row['item_id'] == case['item_id'])
    masked_item = next(row for row in masked['bundle']['items'] if row['item_id'] == case['item_id'])
    for key in ('title', 'reason', 'resolution_note'):
        assert VENDOR in original_item[key]
        assert BUSINESS_NO in original_item[key] or BUSINESS_DIGITS in original_item[key]
        assert VENDOR not in masked_item[key]
        assert BUSINESS_NO not in masked_item[key] and BUSINESS_DIGITS not in masked_item[key]
        assert '220원' in masked_item[key]
    assert '110원' in masked_item['reason']
    assert masked_item['snapshot']['document']['source_sha256'] == case['snapshot']['document']['source_sha256']
    assert masked['bundle']['contract_fingerprint'] == case['workflow']['fingerprint']
    assert masked['bundle']['request_revision'] == 2
    assert masked['bundle']['counts'] == PARTIAL_COUNTS
    assert masked_item['status'] == 'RECEIVED'
    all_metadata = json.dumps(masked_metadata, ensure_ascii=False)
    assert VENDOR not in all_metadata
    assert BUSINESS_NO not in all_metadata and BUSINESS_DIGITS not in all_metadata


def rows_for_request(db, case):
    selections = {
        'request': db.query(ResubmissionRequest).filter_by(request_id=case['rid']).all(),
        'bundle': db.query(RequestBundle).filter_by(request_id=case['rid']).all(),
        'items': db.query(RequestBundleItem).filter_by(request_id=case['rid']).order_by(RequestBundleItem.item_id).all(),
        'versions': db.query(DocumentVersion).filter(DocumentVersion.document_id.in_([case['old_id'], case['new_id']])).order_by(DocumentVersion.document_id).all(),
    }
    return {key: [{column.name: getattr(row, column.name) for column in row.__table__.columns}
                  for row in rows] for key, rows in selections.items()}


def test_backup_restore_keeps_partial_bundle_and_document_version_snapshot(operator_client, db_factory, partial_bundle, tmp_path):
    import manage_pilot as pilot
    case = partial_bundle
    with db_factory() as db:
        expected = rows_for_request(db, case)
        originals = {doc.document_id: (doc.storage_path, info.sha256)
            for doc, info in db.query(Document, DocumentFileInfo).join(DocumentFileInfo)
            .filter(Document.contract_id == case['cid']).all()}
    # The API fixture uses test.db. Publish its SQLite snapshot under the normal
    # backup filename inside the same disposable storage root, never a live DB.
    source_root = case['source_db'].parent
    with closing(sqlite3.connect(str(case['source_db']))) as source, closing(sqlite3.connect(str(source_root / 'pilot.db'))) as target:
        source.backup(target)
    archive = tmp_path / 'request-bundle-backup.zip'
    backup_service.create_backup(archive)
    destination = tmp_path / 'restored-request-bundle'
    pilot.restore(archive, destination)
    engine = create_engine('sqlite:///' + str(destination / 'pilot.db'))
    try:
        # Normal startup loads the complete registry; adding newer tables must
        # preserve the backed-up request/version records instead of rebuilding.
        Base.metadata.create_all(engine)
        assert set(Base.metadata.tables) <= set(inspect(engine).get_table_names())
        with Session(engine) as db:
            assert rows_for_request(db, case) == expected
            request = db.get(ResubmissionRequest, case['rid'])
            assert request.status == 'WAITING_RESPONSE' and request.resolved_at is None
            assert request.bundle.request_revision == 2
            assert sorted(item.status for item in request.bundle.items) == ['RECEIVED', 'WAITING_RESPONSE']
            assert json.loads(db.get(RequestBundleItem, case['item_id']).snapshot_json) == case['snapshot']
            assert db.get(DocumentVersion, case['old_id']).is_current is False
            current = db.get(DocumentVersion, case['new_id'])
            assert current.is_current is True and current.version_number == 2
            assert current.previous_document_id == case['old_id']
        assert len(originals) == 2
        for path, digest in originals.values():
            restored = destination / path
            assert restored.is_file()
            assert restored.read_bytes() == (source_root / path).read_bytes()
            assert hashlib.sha256(restored.read_bytes()).hexdigest() == digest
        with closing(sqlite3.connect(str(destination / 'pilot.db'))) as db:
            assert db.execute('PRAGMA foreign_key_check').fetchall() == []
            assert db.execute('SELECT count(*) FROM pilot_auth_sessions').fetchone()[0] == 0
    finally:
        engine.dispose()
