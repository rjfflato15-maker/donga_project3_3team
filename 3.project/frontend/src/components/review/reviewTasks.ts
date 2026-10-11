import { DocumentResponse, DocumentType, ValidationCheck, ReviewBlocker } from '../../types';
import { isUnverifiedBusinessStatus, ruleLabel } from '../../utils/reviewSummary';
import { FieldDeferral, hasValue, ReviewContext, reviewRows } from './reviewFields';

export interface ReviewTask {
  id:string; field:string; label:string; document?:DocumentResponse; missingType?:DocumentType;
  reason:string; checks:ValidationCheck[]; expected:string|null; value:unknown;
  deferral?:FieldDeferral; kind:'field'|'source'|'missing'|'basis';
  /** 검사에서 걸린 문제가 아니라, 계약 기준과 같은 값을 상신 전에 원문과 한 번 더 대조하는 항목 */
  routine?:boolean;
}
export type ReviewRequestStates=Record<string,'draft'|'waiting'>;
/** A saved cursor must not send a problem CTA into routine source review. */
export function reviewStartTask(tasks:ReviewTask[],remembered?:ReviewTask){
  const problems=tasks.filter(task=>!task.routine),pool=problems.length?problems:tasks;
  return pool.find(task=>task.id===remembered?.id&&!task.deferral)||pool.find(task=>!task.deferral)||pool[0];
}
export function pendingReviewTasks(tasks:ReviewTask[],context:ReviewContext|null|undefined,requests:ReviewRequestStates){
  return tasks.filter(task=>{
    if(task.deferral)return true;
    if(task.kind==='missing')return !requests[task.id];
    return !task.document||!requests[task.document.document_id]||!task.checks.some(c=>c.status==='FAIL')||!context?.documents.find(p=>p.document_id===task.document!.document_id)?.fields[task.field]?.human_confirmation;
  });
}

const keysFor=(check:ValidationCheck,doc:DocumentResponse):string[]=>{
  const values=doc.analysis.fields as Record<string,unknown>;
  if(check.rule_id==='BUSINESS_NO_MATCH')return ['business_registration_no'];
  if(check.rule_id==='ACCOUNT_HOLDER_MATCH')return ['company_name'];
  if(check.rule_id==='VENDOR_NAME_MATCH')return ['company_name'];
  if(check.rule_id.startsWith('SOURCE_VALUE_MATCH_'))return [check.rule_id.slice('SOURCE_VALUE_MATCH_'.length).toLowerCase()];
  if(check.rule_id==='AMOUNT_EXTRACTION')return ['supply_amount','tax_amount','total_amount'].filter(key=>!hasValue(values[key]));
  if(check.rule_id==='AMOUNT_COMPONENTS')return ['total_amount'];
  if(check.rule_id.startsWith('AMOUNT_MATCH_'))return [check.message.includes('공급가액 기준')?'supply_amount':'total_amount'];
  if(check.rule_id==='PAYMENT_SCOPE')return ['amount_scope'];
  if(check.rule_id==='INSTALLMENT_TOTAL')return ['total_amount'];
  return [];
};

