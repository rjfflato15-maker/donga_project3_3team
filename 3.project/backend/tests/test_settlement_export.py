import io
import json

from openpyxl import load_workbook

from backend.app.db.models import AuditEvent, Document
from backend.app.services import settlement_export_service as exports
from test_api import create_contract
from test_document_versions import reissue
from test_review_workflow_api import upload, configured_contract


def workbook(response):
    assert response.status_code == 200, response.text
    assert 'spreadsheetml.sheet' in response.headers['content-type']
    return load_workbook(io.BytesIO(response.content), data_only=False)


def row(sheet):
    return dict(zip(next(sheet.values), list(sheet.values)[1]))


def set_fields(db_factory, did, fields, kind=None):
    with db_factory() as db:
        doc = db.get(Document, did)
        if kind:
            doc.document_type = kind
        doc.extract.raw_fields = json.dumps(fields, ensure_ascii=False)
        db.commit()


def test_settlement_preserves_zero_identifiers_and_review_state_without_posting(operator_client, db_factory):
    cid = create_contract(operator_client, vendor_name='가상 검증업체', business_number='001-23-45678',
        title='=HYPERLINK("https://example.invalid","test")')['contract_id']
    invoice = upload(operator_client, cid, 'tax_invoice')['document_id']
    bank = upload(operator_client, cid, 'bank_account')['document_id']
    set_fields(db_factory, invoice, {'supply_amount': 100, 'tax_amount': 0, 'total_amount': 100,
        'amount_scope': 'FULL', 'human_review': {'field_confirmations': {
            'tax_amount': {'value': 0, 'actor_name': '확인 담당자', 'at': '2026-10-06T23:00:00+00:00'}}}}, 'tax_invoice')
    set_fields(db_factory, bank, {'account_number': '001234567890', 'bank_name': '가상은행'}, 'bank_account')
    before = operator_client.get(f'/api/contracts/{cid}').json()
    response = operator_client.get(f'/api/contracts/{cid}/settlement-export',
        params={'masked': False, 'revision': before['workflow']['revision']})
    book = workbook(response)
    summary = row(book['정산 내역'])
    assert summary['등록 사업자번호'] == '001-23-45678'
    assert summary['계좌번호'] == '001234567890'
    assert summary['세금계산서 세액'] == 0
    assert summary['현재 자료 최종 확인일 (한국시간)'] is None
    assert summary['자동 검사 상태'] != '최종 확인 완료'
    assert book['정산 내역']['B2'].data_type == 's'
    assert not any(cell.data_type == 'f' for sheet in book for rows in sheet for cell in rows)
    proof = next(r for r in list(book['필드 확인'].values)[1:] if r[0] == invoice and r[2] == '세액')
    assert proof[3:8] == (0, '사람 확인', '확인 완료', '확인 담당자', '2026-10-07 08:00:00')
    assert operator_client.get(f'/api/contracts/{cid}').json()['workflow'] == before['workflow']
    assert response.headers['cache-control'] == 'no-store'
    events = operator_client.get(f'/api/contracts/{cid}/activity').json()['items']
    assert any(event['type'] == 'SETTLEMENT_EXPORT_REQUEST' and event['title'] == '정산 엑셀 다운로드' for event in events)
    with db_factory() as db:
        assert db.query(AuditEvent).filter_by(contract_id=cid, action='SETTLEMENT_EXPORT_REQUEST').count() == 1


def test_settlement_masking_defaults_on_and_unknown_values_stay_blank(operator_client, db_factory):
    cid = create_contract(operator_client, vendor_name='민감 거래처', business_number='001-23-45678')['contract_id']
    did = upload(operator_client, cid, 'bank_account')['document_id']
    set_fields(db_factory, did, {'company_name': '민감 거래처', 'account_number': '001234567890'}, 'bank_account')
    book = workbook(operator_client.get(f'/api/contracts/{cid}/settlement-export'))
    values = '\n'.join(str(cell.value) for sheet in book for rows in sheet for cell in rows)
    assert '민감 거래처' not in values and '001-23-45678' not in values and '001234567890' not in values
    assert row(book['정산 내역'])['세금계산서 세액'] is None


def test_settlement_does_not_choose_or_sum_independent_invoices_and_excludes_previous_versions(operator_client, db_factory):
    cid = create_contract(operator_client)['contract_id']
    first = upload(operator_client, cid, 'tax_invoice')['document_id']
    second = upload(operator_client, cid, 'tax_invoice')['document_id']
    set_fields(db_factory, first, {'total_amount': 110}, 'tax_invoice')
    set_fields(db_factory, second, {'total_amount': 110}, 'tax_invoice')
    revision = operator_client.get(f'/api/contracts/{cid}').json()['workflow']['revision']
    response = reissue(operator_client, cid, first, revision,
        text='세금계산서\n공급가액: 200원\n세액: 20원\n합계금액: 220원\n전액 청구', target_document_type='tax_invoice')
    assert response.status_code == 200, response.text
    replacement = response.json()[0]['document_id']
    book = workbook(operator_client.get(f'/api/contracts/{cid}/settlement-export', params={'masked': False}))
    summary = row(book['정산 내역'])
    assert summary['세금계산서 합계'] is None
    assert '여러 건' in summary['확인 사항']
    assert {r[0] for r in list(book['서류별 값'].values)[1:]} == {second, replacement}


def test_settlement_separates_final_approval_from_automatic_review_and_drops_stale_date(operator_client, separate_client, db_factory):
    representative, cid, body = configured_contract(operator_client, separate_client)
    assert operator_client.post(f'/api/pilot/contracts/{cid}/approvals', json={**body, 'step': 1}).status_code == 200
    result = representative.post(f'/api/contracts/{cid}/reviews', json=body)
    assert result.status_code == 200, result.text
    approved = row(workbook(operator_client.get(f'/api/contracts/{cid}/settlement-export'))['정산 내역'])
    assert approved['대표 최종 확인 상태'] == '최종 확인 완료'
    assert approved['현재 자료 최종 확인일 (한국시간)']
    assert approved['자동 검사 상태'] == '확인 필요'
    did = operator_client.get(f'/api/contracts/{cid}').json()['documents'][0]['document_id']
    set_fields(db_factory, did, {'total_amount': 999})
    stale = row(workbook(operator_client.get(f'/api/contracts/{cid}/settlement-export'))['정산 내역'])
    assert stale['대표 최종 확인 상태'] == '자료 변경 · 재확인'
    assert stale['현재 자료 최종 확인일 (한국시간)'] is None


def test_settlement_rejects_stale_or_concurrently_changed_data(operator_client, db_factory, monkeypatch):
    cid = create_contract(operator_client)['contract_id']
    did = upload(operator_client, cid)['document_id']
    url = f'/api/contracts/{cid}/settlement-export'
    assert operator_client.get(url, params={'revision': 999}).status_code == 409
    original = exports.workbook_bytes
    def changed(tables):
        content = original(tables)
        set_fields(db_factory, did, {'total_amount': 999})
        return content
    monkeypatch.setattr(exports, 'workbook_bytes', changed)
    assert operator_client.get(url).status_code == 409
    with db_factory() as db:
        assert db.query(AuditEvent).filter_by(action='SETTLEMENT_EXPORT_REQUEST').count() == 0


def test_settlement_requires_login_and_existing_contract(client, operator_client):
    assert operator_client.get('/api/contracts/999999/settlement-export').status_code == 404
    operator_client.post('/api/auth/logout')
    assert client.get('/api/contracts/1/settlement-export').status_code == 401
