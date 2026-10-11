import {ContractDetail,DocumentResponse} from '../../types';
import {ReviewContext,reviewRows} from './reviewFields';
import {ReviewTask} from './reviewTasks';

/** Navigation is metadata only. Every result remains derived from current server evidence. */
export function focusItems(documents:DocumentResponse[],tasks:ReviewTask[],context?:ReviewContext|null):ReviewTask[]{
  const items=new Map<string,ReviewTask>();
  const automatic=new Set(context?.workflow?.submission?.gate?.automatic_review?.map(item=>`${item.document_id}:${item.field}`)||[]);
  for(const doc of documents.filter(d=>d.version?.is_current!==false)){
    const proof=context?.documents.find(p=>p.document_id===doc.document_id);
    const fields=new Set(['company_name','business_registration_no']);
    if(['contract','estimate','tax_invoice'].includes(doc.document_type))fields.add(doc.analysis.fields.total_amount!=null?'total_amount':'amount');
    if(doc.document_type==='bank_account'){fields.add('bank_name');fields.add('account_number');}
    if(doc.document_type==='tax_invoice')for(const field of ['supply_amount','tax_amount','amount_scope'])fields.add(field);
    for(const field of proof?.ai_review?.targets||[])fields.add(field);
    for(const [field,value] of Object.entries(proof?.fields||{}))if(value.human_confirmation)fields.add(field);
    for(const field of [...Object.keys(proof?.deferrals||{}),...Object.keys(proof?.no_issue||{})])fields.add(field);
    for(const row of reviewRows(doc).filter(row=>fields.has(row.key)&&!automatic.has(`${doc.document_id}:${row.key}`))){
      const id=`${doc.document_id}:${row.key}`;
      items.set(id,{id,document:doc,field:row.key,label:row.label,kind:'field',checks:[],expected:null,value:(doc.analysis.fields as Record<string,unknown>)[row.key],reason:'원문 확인 기록을 확인하세요'});
    }
  }
  for(const task of tasks)items.set(task.id,task);
  return [...items.values()];
}
export const focusBasis=(contract:ContractDetail)=>[contract.workflow?.revision,contract.workflow?.fingerprint,contract.workflow?.submission?.gate?.fingerprint].join('|');
const cursorKey=(id:number)=>`c-pilot:review-position:${id}`;
export function readFocusCursor(contract:ContractDetail,items:ReviewTask[]):ReviewTask|undefined{
  try{
    const raw=sessionStorage.getItem(cursorKey(contract.contract_id));if(!raw)return;
    const value=JSON.parse(raw);
    if(value.basis!==focusBasis(contract)){sessionStorage.removeItem(cursorKey(contract.contract_id));return;}
    return items.find(item=>item.id===value.item);
  }catch{return;}
}
export function writeFocusCursor(contract:ContractDetail,item:string){
  try{sessionStorage.setItem(cursorKey(contract.contract_id),JSON.stringify({basis:focusBasis(contract),item}));}catch{/* Navigation still works when storage is unavailable. */}
}
