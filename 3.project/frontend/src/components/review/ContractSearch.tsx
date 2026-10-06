import React, { useEffect, useRef, useState } from 'react';
import { requestJson } from '../../api/client';
import { maskVendorName } from '../../utils/masking';
import { createLatestGuard } from '../../utils/latest';
import { Stage } from '../../utils/stage';
import { Badge } from '../ui/Surface';
import { DashboardItem, stageOfItem } from './StageDashboard';
import { Search } from 'lucide-react';

interface SearchResult { items: DashboardItem[]; total: number; limit: number; offset: number }

const PAGE = 50;
const LABEL:Record<Stage,string> = {RECEIVING:'확인 필요',CHECK:'확인 필요',WAITING:'회신 대기',APPROVAL:'결재 대기',PAYMENT:'지급 대기',DONE:'완료'};

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
  compact?: boolean;
  initialCompletion?: 'ALL' | 'OPEN' | 'DONE';
}

/** 지난 계약 찾기: 서버 검색(계약명·거래처·앱 계약 ID·금액, 진행 중/끝, 등록 기간) */
export const ContractSearch: React.FC<Props> = ({ isMaskingEnabled, onOpen, compact = false, initialCompletion = 'ALL' }) => {
  const [q, setQ] = useState('');
  const [completion, setCompletion] = useState<'ALL' | 'OPEN' | 'DONE'>(initialCompletion);
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [rows, setRows] = useState<DashboardItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
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
    guard.invalidate(); setLoading(true); setRows([]); setTotal(0);
    const id = setTimeout(() => { void run(0); }, 250);
    return () => { clearTimeout(id); guard.invalidate(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, completion, from, to]);


  return <>
    {!compact&&<div className="heading"><div><small className="eyebrow">CONTRACT WORKSPACE</small><h1>계약 찾기</h1><p>등록일과 진행 상태로 지난 계약까지 찾습니다.</p></div></div>}
    <div className="toolbar"><label className="search"><Search size={17}/><input aria-label="검색어" value={q} onChange={e=>setQ(e.target.value)} placeholder="계약명, 거래처, 금액 검색"/></label><small>{loading?'조회 중…':`${total}건`}</small></div>
    {!compact&&<div className="search-period"><label>진행<select value={completion} onChange={e=>setCompletion(e.target.value as typeof completion)}><option value="ALL">전체</option><option value="OPEN">진행 중</option><option value="DONE">완료</option></select></label><label>등록일부터<input type="date" value={from} onChange={e=>setFrom(e.target.value)}/></label><label>등록일까지<input type="date" value={to} min={from||undefined} onChange={e=>setTo(e.target.value)}/></label></div>}
    {error&&<p className="story-alert" role="alert">{error}</p>}
    <div className="desktop-list table-wrap"><table className="contracts"><thead><tr><th>계약</th><th>거래처</th><th className="right">계약 금액</th><th>상태</th><th>다음 할 일</th></tr></thead><tbody>{rows.map(c=>{const s=stageOfItem(c);return <tr key={c.contract_id}><td><button className="contract-link" onClick={()=>onOpen(c.contract_id)}>{c.title}</button><small className="sub">계약 #{c.contract_id} · {kstDate(c.created_at)}</small></td><td>{maskVendorName(c.vendor_name,isMaskingEnabled)}</td><td className="right number">{Math.round(c.contract_amount).toLocaleString('ko-KR')}원</td><td><Badge tone={s==='DONE'?'green':s==='APPROVAL'?'blue':'amber'}>{LABEL[s]}</Badge></td><td className="next">{c.payment?.status==='RECONFIRMATION_REQUIRED'?`이미 ${c.payment.recorded_paid_on} 지급 · 재확인 필요`:c.payment?.paid_on?`${c.payment.paid_on} 지급 완료`:c.action_summary||LABEL[s]}</td></tr>;})}</tbody></table></div>
    <div className="mobile-list">{rows.map(c=><button key={c.contract_id} onClick={()=>onOpen(c.contract_id)}><div><Badge>{LABEL[stageOfItem(c)]}</Badge><small>계약 #{c.contract_id}</small></div><strong>{c.title}</strong><span>{maskVendorName(c.vendor_name,isMaskingEnabled)}</span><div><b>{Math.round(c.contract_amount).toLocaleString('ko-KR')}원</b></div></button>)}</div>
    {!loading&&!rows.length&&<div className="empty">검색 결과가 없습니다.</div>}
    <div className="panel-footer"><span>{total}건 중 {rows.length}건</span>{rows.length<total&&<button className="text-button" disabled={loading} onClick={()=>void run(rows.length)}>더 보기</button>}</div>
  </>;
};
