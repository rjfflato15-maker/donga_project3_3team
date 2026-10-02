import React, { useEffect, useState } from 'react';
import { CheckCircle2, History, X } from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { AuditEntry, ContractDetail } from '../types';

export const approvalLabels: Record<string, string> = { PENDING: '대표 확인 전', CONFIRMED: '대표 확인 완료', RETURNED: '보완 요청', STALE: '자료 변경 · 재확인' };
const actions: Record<string, string> = { CONTRACT_CREATED: '계약 등록', CONTRACT_UPDATED: '계약 기준 수정', CONTRACT_DELETED: '계약 제외', DOCUMENT_UPLOAD: '원본 등록', DOCUMENT_DELETE: '증빙 제외', ORIGINAL_RESTORED: '원본 복구', EXTRACT_CORRECTED: '추출값 보정', ORIGINAL_VIEW: '원본 열람 요청', ORIGINAL_DOWNLOAD: '원본 다운로드 요청', MASKED_VIEW: '가린 문서 열람 요청', MASKED_DOWNLOAD: '가린 문서 다운로드 요청', ORIGINAL_PREVIEW: '원본 미리보기', MASKED_PREVIEW: '가린 원본 미리보기', ORIGINAL_TEXT_PREVIEW: '원문 텍스트 보기', MASKED_TEXT_PREVIEW: '가린 텍스트 보기', REPRESENTATIVE_CONFIRMED: '대표 확인 완료', REPRESENTATIVE_RETURNED: '대표 보완 요청', RULE_VALIDATION: '규칙 재검수', AUTO_CONTRACT_CREATED: '문서로 계약 등록', COMPANY_POLICY_UPDATED: '회사 정책 변경', RESUBMISSION_REQUEST_RECORDED: '재제출 요청 기록', RESUBMISSION_REQUEST_RESOLVED: '재제출 요청 처리', APPROVAL_FIRST_STAGE: '1단계 검토 완료', COMPANY_APPROVAL_POLICY_UPDATED: '회사 결재 설정 변경' };
for (const action of ['ORIGINAL_VIEW', 'ORIGINAL_DOWNLOAD', 'MASKED_VIEW', 'MASKED_DOWNLOAD', 'ORIGINAL_PREVIEW', 'MASKED_PREVIEW', 'ORIGINAL_TEXT_PREVIEW', 'MASKED_TEXT_PREVIEW']) {
  actions[action + '_REQUEST'] = actions[action].replace(/ 요청$/, '') + ' 요청';
}
const formatTime = (value: string) => new Date(/Z$|[+]\d\d:/.test(value) ? value : value + 'Z').toLocaleString('ko-KR');
const button = 'rounded-xl px-4 py-2 text-xs font-bold disabled:opacity-40';

