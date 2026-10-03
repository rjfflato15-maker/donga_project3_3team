import React, { useState } from 'react';
import { ContractDetail } from '../../types';
import { requestJson } from '../../api/client';
import { isReadingCheck, ruleLabel } from '../../utils/reviewSummary';
import { Loader2, Sparkles } from 'lucide-react';

export interface AssignDraft { title: string; memo: string; document_id: number | null }
interface Item {
  issue_id: string; rule_id: string; field: string; status: string; reason: string; document_id: number | null;
  next_action: 'DRAFT_REQUEST_AFTER_REVIEW' | 'INTERNAL_PREPARATION' | 'INTERNAL_REVIEW' | 'MANUAL_CONFIRMATION' | 'VERIFY_EXTRACTION_FIRST';
  request_draft: { subject: string; body: string } | null;
  assignment_draft: { title: string; memo: string } | null;
}
interface Preview { items: Item[]; recheck_differences: { rule_id: string; field: string }[] }

/** 화면 규칙과 맞춘다: 국세청 미연동 안내는 할 일에서 빼고, 앱이 못 읽은 값은 거래처 요청 전에 원문부터 본다 */
export const adaptItems = (items: Item[]): Item[] => items
  .filter((it) => it.rule_id !== 'BUSINESS_STATUS')
  .map((it) => isReadingCheck({ rule_id: it.rule_id, status: it.status } as Parameters<typeof isReadingCheck>[0])
    ? { ...it, next_action: 'VERIFY_EXTRACTION_FIRST', request_draft: null }
    : it);

const ACTION_KO: Record<Item['next_action'], string> = {
  DRAFT_REQUEST_AFTER_REVIEW: '원문 확인 뒤 거래처 요청',
  INTERNAL_PREPARATION: '사내에서 준비',
  INTERNAL_REVIEW: '사내에서 원문·기준 확인',
  MANUAL_CONFIRMATION: '담당자가 따로 확인',
  VERIFY_EXTRACTION_FIRST: '읽은 값부터 확인',
};

interface Props {
  contract: ContractDetail;
  canEdit: boolean;
  onAssign?: (draft: AssignDraft) => void;
  onRequest: (item: { document_id: number | null; field: string }) => void;
  onOpenDocument?: (documentId: number) => void;
}

/** 검수 도우미: 저장된 자료로 규칙을 메모리에서 다시 돌려 할 일 초안만 만든다. 저장·발송하지 않는다 */
export const AssistantPreview: React.FC<Props> = ({ contract, canEdit, onAssign, onRequest, onOpenDocument }) => {
  const [data, setData] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [moved, setMoved] = useState<Set<string>>(new Set());
  const run = async () => {
    setBusy(true); setError('');
    try {
      const res = await requestJson<Preview>(`/api/pilot/contracts/${contract.contract_id}/assistant-preview`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ revision: contract.workflow?.revision, fingerprint: contract.workflow?.fingerprint }),
      });
      setData({ ...res, items: adaptItems(res.items) });
      setMoved(new Set());
    } catch (e) {
      setError(e instanceof Error ? e.message : '초안을 만들지 못했습니다.');
    } finally { setBusy(false); }
  };
  if (!contract.workflow?.fingerprint) return null;

  if (!data) return (
    <div className="flex flex-wrap items-center gap-2">
      <button onClick={() => void run()} disabled={busy} className="inline-flex items-center gap-1.5 rounded-lg border border-violet-300 bg-violet-50 px-3 py-1.5 text-sm font-semibold text-violet-800 hover:bg-violet-100 disabled:opacity-50">
        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />} 할 일 정리 (검수 도우미)
      </button>
      <span className="text-xs text-slate-500">항목마다 누가 무엇을 할지 초안을 만듭니다. 저장·발송은 하지 않습니다.</span>
      {error && <span role="alert" className="text-xs text-rose-600">{error}</span>}
    </div>
  );

  return (
    <section className="rounded-2xl border border-violet-200 bg-violet-50/50 p-4 space-y-2" aria-labelledby="assist-title">
      <div className="flex flex-wrap items-center gap-2">
        <h3 id="assist-title" className="font-bold text-violet-900">검수 도우미가 정리한 할 일 {data.items.length}건</h3>
        <span className="text-xs text-violet-700">초안일 뿐입니다 · 저장·발송 안 함 · AI·외부 조회 없이 규칙만 다시 돌림</span>
        <button onClick={() => setData(null)} className="ml-auto text-xs text-slate-500">닫기</button>
      </div>
      {data.recheck_differences.length > 0 && (
        <p className="rounded-lg bg-amber-100 px-3 py-2 text-xs text-amber-900">저장된 검사 결과와 지금 다시 돌린 결과가 {data.recheck_differences.length}곳 다릅니다. 위의 ‘다시 검사’를 눌러 결과를 갱신하세요.</p>
      )}
      <ul className="space-y-2">
        {data.items.map((it) => (
          <li key={it.issue_id} className="rounded-xl bg-white p-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-violet-100 px-2 py-0.5 text-xs font-bold text-violet-800">{ACTION_KO[it.next_action]}</span>
              <b className="text-slate-900">{ruleLabel(it.rule_id)}</b>
            </div>
            <p className="mt-1 text-slate-600">{it.reason}</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {it.assignment_draft && onAssign && canEdit && (
                moved.has(it.issue_id)
                  ? <span className="text-xs font-semibold text-emerald-700">아래 ‘맡기기’ 칸에 옮겼어요</span>
                  : <button onClick={() => { onAssign({ ...it.assignment_draft!, title: `${ruleLabel(it.rule_id)} · ${it.assignment_draft!.title}`, document_id: it.document_id }); setMoved(new Set(moved).add(it.issue_id)); }}
                      className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50">담당자에게 맡기기로 옮기기</button>
              )}
              {it.next_action === 'VERIFY_EXTRACTION_FIRST' && it.document_id != null && onOpenDocument && (
                <button onClick={() => onOpenDocument(it.document_id!)}
                  className="rounded-lg border border-indigo-300 px-2.5 py-1 text-xs font-semibold text-indigo-700 hover:bg-indigo-50">원문 보고 값 확인</button>
              )}
              {it.request_draft && (
                <button onClick={() => onRequest({ document_id: it.document_id, field: it.field })}
                  className="rounded-lg border border-indigo-300 px-2.5 py-1 text-xs font-semibold text-indigo-700 hover:bg-indigo-50">요청 문구 보기</button>
              )}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
};
