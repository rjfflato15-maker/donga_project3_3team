import type { ContractListItem } from '../../types';
import { Stage, stageOf, isMyTurn, approvalWaitingFor, Role } from '../../utils/stage';

export interface DashboardItem extends ContractListItem {
  stage?: string | null;
  paid_on?: string | null;
  payment?: import('../../types').ContractPayment | null;
  work_state?: { review_blockers?: import('../../types').ReviewBlocker[]; submission_status?:string; counts?: { immediate_check_items?: number; waiting_requests?: number }; next_actions?: { role: string; label: string }[]; waiting_for?: string[] } | null;
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
      const blockers=c.work_state?.review_blockers;
      if(blockers){
        if(blockers.some(b=>['READING_FAILED','READING_INCOMPLETE','SOURCE_UNVERIFIED'].includes(b.code)))return '원본·판독 복구 후 원문 확인';
        const n=blockers.filter(b=>b.code==='HUMAN_REVIEW_REQUIRED').length;
        if(n)return `원문 대조 ${n}항목 · 검토 후 상신`;
        if(c.approval_status==='RETURNED')return '반려 사유 재검토·결재 재상신';
        if(c.open_issue_count)return `불일치·미확인 ${c.open_issue_count}건 · 보완 판단`;
        return '검토 의견 기록·결재 상신';
      }
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
      if(c.work_state?.submission_status==='SUBMITTED')return mine?'상신 자료 검토·승인 또는 반려':'담당자 상신 완료 · 대표 결재 대기';
      if (mine) return representative ? '결재할 차례예요' : '문제 없음 · 담당 검토 결재 차례예요';
      const w = approvalWaitingFor(c.work_state?.next_actions);
      return w === 'operator' ? '담당자 검토 결재를 기다려요' : '문제 없음 · 대표 결재를 기다려요';
    }
    case 'PAYMENT': return c.payment?.status==='VOIDED'?'지급 기록 취소됨 · 실제 지급 사실을 확인하세요':c.payment?.status === 'RECONFIRMATION_REQUIRED' ? `이미 ${c.payment.recorded_paid_on} 지급 · 같은 지급인지 재확인` : mine ? '대표 결재 끝 · 지급하고 기록하세요' : '대표 결재 끝 · 담당자가 지급을 기록해요';
    default: return c.paid_on ? `${c.paid_on} 지급 완료` : '끝';
  }
}

