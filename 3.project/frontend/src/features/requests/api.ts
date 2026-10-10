import { requestJson } from '../../api/client';
import type { BundleContext, BundledRequest } from './model';

const base = (cid: number) => `/api/pilot/contracts/${cid}`;
export const bundleApi = {
  context: (cid: number, signal?: AbortSignal) => requestJson<BundleContext>(`${base(cid)}/resubmission-bundle-context`, { signal }),
  create: (cid: number, body: unknown) => requestJson<BundledRequest>(`${base(cid)}/resubmission-bundles`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  }),
  resolve: (cid: number, rid: number, body: unknown) => requestJson<BundledRequest>(`${base(cid)}/resubmission-bundles/${rid}/items`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  }),
  correct: (cid:number,rid:number,body:unknown)=>requestJson<BundledRequest>(`${base(cid)}/resubmission-bundles/${rid}/corrections`,{
    method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),
  }),
};

