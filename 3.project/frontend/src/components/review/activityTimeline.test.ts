import { describe, expect, it } from 'vitest';
import { fieldChanges, summarize, kst, ActivityItem } from './ActivityTimeline';

const item = (type: string, data: Record<string, unknown>): ActivityItem => ({
  event_id: 1, type, title: '', occurred_at: '2026-10-05T07:10:00+00:00', actor_name: '담당자', document_id: 1, review_id: null, details_available: true, data,
});

describe('처리 기록 요약', () => {
  it('전후 저장값 차이만, amount와 total_amount가 같은 변화면 하나로', () => {
    const lines = fieldChanges({ total_amount: 1650000, amount: 1650000, tax_amount: 150000 }, { total_amount: 1540000, amount: 1540000, tax_amount: 150000 });
    expect(lines).toEqual(['합계금액 1,650,000원 → 1,540,000원']);
  });
  it('재발행: 번째 본과 전후 값, 이전 값이 없으면 없다고 말한다', () => {
    expect(summarize(item('DOCUMENT_REISSUED', { version_number: 3, previous_fields: { total_amount: 1 }, new_fields: { total_amount: 2 }, note: '합계 재발행' })))
      .toEqual(['3번째 본으로 교체', '합계금액 1원 → 2원', '메모: 합계 재발행']);
    expect(summarize(item('DOCUMENT_REISSUED', { previous_fields: null, new_fields: {} }))).toContain('이전 본의 값은 기록되지 않았어요');
  });
  it('묶음 요청 회신은 항목별 받음/취소', () => {
    expect(summarize(item('RESUBMISSION_BUNDLE_ITEMS_RESOLVED', { items: [{ title: '통장사본 제출 요청', status: 'RECEIVED' }, { title: '세금계산서 제출 요청', status: 'CANCELLED' }] })))
      .toEqual(['통장사본 제출 요청 받음, 세금계산서 제출 요청 취소']);
  });
  it('기록에 없는 것은 지어내지 않는다', () => {
    expect(summarize(item('REPRESENTATIVE_CONFIRMED', {}))).toEqual([]);
  });
  it('UTC를 한국 시간으로', () => {
    expect(kst('2026-10-04T15:30:00+00:00')).toMatch(/10\. 5\..*00:30/);
  });
});

describe('처리 기록 값 표시', () => {
  it('금액 기준·청구 범위는 한국어로', () => {
    expect(fieldChanges({ amount_basis: 'UNKNOWN', amount_scope: 'UNKNOWN' }, { amount_basis: 'TOTAL', amount_scope: 'FULL' }))
      .toEqual(['청구 범위 미확인 → 전액 청구', '금액 기준 미확인 → 합계(부가세 포함)']);
  });
  it('국세청 안내는 확인할 항목으로 세지 않는다', () => {
    expect(summarize(item('RULE_VALIDATION', { checks: [{ rule_id: 'BUSINESS_STATUS', status: 'REVIEW' }, { rule_id: 'AMOUNT_EXTRACTION', status: 'PASS' }] })))
      .toEqual(['확인할 항목 없음']);
  });
});
