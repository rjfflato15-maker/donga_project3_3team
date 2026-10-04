import React, { useMemo, useState } from 'react';
import { ContractListItem } from '../../types';
import { maskVendorName } from '../../utils/masking';
import { Stage, stageOf, STAGE_KO, STAGE_PILL } from '../../utils/stage';
import { Plus, Search } from 'lucide-react';

export interface DashboardItem extends ContractListItem {
  stage?: string | null;
  paid_on?: string | null;
  action_summary?: string;
  waiting_request_count?: number;
  earliest_due_on?: string | null;
  approval_next_step?: number | null;
  open_issue_count?: number;
}

export const stageOfItem = (c: DashboardItem): Stage => stageOf({
  stage: c.stage, approval_status: c.approval_status, paid_on: c.paid_on ?? (c as { payment?: { paid_on?: string } }).payment?.paid_on,
  waiting_request_count: c.waiting_request_count,
  missing_count: Math.max(0, (c.total_docs_count ?? 0) - (c.submitted_docs_count ?? 0)),
  open_issue_count: c.open_issue_count,
});

const today = () => new Date().toISOString().slice(0, 10);

/**
 * 검색: 거래처·계약명은 글자 그대로, 금액은 '2090000', '2,090,000', '2,090,000원'을 같은 값으로 찾는다.
 * 숫자·쉼표·원·공백으로만 된 입력일 때만 금액 정규화를 쓴다.
 */
export function matchesQuery(c: Pick<DashboardItem, 'title' | 'vendor_name' | 'contract_amount'>, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  if (`${c.title} ${c.vendor_name}`.toLowerCase().includes(q)) return true;
  if (/^[\d,\s원]+$/.test(q)) {
    const digits = q.replace(/[^\d]/g, '');
    return digits.length > 0 && String(Math.round(c.contract_amount)).includes(digits);
  }
  return false;
}

/** 표의 '다음 할 일' 한 줄 */
function nextAction(c: DashboardItem, s: Stage, representative: boolean): string {
  switch (s) {
    case 'RECEIVING': return `서류 ${c.submitted_docs_count}/${c.total_docs_count}종 · 빠진 서류를 받으세요`;
    case 'CHECK': {
      const ap = (c.approval_status || '').toUpperCase();
      if (ap === 'RETURNED') return '대표가 돌려보냈어요 · 다시 확인하세요';
      const n = c.open_issue_count ?? 0;
      return `${n ? `확인할 것 ${n}건` : '다시 확인하세요'}${ap === 'STALE' ? ' · 서류가 바뀌었어요' : ''}`;
    }
    case 'WAITING': return '거래처 답을 기다리는 중';
    case 'APPROVAL': return representative ? '결재할 차례예요' : '문제 없음 · 대표 결재를 기다려요';
    case 'PAYMENT': return '대표 결재 끝 · 지급하고 기록하세요';
    default: return c.paid_on ? `${c.paid_on} 지급 완료` : '끝';
  }
}

interface Props {
  contracts: DashboardItem[];
  isMaskingEnabled: boolean;
  canEdit: boolean;
  representative?: boolean;
  onOpen: (contractId: number) => void;
  onNew?: () => void;
  /** 지난 계약 찾기: 끝난 계약까지 모두, 최근 등록 순서 */
  history?: boolean;
}

