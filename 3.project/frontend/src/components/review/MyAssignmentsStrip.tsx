import React, { useEffect, useState } from 'react';
import { Assignment, assignmentApi, ASSIGNMENT_STATUS_KO } from './AssignmentPanel';

interface Props {
  refreshKey: unknown;
  contracts: { contract_id: number; title: string }[];
  onOpen: (contractId: number) => void;
}

/** 대시보드 맨 위 '내가 맡은 일': 맡은 일이 없으면 아무것도 그리지 않는다 */
export const MyAssignmentsStrip: React.FC<Props> = ({ refreshKey, contracts, onOpen }) => {
  const [items, setItems] = useState<Assignment[]>([]);
  useEffect(() => {
    let active = true;
    assignmentApi.mine().then((r) => { if (active) setItems(r.assignments); }).catch(() => { if (active) setItems([]); });
    return () => { active = false; };
  }, [refreshKey]);
  if (items.length === 0) return null;
  const titleOf = (id: number) => contracts.find((c) => c.contract_id === id)?.title ?? `계약 ${id}`;
  return (
    <section className="rounded-2xl border-2 border-indigo-200 bg-indigo-50/60 p-4" aria-labelledby="mine-title">
      <h2 id="mine-title" className="mb-2 font-bold text-indigo-900">내가 맡은 일 {items.length}건</h2>
      <ul className="space-y-1.5">
        {items.map((a) => (
          <li key={a.assignment_id}>
            <button onClick={() => onOpen(a.contract_id)} className="flex w-full flex-wrap items-center gap-2 rounded-xl bg-white px-3 py-2 text-left text-sm hover:bg-indigo-50">
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-bold text-slate-600">{ASSIGNMENT_STATUS_KO[a.status]}</span>
              <b className="text-slate-900">{a.title}</b>
              <span className="text-xs text-slate-500">· {titleOf(a.contract_id)} · {a.assigner_name}님이 맡김</span>
              {a.is_stale && <span className="text-xs font-semibold text-amber-700">자료 바뀜</span>}
              {a.due_on && <span className={`ml-auto text-xs ${a.overdue ? 'font-bold text-rose-600' : 'text-slate-500'}`}>기한 {a.due_on}{a.overdue ? ' 지남' : ''}</span>}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
};
