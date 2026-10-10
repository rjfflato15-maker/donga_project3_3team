export interface Assignment {
  assignment_id: number; contract_id: number; document_id: number | null; contract_revision: number; assignment_revision: number;
  assigner_id: number; assigner_name: string; assignee_id: number; assignee_name: string;
  title: string; memo: string; due_on: string | null; status: 'OPEN' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED';
  is_stale: boolean; overdue: boolean; created_at: string; completed_at: string | null;
}
export interface Assignee { user_id: number; display_name: string; role: string }

export const ASSIGNMENT_STATUS_KO: Record<Assignment['status'], string> = { OPEN: '맡김', IN_PROGRESS: '하는 중', COMPLETED: '끝남', CANCELLED: '취소' };
