import React, { useEffect, useState } from 'react';
import { ContractDetail } from '../../types';
import { requestJson } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { DOCUMENT_TYPE_KO } from '../../utils/reviewSummary';
import { UserPlus } from 'lucide-react';

export interface Assignment {
  assignment_id: number; contract_id: number; document_id: number | null; contract_revision: number; assignment_revision: number;
  assigner_id: number; assigner_name: string; assignee_id: number; assignee_name: string;
  title: string; memo: string; due_on: string | null; status: 'OPEN' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED';
  is_stale: boolean; overdue: boolean; created_at: string; completed_at: string | null;
}
interface Assignee { user_id: number; display_name: string; role: string }

export const ASSIGNMENT_STATUS_KO: Record<Assignment['status'], string> = { OPEN: '맡김', IN_PROGRESS: '하는 중', COMPLETED: '끝남', CANCELLED: '취소' };
const ROLE_KO: Record<string, string> = { operator: '담당자', representative: '대표', admin: '관리자' };
const isOpen = (a: Assignment) => a.status === 'OPEN' || a.status === 'IN_PROGRESS';

export const assignmentApi = {
  mine: () => requestJson<{ assignments: Assignment[]; count: number }>('/api/pilot/assignments/mine'),
};

/** 계약 화면 '사내 담당자에게 맡기기': 맡겨도 결재·수정 권한은 바뀌지 않는다 */
export const AssignmentPanel: React.FC<{ contract: ContractDetail; initialTitle?: string }> = ({ contract, initialTitle }) => {
  const { user } = useAuth();
  const me = user?.user_id;
  const rep = user?.role === 'representative';
  const [items, setItems] = useState<Assignment[]>([]);
  const [people, setPeople] = useState<Assignee[]>([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ assignee_id: '', title: '', memo: '', due_on: '', document_id: '' });
  const [note, setNote] = useState('');
  const [acting, setActing] = useState<{ id: number; action: 'COMPLETE' | 'CANCEL' } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const revision = contract.workflow?.revision ?? 1;
  const base = `/api/pilot/contracts/${contract.contract_id}/assignments`;

  const load = async () => {
    try { setItems((await requestJson<{ assignments: Assignment[] }>(base)).assignments); setError(''); }
    catch (e) { setError(e instanceof Error ? e.message : '맡긴 일을 불러오지 못했습니다.'); }
  };
  useEffect(() => { void load(); setActing(null); }, [contract.contract_id, contract.updated_at]);
  useEffect(() => { requestJson<Assignee[]>('/api/pilot/assignees').then(setPeople).catch(() => setPeople([])); }, []);
  useEffect(() => { if (initialTitle) { setOpen(true); setForm((f) => ({ ...f, title: initialTitle })); } }, [initialTitle]);

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true); setError('');
    try { await fn(); await load(); return true; }
    catch (e) { setError(e instanceof Error ? e.message : '처리하지 못했습니다.'); await load(); return false; }
    finally { setBusy(false); }
  };
  const create = () => run(() => requestJson(base, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      assignee_id: Number(form.assignee_id), contract_revision: revision, title: form.title.trim(), memo: form.memo.trim(),
      due_on: form.due_on || null, document_id: form.document_id ? Number(form.document_id) : null,
    }),
  })).then((ok) => { if (ok) { setOpen(false); setForm({ assignee_id: '', title: '', memo: '', due_on: '', document_id: '' }); } });
  const change = (a: Assignment, action: string, noteText: string, extra: Record<string, unknown> = {}) => run(() => requestJson(`${base}/${a.assignment_id}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, assignment_revision: a.assignment_revision, note: noteText, ...extra }),
  })).then((ok) => { if (ok) { setActing(null); setNote(''); } });

  const active = items.filter(isOpen);
  const closed = items.filter((a) => !isOpen(a));
  const docName = (id: number | null) => {
    const d = id ? contract.documents.find((x) => x.document_id === id) : null;
    return d ? DOCUMENT_TYPE_KO[d.document_type] ?? d.document_type : null;
  };

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 space-y-3" aria-labelledby="assign-title">
      <div className="flex flex-wrap items-center gap-2">
        <h2 id="assign-title" className="font-bold text-slate-900">사내 담당자에게 맡기기</h2>
        <span className="text-xs text-slate-500">맡겨도 결재·수정 권한은 그대로입니다.</span>
        {!open && <button onClick={() => setOpen(true)} className="ml-auto inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"><UserPlus className="h-4 w-4" />일 맡기기</button>}
      </div>

      {open && (
        <div className="grid gap-2 rounded-xl bg-slate-50 p-3 text-sm sm:grid-cols-2">
          <label className="space-y-1"><span className="text-xs text-slate-500">누구에게</span>
            <select value={form.assignee_id} onChange={(e) => setForm({ ...form, assignee_id: e.target.value })} className="w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5">
              <option value="">고르세요</option>
              {people.map((p) => <option key={p.user_id} value={p.user_id}>{p.display_name} ({ROLE_KO[p.role] ?? p.role}){p.user_id === me ? ' · 나' : ''}</option>)}
            </select></label>
          <label className="space-y-1"><span className="text-xs text-slate-500">어느 서류 (선택)</span>
            <select value={form.document_id} onChange={(e) => setForm({ ...form, document_id: e.target.value })} className="w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5">
              <option value="">계약 전체</option>
              {contract.documents.map((d) => <option key={d.document_id} value={d.document_id}>{DOCUMENT_TYPE_KO[d.document_type] ?? d.document_type} · {d.original_file_name}</option>)}
            </select></label>
          <label className="space-y-1 sm:col-span-2"><span className="text-xs text-slate-500">할 일</span>
            <input value={form.title} maxLength={200} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="예: 견적서 합계 금액 원문 확인" className="w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5" /></label>
          <label className="space-y-1 sm:col-span-2"><span className="text-xs text-slate-500">메모 (선택)</span>
            <textarea value={form.memo} maxLength={2000} rows={2} onChange={(e) => setForm({ ...form, memo: e.target.value })} className="w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5" /></label>
          <label className="space-y-1"><span className="text-xs text-slate-500">기한 (선택)</span>
            <input type="date" value={form.due_on} onChange={(e) => setForm({ ...form, due_on: e.target.value })} className="w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5" /></label>
          <div className="flex items-end justify-end gap-2">
            <button onClick={() => setOpen(false)} className="rounded-lg px-3 py-1.5 text-slate-600">닫기</button>
            <button onClick={() => void create()} disabled={busy || !form.assignee_id || !form.title.trim()} className="rounded-lg bg-indigo-600 px-3 py-1.5 font-semibold text-white disabled:opacity-40">맡기기</button>
          </div>
        </div>
      )}

      {active.length === 0 && !open && <p className="text-sm text-slate-500">맡긴 일이 없습니다.</p>}
      <ul className="space-y-2">
        {active.map((a) => {
          const mine = a.assignee_id === me;
          const canComplete = (mine || rep) && !a.is_stale;
          const canCancel = a.assigner_id === me || rep;
          return (
            <li key={a.assignment_id} className={`rounded-xl border p-3 text-sm ${a.is_stale ? 'border-amber-300 bg-amber-50' : 'border-slate-200'}`}>
              <div className="flex flex-wrap items-center gap-2">
                <span className={`rounded-full px-2 py-0.5 text-xs font-bold ${a.status === 'IN_PROGRESS' ? 'bg-indigo-100 text-indigo-700' : 'bg-slate-100 text-slate-600'}`}>{ASSIGNMENT_STATUS_KO[a.status]}</span>
                <b className="text-slate-900">{a.title}</b>
                {docName(a.document_id) && <span className="text-xs text-slate-500">· {docName(a.document_id)}</span>}
                <span className="ml-auto text-xs text-slate-500">{a.assigner_name} → <b className="text-slate-700">{a.assignee_name}{mine ? ' (나)' : ''}</b>{a.due_on && <> · 기한 <span className={a.overdue ? 'font-bold text-rose-600' : ''}>{a.due_on}{a.overdue ? ' 지남' : ''}</span></>}</span>
              </div>
              {a.memo && <p className="mt-1 whitespace-pre-wrap text-slate-600">{a.memo}</p>}
              {a.is_stale && <p className="mt-1 text-xs text-amber-800">맡긴 뒤 계약 자료가 바뀌었습니다. {a.document_id ? '이 서류의 일은 취소하고 새로 맡기세요.' : '최신 자료로 다시 맡기거나 취소하세요.'}</p>}
              <div className="mt-2 flex flex-wrap gap-2">
                {mine && a.status === 'OPEN' && !a.is_stale && <button disabled={busy} onClick={() => void change(a, 'START', '시작')} className="rounded-lg bg-indigo-600 px-2.5 py-1 text-xs font-semibold text-white disabled:opacity-40">시작</button>}
                {canComplete && <button disabled={busy} onClick={() => { setActing({ id: a.assignment_id, action: 'COMPLETE' }); setNote(''); }} className="rounded-lg border border-emerald-300 px-2.5 py-1 text-xs font-semibold text-emerald-700">끝냄</button>}
                {a.is_stale && !a.document_id && canCancel && <button disabled={busy} onClick={() => void change(a, 'REASSIGN', '최신 자료로 다시 맡김', { assignee_id: a.assignee_id, contract_revision: revision })} className="rounded-lg border border-amber-400 px-2.5 py-1 text-xs font-semibold text-amber-800">최신 자료로 다시 맡기기</button>}
                {canCancel && <button disabled={busy} onClick={() => { setActing({ id: a.assignment_id, action: 'CANCEL' }); setNote(''); }} className="rounded-lg px-2.5 py-1 text-xs text-slate-500 hover:bg-slate-100">취소</button>}
              </div>
              {acting?.id === a.assignment_id && (
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <input autoFocus value={note} maxLength={2000} onChange={(e) => setNote(e.target.value)} placeholder={acting.action === 'COMPLETE' ? '무엇을 확인했는지 (예: 원문과 합계 일치 확인)' : '취소 이유'}
                    className="min-w-0 flex-1 rounded-lg border border-slate-300 px-2 py-1 text-sm" />
                  <button disabled={busy || !note.trim()} onClick={() => void change(a, acting.action, note.trim())} className="rounded-lg bg-slate-800 px-2.5 py-1 text-xs font-semibold text-white disabled:opacity-40">{acting.action === 'COMPLETE' ? '끝냄으로 기록' : '취소하기'}</button>
                  <button onClick={() => setActing(null)} className="text-xs text-slate-500">닫기</button>
                </div>
              )}
            </li>
          );
        })}
      </ul>
      {closed.length > 0 && (
        <details className="text-sm text-slate-500">
          <summary className="cursor-pointer">끝났거나 취소한 일 {closed.length}건</summary>
          <ul className="mt-2 space-y-1">
            {closed.map((a) => <li key={a.assignment_id}>{ASSIGNMENT_STATUS_KO[a.status]} · {a.title} · {a.assignee_name}{a.completed_at ? ` · ${a.completed_at.slice(0, 10)}` : ''}</li>)}
          </ul>
        </details>
      )}
      {error && <p role="alert" className="text-xs text-rose-600">{error}</p>}
    </section>
  );
};
