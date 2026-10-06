// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import { StageDashboard, DashboardItem } from './StageDashboard';

afterEach(cleanup);

const base = (over: Partial<DashboardItem>): DashboardItem => ({
  contract_id: 1, title: '업무지원 시스템 구축', vendor_name: '가상 새봄기획', business_number: '', contract_amount: 1100000,
  review_status: 'REVIEW', completeness_rate: 100, submitted_docs_count: 6, total_docs_count: 6, created_at: '2026-10-01T00:00:00',
  ...over,
});
// 2단계 결재에서 담당자 차례인 계약
const operatorTurn = base({ contract_id: 1, stage: 'APPROVAL', approval_status: 'IN_PROGRESS', work_state: { next_actions: [{ role: 'operator', label: '담당 검토' }] } });
// 1단계 결재(대표 차례)
const repTurn = base({ contract_id: 2, title: '홈페이지 유지보수', contract_amount: 1210000, stage: 'APPROVAL', work_state: { next_actions: [{ role: 'representative', label: '최종 확인' }] } });
// 회신 대기 중이지만 사내에서 바로 확인할 것이 있음
const waitingWithCheck = base({ contract_id: 3, title: '교육 콘텐츠', contract_amount: 2090000, stage: 'WAITING', work_state: { counts: { immediate_check_items: 1 }, next_actions: [{ role: 'operator', label: '사내 확인' }] } });
// 지급 단계(담당자만 기록)
const payment = base({ contract_id: 4, title: '서버 임대', contract_amount: 5500000, stage: 'PAYMENT', approval_status: 'CONFIRMED', work_state: { next_actions: [{ role: 'operator', label: '지급 기록' }] } });
const done = base({ contract_id: 5, title: '지급 마친 장비 임대', stage: 'DONE', work_state: { next_actions: [] } });

const rowOf = (title: string) => screen.getByText(title).closest('tr') as HTMLElement;

describe('첫 화면: 역할별 차례가 건수·문구·버튼에서 같다', () => {
  it('담당자: 2단계 결재의 담당 검토·사내 확인·지급이 내 차례', () => {
    render(<StageDashboard contracts={[operatorTurn, repTurn, waitingWithCheck, payment, done]} isMaskingEnabled={false} canEdit onOpen={() => undefined} />);
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('업무함');
    expect(screen.getByText(/지금 처리할 계약 3건/)).toBeTruthy();
    const op = rowOf('업무지원 시스템 구축');
    expect(within(op).getByText(/담당 검토 결재 차례예요/)).toBeTruthy();
    expect(within(op).getByRole('button').textContent).toBe('결재하기');
    const rep = rowOf('홈페이지 유지보수');
    expect(within(rep).getByText(/대표 결재를 기다려요/)).toBeTruthy();
    expect(within(rep).getByRole('button').textContent).toBe('보기');
    expect(within(rowOf('교육 콘텐츠')).getByRole('button').textContent).toBe('확인하기');
    expect(within(rowOf('서버 임대')).getByRole('button').textContent).toBe('지급 기록');
    expect(screen.queryByText('지급 마친 장비 임대')).toBeNull();
    // 내 차례가 위로
    const titles = screen.getAllByRole('row').slice(1).map((r) => r.textContent ?? '');
    expect(titles.findIndex((t) => t.includes('홈페이지 유지보수'))).toBe(titles.length - 1);
  });
  it('대표: 담당 검토 중인 계약은 내 차례가 아니고, 대표 결재만 내 차례', () => {
    render(<StageDashboard contracts={[operatorTurn, repTurn, waitingWithCheck, payment]} isMaskingEnabled={false} canEdit={false} representative onOpen={() => undefined} />);
    expect(screen.getByText(/지금 처리할 계약 1건/)).toBeTruthy();
    const op = rowOf('업무지원 시스템 구축');
    expect(within(op).getByText(/담당자 검토 결재를 기다려요/)).toBeTruthy();
    expect(within(op).getByRole('button').textContent).toBe('보기');
    expect(within(rowOf('홈페이지 유지보수')).getByRole('button').textContent).toBe('결재하기');
    expect(within(rowOf('서버 임대')).getByText(/담당자가 지급을 기록해요/)).toBeTruthy();
  });
  it('회신 대기 중 사내 확인 건수를 보인다', () => {
    render(<StageDashboard contracts={[waitingWithCheck]} isMaskingEnabled={false} canEdit onOpen={() => undefined} />);
    expect(within(rowOf('교육 콘텐츠')).getByText(/사내에서 바로 확인할 것 1건/)).toBeTruthy();
  });
});
