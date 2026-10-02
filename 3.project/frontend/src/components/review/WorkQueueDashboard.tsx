import React, { useMemo, useState } from 'react';
import { ContractListItem } from '../../types';
import { maskVendorName } from '../../utils/masking';
import { Plus, Upload } from 'lucide-react';

type Bucket = 'check' | 'waiting' | 'approval' | 'returned' | 'done';

const BUCKETS: { key: Bucket; label: string; hint: string; tone: string }[] = [
  { key: 'check', label: '확인 필요', hint: '서류를 보고 처리할 계약', tone: 'border-amber-300 bg-amber-50 text-amber-900' },
  { key: 'waiting', label: '회신 대기', hint: '재제출을 요청한 계약', tone: 'border-sky-300 bg-sky-50 text-sky-900' },
  { key: 'approval', label: '결재 대기', hint: '확인할 것이 없거나 결재가 진행 중', tone: 'border-indigo-300 bg-indigo-50 text-indigo-900' },
  { key: 'returned', label: '반려·다시 확인', hint: '대표가 돌려보냈거나 자료가 바뀜', tone: 'border-rose-300 bg-rose-50 text-rose-900' },
  { key: 'done', label: '완료', hint: '최종 확인이 끝난 계약', tone: 'border-emerald-300 bg-emerald-50 text-emerald-900' },
];

const PILL: Record<Bucket, string> = {
  check: 'bg-amber-100 text-amber-800',
  waiting: 'bg-sky-100 text-sky-800',
  approval: 'bg-indigo-100 text-indigo-800',
  returned: 'bg-rose-100 text-rose-700',
  done: 'bg-emerald-100 text-emerald-700',
};

export interface DashboardItem extends ContractListItem {
  action_summary?: string;
  waiting_request_count?: number;
  earliest_due_on?: string | null;
  approval_next_step?: number | null;
  open_issue_count?: number;
}

export function bucketOf(c: DashboardItem): Bucket {
  const approval = (c.approval_status || '').toUpperCase();
  if (approval === 'CONFIRMED') return 'done';
  if (approval === 'RETURNED' || approval === 'STALE') return 'returned';
  if ((c.waiting_request_count ?? 0) > 0) return 'waiting';
  if (c.approval_next_step === 2) return 'approval';
  if (c.open_issue_count === 0) return 'approval';
  return 'check';
}

const today = () => new Date().toISOString().slice(0, 10);

interface Props {
  contracts: DashboardItem[];
  isMaskingEnabled: boolean;
  canEdit: boolean;
  onOpen: (contractId: number) => void;
  onNewFromDocuments?: () => void;
  onUpload?: () => void;
}

export const WorkQueueDashboard: React.FC<Props> = ({ contracts, isMaskingEnabled, canEdit, onOpen, onNewFromDocuments, onUpload }) => {
  const grouped = useMemo(() => {
    const map: Record<Bucket, DashboardItem[]> = { check: [], waiting: [], approval: [], returned: [], done: [] };
    contracts.forEach((c) => map[bucketOf(c)].push(c));
    // 회신 대기는 기한이 이른 순서, 나머지는 최근 등록 순서
    map.waiting.sort((a, b) => (a.earliest_due_on || '9999').localeCompare(b.earliest_due_on || '9999'));
    return map;
  }, [contracts]);
  const [filter, setFilter] = useState<Bucket | 'all'>('all');
  const order: Bucket[] = ['returned', 'check', 'waiting', 'approval', 'done'];
  const rows = filter === 'all' ? order.flatMap((b) => grouped[b]) : grouped[filter];
  const overdue = grouped.waiting.filter((c) => c.earliest_due_on && c.earliest_due_on < today()).length;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">검수 할 일</h1>
          <p className="text-sm text-slate-500">처리할 계약부터 보여 줍니다. 상태를 누르면 그 계약만 모아 볼 수 있어요.</p>
        </div>
        {canEdit && (
          <div className="ml-auto flex flex-wrap gap-2">
            {onUpload && (
              <button onClick={onUpload} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:border-indigo-300">
                <Upload className="h-4 w-4" /> 서류 올리기
              </button>
            )}
            {onNewFromDocuments && (
              <button onClick={onNewFromDocuments} className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-700">
                <Plus className="h-4 w-4" /> 서류 6종으로 계약 등록
              </button>
            )}
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
        {BUCKETS.map((b) => {
          const on = filter === b.key;
          return (
            <button
              key={b.key}
              onClick={() => setFilter(on ? 'all' : b.key)}
              aria-pressed={on}
              className={`rounded-2xl border p-3 text-left transition ${grouped[b.key].length ? b.tone : 'border-slate-200 bg-white text-slate-500'} ${on ? 'ring-2 ring-indigo-400' : ''}`}
            >
              <div className="text-sm font-semibold">{b.label}</div>
              <div className="text-2xl font-bold tabular-nums">{grouped[b.key].length}</div>
              <div className="text-[11px] opacity-80">{b.key === 'waiting' && overdue ? `기한 지남 ${overdue}건` : b.hint}</div>
            </button>
          );
        })}
      </div>

      <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
        <table className="w-full min-w-[720px] text-sm">
          <thead className="border-b border-slate-100 text-left text-slate-500">
            <tr>
              <th className="px-4 py-2.5 font-medium">상태</th>
              <th className="px-4 py-2.5 font-medium">거래처 · 계약</th>
              <th className="px-4 py-2.5 text-right font-medium">계약 금액</th>
              <th className="px-4 py-2.5 font-medium">확인할 것</th>
              <th className="px-4 py-2.5" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-10 text-center text-slate-500">
                {contracts.length ? '이 상태의 계약이 없습니다.' : '아직 등록된 계약이 없습니다. 오른쪽 위에서 서류 6종으로 계약을 등록해 보세요.'}
              </td></tr>
            )}
            {rows.map((c) => {
              const b = bucketOf(c);
              const label = BUCKETS.find((x) => x.key === b)!.label;
              const late = c.earliest_due_on && c.earliest_due_on < today();
              return (
                <tr key={c.contract_id} className="cursor-pointer hover:bg-slate-50" onClick={() => onOpen(c.contract_id)}>
                  <td className="px-4 py-3"><span className={`rounded-md px-2 py-0.5 text-xs font-semibold ${PILL[b]}`}>{label}</span></td>
                  <td className="px-4 py-3">
                    <div className="font-semibold text-slate-900">{maskVendorName(c.vendor_name, isMaskingEnabled)}</div>
                    <div className="max-w-[18rem] truncate text-xs text-slate-500">{c.title}</div>
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">{Math.round(c.contract_amount).toLocaleString('ko-KR')}원</td>
                  <td className="px-4 py-3 text-slate-700">
                    {c.action_summary || (c.completeness_rate < 100 ? `서류 ${c.submitted_docs_count}/${c.total_docs_count}종 제출` : '검사 결과 확인')}
                    {c.earliest_due_on && (
                      <div className={`text-xs ${late ? 'font-semibold text-rose-600' : 'text-slate-500'}`}>회신 기한 {c.earliest_due_on}{late ? ' · 지남' : ''}</div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={(e) => { e.stopPropagation(); onOpen(c.contract_id); }}
                      className={b === 'done' ? 'rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700' : 'rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700'}
                    >
                      {b === 'done' ? '보기' : '검수하기'}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-slate-500">수정·제외는 계약 화면의 ⋯ 메뉴에서 할 수 있습니다.</p>
    </div>
  );
};
