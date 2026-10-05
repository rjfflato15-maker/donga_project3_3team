import { describe, expect, it } from 'vitest';
import { createLatestGuard, replyNotice } from './latest';

describe('최근 조회만 반영', () => {
  it('먼저 보낸 느린 조회(A)는 나중 조회(B) 뒤에 와도 버린다', () => {
    const g = createLatestGuard();
    const a = g.next();
    const b = g.next();
    expect(g.isLatest(b)).toBe(true);
    expect(g.isLatest(a)).toBe(false);
  });
  it('계약 전환(invalidate) 뒤에는 이전 조회를 모두 버린다', () => {
    const g = createLatestGuard();
    const a = g.next();
    g.invalidate();
    expect(g.isLatest(a)).toBe(false);
  });
});

describe('회신 저장 안내', () => {
  it('저장·조회 모두 성공이면 안내 없음', () => {
    expect(replyNotice(true, true)).toBeNull();
  });
  it('저장 성공 + 조회 실패는 저장했다고 말하고 새로고침 안내', () => {
    expect(replyNotice(true, false)?.text).toMatch(/^저장했어요.*불러오지 못했어요/);
  });
  it('저장 실패 + 조회 성공/실패를 구분한다', () => {
    expect(replyNotice(false, true, '충돌')?.text).toContain('다시 불러왔어요');
    const both = replyNotice(false, false, '충돌')?.text ?? '';
    expect(both).toContain('불러오지 못했어요');
    expect(both).not.toContain('다시 불러왔어요');
  });
});
