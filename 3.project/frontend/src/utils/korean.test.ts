import { describe, expect, it } from 'vitest';
import { fixParticles, josa } from './korean';

describe('조사 맞추기', () => {
  it('받침에 따라 조사를 고른다', () => {
    expect(josa('통장사본', '이/가')).toBe('통장사본이');
    expect(josa('견적서', '이/가')).toBe('견적서가');
    expect(josa('세금계산서', '을/를')).toBe('세금계산서를');
    expect(josa('사업자등록증', '을/를')).toBe('사업자등록증을');
    expect(josa('2,200,000원', '이/가')).toBe('2,200,000원이');
  });
  it('붙어 나온 이(가)·을(를) 표기를 고친다', () => {
    expect(fixParticles('통장사본이(가) 제출되지 않았습니다.')).toBe('통장사본이 제출되지 않았습니다.');
    expect(fixParticles('견적서이(가) 없고 세금계산서을(를) 보내 주세요')).toBe('견적서가 없고 세금계산서를 보내 주세요');
  });
});
