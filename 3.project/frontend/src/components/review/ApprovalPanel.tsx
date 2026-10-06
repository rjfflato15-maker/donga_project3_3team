import React, { useEffect, useMemo, useState } from 'react';
import { Check, CheckCheck } from 'lucide-react';
import { ContractDetail } from '../../types';
import { requestJson } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { buildReviewOverview, isUnverifiedBusinessStatus } from '../../utils/reviewSummary';
import { ActivityItem, fieldChanges, kst } from './ActivityTimeline';
import { Surface, Badge } from '../ui/Surface';
import { maskBusinessNumber, maskResidentNumber } from '../../utils/masking';

export interface ApprovalState {
  steps: { role: 'operator' | 'representative'; label: string }[];
  completed_steps: number; next_step: number | null; status: 'PENDING' | 'IN_PROGRESS' | 'CONFIRMED';
  history: { signoff_id: number; actor_name: string; note: string; created_at: string; current: boolean }[];
}
const ROLE_KO = { operator: '담당자', representative: '대표' } as const;
interface Props { contract: ContractDetail; onChanged: () => Promise<void>; embedded?: boolean; masked?: boolean }

export const ApprovalPanel: React.FC<Props> = ({ contract, onChanged, masked = true }) => {
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
  return <div className="cp-approval-grid">
    <div className="cp-approval-main">
      <Surface title="결재 요약" action={approval === 'STALE' && <Badge tone="blue">재결재</Badge>}>
        <dl className="cp-summary"><div><dt>필수 서류</dt><dd>{contract.summary.submitted_document_count}/{contract.summary.required_document_count}종 <Badge tone={blocked ? 'amber' : 'green'}>{blocked ? '보완 필요' : '등록 완료'}</Badge></dd></div><div><dt>자동 검사</dt><dd>{overview.issues.length ? <Badge tone="amber">남은 확인 {overview.issues.length}건</Badge> : <><Check size={15} />적용된 검사 {contract.checks.filter((c) => c.status === 'PASS').length}개 일치</>}</dd></div>{steps.length > 1 && <div><dt>담당 검토</dt><dd>{currentSignoff ? `${currentSignoff.actor_name} · ${kst(currentSignoff.created_at)}` : '미완료'}</dd></div>}<div><dt>국세청 진위 조회</dt><dd><Badge>미조회</Badge></dd></div></dl>
        <div className="cp-panel-footer"><span>자동 검사와 사람의 원문 확인은 별도 기록입니다.</span></div>
      </Surface>
      <Surface title="최근 기록된 변경" sub="현재 조회된 처리 기록 기준">
        {eventLoading ? <p role="status" className="cp-panel-body cp-muted">변경 기록 조회 중…</p> : eventError ? <p role="alert" className="cp-panel-body">변경 기록 조회 실패: {eventError}</p> : changes.length ? <div className="cp-table-scroll"><table className="cp-data-table cp-changes"><thead><tr><th>서류·처리</th><th>변경 내용</th></tr></thead><tbody>{changes.map(({event,lines}) => <tr key={event.event_id}><td><strong>{event.title}</strong><small className="cp-sub">{kst(event.occurred_at)} · {event.actor_name}</small>{event.document_id != null && <small className="cp-sub">문서 #{event.document_id}</small>}</td><td>{lines.map((line,i) => <div key={i}>{line}</div>)}</td></tr>)}</tbody></table></div> : <p className="cp-panel-body cp-muted">조회된 기록에 값 변경이 없습니다.</p>}
      </Surface>
      {currentSignoff && <Surface title="담당 검토 의견"><div className="cp-panel-body"><p>{displayNote(currentSignoff.note)}</p><small className="cp-sub">{currentSignoff.actor_name} · {kst(currentSignoff.created_at)}</small></div></Surface>}
    </div>
    <div className="cp-approval-side">
      <Surface title={nextStep ? nextStep.label : '결재'} action={<Badge tone={myTurn ? 'blue' : 'gray'}>{approval === 'CONFIRMED' ? '완료' : myTurn ? '내 차례' : '대기'}</Badge>} className="cp-decision">
        <div className="cp-decision-body">
          <ol className="cp-approval-line" aria-label="결재 단계">{steps.map((step,i) => {
            const done = approval === 'CONFIRMED' || !!state && i < state.completed_steps;
            const actor = step.role === 'operator' && done ? currentSignoff?.actor_name : step.role === 'representative' && done ? currentFinal?.actor_name : null;
            return <li key={i}><span className={`cp-person ${done ? 'complete' : nextIndex === i ? 'pending' : ''}`}>{done ? <Check size={18}/> : i+1}</span><strong>{actor || ROLE_KO[step.role]}</strong><small>{step.label} · {done ? '완료' : nextIndex === i ? '대기' : '예정'}</small></li>;
          })}</ol>
          {approval === 'CONFIRMED' ? <div className="cp-decision-state"><CheckCheck size={25}/><strong>결재 완료</strong><small>자료가 바뀌면 다시 결재합니다.</small></div> : myTurn ? <>
            {blocked && <p className="cp-alert">필수 서류나 원본이 없어 승인할 수 없습니다.</p>}
            <label className="cp-field-label" htmlFor="approval-note">결재 의견 <small>필수</small></label><textarea id="approval-note" rows={3} maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} placeholder="검토 내용과 승인·반려 사유" />
            <small className="cp-help">{unverified ? '남은 확인이 있어 의견 10자 이상 필요합니다.' : '의견을 남겨 주세요.'}</small>
            {unverified && <label className="cp-check-label"><input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} /><span>{ackText}</span></label>}
            <div className="cp-decision-buttons">{isLast && <button className="cp-button" disabled={busy || !note.trim()} onClick={() => void submit('RETURNED')}>반려</button>}<button className="cp-button cp-primary" disabled={!canSubmit} onClick={() => void submit('CONFIRMED')}><Check size={15}/>{busy ? '저장 중…' : isLast ? '승인' : `${nextStep!.label} 완료`}</button></div>
          </> : <div className="cp-decision-state"><CheckCheck size={25}/><strong>{nextStep ? `${ROLE_KO[nextStep.role]} ${nextStep.label} 대기` : queryError ? '결재 상태 조회 실패' : '결재 상태 확인 중'}</strong></div>}
          {queryError && <p role="alert" className="cp-alert">{queryError}<button className="cp-text-button" onClick={() => setReload((n) => n+1)}>다시 불러오기</button></p>}
          {error && <p role="alert" className="cp-alert">저장하지 못했습니다: {error}</p>}
        </div>
      </Surface>
      <Surface title="결재 의견 이력"><div className="cp-opinions">{opinions.slice(0,3).map((o) => <article key={o.id}><div><Badge tone={o.tone}>{o.label}</Badge><small>{kst(o.at)}</small></div><p>{displayNote(o.note)}</p><small>{o.name}</small></article>)}{!opinions.length && <p className="cp-muted">기록된 결재 의견 없음</p>}</div></Surface>
    </div>
  </div>;
};
