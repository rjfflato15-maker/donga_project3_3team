"""Explicit operator review in synthetic API fixtures, never a bypass flag."""
from uuid import uuid4


def complete_source_review(client, cid):
    for _ in range(20):
        detail = client.get(f'/api/contracts/{cid}').json()
        blockers = detail['workflow']['submission']['gate']['blockers']
        needed = [b for b in blockers if b['code'] == 'HUMAN_REVIEW_REQUIRED']
        if not needed:
            return detail
        did = needed[0]['document_id']
        doc = next(d for d in detail['documents'] if d['document_id'] == did)
        fields = [b['field'] for b in needed if b['document_id'] == did]
        result = client.put(f'/api/documents/{did}/fields', json={'fields': {},
            'document_type': doc['document_type'], 'revision': detail['workflow']['revision'],
            'note': '합성 테스트 자료 원문 대조 완료', 'confirmed_fields': fields})
        assert result.status_code == 200, result.text
    raise AssertionError('Synthetic review did not converge')


def submission_body(detail, **overrides):
    wf = detail['workflow']
    exceptions = wf['submission']['gate']['exception_items']
    return {'review_cycle':wf['reviews'][0]['review_id'] if wf['reviews'] else 0, 'revision': wf['revision'], 'fingerprint': wf['fingerprint'],
            'idempotency_key': str(uuid4()), 'note': '합성 자료의 원문 대조와 회신을 검토했습니다.',
            'acknowledge_exception': bool(exceptions),
            'exception_reason': '합성 사례의 남은 업무상 예외 항목을 대표에게 명시해서 요청합니다.' if exceptions else '',
            'exception_items': [i['key'] for i in exceptions], **overrides}


def submit_ready(client, cid):
    detail = complete_source_review(client, cid)
    body = submission_body(detail)
    result = client.post(f'/api/pilot/contracts/{cid}/submission', json=body)
    assert result.status_code == 200, result.text
    return result.json()
