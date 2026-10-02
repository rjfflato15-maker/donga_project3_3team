import React, { useEffect, useMemo, useState } from 'react';
import { ContractDetail } from '../../types';
import { requestJson } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { buildReviewOverview } from '../../utils/reviewSummary';
import { CheckCircle2 } from 'lucide-react';

interface ApprovalState {
  steps: { role: 'operator' | 'representative'; label: string }[];
  completed_steps: number;
  next_step: number | null;
  status: 'PENDING' | 'IN_PROGRESS' | 'CONFIRMED';
  history: { signoff_id: number; actor_name: string; note: string; created_at: string; current: boolean }[];
}

const ROLE_KO = { operator: '담당자', representative: '대표' } as const;

interface Props {
  contract: ContractDetail;
  onChanged: () => Promise<void>;
}

export const ApprovalPanel: React.FC<Props> = ({ contract, onChanged }) => {
  const { user } = useAuth();
  const [state, setState] = useState<ApprovalState | null>(null);
  const [note, setNote] = useState('');
  const [ack, setAck] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const overview = useMemo(() => buildReviewOverview(contract), [contract]);
  const wf = contract.workflow;

  const [reload, setReload] = useState(0);
  useEffect(() => {
    setNote(''); setAck(false);
    const controller = new AbortController();
    requestJson<ApprovalState>(`/api/pilot/contracts/${contract.contract_id}/approvals`, { signal: controller.signal })
      .then((v) => { setState(v); setError(''); })
      .catch((e) => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, [contract.contract_id, contract.updated_at, wf?.revision, wf?.approval_status, reload]);

  if (!wf) return null;
  const approval = wf.approval_status;
  const steps = state?.steps ?? [{ role: 'representative' as const, label: '최종 확인' }];
  const nextIndex = state?.next_step ? state.next_step - 1 : null;
  const nextStep = nextIndex !== null ? steps[nextIndex] : null;
  const isLast = nextIndex !== null && nextIndex === steps.length - 1;
  const myTurn = !!nextStep && (user?.role === nextStep.role || user?.role === 'admin');
  const blocked = contract.summary.missing_count > 0 || !contract.documents.length || contract.documents.some((d) => !d.file_available);
  const unverified = contract.checks.some((c) => c.status !== 'PASS');
  const canSubmit = !busy && !blocked && note.trim().length > 0 && (!unverified || (ack && note.trim().length >= 10));

  const submit = async (decision: 'CONFIRMED' | 'RETURNED') => {
    if (!state?.next_step) return;
    setBusy(true); setError('');
    try {
      await requestJson(`/api/pilot/contracts/${contract.contract_id}/approvals`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ step: state.next_step, decision, note: note.trim(), revision: wf.revision, fingerprint: wf.fingerprint, acknowledge_unverified: ack }),
      });
      setReload((n) => n + 1);
      await onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : '처리하지 못했습니다.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 space-y-4" aria-labelledby="approval-title">
      <div className="flex flex-wrap items-center gap-3">
        <h2 id="approval-title" className="flex items-center gap-2 font-bold text-slate-900"><CheckCircle2 className="h-5 w-5 text-indigo-600" /> 결재</h2>
        <ol className="flex flex-wrap gap-1 text-xs" aria-label="결재 단계">
          {steps.map((s, i) => {
            const done = approval === 'CONFIRMED' || (state ? i < state.completed_steps : false);
            const current = nextIndex === i;
            return (
              <li key={i} className={`rounded-full px-2.5 py-1 font-semibold ${done ? 'bg-emerald-100 text-emerald-700' : current ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-500'}`}>
                {i + 1}. {s.label} ({ROLE_KO[s.role]}){done ? ' ✓' : ''}
              </li>
            );
          })}
        </ol>
        {approval === 'RETURNED' && <span className="rounded-full bg-rose-100 px-2.5 py-1 text-xs font-bold text-rose-700">반려됨 · 다시 처리 필요</span>}
        {approval === 'STALE' && !state?.completed_steps && <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-bold text-amber-800">자료가 바뀌어 다시 결재 필요</span>}
      </div>

      {approval === 'CONFIRMED' ? (
        <p className="rounded-xl bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-800">결재가 끝났습니다. 서류나 계약 기준이 바뀌면 다시 결재가 필요합니다.</p>
      ) : (
        <>
          <div className={`rounded-xl px-4 py-3 text-sm ${overview.issues.length ? 'bg-amber-50 text-amber-900' : 'bg-emerald-50 text-emerald-900'}`}>
            {overview.issues.length ? `남은 확인 항목 ${overview.issues.length}건이 있습니다. 위의 카드를 확인한 뒤 결재하세요.` : '남은 확인 항목이 없습니다.'}
            {blocked && <div className="mt-1 text-xs">필수 서류나 원본이 없으면 결재할 수 없습니다. 먼저 보완해 주세요.</div>}
          </div>

          {myTurn ? (
            <div className="space-y-3">
              <label className="block text-sm font-semibold text-slate-700" htmlFor="approval-note">
                {isLast ? '결재 메모' : '검토 메모'} <span className="font-normal text-slate-500">(무엇을 확인했는지 남겨 주세요)</span>
              </label>
              <textarea id="approval-note" value={note} onChange={(e) => setNote(e.target.value)} rows={3} maxLength={2000}
                className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800"
                placeholder="예: 세금계산서 수정본으로 금액 일치 확인, 나머지 서류 이상 없음" />
              {unverified && (
                <label className="flex items-start gap-2 text-sm text-slate-600">
                  <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} className="mt-1 h-4 w-4 accent-indigo-600" />
                  자동으로 확인되지 않은 항목(국세청 조회 미연동 포함)을 직접 검토했습니다. <span className="text-slate-400">메모 10자 이상 필요</span>
                </label>
              )}
              <div className="flex flex-wrap gap-2">
                <button disabled={!canSubmit} onClick={() => void submit('CONFIRMED')}
                  className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-40">
                  {nextStep!.label} 완료
                </button>
                {isLast && (
                  <button disabled={busy || !note.trim()} onClick={() => void submit('RETURNED')}
                    className="rounded-lg border border-rose-200 bg-white px-4 py-2 text-sm font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-40">
                    반려 · 담당자에게 돌려보내기
                  </button>
                )}
              </div>
            </div>
          ) : (
            nextStep && (
              <p className="rounded-xl bg-indigo-50 px-4 py-3 text-sm text-indigo-900">
                다음 단계: <b>{nextStep.label}</b> ({ROLE_KO[nextStep.role]} 계정에서 진행합니다)
              </p>
            )
          )}
        </>
      )}
      {error && <p role="alert" className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
    </section>
  );
};
