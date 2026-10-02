import pytest
from backend.app.services.contract_summary_service import render_template,amount_display
from test_api import create_contract
from test_review_workflow_api import upload


def test_summary_uses_actual_reference_counts_and_unknown_basis(operator_client):
    cid=create_contract(operator_client,title='계약 2026',vendor_name='상대 업체 17',contract_amount=1000.05,amount_basis='UNKNOWN')['contract_id']
    upload(operator_client,cid,'estimate');upload(operator_client,cid,'estimate')
    result=operator_client.get(f'/api/contracts/{cid}/summary')
    assert result.status_code==200,result.text
    data=result.json()
    assert data['facts']['contract_amount']=='1,000.05' and data['facts']['submitted_document_count']=='1'
    assert data['facts']['amount_basis']=='부가세 포함 여부 확인 필요'
    assert '2026' in data['text'] and '17' in data['text'] and '1,000.05원' in data['text']
    assert data['llm_used'] is False and data['numeric_placeholders_verified'] is True
    assert operator_client.get(f'/api/contracts/{cid}/summary',params={'revision':data['revision']+1}).status_code==409


def test_summary_disallows_invented_numbers_or_placeholders():
    assert amount_display(11000000)=='11,000,000'
    with pytest.raises(ValueError):render_template('금액은 9999원입니다.',{'contract_amount':'1100'})
    with pytest.raises(ValueError):render_template('{contract_amount} {contract_amount}',{'contract_amount':'1100'})
    with pytest.raises(ValueError):render_template('{contract_amount.__class__}',{'contract_amount':'1100'})
