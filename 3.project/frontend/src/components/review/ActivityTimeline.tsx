import React, { useEffect, useRef, useState } from 'react';
import { requestJson } from '../../api/client';
import { createLatestGuard } from '../../utils/latest';
import { History } from 'lucide-react';
import { Surface } from '../ui/Surface';
import { fixParticles } from '../../utils/korean';

export interface ActivityItem {
  event_id: number;
  type: string;
  title: string;
  occurred_at: string;
  actor_name: string | null;
  document_id: number | null;
  review_id: number | null;
  details_available: boolean;
  data: Record<string, unknown>;
}
interface ActivityPage {
  contract_id: number; revision: number; fingerprint: string;
  items: ActivityItem[]; has_more: boolean; next_before_event_id: number | null; limitations?: string[];
}

const FIELD_KO: Record<string, string> = {
  company_name: '상호', business_registration_no: '사업자번호', supply_amount: '공급가액', tax_amount: '세액',
  total_amount: '합계금액', amount: '금액', issue_date: '발행일', account_number: '계좌번호', bank_name: '은행',
  amount_scope: '청구 범위', amount_basis: '금액 기준', title: '제목',
};
const VALUE_KO: Record<string, Record<string, string>> = {
  amount_basis: { TOTAL: '합계(부가세 포함)', SUPPLY: '공급가액', UNKNOWN: '미확인' },
  amount_scope: { FULL: '전액 청구', PARTIAL: '일부(분할) 청구', UNKNOWN: '미확인' },
};
const fmt = (k: string, v: unknown) => {
  if (v === null || v === undefined || v === '') return '없음';
  if (VALUE_KO[k] && typeof v === 'string') return VALUE_KO[k][v] ?? v;
  if (/amount$/.test(k) && typeof v === 'number') return `${v.toLocaleString('ko-KR')}원`;
  return String(v);
};

/** 저장값 전후 차이. amount와 total_amount가 같은 변화면 하나로 */
export function fieldChanges(before: unknown, after: unknown): string[] {
  if (!before || !after || typeof before !== 'object' || typeof after !== 'object') return [];
  const b = before as Record<string, unknown>, a = after as Record<string, unknown>;
  const out: string[] = [];
  const seen = new Set<string>();
  for (const k of Object.keys(FIELD_KO)) {
    if (!(k in a) || JSON.stringify(b[k]) === JSON.stringify(a[k])) continue;
    const line = `${fmt(k, b[k])} → ${fmt(k, a[k])}`;
    if (k === 'amount' && seen.has(line)) continue;
    seen.add(line);
    out.push(`${FIELD_KO[k]} ${line}`);
  }
  return out;
}

/** 사건 한 줄 요약: 기록된 내용만 쓴다 */
export function summarize(item: ActivityItem): string[] {
  const d = item.data ?? {};
  const note = typeof d.note === 'string' && d.note ? fixParticles(d.note) : '';
  const lines: string[] = [];
  switch (item.type) {
    case 'EXTRACT_CORRECTED':
      lines.push(...fieldChanges(d.before, d.after));
      if (Array.isArray(d.confirmed_fields) && d.confirmed_fields.length) lines.push(`원문과 맞음 확인: ${(d.confirmed_fields as string[]).map((k) => FIELD_KO[k] ?? k).join(', ')}`);
      break;
    case 'DOCUMENT_REISSUED':
      if (typeof d.version_number === 'number') lines.push(`${d.version_number}번째 본으로 교체`);
      if (d.previous_fields === null) lines.push('이전 본의 값은 기록되지 않았어요');
      else lines.push(...fieldChanges(d.previous_fields, d.new_fields));
      break;
    case 'RULE_VALIDATION': {
      // 국세청 미연동 안내는 확인할 항목으로 세지 않는다
      const checks = Array.isArray(d.checks) ? (d.checks as { status?: string; rule_id?: string }[]) : null;
      if (checks) {
        const open = checks.filter((c) => c.status && c.status !== 'PASS' && c.rule_id !== 'BUSINESS_STATUS').length;
        lines.push(open ? `확인할 항목 ${open}개` : '확인할 항목 없음');
      }
      break;
    }
    case 'RESUBMISSION_BUNDLE_RECORDED':
    case 'RESUBMISSION_BUNDLE_ITEMS_RESOLVED': {
      const items = Array.isArray(d.items) ? (d.items as { title?: string; status?: string }[]) : [];
      if (items.length) lines.push(items.map((i) => `${i.title ?? '항목'}${i.status === 'RECEIVED' ? ' 받음' : i.status === 'CANCELLED' ? ' 취소' : ''}`).join(', '));
      if (typeof d.due_on === 'string' && d.due_on) lines.push(`회신 기한 ${d.due_on}`);
      if (typeof d.memo === 'string' && d.memo) lines.push(fixParticles(d.memo));
      break;
    }
    case 'RESUBMISSION_REQUEST_RECORDED':
      if (typeof d.memo === 'string' && d.memo) lines.push(fixParticles(d.memo));
      break;
    case 'PAYMENT_RECORDED':
    case 'PAYMENT_RECONFIRMED':
      if (typeof d.paid_on === 'string') lines.push(`지급일 ${d.paid_on}`);
      break;
    default:
      break;
  }
  if (note) lines.push(`메모: ${note}`);
  return lines;
}

