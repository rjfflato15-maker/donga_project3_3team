// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { DocumentViewerModal } from './DocumentViewerModal';
import { requestJson } from '../api/client';
import { DocumentResponse } from '../types';

vi.mock('../api/client', () => ({ requestJson: vi.fn(), downloadProtected: vi.fn() }));
const doc: DocumentResponse = { document_id: 42, contract_id: 1, document_type: 'estimate',
  original_file_name: 'synthetic.txt', file_available: true, confidence: 1,
  processing_status: 'COMPLETED', mask_status: 'MASKED', analysis: { fields: {}, warnings: [] },
  raw_text: 'RAW_PRIVATE_SENTINEL', masked_text: 'OLD_SIDECAR_PRIVATE_SENTINEL' };
beforeEach(() => { vi.mocked(requestJson).mockResolvedValue({ text: 'Protected preview' }); });
afterEach(() => { cleanup(); vi.resetAllMocks(); });

it('never substitutes a stale sidecar while masked preview is pending or fails', async () => {
  let reject!: (error: Error) => void;
  vi.mocked(requestJson).mockImplementation(() => new Promise((_, fail) => { reject = fail; }));
  const { container } = render(<DocumentViewerModal document={doc} onClose={() => {}} />);
  expect(container.textContent).not.toContain('PRIVATE_SENTINEL');
  fireEvent.click(screen.getByRole('button', { name: /문서 텍스트 미리보기/ }));
  expect(container.textContent).not.toContain('PRIVATE_SENTINEL');
  reject(new Error('Synthetic masking unavailable'));
  expect((await screen.findByRole('alert')).textContent).toContain('Synthetic masking unavailable');
  expect(container.textContent).not.toContain('PRIVATE_SENTINEL');
});

it('drops an earlier raw response immediately when masking is turned back on', async () => {
  vi.mocked(requestJson).mockImplementation(async path => {
    if (path.endsWith('masked=false')) return { text: 'RAW_PRIVATE_SENTINEL' };
    return { text: 'Protected preview' };
  });
  const { container } = render(<DocumentViewerModal document={doc} onClose={() => {}} isMaskingEnabled={false} />);
  await screen.findByText('RAW_PRIVATE_SENTINEL');
  vi.mocked(requestJson).mockImplementation(() => new Promise(() => {}));
  fireEvent.click(screen.getByRole('button', { name: '개인정보·사업자 마스킹: OFF' }));
  expect(container.textContent).not.toContain('RAW_PRIVATE_SENTINEL');
  expect(container.textContent).not.toContain('OLD_SIDECAR_PRIVATE_SENTINEL');
});

it('renders hostile stored field and document text as inert text, without HTML nodes', async () => {
  const payload = '<img src=x onerror="window.pwned=1"><script>window.pwned=2</script><a href="javascript:alert(1)">click</a>';
  vi.mocked(requestJson).mockResolvedValue({ text: payload });
  const { container } = render(<DocumentViewerModal document={{ ...doc, analysis: {
    fields: { company_name: payload }, warnings: [] } }} onClose={() => {}} isMaskingEnabled={false} />);
  await waitFor(() => expect(screen.getAllByText(payload).length).toBeGreaterThan(0));
  fireEvent.click(screen.getByRole('button', { name: /문서 텍스트 미리보기/ }));
  await waitFor(() => expect(container.textContent).toContain(payload));
  expect(container.querySelector('script, [onerror], a[href^="javascript:"]')).toBeNull();
  expect(container.querySelector('img[src="x"]')).toBeNull();
});