export const PilotReviewPanel: React.FC<{ contract: ContractDetail; onChanged: () => Promise<void>; historyOnly?: boolean }> = ({ contract, onChanged, historyOnly = false }) => {
  const { user } = useAuth();
  const representative = user?.role === 'representative' || user?.role === 'admin';
  const [note, setNote] = useState('');
  const [acknowledge, setAcknowledge] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [activity, setActivity] = useState<AuditEntry[]>([]);
  const [snapshot, setSnapshot] = useState<Awaited<ReturnType<typeof api.reviewSnapshot>> | null>(null);
  useEffect(() => {
    setNote(''); setAcknowledge(false); setSnapshot(null); setActivity([]); setError('');
    let active = true;
    api.audit(contract.contract_id).then(value => { if (active) setActivity(value); }).catch(reason => { if (active) setError(reason.message); });
    return () => { active = false; };
  }, [contract]);
  const act = async (operation: () => Promise<void>) => {
    setBusy(true); setError('');
    try { await operation(); } catch (reason) { setError(reason instanceof Error ? reason.message : '처리하지 못했습니다.'); }
    finally { setBusy(false); }
  };
  const review = async (decision: string) => {
    if (!contract.workflow) return;
    await api.review(contract.contract_id, { decision, note, acknowledge_unverified: acknowledge, revision: contract.workflow.revision, fingerprint: contract.workflow.fingerprint });
    await onChanged();
  };
  const blocked = contract.summary.missing_count > 0 || !contract.documents.length || contract.documents.some(doc => !doc.file_available);
  const needsCheck = contract.checks.some(check => check.status !== 'PASS');
  const status = contract.workflow?.approval_status || 'PENDING';
  if (historyOnly) return <section className="bg-white rounded-2xl border border-slate-200/80 p-5 space-y-4">
    <button className="flex items-center gap-2 text-sm font-bold text-indigo-600" onClick={() => setHistoryOpen(value => !value)}><History size={15} />{historyOpen ? '처리 기록 접기' : '처리 기록 보기 (결재·수정·열람)'}</button>
    {error && <p role="alert" className="rounded-xl bg-rose-50 p-3 text-xs text-rose-800">{error}</p>}
    {historyOpen && <div className="space-y-4 border-t border-slate-100 pt-4">
      <h3 className="text-sm font-bold">결재 기록</h3>{contract.workflow?.reviews.map(item => <div key={item.review_id} className="rounded-xl border border-slate-200 p-3 text-xs"><p className="font-bold">{approvalLabels[item.decision]} · 버전 {item.revision} · {item.actor_name}</p><p className="mt-1 text-slate-500">{formatTime(item.created_at)}</p><p className="mt-2 whitespace-pre-wrap">{item.note}</p><button className="mt-2 font-bold text-indigo-600" onClick={() => void act(async () => { setSnapshot(await api.reviewSnapshot(item.review_id)); })}>당시 검사 결과</button></div>)}{!contract.workflow?.reviews.length && <p className="text-xs text-slate-500">결재 기록이 없습니다.</p>}
      {snapshot && <div className="rounded-xl bg-slate-50 p-4 text-xs"><div className="flex justify-between"><strong>결재 당시 결과</strong><button aria-label="이전 결과 닫기" onClick={() => setSnapshot(null)}><X size={15} /></button></div>{snapshot.snapshot.checks.map((item, index) => <p key={index} className="mt-2">[{item.status}] {item.message}</p>)}</div>}
      <h3 className="text-sm font-bold">최근 활동 · 최대 100개</h3>{activity.map(item => <div key={item.event_id} className="rounded-xl bg-slate-50 p-3 text-xs"><p><strong>{actions[item.action] || item.action}</strong> · {item.actor_name} · {formatTime(item.created_at)}</p>{typeof item.details.note === 'string' && <p className="mt-1 text-slate-500">{item.details.note}</p>}</div>)}
    </div>}
  </section>;
  return <section className="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-sm space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="flex items-center gap-2 text-lg font-bold text-slate-900"><CheckCircle2 className="w-5 h-5 text-indigo-600" />대표 최종 확인</h2><span className={'rounded-full border px-3 py-1 text-xs font-bold ' + (status === 'CONFIRMED' ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-amber-200 bg-amber-50 text-amber-800')}>{approvalLabels[status]} · 버전 {contract.workflow?.revision}</span></div>
    <p className="text-xs leading-6 text-slate-500">자동 검수와 대표 확인은 별도로 기록합니다. 원본과 경고를 직접 확인하고 근거를 남기세요. 확인 후 자료가 바뀌면 재확인이 필요합니다.</p>
    <div className="flex flex-wrap gap-3 rounded-xl bg-slate-50 p-3 text-xs font-semibold text-slate-600"><span>계약 금액 기준: {contract.workflow?.amount_basis === 'TOTAL' ? '부가세 포함 합계' : contract.workflow?.amount_basis === 'SUPPLY' ? '공급가액' : '미확인'}</span><span>명시 세액: {contract.workflow?.tax_amount == null ? '미확인' : contract.workflow.tax_amount.toLocaleString() + '원'}</span><span>{contract.workflow?.payment_mode === 'INSTALLMENT' ? '분할 지급' : '전액 지급'}</span></div>
    {error && <p role="alert" className="rounded-xl bg-rose-50 p-3 text-xs text-rose-800">{error}</p>}
    {representative ? <>
      {blocked && <p className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">필수 증빙 또는 원본이 없습니다. 담당자에게 보완을 요청한 후 최종 확인하세요.</p>}
      <label className="block text-xs font-bold text-slate-700">확인 근거 / 보완 요청<textarea className="mt-2 w-full rounded-xl border border-slate-300 px-3 py-2 text-xs font-medium" rows={3} maxLength={2000} value={note} onChange={e => setNote(e.target.value)} placeholder="어떤 원본을 확인했는지와 처리 근거를 남겨 주세요." /></label>
      {needsCheck && <label className="flex items-start gap-2 text-xs leading-6 text-slate-600"><input className="mt-1" type="checkbox" checked={acknowledge} onChange={e => setAcknowledge(e.target.checked)} />불일치·국세청 미확인 등 자동 확인되지 않은 항목을 직접 검토했습니다.</label>}
      <div className="flex gap-2"><button disabled={busy || blocked || !note.trim() || (needsCheck && (!acknowledge || note.trim().length < 10))} className={button + ' bg-indigo-600 text-white hover:bg-indigo-700'} onClick={() => void act(() => review('CONFIRMED'))}>최종 확인 완료</button><button disabled={busy || !note.trim()} className={button + ' border border-slate-200 bg-slate-100 text-slate-700'} onClick={() => void act(() => review('RETURNED'))}>보완 요청</button></div>
    </> : <p className="rounded-xl bg-indigo-50/60 p-3 text-xs font-semibold text-indigo-800">담당자는 자료를 보완하고, 대표 계정이 최종 확인을 남깁니다.</p>}
    <button className="flex items-center gap-2 text-xs font-bold text-indigo-600" onClick={() => setHistoryOpen(value => !value)}><History size={15} />{historyOpen ? '확인 · 활동 기록 접기' : '확인 · 활동 기록 보기'}</button>
    {historyOpen && <div className="space-y-4 border-t border-slate-100 pt-4">
      <h3 className="text-sm font-bold">대표 확인 기록</h3>{contract.workflow?.reviews.map(item => <div key={item.review_id} className="rounded-xl border border-slate-200 p-3 text-xs"><p className="font-bold">{approvalLabels[item.decision]} · 버전 {item.revision} · {item.actor_name}</p><p className="mt-1 text-slate-500">{formatTime(item.created_at)}</p><p className="mt-2 whitespace-pre-wrap">{item.note}</p><button className="mt-2 font-bold text-indigo-600" onClick={() => void act(async () => { setSnapshot(await api.reviewSnapshot(item.review_id)); })}>당시 검수 결과</button></div>)}{!contract.workflow?.reviews.length && <p className="text-xs text-slate-500">확인 기록이 없습니다.</p>}
      {snapshot && <div className="rounded-xl bg-slate-50 p-4 text-xs"><div className="flex justify-between"><strong>확인 당시 결과</strong><button aria-label="이전 결과 닫기" onClick={() => setSnapshot(null)}><X size={15} /></button></div>{snapshot.snapshot.checks.map((item, index) => <p key={index} className="mt-2">[{item.status}] {item.message}</p>)}</div>}
      <h3 className="text-sm font-bold">최근 활동 · 최대 100개</h3>{activity.map(item => <div key={item.event_id} className="rounded-xl bg-slate-50 p-3 text-xs"><p><strong>{actions[item.action] || item.action}</strong> · {item.actor_name} · {formatTime(item.created_at)}</p>{typeof item.details.note === 'string' && <p className="mt-1 text-slate-500">{item.details.note}</p>}</div>)}
    </div>}
  </section>;
};
