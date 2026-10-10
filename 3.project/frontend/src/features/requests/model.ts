import type { ContractDetail, DocumentType } from '../../types';
import type { ResubmissionRequest } from '../../api/followUp';
import { DOCUMENT_LABEL as DOCUMENT_TYPE_KO } from '../../utils/documentLabels';
import { fixParticles, josa } from '../../utils/korean';

export interface BundleCandidate {
  issue_key: string;
  title: string;
  document_type: DocumentType | null;
  document_id: number | null;
  reason: string;
  requires_original_review: boolean;
  already_requested?: boolean;
  pending_items?: { request_id: number; item_id: number }[];
  checks?:import('../../types').ValidationCheck[];snapshot?:unknown;
}
export interface BundleContext {
  contract_id: number;
  revision: number;
  fingerprint: string;
  document_counts: { required: number; received: number; missing: number };
  vendor_candidates: BundleCandidate[];
  internal_items: BundleCandidate[];
  reading_items: BundleCandidate[];
  pending_items: { request_id: number; item_id: number; issue_key: string; title: string }[];
  legacy_pending_request_count: number;
}
export interface BundleItem {
  item_id: number; issue_key: string; title: string; document_type: DocumentType | null; document_id: number | null;
  reason: string; status: 'WAITING_RESPONSE' | 'RECEIVED' | 'CANCELLED'; resolution_note: string | null;
}
export interface RequestBundle {
  request_revision: number;
  items: BundleItem[];
  counts: { total: number; waiting: number; received: number; cancelled: number };
}
export type BundledRequest = ResubmissionRequest & { bundle?: RequestBundle | null };

/** 선택·동의를 받은 자료 기준. 기준이 바뀌면 그 동의로 저장하지 않는다 */
export interface Basis { contractId: number; revision: number; fingerprint: string }
export const sameBasis = (a: Basis, b: Basis) => a.contractId === b.contractId && a.revision === b.revision && a.fingerprint === b.fingerprint;

/** 요청 항목의 현재 서류: 재발행으로 ID가 바뀌어도 같은 논리 문서(issue_key 'document:{논리 ID}')의 현재 본을 찾는다 */
export function currentDocumentFor(item: { issue_key: string; document_id: number | null; document_type?: DocumentType | null }, docs: { document_id: number; document_type?: DocumentType; version?: { logical_document_id: number; is_current: boolean } | null }[]): number | null {
  if (item.issue_key.startsWith('missing:') && item.document_type) {
    const matches = docs.filter((d) => d.document_type === item.document_type && d.version?.is_current !== false);
    return matches.length === 1 ? matches[0].document_id : null;
  }
  const m = /^document:(\d+)$/.exec(item.issue_key);
  if (m) {
    const logical = Number(m[1]);
    const cur = docs.find((d) => (d.version?.logical_document_id ?? d.document_id) === logical && d.version?.is_current !== false);
    if (cur) return cur.document_id;
  }
  return item.document_id != null && docs.some((d) => d.document_id === item.document_id) ? item.document_id : null;
}

/** 요청 뒤에 그 서류가 올라왔는지: 빠진 서류는 그 종류가 생겼는지, 서류 보완은 같은 논리 문서의 현재 본이 바뀌었는지 */
export function itemArrived(i: { issue_key: string; document_id: number | null; document_type: DocumentType | null }, docs: { document_id: number; document_type: DocumentType; version?: { logical_document_id: number; is_current: boolean } | null }[]): boolean {
  if (i.issue_key.startsWith('missing:')) return docs.some((d) => d.document_type === i.document_type && d.version?.is_current !== false);
  const cur = currentDocumentFor(i, docs);
  return cur != null && i.document_id != null && cur !== i.document_id;
}

export const docName = (c: { document_type: DocumentType | null; title: string }) => (c.document_type ? DOCUMENT_TYPE_KO[c.document_type] ?? c.title : c.title);

const AMOUNT_RULE_WORDS = /금액|합계|세액|공급가액/;

export function buildText(contract: Pick<ContractDetail, 'vendor_name' | 'title'>, items: BundleCandidate[], long: boolean) {
  const lines = items.map((c) => {
    const name = docName(c);
    if (!c.document_id) return `- ${josa(name, '을/를')} 보내 주세요.`;
    const reasons = c.reason.split('\n').map((r) => fixParticles(r.replace(/^[^:]+:\s*/, '').trim())).filter(Boolean);
    const fix = c.document_type === 'tax_invoice' && AMOUNT_RULE_WORDS.test(c.reason) ? '홈택스에서 수정 세금계산서를 발행해 주세요.' : `확인 후 고친 ${josa(name, '을/를')} 보내 주세요.`;
    if (long) return [`- ${name}`, ...reasons.map((r) => `  · ${r}`), `  → ${fix}`].join('\n');
    return `- ${name}: ${reasons[0] ?? ''}${reasons.length > 1 ? ` 외 ${reasons.length - 1}건` : ''} ${fix}`;
  });
  if (!long) return `[${contract.vendor_name}] '${contract.title}' 계약 증빙 관련 요청드립니다.\n${lines.join('\n')}`;
  return [`${contract.vendor_name} 담당자님, 안녕하세요.`, '', `「${contract.title}」 계약의 증빙 서류를 확인한 결과, 아래 ${items.length}건을 부탁드립니다.`, ...lines, '', '감사합니다.'].join('\n');
}

