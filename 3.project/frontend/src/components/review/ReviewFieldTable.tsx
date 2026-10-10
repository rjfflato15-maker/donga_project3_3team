import {DocumentResponse,ValidationCheck} from '../../types';
import {DOCUMENT_LABEL} from '../../utils/documentLabels';
import {maskBusinessNumber,maskResidentNumber,maskVendorName} from '../../utils/masking';
import {displayValue,FieldDeferral,hasValue,Provenance} from './reviewFields';
import {VlmCandidate} from '../../hooks/useVlmReread';
import {ReviewRequestStates} from './reviewTasks';

export interface ReviewFieldRow {id:string;document:DocumentResponse;field:string;label:string;value:unknown;expected:string|null;checks:ValidationCheck[];deferral?:FieldDeferral}
export function criterion(field:string,value:string|null,masked:boolean){
  if(!value)return '—';
  if(field.endsWith('amount')&&/^[\d,\s.₩원]+$/.test(value))return displayValue(field,Number(value.replace(/[,\s₩원]/g,'')),false);
  if(field==='company_name')return maskVendorName(value,masked);
  return masked?maskResidentNumber(maskBusinessNumber(value)):value;
}
interface Props {rows:ReviewFieldRow[];doc:DocumentResponse;selected:string|null;proofs:Provenance[];masked:boolean;busy:boolean;requestStates?:ReviewRequestStates;
  candidates:VlmCandidate[];picked:Set<string>;canPick:(field:string)=>boolean;onPick:(field:string)=>void;onSelect:(row:ReviewFieldRow)=>void;}
export function ReviewFieldTable({rows,doc,selected,proofs,masked,busy,requestStates={},candidates,picked,canPick,onPick,onSelect}:Props){
  return <table className="flow-field-table"><thead><tr><th>항목</th><th>비교 기준</th><th>읽은 값</th><th>처리</th></tr></thead><tbody>{rows.map(row=>{
    const docProof=proofs.find(item=>item.document_id===row.document.document_id),proof=docProof?.fields[row.field];
    const active=row.document.document_id===doc.document_id&&selected===row.field;
    const candidate=row.document.document_id===doc.document_id?candidates.find(item=>item.field===row.field):undefined;
    const request=proof?.human_confirmation&&row.checks.some(c=>c.status==='FAIL')?requestStates[row.document.document_id]:null;
    const status=docProof?.no_issue?.[row.field]?'문제 없음 기록':row.deferral?'보류':request==='draft'?'요청에 담음':request==='waiting'?'회신 대기':proof?.human_confirmation?row.checks.some(c=>c.status==='FAIL')?'조치 선택':row.checks.some(c=>c.status!=='PASS')?'판단 남음':'원문 확인됨':null;
    return <tr key={row.id} className={active?'flow-selected-row':''} onClick={event=>{if(!busy&&!((event.target as HTMLElement).closest('button,input,label')))onSelect(row);}}><th scope="row"><button className="flow-select-row" aria-label={`${row.document.document_id===doc.document_id?'':DOCUMENT_LABEL[row.document.document_type]+' '}${row.label} 상세 보기`} aria-pressed={active} disabled={busy} onClick={()=>onSelect(row)}><strong>{row.label}</strong><small>{DOCUMENT_LABEL[row.document.document_type]}</small></button></th>
      <td data-label="비교 기준">{criterion(row.field,row.expected,masked)}</td><td data-label="읽은 값"><span className={!hasValue(row.value)?'flow-reading-failed':'flow-field-value'}>{row.field==='__document__'?!row.document.file_available?'원본 없음':'원문 확인 필요':displayValue(row.field,row.value,masked)}</span>{candidate&&<label className="flow-candidate"><input type="checkbox" aria-label={`${row.label} AI 제안 선택`} checked={picked.has(row.field)} disabled={!canPick(row.field)} onChange={()=>onPick(row.field)}/><span>AI {displayValue(row.field,candidate.value,masked)}</span>{!candidate.usable&&<small>{candidate.reason}</small>}</label>}</td><td><span className={status?`flow-field-status ${row.deferral?'deferred':'confirmed'}`:'sr-only'}>{status||'확인 필요'}</span></td></tr>;
  })}</tbody></table>;
}
