"""Keep original, extracted-text and masked paths distinct after storage moves."""
import pytest

from backend.app.db.models import Document
from backend.app.services import storage_service
from test_api import create_contract, text_files


@pytest.fixture
def relocated_storage(tmp_path, monkeypatch):
    root = tmp_path / 'restored-company'
    root.mkdir()
    project = tmp_path / 'project'
    monkeypatch.setattr(storage_service, 'STORAGE_DIR', root)
    monkeypatch.setattr(storage_service, 'PROJECT_ROOT', project)
    return root, project / 'storage'


@pytest.mark.parametrize('namespace', ['raw', 'masked', 'text'])
@pytest.mark.parametrize('legacy', [False, True])
def test_missing_path_never_uses_another_namespace(namespace, legacy, relocated_storage):
    root, old_root = relocated_storage
    for alternative in {'raw', 'masked', 'text'} - {namespace}:
        for storage in (root, old_root):
            substitute = storage / alternative / 'shared.txt'
            substitute.parent.mkdir(parents=True, exist_ok=True)
            substitute.write_text('wrong namespace', encoding='utf-8')
    key = (rf'Z:\old-company\storage\{namespace}\7\shared.txt'
           if legacy else f'{namespace}/7/shared.txt')
    assert storage_service.resolve_path(key) is None


@pytest.mark.parametrize('namespace', ['raw', 'masked', 'text'])
def test_windows_legacy_path_resolves_same_namespace_after_restore(namespace, relocated_storage):
    root, _ = relocated_storage
    original = root / namespace / '7' / 'shared.txt'
    original.parent.mkdir(parents=True)
    original.write_text('restored namespace content', encoding='utf-8')
    key = rf'Z:\old-company\storage\{namespace}\7\shared.txt'
    assert storage_service.resolve_path(key) == original.resolve()


@pytest.mark.parametrize('namespace', ['raw', 'masked'])
def test_legacy_flat_layout_in_same_namespace_remains_supported(namespace, relocated_storage):
    root, _ = relocated_storage
    original = root / namespace / 'shared.txt'
    original.parent.mkdir(parents=True)
    original.write_text('legacy flat content', encoding='utf-8')
    key = rf'Z:\old-company\storage\{namespace}\shared.txt'
    assert storage_service.resolve_path(key) == original.resolve()


def test_missing_txt_original_invalidates_approval_and_cannot_download_masked_copy(
        operator_client, separate_client, db_factory):
    representative = separate_client()
    response = representative.put('/api/pilot/settings', json={
        'company_name': '원본 유실 저장소 회귀 테스트', 'required_document_types': ['contract']})
    assert response.status_code == 200, response.text
    cid = create_contract(operator_client)['contract_id']
    response = operator_client.post(f'/api/contracts/{cid}/documents', files=text_files()[:1])
    assert response.status_code == 200, response.text
    did = response.json()[0]['document_id']
    detail = operator_client.get(f'/api/contracts/{cid}').json()
    review = {'decision': 'CONFIRMED', 'note': '원문 확인 및 국세청 미조회 범위를 확인한 저장소 회귀 테스트',
              'revision': detail['workflow']['revision'], 'fingerprint': detail['workflow']['fingerprint'],
              'acknowledge_unverified': True}
    response = representative.post(f'/api/contracts/{cid}/reviews', json=review)
    assert response.status_code == 200, response.text
    assert response.json()['workflow']['approval_status'] == 'CONFIRMED'
    with db_factory() as db:
        doc = db.get(Document, did)
        original = storage_service.resolve_path(doc.storage_path)
        masked = storage_service.resolve_path(doc.masking.masked_file_path)
        assert original.name == masked.name and original != masked
        original.unlink()
        assert masked.is_file(), 'The privacy sidecar still exists when the original is lost.'
    response = operator_client.get(f'/api/contracts/{cid}')
    assert response.status_code == 200, response.text
    missing = response.json()
    assert missing['documents'][0]['file_available'] is False
    assert missing['workflow']['fingerprint'] != detail['workflow']['fingerprint']
    assert missing['workflow']['approval_status'] == 'STALE'
    listed = next(c for c in operator_client.get('/api/contracts').json() if c['contract_id'] == cid)
    assert listed['missing_original_count'] == 1
    for endpoint in ('download', 'file', 'text-preview'):
        response = operator_client.get(f'/api/documents/{did}/{endpoint}', params={'masked': False})
        assert response.status_code == 404, (endpoint, response.text)
    assert representative.post(f'/api/contracts/{cid}/reviews', json=review).status_code == 409
    review.update(revision=missing['workflow']['revision'], fingerprint=missing['workflow']['fingerprint'])
    assert representative.post(f'/api/contracts/{cid}/reviews', json=review).status_code == 400
