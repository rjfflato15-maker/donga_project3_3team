import {ArrowRight, ChevronRight} from 'lucide-react';
import {DocumentResponse} from '../../types';
import {displayValue, hasValue, reviewRows} from './reviewFields';
import './documentChangeSummary.css';

export interface DocumentComparison {
  revision:number;
  previous_document_id:number;
  new_document_id:number;
  previous_version:number;
  new_version:number;
  previous_fields:Record<string,unknown>;
  new_fields:Record<string,unknown>;
  changes:{field:string;previous_value:unknown;new_value:unknown}[];
}

interface Props {
  doc:DocumentResponse;
  comparison:DocumentComparison|null;
  loading:boolean;
  error:string;
  masked:boolean;
  selected:string|null;
  busy:boolean;
  onSelect:(field:string)=>void;
  onPrevious?:()=>void;
  onRetry:()=>void;
}

const otherLabels:Record<string,string>={title:'문서 제목',contract_period_start:'계약 시작일',contract_period_end:'계약 종료일',amount_basis:'금액 기준',amount:'금액 (기존 필드)'};
const otherValue=(field:string,value:unknown,masked:boolean)=>field==='amount_basis'
  ? value==='TOTAL'?'부가세 포함':value==='SUPPLY'?'공급가액':'못 읽음'
  :displayValue(field,value,masked);

/** Differences describe saved extraction values, never proof that the original is correct. */
export function DocumentChangeSummary({doc,comparison,loading,error,masked,selected,busy,onSelect,onPrevious,onRetry}:Props) {
  const rows=reviewRows(doc);
  const changes=comparison?.changes??[];
  const changed=rows.flatMap(row=>{
    const change=changes.find(item=>item.field===row.key);
    return change&& (hasValue(change.previous_value)||hasValue(change.new_value))?[{...change,label:row.label}]:[];
  });
  const same=rows.filter(row=>comparison&&hasValue(comparison.previous_fields[row.key])&&hasValue(comparison.new_fields[row.key])&&comparison.previous_fields[row.key]===comparison.new_fields[row.key]);
  const unread=rows.filter(row=>comparison&&!hasValue(comparison.previous_fields[row.key])&&!hasValue(comparison.new_fields[row.key]));
  const others=changes.filter(change=>!rows.some(row=>row.key===change.field)&&!(change.field==='amount'&&changes.some(item=>item.field==='total_amount')));
  const renderChange=(change:typeof changed[number])=><button type="button" key={change.field} className="flow-change-item" aria-label={`${change.label} 변경 확인`} aria-pressed={selected===change.field} disabled={busy} onClick={()=>onSelect(change.field)}>
    <span className="flow-change-field">{change.label}{!hasValue(change.previous_value)?<small>새로 읽음</small>:!hasValue(change.new_value)?<small>이번 본 못 읽음</small>:null}</span>
    <span className="flow-change-values"><span className="flow-change-before">{displayValue(change.field,change.previous_value,masked)}</span><ArrowRight size={12} aria-hidden="true"/><strong>{displayValue(change.field,change.new_value,masked)}</strong></span><ChevronRight size={13} aria-hidden="true"/>
  </button>;

  return <section className="flow-change-summary" aria-label="수정본 변경 요약" aria-busy={loading}>
    <div className="flow-change-heading"><div><strong>수정본 변경 요약</strong><small>{comparison?`${comparison.previous_version}차본 → ${comparison.new_version}차본 · 읽은 값 비교`:'이전 본과 읽은 값 비교'}</small></div>{comparison&&onPrevious&&<button type="button" className="text-button" disabled={busy||loading} onClick={onPrevious}>{comparison.previous_version}차본 원문 보기</button>}</div>
    {loading?<p role="status" className="flow-change-state">바뀐 항목을 비교하고 있어요.</p>:error?<div className="flow-change-state" role="alert"><span>{error}</span><button type="button" className="text-button" onClick={onRetry}>변경 요약 다시 불러오기</button></div>:comparison?<>
      {changed.length>0?<div className="flow-change-list">{changed.slice(0,3).map(renderChange)}{changed.length>3&&<details className="flow-change-more"><summary>나머지 변경 {changed.length-3}개 보기</summary>{changed.slice(3).map(renderChange)}</details>}</div>:<p className="flow-change-state">{same.length?'읽은 값의 차이가 없어요.':'양쪽에서 읽힌 검수 항목이 없어요.'}</p>}
      <div className="flow-change-foot">{same.length>0&&<details><summary>같은 항목 {same.length}개</summary><p>{same.map(row=>`${row.label} 같음`).join(' · ')}</p></details>}{unread.length>0&&<span>양쪽 모두 못 읽음 {unread.length}개</span>}{others.length>0&&<details><summary>그 밖의 정보 변경 {others.length}개</summary>{others.map(change=><p key={change.field}>{otherLabels[change.field]||'기타 정보'} · {otherValue(change.field,change.previous_value,masked)} → {otherValue(change.field,change.new_value,masked)}</p>)}</details>}</div>
    </>:null}
  </section>;
}
