import { describe, expect, it } from 'vitest';
import { searchQuery } from './ContractSearch';

describe('지난 계약 검색 조건', () => {
  it('빈 값은 보내지 않고, 진행 상태와 페이지는 항상', () => {
    expect(searchQuery({ q: '  ', completion: 'ALL', from: '', to: '' }, 0)).toBe('limit=50&offset=0&completion=ALL');
  });
  it('검색어·기간을 함께', () => {
    const qs = new URLSearchParams(searchQuery({ q: '2,090,000원', completion: 'DONE', from: '2026-10-01', to: '2026-10-31' }, 50));
    expect(qs.get('q')).toBe('2,090,000원');
    expect(qs.get('completion')).toBe('DONE');
    expect(qs.get('date_from')).toBe('2026-10-01');
    expect(qs.get('date_to')).toBe('2026-10-31');
    expect(qs.get('offset')).toBe('50');
  });
});
