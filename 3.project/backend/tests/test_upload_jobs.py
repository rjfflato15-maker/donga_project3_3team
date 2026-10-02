from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta
from backend.app.db.models import Document,DocumentUploadJob,AuditEvent
from backend.app.services import pipeline_service
from backend.app.api import upload_jobs
from test_api import create_contract
from test_review_workflow_api import upload
from test_storage_concurrency import block_analysis

TEXT='외주 용역 계약서\n상호: 가상 검증업체\n사업자등록번호: 220-88-12345\n합계금액: 110원\n전액 청구'


def submit(client,cid,revision,**extra):
    return client.post(f'/api/pilot/contracts/{cid}/document-jobs',files={'file':('job.txt',TEXT.encode(),'text/plain')},
                       data={'idempotency_key':'same-client-request-key','revision':revision,'target_document_type':'contract',**extra})


def test_same_request_replay_publishes_once_and_key_cannot_change_file_conditions(operator_client,db_factory,monkeypatch):
    c=create_contract(operator_client,contract_amount=110);cid=c['contract_id'];calls=[]
    original=pipeline_service.analyze_document
    def counted(*a,**kw):calls.append(1);return original(*a,**kw)
    monkeypatch.setattr(pipeline_service,'analyze_document',counted)
    first=submit(operator_client,cid,c['workflow']['revision'])
    assert first.status_code==202,first.text
    job=operator_client.get(f"/api/pilot/document-jobs/{first.json()['job_id']}").json()
    assert job['status']=='COMPLETED' and job['document_id']
    replay=submit(operator_client,cid,c['workflow']['revision'])
    assert replay.status_code==202 and replay.json()['replayed'] and replay.json()['document_id']==job['document_id']
    assert len(calls)==1
    assert submit(operator_client,cid,c['workflow']['revision'],change_note='different condition').status_code==409
    with db_factory() as db:
        assert db.query(Document).count()==1 and db.query(DocumentUploadJob).count()==1
        assert db.query(AuditEvent).filter_by(action='DOCUMENT_UPLOAD').count()==1


def test_status_is_readable_during_analysis_and_replay_does_not_start_second_worker(operator_client,separate_client,db_factory,monkeypatch):
    c=create_contract(operator_client);cid=c['contract_id'];other=separate_client('operator')
    started,finish=block_analysis(monkeypatch)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending=pool.submit(submit,operator_client,cid,c['workflow']['revision'])
        try:
            assert started.wait(2)
            with db_factory() as db:jid=db.query(DocumentUploadJob).first().job_id
            state=other.get(f'/api/pilot/document-jobs/{jid}').json()
            assert state['status']=='RUNNING' and state['stage']=='ANALYZING'
            replay=submit(other,cid,c['workflow']['revision'])
            assert replay.status_code==202 and replay.json()['replayed']
            assert other.post(f'/api/pilot/document-jobs/{jid}/retry',json={'job_revision':state['job_revision'],'contract_revision':c['workflow']['revision']}).status_code==409
        finally:finish.set()
        assert pending.result(timeout=10).status_code==202
    with db_factory() as db:assert db.query(Document).count()==1


def test_failed_analysis_retry_reuses_job_without_failed_document_duplicate(operator_client,db_factory,monkeypatch):
    c=create_contract(operator_client);cid=c['contract_id'];original=pipeline_service.analyze_document
    def failed(*a,**kw):raise RuntimeError('unit OCR failure')
    monkeypatch.setattr(pipeline_service,'analyze_document',failed)
    response=submit(operator_client,cid,c['workflow']['revision']);jid=response.json()['job_id']
    job=operator_client.get(f'/api/pilot/document-jobs/{jid}').json()
    assert job['status']=='FAILED' and job['error_code']=='SOURCE_UNREADABLE' and job['document_id'] is None
    monkeypatch.setattr(pipeline_service,'analyze_document',original)
    retried=operator_client.post(f'/api/pilot/document-jobs/{jid}/retry',json={'job_revision':job['job_revision'],'contract_revision':c['workflow']['revision']})
    assert retried.status_code==202,retried.text
    job=operator_client.get(f'/api/pilot/document-jobs/{jid}').json()
    assert job['status']=='COMPLETED' and job['attempt_count']==2
    with db_factory() as db:assert db.query(Document).count()==1


