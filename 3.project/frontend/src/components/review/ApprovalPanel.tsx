import React, { useEffect, useMemo, useState } from 'react';
import { Check, CheckCheck, ArrowUpRight } from 'lucide-react';
import { ContractDetail } from '../../types';
import { requestJson } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { buildReviewOverview, isUnverifiedBusinessStatus } from '../../utils/reviewSummary';
import { ActivityItem, fieldChanges, kst } from './ActivityTimeline';
import { Surface, Badge } from '../ui/Surface';
import { maskBusinessNumber, maskResidentNumber } from '../../utils/masking';
import { DOCUMENT_LABEL } from '../../utils/documentLabels';
import { BundledRequest, currentDocumentFor } from './BundleRequest';

export interface ApprovalState {
  steps: { role: 'operator' | 'representative'; label: string }[];
  completed_steps: number; next_step: number | null; status: 'PENDING' | 'IN_PROGRESS' | 'CONFIRMED';
  history: { signoff_id: number; actor_name: string; note: string; created_at: string; current: boolean }[];
}
const ROLE_KO = { operator: '담당자', representative: '대표' } as const;
interface Props { contract: ContractDetail; onChanged: () => Promise<void>; embedded?: boolean; masked?: boolean; onOpenDocumentId?:(id:number)=>void; requests?:BundledRequest[] }

