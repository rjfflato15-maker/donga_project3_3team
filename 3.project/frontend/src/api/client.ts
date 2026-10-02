import { ContractDetail, ContractListItem, DocumentResponse, PipelineSimulationResponse,
  ValidationReportResponse, AutoContractSynthesisResponse, AnalysisFields, DocumentType, PilotInfo, AuditEntry } from '../types';

export async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, { credentials: 'same-origin', ...init });
  if (!res.ok) {
    if (res.status === 401) window.dispatchEvent(new Event('session-expired'));
    let message = '요청을 완료하지 못했습니다.';
    try {
      const body = await res.json();
      message = typeof body.detail === 'string' ? body.detail : (Array.isArray(body.detail) ? body.detail.map((e: { msg: string }) => e.msg).join(', ') : message);
    } catch { /* Use the readable fallback for non-JSON failures. */ }
    throw new Error(message);
  }
  return res.status === 204 ? undefined as T : res.json();
}

const json = (method: string, data: unknown): RequestInit => ({
  method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data),
});
const uploadBody = (files: File[], target?: string) => {
  const body = new FormData();
  files.forEach(file => body.append('files', file));
  if (target) body.append('target_document_type', target);
  return body;
};

export const api = {
  listContracts: () => requestJson<ContractListItem[]>('/api/contracts'),
  getContract: (id: number) => requestJson<ContractDetail>('/api/contracts/' + id),
  createContract: (data: { title: string; vendor_name: string; business_number: string; contract_amount: number; amount_basis?: string; tax_amount?: number | null; payment_mode?: string }) =>
    requestJson<ContractDetail>('/api/contracts', json('POST', data)),
  updateContract: (id: number, data: { title?: string; vendor_name?: string; business_number?: string; contract_amount?: number; amount_basis?: string; tax_amount?: number | null; payment_mode?: string; revision?: number; change_note?: string }) =>
    requestJson<ContractDetail>('/api/contracts/' + id, json('PUT', data)),
  deleteContract: (id: number) => requestJson<void>('/api/contracts/' + id, { method: 'DELETE' }),
  seedDemoContract: () => requestJson<ContractDetail>('/api/contracts/seed-demo', { method: 'POST' }),
  async parseContractFile(file: File): Promise<{ title?: string; vendor_name?: string; business_number?: string; contract_amount?: number; issue_date?: string; document_type?: string; raw_text_snippet?: string }> {
    const body = new FormData(); body.append('file', file);
    return requestJson('/api/contracts/parse-file', { method: 'POST', body });
  },
  uploadDocuments: (id: number, files: File[], target?: string) =>
    requestJson<DocumentResponse[]>('/api/contracts/' + id + '/documents', { method: 'POST', body: uploadBody(files, target) }),
  getDocument: (id: number) => requestJson<DocumentResponse>('/api/documents/' + id),
  reissueDocument: (contractId: number, file: File, replacesId: number, revision: number, changeNote: string) => {
    const body = new FormData();
    body.append('files', file);
    body.append('upload_mode', 'REISSUE');
    body.append('replaces_document_id', String(replacesId));
    body.append('revision', String(revision));
    body.append('change_note', changeNote);
    return requestJson<DocumentResponse[]>('/api/contracts/' + contractId + '/documents', { method: 'POST', body });
  },
  deleteDocument: (id: number) => requestJson<void>('/api/documents/' + id, { method: 'DELETE' }),
  restoreOriginal: (id: number, file: File) => {
    const body = new FormData(); body.append('file', file);
    return requestJson<DocumentResponse>('/api/documents/' + id + '/original', { method: 'PUT', body });
  },
  correctFields: (id: number, fields: AnalysisFields, document_type: DocumentType, revision: number, note: string) =>
    requestJson<DocumentResponse>('/api/documents/' + id + '/fields', json('PUT', { fields, document_type, revision, note })),
  triggerValidation: (id: number) => requestJson<ValidationReportResponse>('/api/contracts/' + id + '/validate', { method: 'POST' }),
  simulatePipeline: (id: number) => requestJson<PipelineSimulationResponse>('/api/pipeline/' + id + '/simulate', { method: 'POST' }),
  autoParseBatchDocuments: (files: File[]) => requestJson<AutoContractSynthesisResponse>('/api/contracts/auto-parse-batch', { method: 'POST', body: uploadBody(files) }),
  autoCreateBatchContract: (data: { title: string; vendor_name: string; business_number: string; contract_amount: number }, files: File[]) => {
    const body = uploadBody(files);
    Object.entries(data).forEach(([key, value]) => body.append(key, String(value)));
    return requestJson<ContractDetail>('/api/contracts/auto-create-batch', { method: 'POST', body });
  },
  pilotInfo: () => requestJson<PilotInfo>('/api/pilot/info'),
  pilotMetrics: () => requestJson<import('../types').PilotMetrics>('/api/pilot/metrics'),
  savePilotSettings: (company_name: string, required_document_types: DocumentType[]) =>
    requestJson<PilotInfo>('/api/pilot/settings', json('PUT', { company_name, required_document_types })),
  audit: (id?: number) => requestJson<AuditEntry[]>('/api/pilot/audit' + (id ? '?contract_id=' + id : '')),
  review: (id: number, data: { decision: string; note: string; revision: number; fingerprint: string; acknowledge_unverified: boolean }) =>
    requestJson<ContractDetail>('/api/contracts/' + id + '/reviews', json('POST', data)),
  reviewSnapshot: (id: number) => requestJson<{ snapshot: { checks: { status: string; message: string }[] }; note: string }>('/api/pilot/reviews/' + id),
  users: () => requestJson<{ user_id: number; email: string; display_name: string; role: string; active: boolean; must_change_password: boolean }[]>('/api/pilot/users'),
  addUser: (data: { email: string; display_name: string; role: string; temporary_password: string }) => requestJson('/api/pilot/users', json('POST', data)),
  setUserActive: (id: number, active: boolean) => requestJson('/api/pilot/users/' + id, json('PATCH', { active })),
  resetPassword: (id: number, temporary_password: string) => requestJson('/api/pilot/users/' + id + '/reset-password', json('POST', { temporary_password })),
};

export async function downloadProtected(path: string, fallback: string) {
  const res = await fetch(path, { credentials: 'same-origin' });
  if (!res.ok) {
    if (res.status === 401) window.dispatchEvent(new Event('session-expired'));
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || '다운로드를 완료하지 못했습니다.');
  }
  const disposition = res.headers.get('Content-Disposition') || '';
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const name = encoded ? decodeURIComponent(encoded) : fallback;
  const url = URL.createObjectURL(await res.blob());
  const anchor = document.createElement('a');
  anchor.href = url; anchor.download = name; document.body.appendChild(anchor); anchor.click(); anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
