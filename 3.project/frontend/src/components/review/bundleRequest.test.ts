import { describe, expect, it } from 'vitest';
import { buildText, currentDocumentFor, sameBasis, BundleCandidate } from './BundleRequest';
import { splitInternalIssues } from './ContractStageView';
import { IssueGroup } from '../../utils/reviewSummary';

const contract = { vendor_name: '가상 업체', title: '외주 계약' };
const cand = (over: Partial<BundleCandidate>): BundleCandidate => ({
  issue_key: 'missing:bank_account', title: '통장사본 제출 요청', document_type: 'bank_account', document_id: null,
  reason: '통장사본 제출이 필요합니다.', requires_original_review: false, ...over,
});

describe('묶음 요청 문구', () => {
  const twoFails = cand({ issue_key: 'document:7', title: '견적서 보완 요청', document_type: 'estimate', document_id: 9,
    reason: 'document_02.pdf: 사업자번호가 다릅니다.\ndocument_02.pdf: 견적 금액이 계약과 다릅니다.', requires_original_review: true });
  it('자세히에는 같은 서류의 사유를 모두 넣는다', () => {
    const t = buildText(contract, [twoFails], true);
    expect(t).toContain('사업자번호가 다릅니다');
    expect(t).toContain('견적 금액이 계약과 다릅니다');
  });
  it('짧게는 첫 사유와 나머지 건수를 보인다', () => {
    const t = buildText(contract, [twoFails], false);
    expect(t).toContain('사업자번호가 다릅니다. 외 1건');
  });
  it('여러 서류를 한 문구로, 빠진 서류는 보내 달라고', () => {
    const t = buildText(contract, [cand({}), cand({ issue_key: 'missing:tax_invoice', title: '세금계산서 제출 요청', document_type: 'tax_invoice', reason: '세금계산서 제출이 필요합니다.' }), twoFails], false);
    expect(t).toContain('통장사본을 보내 주세요');
    expect(t).toContain('세금계산서를 보내 주세요');
    expect(t.split('\n').filter((l) => l.startsWith('- '))).toHaveLength(3);
  });
});

describe('요청 항목의 현재 서류', () => {
  const docs = [
    { document_id: 9, version: { logical_document_id: 7, is_current: false } },
    { document_id: 12, version: { logical_document_id: 7, is_current: true } },
    { document_id: 13, version: { logical_document_id: 13, is_current: true } },
  ];
  it('재발행으로 ID가 바뀌면 같은 논리 문서의 현재 본을 연다', () => {
    expect(currentDocumentFor({ issue_key: 'document:7', document_id: 9 }, docs)).toBe(12);
  });
  it('같은 종류의 별도 서류와 혼동하지 않는다', () => {
    expect(currentDocumentFor({ issue_key: 'document:13', document_id: 13 }, docs)).toBe(13);
    expect(currentDocumentFor({ issue_key: 'document:99', document_id: 99 }, docs)).toBeNull();
  });
  it('누락 요청에 도착한 한 개의 현재 본을 열고, 여러 개이면 임의로 고르지 않는다', () => {
    const item = {issue_key:'missing:estimate',document_id:null,document_type:'estimate' as const};
    const one = [{document_id:20,document_type:'estimate' as const,version:{logical_document_id:20,is_current:true}}];
    expect(currentDocumentFor(item,one)).toBe(20);
    expect(currentDocumentFor(item,[...one,{...one[0],document_id:21}])).toBeNull();
    expect(currentDocumentFor(item,[{...one[0],version:{logical_document_id:20,is_current:false}}])).toBeNull();
  });
});

describe('원문 확인 동의의 기준', () => {
  it('계약·revision·fingerprint가 모두 같을 때만 같은 기준', () => {
    const a = { contractId: 1, revision: 3, fingerprint: 'x' };
    expect(sameBasis(a, { ...a })).toBe(true);
    expect(sameBasis(a, { ...a, revision: 4 })).toBe(false);
    expect(sameBasis(a, { ...a, fingerprint: 'y' })).toBe(false);
    expect(sameBasis(a, { ...a, contractId: 2 })).toBe(false);
  });
});

describe('회사 안에서 확인할 것', () => {
  const doc = { document_id: 9, document_type: 'estimate' } as IssueGroup['document'];
  const mixed: IssueGroup = {
    key: 'doc-9', kind: 'vendor', title: '견적서', document: doc, status: 'FAIL',
    checks: [
      { rule_id: 'BUSINESS_NO_MATCH', status: 'FAIL', field: '9', message: '번호 다름', expected: null, actual: null } as never,
      { rule_id: 'AMOUNT_EXTRACTION', status: 'REVIEW', field: '9', message: '금액 판독', expected: null, actual: null } as never,
    ],
  };
  it('거래처 후보 서류의 판독 문제는 따로 남기고, 거래처 문제는 뺀다', () => {
    const out = splitInternalIssues([mixed], new Set(['d9']));
    expect(out).toHaveLength(1);
    expect(out[0].kind).toBe('reading');
    expect(out[0].checks.map((c) => c.rule_id)).toEqual(['AMOUNT_EXTRACTION']);
  });
  it('거래처 후보가 아닌 문제는 그대로', () => {
    expect(splitInternalIssues([mixed], new Set())).toEqual([mixed]);
  });
});

import { itemArrived } from './BundleRequest';

describe('요청한 서류가 올라왔는지', () => {
  const docs = [
    { document_id: 9, document_type: 'estimate' as const, version: { logical_document_id: 7, is_current: false } },
    { document_id: 12, document_type: 'estimate' as const, version: { logical_document_id: 7, is_current: true } },
  ];
  it('빠진 서류는 그 종류가 생기면 올라온 것', () => {
    expect(itemArrived({ issue_key: 'missing:bank_account', document_id: null, document_type: 'bank_account' }, docs)).toBe(false);
    expect(itemArrived({ issue_key: 'missing:estimate', document_id: null, document_type: 'estimate' }, docs)).toBe(true);
  });
  it('서류 보완은 같은 논리 문서의 현재 본이 바뀌면 올라온 것', () => {
    expect(itemArrived({ issue_key: 'document:7', document_id: 9, document_type: 'estimate' }, docs)).toBe(true);
    expect(itemArrived({ issue_key: 'document:7', document_id: 12, document_type: 'estimate' }, docs)).toBe(false);
  });
});
