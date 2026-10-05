import React, { useEffect, useRef, useState } from 'react';
import { requestJson } from '../../api/client';
import { maskVendorName } from '../../utils/masking';
import { createLatestGuard } from '../../utils/latest';
import { STAGE_KO, STAGE_PILL, Stage } from '../../utils/stage';
import { DashboardItem, stageOfItem } from './StageDashboard';
import { Search } from 'lucide-react';

interface SearchResult { items: DashboardItem[]; total: number; limit: number; offset: number }

const PAGE = 50;

/** 서버 검색 조건(쿼리 문자열). 빈 값은 보내지 않는다 */
export function searchQuery(f: { q: string; completion: 'ALL' | 'OPEN' | 'DONE'; from: string; to: string }, offset: number) {
  const qs = new URLSearchParams({ limit: String(PAGE), offset: String(offset), completion: f.completion });
  if (f.q.trim()) qs.set('q', f.q.trim());
  if (f.from) qs.set('date_from', f.from);
  if (f.to) qs.set('date_to', f.to);
  return qs.toString();
}

const kstDate = (iso: string) => new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Seoul' }).format(new Date(iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`));

interface Props {
  isMaskingEnabled: boolean;
  onOpen: (contractId: number) => void;
}

/** 지난 계약 찾기: 서버 검색(계약명·거래처·앱 계약 ID·금액, 진행 중/끝, 등록 기간) */
export const ContractSearch: React.FC<Props> = ({ isMaskingEnabled, onOpen }) => {
  const [q, setQ] = useState('');
  const [completion, setCompletion] = useState<'ALL' | 'OPEN' | 'DONE'>('ALL');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [rows, setRows] = useState<DashboardItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const guard = useRef(createLatestGuard()).current;

  const run = async (offset: number) => {
    const t = guard.next();
    setLoading(true);
    try {
      const r = await requestJson<SearchResult>(`/api/contracts/search?${searchQuery({ q, completion, from, to }, offset)}`);
      if (!guard.isLatest(t)) return;
      setRows((prev) => (offset === 0 ? r.items : [...prev, ...r.items.filter((i) => !prev.some((p) => p.contract_id === i.contract_id))]));
      setTotal(r.total);
      setError('');
    } catch (e) {
      if (guard.isLatest(t)) setError(e instanceof Error ? e.message : '찾지 못했어요.');
    } finally { if (guard.isLatest(t)) setLoading(false); }
  };
  // 입력이 멈추면 검색
  useEffect(() => {
    const id = setTimeout(() => { void run(0); }, 250);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, completion, from, to]);

  const input = 'rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-800 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200';
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">지난 계약 찾기</h1>
        <p className="text-sm text-slate-500">끝난 계약까지 모두 찾아요. 기간은 <b>계약을 처음 등록한 날</b> 기준이에요.</p>
      </div>
      <div className="flex flex-wrap items-end gap-2">
        <label className="flex min-w-[220px] flex-1 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-200">
          <Search className="h-4 w-4 text-slate-400" />
          <span className="sr-only">검색어</span>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="거래처·계약명·금액·앱 계약 번호" className="min-w-0 flex-1 bg-white text-slate-800 outline-none" />
        </label>
        <label className="grid gap-1 text-xs text-slate-500">진행
          <select value={completion} onChange={(e) => setCompletion(e.target.value as 'ALL' | 'OPEN' | 'DONE')} className={input}>
            <option value="ALL">전체</option><option value="OPEN">진행 중</option><option value="DONE">지급까지 끝</option>
          </select></label>
        <label className="grid gap-1 text-xs text-slate-500">등록일부터<input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className={input} /></label>
        <label className="grid gap-1 text-xs text-slate-500">등록일까지<input type="date" value={to} min={from || undefined} onChange={(e) => setTo(e.target.value)} className={input} /></label>
      </div>
      {error && <p role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
      <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr><th className="px-4 py-2.5 font-medium">단계</th><th className="px-4 py-2.5 font-medium">계약</th><th className="px-4 py-2.5 text-right font-medium">금액</th><th className="px-4 py-2.5 font-medium">등록일</th><th className="px-4 py-2.5 font-medium">지급</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {!loading && rows.length === 0 && <tr><td colSpan={5} className="px-4 py-10 text-center text-slate-500">찾는 계약이 없어요.</td></tr>}
            {rows.map((c) => {
              const s: Stage = stageOfItem(c);
              return (
                <tr key={c.contract_id} className="cursor-pointer hover:bg-slate-50" onClick={() => onOpen(c.contract_id)}>
                  <td className="px-4 py-3"><span className={`whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-bold ${STAGE_PILL[s]}`}>{STAGE_KO[s]}</span></td>
                  <td className="px-4 py-3">
                    <div className="max-w-[18rem] truncate font-semibold text-slate-900">{c.title}</div>
                    <div className="text-xs text-slate-500">{maskVendorName(c.vendor_name, isMaskingEnabled)} · 앱 계약 {c.contract_id}번</div>
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">{Math.round(c.contract_amount).toLocaleString('ko-KR')}원</td>
                  <td className="px-4 py-3 tabular-nums text-slate-600">{c.created_at ? kstDate(c.created_at) : '-'}</td>
                  <td className="px-4 py-3 text-slate-600">{c.payment?.paid_on ? c.payment.paid_on : c.payment?.status === 'RECONFIRMATION_REQUIRED' ? `${c.payment.recorded_paid_on} (재확인 필요)` : '-'}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="flex items-center gap-3 text-xs text-slate-500">
        <span>{total}건 중 {rows.length}건</span>
        {rows.length < total && <button onClick={() => void run(rows.length)} disabled={loading} className="font-semibold text-indigo-600 hover:underline disabled:opacity-40">{loading ? '불러오는 중…' : '더 보기'}</button>}
      </div>
    </div>
  );
};
