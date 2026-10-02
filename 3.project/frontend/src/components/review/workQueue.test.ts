import { describe, expect, it } from 'vitest';
import { bucketOf, DashboardItem } from './WorkQueueDashboard';

const item = (patch: Partial<DashboardItem>): DashboardItem => ({
  contract_id: 1, title: '계약', vendor_name: '거래처', business_number: '', contract_amount: 1000,
  review_status: 'REVIEW', completeness_rate: 100, submitted_docs_count: 6, total_docs_count: 6, created_at: '',
  approval_status: 'PENDING', ...patch,
});

describe('bucketOf', () => {
  it('최종 확인이 끝나면 완료', () => {
    expect(bucketOf(item({ approval_status: 'CONFIRMED', waiting_request_count: 2 }))).toBe('done');
  });
  it('반려되거나 자료가 바뀌면 반려·다시 확인이 회신 대기보다 먼저', () => {
    expect(bucketOf(item({ approval_status: 'RETURNED', waiting_request_count: 1 }))).toBe('returned');
    expect(bucketOf(item({ approval_status: 'STALE' }))).toBe('returned');
  });
  it('재제출 요청이 열려 있으면 회신 대기', () => {
    expect(bucketOf(item({ waiting_request_count: 1, open_issue_count: 3 }))).toBe('waiting');
  });
  it('1단계 검토가 끝났거나 남은 문제가 없으면 결재 대기', () => {
    expect(bucketOf(item({ approval_next_step: 2 }))).toBe('approval');
    expect(bucketOf(item({ open_issue_count: 0 }))).toBe('approval');
  });
  it('문제 수를 모르거나 남아 있으면 확인 필요', () => {
    expect(bucketOf(item({}))).toBe('check');
    expect(bucketOf(item({ open_issue_count: 2, approval_next_step: 1 }))).toBe('check');
  });
});
