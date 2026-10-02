import { describe, expect, it } from 'vitest';
import { minutes } from './WorkStatsStrip';

describe('처리 시간 표시', () => {
  it('짧으면 분, 길면 시간·일로 읽기 쉽게', () => {
    expect(minutes(null)).toBe('기록 없음');
    expect(minutes(30)).toBe('1분 미만');
    expect(minutes(25 * 60)).toBe('25분');
    expect(minutes(301 * 60)).toBe('5시간 1분');
    expect(minutes(120 * 60)).toBe('2시간');
    expect(minutes((1440 + 90) * 60)).toBe('1일 1시간 30분');
  });
});