/** 한국 시간 표시 */
export const kst = (iso: string) => {
  const t = new Date(/[zZ]$|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`);
  if (isNaN(t.getTime())) return iso;
  return new Intl.DateTimeFormat('ko-KR', { timeZone: 'Asia/Seoul', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false }).format(t);
};

interface Props {
  contractId: number;
  revision?: number;
  fingerprint?: string;
  masked: boolean;
  /** 이 사건 ID보다 뒤(최근)의 것만. 대표 요약에서 '지난 결재 이후'를 보일 때 */
  title?: string;
  limit?: number;
  compact?: boolean;
}

/** 처리 기록: 등록→요청→회신→수정→재발행→검사→결재→지급. 기록된 사건만 최신 순으로 */
export const ActivityTimeline: React.FC<Props> = ({ contractId, revision, fingerprint, masked, title = '처리 기록', limit = 30, compact = false }) => {
  const [items, setItems] = useState<ActivityItem[]>([]);
  const [next, setNext] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const guard = useRef(createLatestGuard()).current;
  const load = async (before: number | null) => {
    const t = guard.next();
    setLoading(true);
    const qs = new URLSearchParams({ limit: String(limit), masked: String(masked) });
    if (before != null) qs.set('before_event_id', String(before));
    if (revision != null) qs.set('revision', String(revision));
    if (fingerprint) qs.set('fingerprint', fingerprint);
    try {
      const page = await requestJson<ActivityPage>(`/api/contracts/${contractId}/activity?${qs}`);
      if (!guard.isLatest(t) || page.contract_id !== contractId) return;
      setItems((prev) => {
        const base = before == null ? [] : prev;
        const seen = new Set(base.map((i) => i.event_id));
        return [...base, ...page.items.filter((i) => !seen.has(i.event_id))];
      });
      setNext(page.has_more ? page.next_before_event_id : null);
      setError('');
    } catch (e) {
      if (guard.isLatest(t)) setError(e instanceof Error ? e.message : '처리 기록을 불러오지 못했어요.');
    } finally { if (guard.isLatest(t)) setLoading(false); }
  };
  useEffect(() => { setItems([]); setNext(null); void load(null); return () => guard.invalidate(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [contractId, revision, fingerprint, masked]);

  return <Surface title={compact?undefined:title}>
    {error&&<p className="story-alert" role="alert">처리 기록 조회 실패: {error}</p>}
    {!error&&!loading&&!items.length&&<div className="empty">기록된 처리가 없습니다.</div>}
    <div className="history">{items.filter(i=>!(compact&&i.type==='RULE_VALIDATION')).map(i=><article key={i.event_id}><History size={17}/><div><div><strong>{i.title}</strong><small>{kst(i.occurred_at)}{i.actor_name?` · ${i.actor_name}`:''}</small></div>{(i.details_available?summarize(i):['상세 기록을 읽을 수 없습니다.']).map((line,key)=><p key={key}>{line}</p>)}</div></article>)}</div>
    {next!=null&&<div className="panel-footer"><button className="text-button" disabled={loading} onClick={()=>void load(next)}>이전 기록 더 보기</button></div>}
  </Surface>;
};