def test_retry_after_publication_recovers_validation_without_new_ocr_or_document(operator_client,db_factory,monkeypatch):
    c=create_contract(operator_client);cid=c['contract_id'];original=pipeline_service.PipelineService.revalidate_contract
    def failed(*a,**kw):raise RuntimeError('unit interrupted after publication')
    monkeypatch.setattr(pipeline_service.PipelineService,'revalidate_contract',failed)
    jid=submit(operator_client,cid,c['workflow']['revision']).json()['job_id']
    job=operator_client.get(f'/api/pilot/document-jobs/{jid}').json()
    assert job['status']=='FAILED' and job['document_id']
    did=job['document_id']
    monkeypatch.setattr(pipeline_service.PipelineService,'revalidate_contract',original)
    def forbidden(*a,**kw):raise AssertionError('published retry must not infer again')
    monkeypatch.setattr(pipeline_service,'analyze_document',forbidden)
    revision=operator_client.get(f'/api/contracts/{cid}').json()['workflow']['revision']
    assert operator_client.post(f'/api/pilot/document-jobs/{jid}/retry',json={'job_revision':job['job_revision'],'contract_revision':revision}).status_code==202
    done=operator_client.get(f'/api/pilot/document-jobs/{jid}').json()
    assert done['status']=='COMPLETED' and done['document_id']==did
    with db_factory() as db:assert db.query(Document).count()==1


def test_queued_restart_can_be_recovered_and_stale_retry_revision_rejected(operator_client,db_factory,monkeypatch):
    c=create_contract(operator_client);cid=c['contract_id'];original=upload_jobs.run_upload_job
    monkeypatch.setattr(upload_jobs,'run_upload_job',lambda *a:None)
    jid=submit(operator_client,cid,c['workflow']['revision']).json()['job_id']
    with db_factory() as db:
        row=db.get(DocumentUploadJob,jid);row.status='RUNNING';row.lease_token='lost-worker';row.lease_expires_at=datetime.utcnow()-timedelta(seconds=1);db.commit()
    job=operator_client.get(f'/api/pilot/document-jobs/{jid}').json()
    assert operator_client.post(f'/api/pilot/document-jobs/{jid}/retry',json={'job_revision':job['job_revision']+1,'contract_revision':c['workflow']['revision']}).status_code==409
    monkeypatch.setattr(upload_jobs,'run_upload_job',original)
    assert operator_client.post(f'/api/pilot/document-jobs/{jid}/retry',json={'job_revision':job['job_revision'],'contract_revision':c['workflow']['revision']}).status_code==202
    assert operator_client.get(f'/api/pilot/document-jobs/{jid}').json()['status']=='COMPLETED'


def test_lost_worker_lease_cannot_publish_second_document_after_recovery(operator_client,db_factory,monkeypatch):
    from backend.app.services.upload_job_service import run_upload_job
    c=create_contract(operator_client);cid=c['contract_id'];original=pipeline_service.analyze_document;calls=[]
    def recovered(*a,**kw):
        calls.append(1)
        if len(calls)==1:
            with db_factory() as db:
                row=db.query(DocumentUploadJob).first();jid=row.job_id
                row.status='QUEUED';row.lease_token=None;row.job_revision+=1;db.commit()
            run_upload_job(jid)
        return original(*a,**kw)
    monkeypatch.setattr(pipeline_service,'analyze_document',recovered)
    jid=submit(operator_client,cid,c['workflow']['revision']).json()['job_id']
    assert operator_client.get(f'/api/pilot/document-jobs/{jid}').json()['status']=='COMPLETED'
    with db_factory() as db:
        assert db.query(Document).count()==1
        assert db.query(AuditEvent).filter_by(action='DOCUMENT_UPLOAD').count()==1
