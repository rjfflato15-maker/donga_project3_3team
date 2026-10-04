/**
 * 담당자 흐름 단계: ① 서류 받기 → ② 확인 → ③ 보완 → ④ 결재 → ⑤ 지급 → 끝.
 * 백엔드가 stage를 주면 그대로 쓰고, 없으면 목록·상세의 값으로 같은 규칙을 계산한다.
 */
export type Stage = 'RECEIVING' | 'CHECK' | 'WAITING' | 'APPROVAL' | 'PAYMENT' | 'DONE';

export const STAGE_STEPS: { key: Exclude<Stage, 'DONE'>; no: number; label: string }[] = [
  { key: 'RECEIVING', no: 1, label: '서류 받기' },
  { key: 'CHECK', no: 2, label: '확인' },
  { key: 'WAITING', no: 3, label: '보완' },
  { key: 'APPROVAL', no: 4, label: '결재' },
  { key: 'PAYMENT', no: 5, label: '지급' },
];

export const STAGE_NO: Record<Stage, number> = { RECEIVING: 1, CHECK: 2, WAITING: 3, APPROVAL: 4, PAYMENT: 5, DONE: 6 };

export const STAGE_KO: Record<Stage, string> = {
  RECEIVING: '① 서류 받기', CHECK: '② 확인', WAITING: '③ 보완', APPROVAL: '④ 결재', PAYMENT: '⑤ 지급', DONE: '끝',
};

export const STAGE_PILL: Record<Stage, string> = {
  RECEIVING: 'bg-slate-100 text-slate-700',
  CHECK: 'bg-amber-100 text-amber-800',
  WAITING: 'bg-sky-100 text-sky-800',
  APPROVAL: 'bg-violet-100 text-violet-800',
  PAYMENT: 'bg-emerald-100 text-emerald-800',
  DONE: 'bg-slate-100 text-slate-500',
};

const KNOWN = new Set<Stage>(['RECEIVING', 'CHECK', 'WAITING', 'APPROVAL', 'PAYMENT', 'DONE']);

export interface StageInput {
  stage?: string | null;
  approval_status?: string | null;
  paid_on?: string | null;
  waiting_request_count?: number;
  /** 거래처에게 받아야 하는데 없는 서류 수 */
  missing_count?: number;
  /** 국세청 미연동 안내를 뺀, 사람이 확인할 항목 수 */
  open_issue_count?: number;
}

export function stageOf(c: StageInput): Stage {
  const given = (c.stage || '').toUpperCase() as Stage;
  if (KNOWN.has(given)) return given;
  const approval = (c.approval_status || '').toUpperCase();
  if (c.paid_on) return 'DONE';
  if (approval === 'CONFIRMED') return 'PAYMENT';
  if ((c.waiting_request_count ?? 0) > 0) return 'WAITING';
  if ((c.missing_count ?? 0) > 0) return 'RECEIVING';
  if ((c.open_issue_count ?? 0) > 0 || approval === 'RETURNED') return 'CHECK';
  return 'APPROVAL';
}

export type StepState = 'done' | 'pending' | 'skipped' | 'todo';

/** 실제로 끝난 단계만 'done'. 지금 단계보다 앞인데 남은 일이 있으면 'pending', 요청한 적 없이 지나간 보완은 'skipped' */
export function stepStates(i: { stage: Stage; missing: number; issues: number; waiting: number; requests: number; approved: boolean; paid: boolean }): Record<Exclude<Stage, 'DONE'>, StepState> {
  const no = STAGE_NO[i.stage];
  return {
    RECEIVING: i.missing === 0 ? 'done' : no > 1 ? 'pending' : 'todo',
    CHECK: i.issues === 0 ? 'done' : no > 2 ? 'pending' : 'todo',
    WAITING: i.waiting > 0 ? 'todo' : i.requests > 0 ? 'done' : no > 3 ? 'skipped' : 'todo',
    APPROVAL: i.approved ? 'done' : 'todo',
    PAYMENT: i.paid ? 'done' : 'todo',
  };
}
