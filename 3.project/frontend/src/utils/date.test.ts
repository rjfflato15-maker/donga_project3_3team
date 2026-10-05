import { describe, expect, it } from 'vitest';
import { seoulToday } from './date';

describe('한국 날짜', () => {
  it('한국 자정을 넘으면 UTC로는 전날이어도 다음 날이다', () => {
    expect(seoulToday(new Date('2026-10-04T14:59:59Z'))).toBe('2026-10-04'); // 한국 10/4 23:59:59
    expect(seoulToday(new Date('2026-10-04T15:00:00Z'))).toBe('2026-10-05'); // 한국 10/5 00:00
  });
  it('한국 09시 전후로도 같은 날짜', () => {
    expect(seoulToday(new Date('2026-10-04T23:59:59Z'))).toBe('2026-10-05'); // 한국 08:59:59
    expect(seoulToday(new Date('2026-10-05T00:00:00Z'))).toBe('2026-10-05'); // 한국 09:00
  });
  it('연말 경계', () => {
    expect(seoulToday(new Date('2026-12-31T15:00:00Z'))).toBe('2027-01-01');
  });
});