/** 첫 화면 '할 일': 끝나지 않은 계약을 단계 순서대로, 계약마다 다음 할 일 한 줄과 버튼 하나 */
export const StageDashboard: React.FC<Props> = ({ contracts, isMaskingEnabled, canEdit, representative = false, onOpen, onNew, history = false }) => {
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<Stage | 'all'>('all');
  const withStage = useMemo(() => contracts.map((c) => ({ c, s: stageOfItem(c) })), [contracts]);
  const count = (s: Stage) => withStage.filter((x) => x.s === s).length;
  // 담당자는 손댈 것부터, 대표는 결재할 것부터
  const order: Stage[] = representative
    ? ['APPROVAL', 'PAYMENT', 'CHECK', 'RECEIVING', 'WAITING']
    : ['CHECK', 'RECEIVING', 'PAYMENT', 'WAITING', 'APPROVAL'];
  const active = withStage.filter((x) => x.s !== 'DONE');
  const q = query.trim().toLowerCase();
  const rows = (q || history ? withStage : active)
    .filter((x) => filter === 'all' || x.s === filter)
    .filter((x) => matchesQuery(x.c, q))
    .sort((a, b) => history
      ? b.c.created_at.localeCompare(a.c.created_at)
      : order.indexOf(a.s) - order.indexOf(b.s) || (a.c.earliest_due_on || '9999').localeCompare(b.c.earliest_due_on || '9999'));
  const todo = active.filter((x) => (representative ? ['APPROVAL', 'PAYMENT'] : ['CHECK', 'RECEIVING', 'PAYMENT']).includes(x.s)).length;
  const tiles: { s: Stage; label: string }[] = [
    { s: 'RECEIVING', label: '① 서류 받을 것' },
    { s: 'CHECK', label: '② 확인할 것' },
    { s: 'WAITING', label: '③ 보완 기다리는 중' },
    { s: 'APPROVAL', label: '④ 결재 대기' },
    { s: 'PAYMENT', label: '⑤ 지급할 것' },
  ];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{history ? '지난 계약 찾기' : todo ? `지금 처리할 계약 ${todo}건` : '지금 처리할 계약이 없어요'}</h1>
          <p className="text-sm text-slate-500">{history ? `모든 계약 ${contracts.length}건 · 최근 등록 순서` : representative ? '결재할 계약부터 보여 줍니다.' : '위에서부터 처리하면 됩니다.'}</p>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-200">
            <Search className="h-4 w-4 text-slate-400" />
            <span className="sr-only">계약 검색</span>
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="거래처·계약명·금액"
              className="w-44 bg-white text-slate-800 outline-none" />
          </label>
          {canEdit && onNew && (
            <button onClick={onNew} className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-700">
              <Plus className="h-4 w-4" /> 새 계약 등록
            </button>
          )}
        </div>
      </div>

      <div className={history ? 'hidden' : 'grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6'}>
        {tiles.map((t) => {
          const on = filter === t.s;
          const n = count(t.s);
          return (
            <button key={t.s} onClick={() => setFilter(on ? 'all' : t.s)} aria-pressed={on}
              className={`rounded-xl border bg-white p-3 text-left text-sm transition ${on ? 'border-indigo-500 ring-2 ring-indigo-200' : 'border-slate-200 hover:border-indigo-300'}`}>
              <div className="text-slate-500">{t.label}</div>
              <div className={`text-2xl font-bold tabular-nums ${n ? 'text-slate-900' : 'text-slate-300'}`}>{n}</div>
            </button>
          );
        })}
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm">
          <div className="text-slate-500">끝난 계약</div>
          <div className="text-2xl font-bold tabular-nums text-slate-400">{count('DONE')}</div>
        </div>
      </div>

      <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-4 py-2.5 font-medium">단계</th>
              <th className="px-4 py-2.5 font-medium">계약</th>
              <th className="px-4 py-2.5 text-right font-medium">금액</th>
              <th className="px-4 py-2.5 font-medium">다음 할 일</th>
              <th className="px-4 py-2.5" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-10 text-center text-slate-500">
                {!contracts.length ? '아직 등록된 계약이 없어요. 오른쪽 위 ‘새 계약 등록’으로 시작하세요.' : q ? '찾는 계약이 없어요.' : '이 단계의 계약이 없어요.'}
              </td></tr>
            )}
            {rows.map(({ c, s }) => {
              const late = s === 'WAITING' && c.earliest_due_on && c.earliest_due_on < today();
              const mine = representative ? s === 'APPROVAL' : ['CHECK', 'RECEIVING', 'PAYMENT'].includes(s);
              return (
                <tr key={c.contract_id} className="cursor-pointer hover:bg-slate-50" onClick={() => onOpen(c.contract_id)}>
                  <td className="px-4 py-3"><span className={`whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-bold ${STAGE_PILL[s]}`}>{STAGE_KO[s]}</span></td>
                  <td className="px-4 py-3">
                    <div className="max-w-[18rem] truncate font-semibold text-slate-900">{c.title}</div>
                    <div className="text-xs text-slate-500">{maskVendorName(c.vendor_name, isMaskingEnabled)}</div>
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">{Math.round(c.contract_amount).toLocaleString('ko-KR')}원</td>
                  <td className="px-4 py-3 text-slate-700">
                    {nextAction(c, s, representative)}
                    {s === 'WAITING' && c.earliest_due_on && (
                      <span className={`ml-1 text-xs ${late ? 'font-bold text-rose-600' : 'text-slate-500'}`}>· 기한 {c.earliest_due_on.slice(5).replace('-', '/')}{late ? ' 지남' : ''}</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={(e) => { e.stopPropagation(); onOpen(c.contract_id); }}
                      className={mine ? `rounded-lg px-3 py-1.5 text-xs font-semibold text-white ${s === 'PAYMENT' ? 'bg-emerald-700 hover:bg-emerald-800' : 'bg-indigo-600 hover:bg-indigo-700'}` : 'rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700'}>
                      {mine ? (s === 'PAYMENT' ? '지급 기록' : s === 'APPROVAL' ? '결재하기' : s === 'RECEIVING' ? '서류 받기' : '확인하기') : '보기'}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {!history && <p className="text-xs text-slate-500">끝난 계약은 여기서 빠지고 ‘지난 계약 찾기’에 남아요. 검색하면 끝난 계약도 함께 찾아요.</p>}
    </div>
  );
};
