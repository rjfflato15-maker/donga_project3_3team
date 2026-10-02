import { requestJson } from './client';

export type ContactMethod = 'KAKAO' | 'SMS' | 'EMAIL' | 'PHONE' | 'OTHER';

export const CONTACT_KO: Record<ContactMethod, string> = {
  KAKAO: '카카오톡',
  SMS: '문자',
  EMAIL: '이메일',
  PHONE: '전화',
  OTHER: '기타',
};

/** '…로 요청' 문장용 (조사 포함) */
export const CONTACT_VIA: Record<ContactMethod, string> = {
  KAKAO: '카카오톡으로',
  SMS: '문자로',
  EMAIL: '이메일로',
  PHONE: '전화로',
  OTHER: '기타 방법으로',
};

export interface ResubmissionRequest {
  request_id: number;
  contract_id: number;
  contact_method: ContactMethod;
  requested_on: string;
  due_on: string | null;
  memo: string;
  status: 'WAITING_RESPONSE' | 'RECEIVED' | 'CANCELLED';
  actor_name: string;
  created_at: string;
  resolved_at: string | null;
  resolution_note: string | null;
}

const json = (method: string, data: unknown): RequestInit => ({
  method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data),
});
const base = (contractId: number) => `/api/pilot/contracts/${contractId}/resubmission-requests`;

export const followUpApi = {
  list: (contractId: number) => requestJson<ResubmissionRequest[]>(base(contractId)),
  record: (contractId: number, data: { contact_method: ContactMethod; due_on?: string | null; memo: string }) =>
    requestJson<ResubmissionRequest>(base(contractId), json('POST', data)),
  resolve: (contractId: number, requestId: number, status: 'RECEIVED' | 'CANCELLED', note: string) =>
    requestJson<ResubmissionRequest>(`${base(contractId)}/${requestId}`, json('PATCH', { status, note })),
};
