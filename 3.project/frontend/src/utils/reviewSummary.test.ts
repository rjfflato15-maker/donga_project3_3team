import { describe, expect, it } from 'vitest';
import { ContractDetail, DocumentResponse, ValidationCheck } from '../types';
import { buildReviewOverview, plainMessage, verdictText, isReadingCheck } from './reviewSummary';

const doc = (id: number, type: DocumentResponse['document_type']): DocumentResponse => ({
  document_id: id, contract_id: 1, original_file_name: `document_0${id}.png`, document_type: type, confidence: 1,
  processing_status: 'COMPLETED', mask_status: 'MASKED', analysis: { fields: {}, warnings: [] }, file_available: true,
});
const check = (rule_id: string, status: ValidationCheck['status'], field: string, message = '메시지'): ValidationCheck =>
  ({ rule_id, status, field, message, expected: null, actual: null });
const contract = (checks: ValidationCheck[], documents = [doc(1, 'contract'), doc(5, 'tax_invoice')]): ContractDetail => ({
  contract_id: 1, title: '가상 업무지원 시스템 구축', vendor_name: '가상 솔빛제작소 10', business_number: '000-00-01106',
  contract_amount: 2200000, review_status: 'REVIEW', required_document_types: [], documents, checks,
  summary: { required_document_count: 6, submitted_document_count: 6, completeness_rate: 100, pass_count: 0, fail_count: 0, review_count: 0, missing_count: 0 },
  created_at: '', updated_at: '',
});

describe('buildReviewOverview', () => {
  it('국세청 미연동 확인 필요는 할 일이 아니라 안내로 보낸다', () => {
    const o = buildReviewOverview(contract([check('BUSINESS_STATUS', 'REVIEW', 'business_status'), check('BUSINESS_NO_MATCH', 'PASS', '1')]));
    expect(o.issues).toHaveLength(0);
    expect(o.notices).toHaveLength(1);
    expect(verdictText(o).title).toBe('확인할 항목이 없습니다');
  });

  it('같은 서류의 검사는 한 카드로 묶고 가장 심한 상태를 쓴다', () => {
    const o = buildReviewOverview(contract([
      check('AMOUNT_COMPONENTS', 'FAIL', '5'),
      check('AMOUNT_MATCH_TAX_INVOICE', 'FAIL', '5'),
      check('BUSINESS_NO_MATCH', 'PASS', '5'),
    ]));
    expect(o.issues).toHaveLength(1);
    expect(o.issues[0]).toMatchObject({ kind: 'vendor', status: 'FAIL', title: '전자세금계산서' });
    expect(o.documentStatus.get(5)).toBe('FAIL');
    expect(o.documentStatus.get(1)).toBe('PASS');
  });

  it('앱이 값을 못 읽은 경우는 거래처 문제가 아니라 원문 확인으로 분류한다', () => {
    const o = buildReviewOverview(contract([check('AMOUNT_EXTRACTION', 'REVIEW', '5')]));
    expect(o.issues[0].kind).toBe('reading');
    expect(verdictText(o).title).toContain('원문 확인 1건');
  });

  it('미제출 서류는 별도 종류로 묶고 위험한 순서(불일치 → 미제출 → 확인 필요)로 정렬한다', () => {
    const o = buildReviewOverview(contract([
      check('AMOUNT_EXTRACTION', 'REVIEW', '1'),
      check('REQUIRED_DOCUMENTS', 'MISSING', 'bank_account'),
      check('BUSINESS_NO_MATCH', 'FAIL', '5'),
    ]));
    expect(o.issues.map((i) => i.kind)).toEqual(['vendor', 'missing', 'reading']);
    expect(o.issues[1]).toMatchObject({ missingType: 'bank_account', title: '통장사본 미제출' });
    expect(verdictText(o).title).toBe('지급 전에 확인할 것: 빠진 서류 1종, 서류 내용 확인 1건, 원문 확인 1건');
  });

  it('정상 항목은 검사 종류별로 개수를 센다', () => {
    const o = buildReviewOverview(contract([check('BUSINESS_NO_MATCH', 'PASS', '1'), check('BUSINESS_NO_MATCH', 'PASS', '5')]));
    expect(o.passed).toEqual([expect.objectContaining({ ruleId: 'BUSINESS_NO_MATCH', count: 2 })]);
  });
});

describe('작은 도우미', () => {
  it('메시지 앞의 파일명만 뺀다', () => {
    expect(plainMessage('document_05.png: 공급가액과 세액의 합이 다릅니다.')).toBe('공급가액과 세액의 합이 다릅니다.');
    expect(plainMessage('통장사본이(가) 제출되지 않았습니다.')).toBe('통장사본이 제출되지 않았습니다.');
  });
  it('사업자번호를 못 읽은 확인 필요는 읽기 문제, 다른 번호(불일치)는 아니다', () => {
    expect(isReadingCheck(check('BUSINESS_NO_MATCH', 'REVIEW', '5'))).toBe(true);
    expect(isReadingCheck(check('BUSINESS_NO_MATCH', 'FAIL', '5'))).toBe(false);
  });
});

describe('회사 내부 서류', () => {
  it('납품 검수확인서는 거래처 요청 대상이 아니다', async () => {
    const { isInternalDocument } = await import('./reviewSummary');
    expect(isInternalDocument('inspection_confirmation')).toBe(true);
    expect(isInternalDocument('bank_account')).toBe(false);
  });
});

import { adaptItems } from '../components/review/AssistantPreview';

describe('검수 도우미 항목 정리', () => {
  const base = { issue_id: 'x', field: '5', reason: '', document_id: 5, request_draft: { subject: 's', body: 'b' }, assignment_draft: null } as const;
  it('국세청 미연동 항목은 빼고, 못 읽은 값은 요청 초안 대신 원문 확인으로 바꾼다', () => {
    const out = adaptItems([
      { ...base, issue_id: 'a', rule_id: 'BUSINESS_STATUS', status: 'REVIEW', next_action: 'MANUAL_CONFIRMATION' },
      { ...base, issue_id: 'b', rule_id: 'AMOUNT_EXTRACTION', status: 'REVIEW', next_action: 'DRAFT_REQUEST_AFTER_REVIEW' },
      { ...base, issue_id: 'c', rule_id: 'AMOUNT_MATCH_TAX_INVOICE', status: 'FAIL', next_action: 'DRAFT_REQUEST_AFTER_REVIEW' },
    ]);
    expect(out.map((i) => i.issue_id)).toEqual(['b', 'c']);
    expect(out[0].next_action).toBe('VERIFY_EXTRACTION_FIRST');
    expect(out[0].request_draft).toBeNull();
    expect(out[1].request_draft).not.toBeNull();
  });
});
