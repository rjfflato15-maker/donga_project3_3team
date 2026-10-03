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


def test_summary_groups_multiple_checks_into_same_document_card():
    from backend.app.services.review_summary_service import issue_card_groups
    from backend.app.schemas.validation import ValidationCheck
    checks=[ValidationCheck(rule_id=rule,field=field,status=status,message='unit') for rule,field,status in [
        ('BUSINESS_NO_MATCH','7','FAIL'),('AMOUNT_MATCH_ESTIMATE','7','FAIL'),
        ('AMOUNT_EXTRACTION','8','REVIEW'),('BUSINESS_STATUS','business_number','REVIEW'),
        ('REQUIRED_DOCUMENTS','contract','MISSING')]]
    groups=issue_card_groups(checks,[{'document_id':7},{'document_id':8}])
    assert [group['key'] for group in groups]==['doc-7','doc-8','missing-contract']
    assert len(groups[0]['checks'])==2


def test_summary_exposes_card_and_check_counts_without_changing_rule_output(operator_client):
    cid=create_contract(operator_client)['contract_id']
    upload(operator_client,cid,'estimate')
    data=operator_client.get(f'/api/contracts/{cid}/summary').json()
    assert data['open_issue_count_unit']=='ISSUE_CARD'
    assert int(data['facts']['open_issue_count'])==len(data['issue_groups'])==data['counts']['issue_card_count']
    assert data['counts']['check_item_count']==sum(len(group['checks']) for group in data['issue_groups'])
    assert all(check['rule_id']!='BUSINESS_STATUS' for group in data['issue_groups'] for check in group['checks'])
