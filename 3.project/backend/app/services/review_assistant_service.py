"""Plan → read stored evidence → in-memory recheck → draft, never publish."""
import hashlib
import json
from fastapi import HTTPException
from ..schemas.common import DocumentType, DOCUMENT_TYPE_KOREAN
from .readonly_review_service import snapshot, require_unchanged

INTERNAL_DOCUMENTS={'contract','inspection_confirmation'}


def issue_key(check):
    body=[check.rule_id,check.field,check.expected,check.actual]
    return hashlib.sha256(json.dumps(body,ensure_ascii=False).encode()).hexdigest()[:20]


def prepare_item(check,data):
    docs={str(d['document_id']):d for d in data['documents']}
    doc=docs.get(check.field)
    kind=doc['document_type'] if doc else check.field if check.field in {t.value for t in DocumentType} else None
    label=DOCUMENT_TYPE_KOREAN.get(DocumentType(kind),'서류') if kind else '서류'
    request=None;internal=None
    action='VERIFY_EXTRACTION_FIRST'
    if check.rule_id=='BUSINESS_STATUS':
        # This preview always uses DisabledNtsClient. Unqueried is a notice,
        # not an actionable defect or a vendor resubmission request.
        action='INFORMATIONAL_NOTICE'
    elif check.rule_id in {'AMOUNT_EXTRACTION','ORIGINAL_FILE','DOCUMENT_PROCESSING','DOCUMENT_TYPE'} or (check.rule_id=='BUSINESS_NO_MATCH' and check.status.value=='REVIEW'):
        action='VERIFY_EXTRACTION_FIRST'
        internal={'title':'원문에서 읽은 값부터 확인','memo':check.message}
    elif check.rule_id=='AMOUNT_BASIS':
        action='INTERNAL_REVIEW'
        internal={'title':'원문·분류·등록 기준 확인','memo':check.message}
    elif kind in INTERNAL_DOCUMENTS:
        action='INTERNAL_PREPARATION'
        internal={'title':f'{label} 준비 또는 원문 확인','memo':check.message}
    elif kind in {'estimate','tax_invoice','business_registration','bank_account'}:
        action='DRAFT_REQUEST_AFTER_REVIEW'
        request={'recipient_name':data['reference']['vendor_name'], 'document_type':kind,
                 'subject':f"{data['reference']['title']} · {label} 확인 요청 초안",
                 'body':f"{data['reference']['vendor_name']} 담당자님, ‘{data['reference']['title']}’의 {label}을 확인 부탁드립니다. "
                        +(f'{label} 원문을 보내 주세요.' if check.status.value=='MISSING' else '등록한 자료와 원문을 먼저 검토한 뒤, 해당 항목을 확인할 수 있는 자료 또는 정정본을 부탁드립니다.'),
                 'review_before_use':True,'sent':False}
    else:
        internal={'title':'등록 기준과 추출값 대조','memo':check.message}
    return {'issue_id':issue_key(check),'rule_id':check.rule_id,'field':check.field,'status':check.status.value,
            'reason':check.message,'expected':check.expected,'actual':check.actual,
            'document_id':doc['document_id'] if doc else None,'next_action':action,
            'recheck':{'tool':'LOCAL_RULE_RECHECK','completed':True,'revision':data['revision'],'fingerprint':data['fingerprint']},
            'request_draft':request,'assignment_draft':internal,'persisted':False,
            'actionable':action!='INFORMATIONAL_NOTICE'}


def assistant_preview(db,cid,revision,fingerprint,issue_ids=None):
    data=snapshot(db,cid,revision,fingerprint)
    checks=[c for c in data['checks'] if c.status.value!='PASS']
    known={issue_key(c) for c in checks}
    if issue_ids and set(issue_ids)-known:
        raise HTTPException(422,'현재 검수 자료에 없는 issue_id입니다. 미리보기를 새로 불러오세요.')
    selected=[c for c in checks if not issue_ids or issue_key(c) in issue_ids]
    items=[prepare_item(c,data) for c in selected]
    recorded={(r['rule_id'],r['field']):r for r in data['recorded_checks']}
    differences=[]
    current={(c.rule_id,c.field):{'status':c.status.value,'expected':c.expected,'actual':c.actual} for c in data['checks']}
    for key in sorted(set(recorded)|set(current),key=lambda pair:tuple(str(value) for value in pair)):
        before=recorded.get(key)
        before={k:before[k] for k in ('status','expected','actual')} if before else None
        after=current.get(key)
        if before!=after:differences.append({'rule_id':key[0],'field':key[1],'recorded':before,'preview':after})
    require_unchanged(db,data)
    return {'contract_id':cid,'revision':data['revision'],'fingerprint':data['fingerprint'],
            'preview_only':True,'persisted':False,'automatic_send':False,'llm_used':False,'external_api_calls':0,
            'summary':data['summary'].model_dump(),'items':items,'item_count':len(items),
            'actionable_item_count':sum(i['actionable'] for i in items),'recheck_differences':differences,
            'steps':[{'tool':'READ_CURRENT_STORED_EVIDENCE','status':'COMPLETED','document_count':len(data['documents'])},
                     {'tool':'LOCAL_RULE_RECHECK','status':'COMPLETED','writes':0,'nts_mode':'disabled'},
                     {'tool':'PREPARE_DRAFTS','status':'COMPLETED','saved':0,'sent':0}]}
