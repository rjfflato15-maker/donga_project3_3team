import { describe, expect, it } from 'vitest';
import { maskForDisplay } from './ContractStageView';

describe('화면 표시 가림', () => {
  it('가림 ON이면 하이픈 있는·없는 사업자번호를 모두 가린다', () => {
    expect(maskForDisplay('123-45-67890', true)).toBe('123-**-*****');
    expect(maskForDisplay('1234567890', true)).toBe('123-**-*****');
    expect(maskForDisplay('서류 1234567890, 기준 123-45-67890', true)).not.toMatch(/67890/);
  });
  it('가림 OFF면 원래 값, 쉼표 금액은 ON이어도 그대로', () => {
    expect(maskForDisplay('123-45-67890', false)).toBe('123-45-67890');
    expect(maskForDisplay('2,200,000', true)).toBe('2,200,000');
    expect(maskForDisplay('합계 기준 1,000원 차이', true)).toBe('합계 기준 1,000원 차이');
  });
});
