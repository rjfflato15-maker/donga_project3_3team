import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db.models import User,UserProfile,AuditEvent,WorkAssignment
from conftest import TEST_PASSWORD
from test_api import create_contract
from test_review_workflow_api import upload
from test_document_versions import reissue


@pytest.fixture
def coworker(db_factory,password_hash,client):
    with db_factory() as db:
        user=User(email='coworker@tests.local',password=password_hash);db.add(user);db.flush()
        db.add(UserProfile(user_id=user.user_id,role='operator',display_name='다른 담당자',active=True,must_change_password=False))
        db.commit();uid=user.user_id
    other=TestClient(app)
    assert other.post('/api/auth/login',json={'email':'coworker@tests.local','password':TEST_PASSWORD}).status_code==200
    yield other,uid
    other.close()


def create_task(client,cid,uid,**extra):
    rev=client.get(f'/api/contracts/{cid}').json()['workflow']['revision']
    return client.post(f'/api/pilot/contracts/{cid}/assignments',json={'assignee_id':uid,'contract_revision':rev,'title':'원문 검수','memo':'금액 확인','due_on':'2026-10-05',**extra})


def update_task(client,cid,aid,rev,action,**extra):
    return client.patch(f'/api/pilot/contracts/{cid}/assignments/{aid}',json={'assignment_revision':rev,'action':action,'note':'단위 테스트 업무 처리',**extra})


def test_assignment_owner_permissions_reassign_and_complete_without_approval_rights(operator_client,coworker,accounts,db_factory):
    other,uid=coworker;cid=create_contract(operator_client)['contract_id']
    before=operator_client.get(f'/api/contracts/{cid}').json()['workflow']
    result=create_task(operator_client,cid,uid)
    assert result.status_code==201,result.text
    row=result.json();aid=row['assignment_id']
    assert other.get('/api/pilot/assignments/mine').json()['count']==1
    assert operator_client.get('/api/pilot/assignments/mine').json()['count']==0
    assert update_task(operator_client,cid,aid,1,'START').status_code==403
    assert update_task(operator_client,cid,aid,1,'COMPLETE').status_code==403
    assert update_task(other,cid,aid,1,'CANCEL').status_code==403
    assert update_task(other,cid,aid,1,'START').json()['status']=='IN_PROGRESS'
    assert update_task(operator_client,cid,aid,1,'CANCEL').status_code==409
    next_task=update_task(operator_client,cid,aid,2,'REASSIGN',assignee_id=accounts['operator']['user_id'],contract_revision=before['revision'])
    assert next_task.status_code==200 and next_task.json()['status']=='OPEN'
    assert other.get('/api/pilot/assignments/mine').json()['count']==0
    assert update_task(other,cid,aid,3,'COMPLETE').status_code==403
    assert update_task(operator_client,cid,aid,3,'COMPLETE').json()['status']=='COMPLETED'
    assert update_task(operator_client,cid,aid,4,'UPDATE',memo='수정 시도').status_code==409
    after=operator_client.get(f'/api/contracts/{cid}').json()['workflow']
    assert before==after
    assert operator_client.post(f'/api/contracts/{cid}/reviews',json={'revision':before['revision'],'fingerprint':before['fingerprint'],'decision':'CONFIRMED','note':'업무 완료가 결재 권한을 주지 않음'}).status_code==403
    with db_factory() as db:assert db.query(AuditEvent).filter_by(action='ASSIGNMENT_CHANGED').count()==3


def test_reissue_marks_assignment_stale_and_cannot_complete_prior_document_task(operator_client,coworker):
    other,uid=coworker;cid=create_contract(operator_client)['contract_id'];doc=upload(operator_client,cid)
    assigned=create_task(operator_client,cid,uid,document_id=doc['document_id']).json();aid=assigned['assignment_id']
    assert reissue(operator_client,cid,doc['document_id'],assigned['contract_revision']).status_code==200
    pending=other.get('/api/pilot/assignments/mine').json()['assignments'][0]
    assert pending['is_stale'] is True
    assert update_task(other,cid,aid,1,'COMPLETE').status_code==409
    revision=operator_client.get(f'/api/contracts/{cid}').json()['workflow']['revision']
    assert update_task(operator_client,cid,aid,1,'REASSIGN',assignee_id=uid,contract_revision=revision).status_code==409
    assert update_task(operator_client,cid,aid,1,'CANCEL').json()['status']=='CANCELLED'


def test_active_account_cross_contract_revision_and_completion_contract(operator_client,coworker,separate_client,db_factory):
    other,uid=coworker;cid=create_contract(operator_client)['contract_id'];different=create_contract(operator_client)['contract_id']
    result=create_task(operator_client,cid,uid).json();aid=result['assignment_id']
    assert update_task(operator_client,different,aid,1,'CANCEL').status_code==404
    assert create_task(operator_client,cid,uid,contract_revision=999).status_code==409
    with db_factory() as db:db.get(UserProfile,uid).active=False;db.commit()
    assert create_task(operator_client,cid,uid).status_code==400
    directory=operator_client.get('/api/pilot/assignees').json()
    assert not any(r['user_id']==uid for r in directory)
    assert all(set(r)=={'user_id','display_name','role'} for r in directory)
    representative=separate_client()
    assert update_task(representative,cid,aid,1,'COMPLETE').status_code==200
    assert operator_client.delete(f'/api/contracts/{cid}').status_code==204
    with db_factory() as db:assert db.query(WorkAssignment).count()==0
