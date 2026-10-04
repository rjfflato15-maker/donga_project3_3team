import { describe, expect, it } from 'vitest';
import { stageOf } from './stage';

describe('계약 단계', () => {
  it('백엔드가 준 단계를 그대로 쓴다', () => {
    expect(stageOf({ stage: 'payment', open_issue_count: 3 })).toBe('PAYMENT');
  });
  it('지급 기록이 있으면 끝, 결재만 끝났으면 지급 단계', () => {
    expect(stageOf({ approval_status: 'CONFIRMED', paid_on: '2026-10-05' })).toBe('DONE');
    expect(stageOf({ approval_status: 'CONFIRMED' })).toBe('PAYMENT');
  });
  it('요청해 둔 것이 있으면 문제가 남아 있어도 보완 대기', () => {
    expect(stageOf({ waiting_request_count: 1, missing_count: 1, open_issue_count: 2 })).toBe('WAITING');
  });
  it('빠진 서류가 있으면 서류 받기, 확인할 것만 있으면 확인', () => {
    expect(stageOf({ missing_count: 1, open_issue_count: 1 })).toBe('RECEIVING');
    expect(stageOf({ open_issue_count: 2 })).toBe('CHECK');
  });
  it('반려되면 확인으로 돌아가고, 아무 문제가 없으면 결재', () => {
    expect(stageOf({ approval_status: 'RETURNED', open_issue_count: 0 })).toBe('CHECK');
    expect(stageOf({ open_issue_count: 0, approval_status: 'STALE' })).toBe('APPROVAL');
  });
});

import { stepStates } from './stage';

describe('단계 표시의 완료 체크', () => {
  it('보완 대기 중이어도 빠진 서류·확인할 것이 남아 있으면 앞 단계는 완료가 아니다', () => {
    const s = stepStates({ stage: 'WAITING', missing: 2, issues: 3, waiting: 1, requests: 1, approved: false, paid: false });
    expect(s.RECEIVING).toBe('pending');
    expect(s.CHECK).toBe('pending');
    expect(s.WAITING).toBe('todo');
  });
  it('요청 없이 결재까지 온 정상 계약은 보완을 해당 없음으로', () => {
    const s = stepStates({ stage: 'APPROVAL', missing: 0, issues: 0, waiting: 0, requests: 0, approved: false, paid: false });
    expect([s.RECEIVING, s.CHECK, s.WAITING]).toEqual(['done', 'done', 'skipped']);
  });
  it('요청하고 답을 받았으면 보완 완료', () => {
    expect(stepStates({ stage: 'APPROVAL', missing: 0, issues: 0, waiting: 0, requests: 1, approved: false, paid: false }).WAITING).toBe('done');
  });
});