/** Count actionable server checks/AI follow-up, never every optional unconfirmed field. */
export function buildReviewTasks(documents:DocumentResponse[],checks:ValidationCheck[],context?:ReviewContext|null,blockers:ReviewBlocker[]=[]):ReviewTask[] {
  const docs=documents.filter(doc=>doc.version?.is_current!==false);
  const out=new Map<string,ReviewTask>();
  const add=(doc:DocumentResponse,field:string,check?:ValidationCheck,reason?:string,forceHuman=false)=>{
    const proof=context?.documents.find(p=>p.document_id===doc.document_id);
    const row=reviewRows(doc).find(item=>item.key===field);
    const id=`${doc.document_id}:${field}`;
    if(proof?.no_issue?.[field]&&!forceHuman)return;
    const old=out.get(id),related=check?[...(old?.checks||[]),check]:old?.checks||[];
    out.set(id,{id,field,document:doc,label:row?.label||'서류 원문',kind:row?'field':'source',
      checks:related,expected:related.find(c=>c.expected)?.expected??null,
      value:(doc.analysis.fields as Record<string,unknown>)[field],deferral:proof?.deferrals?.[field],
      reason:old?.reason||reason||(check?.rule_id.startsWith('SOURCE_VALUE_MATCH_')?'원문에서 읽은 값과 저장값이 달라요':check?.rule_id==='VENDOR_NAME_MATCH'?'서류 거래처와 등록한 계약 거래처가 달라요':check?.status==='FAIL'?'비교 기준과 달라요':!hasValue((doc.analysis.fields as Record<string,unknown>)[field])?'읽은 값이 없어요':'원문 확인이 필요해요')});
  };
  for(const check of checks.filter(c=>c.status!=='PASS'&&!isUnverifiedBusinessStatus(c))){
    if(check.rule_id==='REQUIRED_DOCUMENTS'){
      const type=check.field as DocumentType;
      if(!docs.some(doc=>doc.document_type===type))out.set(`missing:${type}`,{id:`missing:${type}`,field:'',label:'서류',kind:'missing',missingType:type,checks:[check],expected:null,value:null,reason:'필수 서류가 없어요'});
      continue;
    }
    const targets=docs.filter(doc=>String(doc.document_id)===check.field||['tax_invoice','contract'].includes(check.field)&&['PAYMENT_SCOPE','INSTALLMENT_TOTAL'].includes(check.rule_id)&&doc.document_type==='tax_invoice');
    if(!targets.length){out.set(`basis:${check.rule_id}:${check.field}`,{id:`basis:${check.rule_id}:${check.field}`,field:'',label:ruleLabel(check.rule_id),kind:'basis',checks:[check],expected:check.expected??null,value:check.actual,reason:'계약 기준을 확인해 주세요'});continue;}
    for(const doc of targets){const keys=keysFor(check,doc);if(keys.length)keys.forEach(key=>add(doc,key,check));else add(doc,'__document__',check,'서류 원문을 확인해 주세요');}
  }
  for(const doc of docs){
    const proof=context?.documents.find(p=>p.document_id===doc.document_id);
    if(doc.document_type==='tax_invoice'&&doc.analysis.fields.amount_scope==='UNKNOWN')add(doc,'amount_scope',undefined,'계약 지급 조건과 청구액을 확인해 전액·일부를 입력해 주세요');
    if(!doc.file_available||doc.processing_status==='FAILED'||proof?.source_version_verified===false)add(doc,'__document__',undefined,!doc.file_available?'원본 파일이 없어요':proof?.source_version_verified===false?'등록한 원본과 현재 파일이 달라요':'서류를 읽지 못했어요');
    if(proof?.ai_review?.manual_review_required){
      for(const field of proof.ai_review.human_unconfirmed_fields??proof.ai_review.targets??[]){
        if(reviewRows(doc).some(row=>row.key===field)&&!proof.fields[field]?.human_confirmation)add(doc,field,undefined,'AI가 읽은 값을 원문에서 확인해 주세요');
      }
    }
    for(const field of Object.keys(proof?.deferrals||{}))add(doc,field,undefined,'보류한 항목을 확인해 주세요');
  }
  for(const blocker of blockers){
    const doc=docs.find(d=>d.document_id===blocker.document_id);
    if(doc&&['SOURCE_UNVERIFIED','READING_FAILED','READING_INCOMPLETE','DOCUMENT_TYPE_UNKNOWN'].includes(blocker.code))add(doc,'__document__',undefined,blocker.reason,true);
    if(doc&&blocker.code==='FIELD_VALUE_REQUIRED'&&blocker.field)add(doc,blocker.field,undefined,blocker.reason,true);
    if(doc&&blocker.code==='HUMAN_REVIEW_REQUIRED'&&blocker.field&&!context?.documents.find(p=>p.document_id===doc.document_id)?.fields[blocker.field]?.human_confirmation){
      const id=`${doc.document_id}:${blocker.field}`,existing=out.has(id);
      add(doc,blocker.field,undefined,blocker.reason||'원문과 같은지 한 번 더 확인',true);
      const task=out.get(id);if(task&&!existing)task.routine=blocker.category!=='EVIDENCE';
    }
  }
  // 실제 문제(누락·불일치·보류 등)를 먼저, 단순 값 대조는 뒤로 둔다.
  return [...out.values()].sort((a,b)=>Number(!!a.routine)-Number(!!b.routine));
}
