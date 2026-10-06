import React, { useMemo, useState } from 'react';
import { ContractListItem } from '../../types';
import { maskVendorName } from '../../utils/masking';
import { Stage, stageOf, isMyTurn, approvalWaitingFor, Role } from '../../utils/stage';
import { ContractSearch } from './ContractSearch';
import { Badge } from '../ui/Surface';
import { ChevronRight, Plus, Search } from 'lucide-react';

export interface DashboardItem extends ContractListItem {
  stage?: string | null;
  paid_on?: string | null;
  payment?: import('../../types').ContractPayment | null;
  work_state?: { counts?: { immediate_check_items?: number; waiting_requests?: number }; next_actions?: { role: string; label: string }[]; waiting_for?: string[] } | null;
  action_summary?: string;
  waiting_request_count?: number;
  earliest_due_on?: string | null;
  approval_next_step?: number | null;
  open_issue_count?: number;
}

export const stageOfItem = (c: DashboardItem): Stage => stageOf({
  stage: c.stage, approval_status: c.approval_status, paid_on: c.paid_on ?? c.payment?.paid_on,
  waiting_request_count: c.waiting_request_count,
  missing_count: Math.max(0, (c.total_docs_count ?? 0) - (c.submitted_docs_count ?? 0)),
  open_issue_count: c.open_issue_count,
});


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
export function nextAction(c: DashboardItem, s: Stage, representative: boolean): string {
  const role: Role = representative ? 'representative' : 'operator';
  const mine = isMyTurn(s, c.work_state?.next_actions, role);
  switch (s) {
    case 'RECEIVING': return `서류 ${c.submitted_docs_count}/${c.total_docs_count}종 · 빠진 서류를 받으세요`;
    case 'CHECK': {
      const ap = (c.approval_status || '').toUpperCase();
      if (ap === 'RETURNED') return '대표가 돌려보냈어요 · 다시 확인하세요';
      const n = c.open_issue_count ?? 0;
      return `${n ? `확인할 것 ${n}건` : '다시 확인하세요'}${ap === 'STALE' ? ' · 서류가 바뀌었어요' : ''}`;
    }
    case 'WAITING': {
      const now = c.work_state?.counts?.immediate_check_items ?? 0;
      return `거래처 답을 기다리는 중${now ? ` · 사내에서 바로 확인할 것 ${now}건` : ''}`;
    }
    case 'APPROVAL': {
      if (mine) return representative ? '결재할 차례예요' : '문제 없음 · 담당 검토 결재 차례예요';
      const w = approvalWaitingFor(c.work_state?.next_actions);
      return w === 'operator' ? '담당자 검토 결재를 기다려요' : '문제 없음 · 대표 결재를 기다려요';
    }
    case 'PAYMENT': return c.payment?.status === 'RECONFIRMATION_REQUIRED' ? `이미 ${c.payment.recorded_paid_on} 지급 · 같은 지급인지 재확인` : mine ? '대표 결재 끝 · 지급하고 기록하세요' : '대표 결재 끝 · 담당자가 지급을 기록해요';
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
  const [filter, setFilter] = useState<Stage | 'all' | 'mine' | 'everything'>('all');
  const withStage = useMemo(() => contracts.map((c) => ({ c, s: stageOfItem(c) })), [contracts]);
  const count = (s: Stage) => withStage.filter((x) => x.s === s).length;
  // 담당자는 손댈 것부터, 대표는 결재할 것부터
  const role: Role = representative ? 'representative' : 'operator';
  const mineOf = (x: { c: DashboardItem; s: Stage }) => isMyTurn(x.s, x.c.work_state?.next_actions, role);
  const order: Stage[] = representative
    ? ['APPROVAL', 'PAYMENT', 'CHECK', 'RECEIVING', 'WAITING']
    : ['CHECK', 'RECEIVING', 'PAYMENT', 'WAITING', 'APPROVAL'];
  const active = withStage.filter((x) => x.s !== 'DONE');
  const q = query.trim().toLowerCase();
  const rows = (q || history ? withStage : active)
    .filter((x) => filter === 'all' || filter === 'everything' || filter === 'mine' && mineOf(x) || x.s === filter)
    .filter((x) => matchesQuery(x.c, q))
    .sort((a, b) => history
      ? b.c.created_at.localeCompare(a.c.created_at)
      : Number(mineOf(b)) - Number(mineOf(a)) || order.indexOf(a.s) - order.indexOf(b.s) || (a.c.earliest_due_on || '9999').localeCompare(b.c.earliest_due_on || '9999'));
  // 제목 건수 = 이 역할의 차례인 계약(버튼·문구와 같은 기준)
  const todo = active.filter(mineOf).length;

  const titleFor=(s:Stage)=>({RECEIVING:'확인 필요',CHECK:'확인 필요',WAITING:'회신 대기',APPROVAL:'결재 대기',PAYMENT:'지급 대기',DONE:'완료'}[s]);
  return <>
    <div className="heading"><div><small className="eyebrow">CONTRACT WORKSPACE</small><h1>{history?'계약 찾기':'업무함'}</h1><p>계약의 현재 상태와 다음 할 일을 확인하세요.</p><span className="sr-only">지금 처리할 계약 {todo}건 · {representative?'대표':'담당자'} 역할 기준</span></div>{canEdit&&onNew&&<button className="button primary" onClick={onNew}><Plus size={17}/>계약 등록</button>}</div>
    {!history&&<div className="stats">{[['진행 중',active.length,'all'],['결재 대기',count('APPROVAL'),'APPROVAL'],['회신 대기',count('WAITING'),'WAITING'],['완료',count('DONE'),'DONE']].map(([label,n,value])=><div key={String(value)}><button className="stat-filter" onClick={()=>setFilter(value as typeof filter)}><span>{label}</span></button><strong>{n}<small>건</small></strong></div>)}</div>}
    <section className="surface"><div className="tabs filters" role="tablist" aria-label="계약 상태">{[['all','진행 중'],['APPROVAL','결재 대기'],['WAITING','회신 대기'],['DONE','완료'],['everything','전체']].map(([value,label])=><button key={value} role="tab" aria-selected={filter===value} className={filter===value?'selected':''} onClick={()=>setFilter(value as typeof filter)}>{label}</button>)}</div>
    {filter==='DONE'||filter==='everything'?<ContractSearch key={filter} compact initialCompletion={filter==='DONE'?'DONE':'ALL'} isMaskingEnabled={isMaskingEnabled} onOpen={onOpen}/>:<>
    <div className="toolbar"><label className="search"><Search size={17}/><input aria-label="계약 검색" value={query} onChange={e=>setQuery(e.target.value)} placeholder="계약명, 거래처, 금액 검색"/></label><small>{rows.length}건</small></div>
    <div className="desktop-list table-wrap"><table className="contracts"><thead><tr><th>계약</th><th>거래처</th><th className="right">계약 금액</th><th>상태</th><th>다음 할 일</th></tr></thead><tbody>{rows.map(({c,s})=><tr key={c.contract_id}><td><button className="contract-link" aria-label={`${c.title} · ${nextAction(c,s,representative)}`} onClick={()=>onOpen(c.contract_id)}>{c.title}</button><small className="sub">계약 #{c.contract_id}</small></td><td>{maskVendorName(c.vendor_name,isMaskingEnabled)}</td><td className="right number">{Math.round(c.contract_amount).toLocaleString('ko-KR')}원</td><td><Badge tone={s==='DONE'?'green':s==='APPROVAL'?'blue':'amber'}>{titleFor(s)}</Badge></td><td className="next">{nextAction(c,s,representative)}{s!=='PAYMENT'&&c.payment?.status==='RECONFIRMATION_REQUIRED'&&<small className="sub">이미 지급한 계약 · 다시 지급 금지</small>}</td></tr>)}</tbody></table></div>
    <div className="mobile-list">{rows.map(({c,s})=><button key={c.contract_id} onClick={()=>onOpen(c.contract_id)}><div><Badge tone={s==='APPROVAL'?'blue':'amber'}>{titleFor(s)}</Badge><small>계약 #{c.contract_id}</small></div><strong>{c.title}</strong><span>{maskVendorName(c.vendor_name,isMaskingEnabled)}</span><div><b>{Math.round(c.contract_amount).toLocaleString('ko-KR')}원</b><ChevronRight size={17}/></div><small>{nextAction(c,s,representative)}</small></button>)}</div>
    {!rows.length&&<div className="empty">{contracts.length?'검색 결과가 없습니다.':'등록된 계약이 없습니다.'}</div>}
    </>}
    </section>
  </>;
};
