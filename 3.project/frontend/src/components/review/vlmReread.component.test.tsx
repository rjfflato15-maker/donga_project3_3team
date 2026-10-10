// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { DocumentWorkspace } from './DocumentWorkspace';
import { requestJson } from '../../api/client';
import { DocumentResponse } from '../../types';
import { useVlmReread, VlmResult } from '../../hooks/useVlmReread';

vi.mock('../../api/client', () => ({ api: { correctFields: vi.fn() }, requestJson: vi.fn(), downloadProtected: vi.fn() }));
vi.mock('../../hooks/useVlmReread', () => ({ useVlmReread: vi.fn() }));
const doc: DocumentResponse = {
  document_id: 4, contract_id: 1, document_type: 'tax_invoice', original_file_name: 'demo.pdf',
  file_available: true, confidence: 1, processing_status: 'COMPLETED', mask_status: 'MASKED',
  analysis: { fields: { tax_amount: null, total_amount: 100, company_name: '가상 거래처' }, warnings: [] },
};
const result: VlmResult = {
  run_id: 8, page: 1, created_at: '2026-10-07T01:00:00Z', model: { name: 'qwen2.5vl:7b' },
  candidates: [
    { field: 'tax_amount', value: 0, quote: '세액: 0원', usable: true, reason: '원문 대조 전 후보' },
    { field: 'total_amount', value: 100, quote: '합계: 100원', usable: true, reason: '원문 대조 전 후보' },
    { field: 'company_name', value: '다른 거래처', quote: '거래처: 다른 거래처', usable: true, reason: '원문 대조 전 후보', changed: true },
  ],
};
const proof = { document_id: 4, source_version_verified: true, fields: {
  tax_amount: { value: null, source: 'UNAVAILABLE', evidence: [] },
  total_amount: { value: 100, source: 'RULE', evidence: [] },
  company_name: { value: '가상 거래처', source: 'RULE', evidence: [] },
} };
const hook = (value: VlmResult = result) => ({ status: { ready: true, model: 'test', message: '' }, result: value, busy: false, error: '', reread: vi.fn(), refresh: vi.fn() });
const props = { doc, checks: [], revision: 3, isMaskingEnabled: true, canEdit: true, onClose: () => {}, onChanged: async () => {} };
beforeEach(() => {
  HTMLElement.prototype.scrollIntoView = vi.fn();
  URL.createObjectURL = vi.fn(() => 'blob:source'); URL.revokeObjectURL = vi.fn();
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, blob: async () => new Blob(['source']) })));
  vi.mocked(useVlmReread).mockReturnValue(hook());
  vi.mocked(requestJson).mockImplementation(async url => url.includes('pages-info') ? { total_pages: 1 } : { revision: 3, documents: [proof] });
});
afterEach(() => { cleanup(); vi.resetAllMocks(); vi.unstubAllGlobals(); });
async function loadOriginal() { fireEvent.load(await screen.findByRole('img')); }

it('live workspace applies changed 0 won only after the original is ready and explicit confirmation', async () => {
  const changed = vi.fn(async () => {});
  render(<DocumentWorkspace {...props} onChanged={changed} />);
  expect(screen.queryByRole('checkbox', { name: '합계 AI 제안 선택' })).toBeNull();
  expect(await screen.findByRole('checkbox', { name: '거래처 AI 제안 선택' })).toHaveProperty('disabled', true);
  expect(screen.getByRole('button', { name: '원문 확인 후 1개 적용' })).toHaveProperty('disabled', true);
  expect(vi.mocked(requestJson).mock.calls.some(([url]) => url.endsWith('/vlm-confirm'))).toBe(false);
  await loadOriginal();
  fireEvent.click(screen.getByRole('button', { name: '원문 확인 후 1개 적용' }));
  await waitFor(() => expect(changed).toHaveBeenCalledOnce());
  const call = vi.mocked(requestJson).mock.calls.find(([url]) => url.endsWith('/vlm-confirm'))!;
  expect(JSON.parse(String(call[1]?.body))).toEqual({ run_id: 8, revision: 3, fields: ['tax_amount'], acknowledge_original: true, note: '1쪽 원문을 직접 대조하고 부가세 AI 후보를 선택함' });
});

it('live workspace honors server change flags even when protected values look identical', async () => {
  vi.mocked(useVlmReread).mockReturnValue(hook({ ...result, candidates: [
    { field: 'company_name', value: '[가림]', quote: '[가림]', usable: true, reason: '', changed: false },
    { field: 'business_registration_no', value: '[가림]', quote: '[가림]', usable: true, reason: '', changed: true },
  ] }));
  render(<DocumentWorkspace {...props} />); await loadOriginal();
  expect(screen.queryByRole('checkbox', { name: '거래처 AI 제안 선택' })).toBeNull();
  expect(screen.getByRole('checkbox', { name: '사업자번호 AI 제안 선택' })).toHaveProperty('disabled', true);
  expect(screen.getByRole('button', { name: '원문 확인 후 0개 적용' })).toHaveProperty('disabled', true);
  expect(screen.getByText('AI [가림]')).toBeTruthy();
});

it('live workspace replaces candidate selection on a new run and blocks saving without an original', async () => {
  const view = render(<DocumentWorkspace {...props} />); await loadOriginal();
  fireEvent.click(screen.getByRole('checkbox', { name: '부가세 AI 제안 선택' }));
  expect(screen.getByRole('button', { name: '원문 확인 후 0개 적용' })).toHaveProperty('disabled', true);
  vi.mocked(useVlmReread).mockReturnValue(hook({ ...result, run_id: 9, candidates: [{ ...result.candidates[1], value: 200, changed: true }] }));
  view.rerender(<DocumentWorkspace {...props} doc={{ ...doc, file_available: false }} />);
  expect(screen.queryByRole('checkbox', { name: '부가세 AI 제안 선택' })).toBeNull();
  expect(screen.getByRole('checkbox', { name: '합계 AI 제안 선택' })).toHaveProperty('checked', true);
  expect(screen.getByRole('checkbox', { name: '합계 AI 제안 선택' })).toHaveProperty('disabled', true);
  expect(screen.getByRole('button', { name: '원문 확인 후 1개 적용' })).toHaveProperty('disabled', true);
});

it('returning to masking clears previously selected private candidate values', async () => {
  const view = render(<DocumentWorkspace {...props} isMaskingEnabled={false} />); await loadOriginal();
  expect(screen.getByRole('checkbox', { name: '거래처 AI 제안 선택' })).toHaveProperty('checked', true);
  view.rerender(<DocumentWorkspace {...props} />); await loadOriginal();
  expect(screen.getByRole('checkbox', { name: '거래처 AI 제안 선택' })).toHaveProperty('checked', false);
  expect(await screen.findByRole('checkbox', { name: '거래처 AI 제안 선택' })).toHaveProperty('disabled', true);
  expect(screen.getByRole('button', { name: '원문 확인 후 0개 적용' })).toHaveProperty('disabled', true);
});
