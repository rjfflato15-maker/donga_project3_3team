import { describe, expect, it } from 'vitest';
import { matchesQuery, stageOfItem, DashboardItem } from './StageDashboard';

const item = (over: Partial<DashboardItem>): DashboardItem => ({
  contract_id: 1, title: '업무지원 시스템 구축', vendor_name: '가상 새봄기획', business_number: '', contract_amount: 2090000,
  review_status: 'REVIEW', completeness_rate: 100, submitted_docs_count: 6, total_docs_count: 6, created_at: '2026-10-01',
  ...over,
});

describe('첫 화면 검색', () => {
  it('금액은 쉼표·원 표기와 상관없이 같은 값으로 찾는다', () => {
    const c = item({});
    for (const q of ['2090000', '2,090,000', '2,090,000원', ' 2,090,000 원 ']) expect(matchesQuery(c, q)).toBe(true);
    expect(matchesQuery(c, '3,090,000')).toBe(false);
  });
  it('거래처·계약명 검색은 그대로', () => {
    expect(matchesQuery(item({}), '새봄')).toBe(true);
    expect(matchesQuery(item({}), '시스템')).toBe(true);
    expect(matchesQuery(item({}), '누리')).toBe(false);
  });
  it('단계 필터와 함께 써도 같은 결과', () => {
    const rows = [
      item({ contract_id: 1, waiting_request_count: 1 }),
      item({ contract_id: 2, contract_amount: 1210000, open_issue_count: 2 }),
      item({ contract_id: 3, open_issue_count: 1 }),
    ];
    const found = rows.filter((c) => stageOfItem(c) === 'CHECK' && matchesQuery(c, '2,090,000원')).map((c) => c.contract_id);
    expect(found).toEqual([3]);
  });
});
