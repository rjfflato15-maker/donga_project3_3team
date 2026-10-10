import { requestJson } from '../../api/client';
import type { Assignment, Assignee } from './model';

const base = (contractId: number) => `/api/pilot/contracts/${contractId}/assignments`;

export const assignmentApi = {
  mine: () => requestJson<{ assignments: Assignment[]; count: number }>('/api/pilot/assignments/mine'),
  list: (contractId: number) => requestJson<{ assignments: Assignment[] }>(base(contractId)),
  assignees: () => requestJson<Assignee[]>('/api/pilot/assignees'),
  create: (contractId: number, body: unknown) => requestJson(base(contractId), {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  }),
  change: (contractId: number, assignmentId: number, body: unknown) => requestJson(`${base(contractId)}/${assignmentId}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  }),
};