export const ApprovalPanel: React.FC<Props> = ({ contract, onChanged, masked = true, onOpenDocumentId, requests=[] }) => {
  const { user } = useAuth();
  const [state, setState] = useState<ApprovalState | null>(null);
  const [note, setNote] = useState(''), [ack, setAck] = useState(false), [busy, setBusy] = useState(false);
  const [error, setError] = useState(''), [queryError, setQueryError] = useState('');
  const [reload, setReload] = useState(0), [events, setEvents] = useState<ActivityItem[]>([]), [eventError,setEventError] = useState('');
  const [eventLoading,setEventLoading] = useState(true);
  const overview = useMemo(() => buildReviewOverview(contract), [contract]);
  const wf = contract.workflow;
  useEffect(() => { setError(''); }, [contract.contract_id]);
  useEffect(() => {
    setNote(''); setAck(false); setState(null); setQueryError('');
    const controller = new AbortController();
    requestJson<ApprovalState>(`/api/pilot/contracts/${contract.contract_id}/approvals`, { signal: controller.signal })
      .then((v) => { if (!controller.signal.aborted) setState(v); })
      .catch((e) => { if (!controller.signal.aborted) setQueryError(e.message); });
    return () => controller.abort();
  }, [contract.contract_id, contract.updated_at, wf?.revision, wf?.fingerprint, wf?.approval_status, reload]);
  useEffect(() => {
    const controller = new AbortController(); setEvents([]);setEventError('');setEventLoading(true);
    requestJson<{ items:ActivityItem[] }>(`/api/contracts/${contract.contract_id}/activity?limit=30&masked=${masked}&revision=${wf?.revision ?? 0}`, {signal:controller.signal})
      .then((r) => { if (!controller.signal.aborted) setEvents(r.items); })
      .catch((e) => { if (!controller.signal.aborted) setEventError(e.message); })
      .finally(() => {if(!controller.signal.aborted)setEventLoading(false);});
    return () => controller.abort();
  }, [contract.contract_id, wf?.revision, masked]);
  if (!wf) return null;
  const approval = wf.approval_status;
  const steps = state?.steps ?? [];
  const nextIndex = state?.next_step ? state.next_step - 1 : null;
  const nextStep = nextIndex !== null ? steps[nextIndex] : null;
  const isLast = nextIndex !== null && nextIndex === steps.length - 1;
  const myTurn = !!nextStep && (user?.role === nextStep.role || user?.role === 'admin');
  const blocked = contract.summary.missing_count > 0 || !contract.documents.length || contract.documents.some((d) => !d.file_available);
  const unverified = contract.checks.some((c) => c.status !== 'PASS');
  const ntsNotRun = contract.checks.some(isUnverifiedBusinessStatus);
  const ackText = `${overview.issues.length ? `남은 확인 항목 ${overview.issues.length}건을 직접 검토했습니다.` : '필수 서류를 검토했습니다.'}${ntsNotRun ? ' 국세청 진위 조회는 이 앱에서 하지 않았음을 확인합니다.' : ''}`;
  const canSubmit = !busy && !blocked && note.trim().length > 0 && (!unverified || ack && note.trim().length >= 10);
  const submit = async (decision:'CONFIRMED' | 'RETURNED') => {
    if (!state?.next_step || !myTurn) return;
    setBusy(true);setError('');
    try {
      await requestJson(`/api/pilot/contracts/${contract.contract_id}/approvals`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ step:state.next_step,decision,note:note.trim(),revision:wf.revision,fingerprint:wf.fingerprint,acknowledge_unverified:ack })});
      setNote('');setAck(false);setReload((n) => n+1);await onChanged();
    } catch(e) {
      setError(e instanceof Error ? e.message : '처리하지 못했습니다.');setNote('');setAck(false);
      try { await onChanged();setReload((n) => n+1); } catch { setQueryError('최신 상태를 불러오지 못했습니다. 다시 불러오세요.');setState(null); }
    } finally {setBusy(false);}
  };
  const currentSignoff = state?.history.find((h) => h.current);
  const displayNote = (value: string) => masked ? maskResidentNumber(maskBusinessNumber(value)) : value;
  const currentFinal = approval === 'CONFIRMED' ? [...wf.reviews].filter((r) => r.revision === wf.revision && r.decision === 'CONFIRMED').sort((a,b) => b.review_id-a.review_id)[0] : null;
  const opinions = [...(state?.history ?? []).map((h) => ({id:`s${h.signoff_id}`, name:h.actor_name,note:h.note,at:h.created_at,label:'담당 검토',tone:'green' as const})),...wf.reviews.map((r) => ({id:`r${r.review_id}`,name:r.actor_name,note:r.note,at:r.created_at,label:r.decision === 'RETURNED' ? '반려' : '최종 결재',tone:r.decision === 'RETURNED' ? 'red' as const : 'green' as const}))].sort((a,b) => b.at.localeCompare(a.at));
  const changes = events.filter((e) => ['EXTRACT_CORRECTED','DOCUMENT_REISSUED'].includes(e.type)).map((e) => ({ event:e, lines:e.details_available ? fieldChanges(e.type === 'DOCUMENT_REISSUED' ? e.data.previous_fields : e.data.before,e.type === 'DOCUMENT_REISSUED' ? e.data.new_fields : e.data.after) : [] })).filter((r) => r.lines.length);

  const changeRows=changes.flatMap(({event,lines})=>lines.map((line,index)=>{const split=line.indexOf(' → '),space=line.indexOf(' ');return {key:`${event.event_id}-${index}`,doc:event.document_id?contract.documents.find(d=>d.document_id===event.document_id):null,event,label:line.slice(0,space),before:line.slice(space+1,split),after:line.slice(split+3)};}));
  // 합계 변경은 먼저 보여 주고 세부 금액은 접어 둔다. 이력의 금액을 현재 값으로 덮어쓰지 않는다.
  const primaryChanges=changeRows.filter(r=>!['공급가액','세액'].includes(r.label)||!changeRows.some(other=>other.event.event_id===r.event.event_id&&other.label==='합계금액'));
  const extraChanges=changeRows.filter(r=>!primaryChanges.includes(r));
  const receipts=requests.flatMap(request=>(request.bundle?.items??[]).filter(item=>item.status==='RECEIVED'&&item.issue_key.startsWith('missing:')).map(item=>({request,item,doc:contract.documents.find(d=>d.document_id===currentDocumentFor(item,contract.documents))})));
  const actors=steps.map((step,i)=>{const done=approval==='CONFIRMED'||!!state&&i<state.completed_steps;return {done,name:step.role==='operator'&&done?currentSignoff?.actor_name:step.role==='representative'&&done?currentFinal?.actor_name:step.role===user?.role?user.display_name:ROLE_KO[step.role]};});
  return <div className="approval-grid"><div className="approval-main">
    <Surface title="결재 요약"><dl className="summary"><div><dt>필수 서류</dt><dd>{contract.summary.submitted_document_count}/{contract.summary.required_document_count}종 <Badge tone={blocked?'amber':'green'}>{blocked?'보완 필요':'등록 완료'}</Badge></dd></div><div><dt>자동 검사</dt><dd>{overview.issues.length?<Badge tone="amber">확인 필요 {overview.issues.length}건</Badge>:<><Check size={15} className="green-text"/>적용된 검사 {contract.checks.filter(c=>c.status==='PASS').length}개 일치</>}</dd></div>{steps.length>1&&<div><dt>담당 검토</dt><dd>{currentSignoff?`${currentSignoff.actor_name} · ${kst(currentSignoff.created_at)}`:'미완료'}</dd></div>}<div><dt>국세청 진위 조회</dt><dd><Badge>미조회</Badge></dd></div></dl></Surface>
    <Surface title="자료 변경 내역" sub="조회된 기록의 이전 값 → 변경 값">
      {eventLoading ? <p className="review-note" role="status">변경 기록 조회 중…</p> : eventError ? <p className="story-alert" role="alert">{eventError}</p> : primaryChanges.length || receipts.length ? <>
        <div className="table-wrap"><table className="changes"><thead><tr><th>서류·항목</th><th>이전</th><th>변경 후</th><th/></tr></thead><tbody>
          {primaryChanges.map(r=><tr key={r.key}><td><strong title={r.doc?.original_file_name}>{r.doc ? DOCUMENT_LABEL[r.doc.document_type] : r.event.title}</strong><small className="sub">{r.label}</small></td><td className="old">{r.before}</td><td><strong>{r.after}</strong><small className="sub">{kst(r.event.occurred_at)}</small></td><td>{r.doc&&onOpenDocumentId&&<button className="text-button" onClick={()=>onOpenDocumentId(r.doc!.document_id)}>원문<ArrowUpRight size={14}/></button>}</td></tr>)}
          {receipts.map(({request,item,doc})=><tr key={`receipt-${request.request_id}-${item.item_id}`}><td><strong>{item.document_type ? DOCUMENT_LABEL[item.document_type] : item.title}</strong><small className="sub">요청 #{request.request_id} · 수령 기록</small></td><td className="old">요청 당시 누락</td><td><strong>받음 기록</strong><small className="sub">자동 검사와 별도</small></td><td>{doc&&onOpenDocumentId&&<button className="text-button" onClick={()=>onOpenDocumentId(doc.document_id)}>원문<ArrowUpRight size={14}/></button>}</td></tr>)}
        </tbody></table></div>
        {extraChanges.length>0&&<details className="more-fields"><summary>세부 금액 변경 {extraChanges.length}개</summary><div className="review-note">{extraChanges.map(r=><p key={r.key}>{r.label} · {r.before} → {r.after}</p>)}</div></details>}
      </> : <p className="review-note">기록된 값 변경이 없습니다.</p>}
    </Surface>
    {currentSignoff&&<Surface title="담당 검토 의견"><div className="review-note"><p>{displayNote(currentSignoff.note)}</p><small>{currentSignoff.actor_name} · {kst(currentSignoff.created_at)}</small></div></Surface>}
    </div><div className="approval-side"><Surface title={nextStep?.role==='representative'?'대표 결재':nextStep?.label||'결재'} action={<Badge tone={myTurn?'blue':'gray'}>{approval==='CONFIRMED'?'완료':myTurn?`${ROLE_KO[nextStep!.role]} 차례`:'대기'}</Badge>} className="decision">
    <div className="decision-body"><div className="approval-line" aria-label="결재 단계">{steps.map((step,i)=><React.Fragment key={i}>{i>0&&<div className="line"/>}<div><span className={`person ${actors[i].done?'complete':nextIndex===i?'pending':''}`}>{actors[i].done?<Check size={18}/>:actors[i].name?.charAt(0)||i+1}</span><strong>{actors[i].name||ROLE_KO[step.role]}</strong><small>{step.label} {actors[i].done?'완료':nextIndex===i?'대기':'예정'}</small></div></React.Fragment>)}</div>
    {approval==='CONFIRMED'?<div className="decision-state"><CheckCheck size={26}/><strong>결재 완료</strong><small>자료가 바뀌면 다시 결재합니다.</small></div>:myTurn?<>{blocked&&<p className="story-alert" role="alert">필수 서류나 원본이 없어 승인할 수 없습니다.</p>}<label className="field-label" htmlFor="approval-note">결재 의견 <small>필수</small></label><textarea id="approval-note" rows={3} maxLength={2000} placeholder="검토 내용과 승인·반려 사유" value={note} onChange={e=>setNote(e.target.value)}/><small className="help">{unverified?'미확인 사항 확인 · 의견 10자 이상':'검토 의견을 입력하세요.'}</small>{unverified&&<label className="check-label"><input type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)}/><span>{ackText}</span></label>}<div className="decision-buttons">{isLast&&<button className="button" disabled={busy||!note.trim()} onClick={()=>void submit('RETURNED')}>반려</button>}<button className="button primary" disabled={!canSubmit} onClick={()=>void submit('CONFIRMED')}><Check size={16}/>{busy?'저장 중…':isLast?'승인':`${nextStep!.label} 완료`}</button></div></>:<div className="decision-state"><CheckCheck size={26}/><strong>{nextStep?`${ROLE_KO[nextStep.role]} ${nextStep.label} 대기`:queryError?'결재 상태 조회 실패':'결재 상태 확인 중'}</strong></div>}
    {queryError&&<p className="story-alert" role="alert">{queryError}<button className="text-button" onClick={()=>setReload(n=>n+1)}>다시 불러오기</button></p>}{error&&<p className="story-alert" role="alert">저장하지 못했습니다: {error}</p>}
    </div></Surface><Surface title="검토·결재 의견 이력" className="opinion-panel"><div className="opinions">{opinions.slice(0,3).map(o=><article key={o.id}><div><Badge tone={o.tone}>{o.label}</Badge><small>{kst(o.at)}</small></div><p>{displayNote(o.note)}</p><small>{o.name}</small></article>)}{approval!=='CONFIRMED'&&<article><div><Badge>대표 결재</Badge></div><p>아직 결정된 의견이 없습니다.</p></article>}</div></Surface></div></div>;
};
