import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ContractDetail, DocumentType } from '../../types';
import { requestJson } from '../../api/client';
import { ContactMethod, CONTACT_KO, CONTACT_VIA, ResubmissionRequest } from '../../api/followUp';
import { DOCUMENT_TYPE_KO } from '../../utils/reviewSummary';
import { fixParticles, josa } from '../../utils/korean';
import { seoulToday } from '../../utils/date';
import { useDialogA11y } from '../../hooks/useDialogA11y';
import { maskBusinessNumber, maskResidentNumber, maskVendorName } from '../../utils/masking';
import { ChevronDown, ChevronRight, Copy, Eye, Upload, X } from 'lucide-react';

/* ---------- API ---------- */
export interface BundleCandidate {
  issue_key: string;
  title: string;
  document_type: DocumentType | null;
  document_id: number | null;
  reason: string;
  requires_original_review: boolean;
  already_requested?: boolean;
  pending_items?: { request_id: number; item_id: number }[];
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

const base = (cid: number) => `/api/pilot/contracts/${cid}`;
export const bundleApi = {
  context: (cid: number, signal?: AbortSignal) => requestJson<BundleContext>(`${base(cid)}/resubmission-bundle-context`, { signal }),
  create: (cid: number, body: unknown) => requestJson<BundledRequest>(`${base(cid)}/resubmission-bundles`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  }),
  resolve: (cid: number, rid: number, body: unknown) => requestJson<BundledRequest>(`${base(cid)}/resubmission-bundles/${rid}/items`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  }),
};

/** 선택·동의를 받은 자료 기준. 기준이 바뀌면 그 동의로 저장하지 않는다 */
export interface Basis { contractId: number; revision: number; fingerprint: string }
export const sameBasis = (a: Basis, b: Basis) => a.contractId === b.contractId && a.revision === b.revision && a.fingerprint === b.fingerprint;

/** 요청 항목의 현재 서류: 재발행으로 ID가 바뀌어도 같은 논리 문서(issue_key 'document:{논리 ID}')의 현재 본을 찾는다 */
export function currentDocumentFor(item: { issue_key: string; document_id: number | null }, docs: { document_id: number; version?: { logical_document_id: number; is_current: boolean } | null }[]): number | null {
  const m = /^document:(\d+)$/.exec(item.issue_key);
  if (m) {
    const logical = Number(m[1]);
    const cur = docs.find((d) => (d.version?.logical_document_id ?? d.document_id) === logical && d.version?.is_current !== false);
    if (cur) return cur.document_id;
  }
  return item.document_id != null && docs.some((d) => d.document_id === item.document_id) ? item.document_id : null;
}

const mask = (t: string, on: boolean) => (on ? maskResidentNumber(maskBusinessNumber(t)) : t);
const docName = (c: { document_type: DocumentType | null; title: string }) => (c.document_type ? DOCUMENT_TYPE_KO[c.document_type] ?? c.title : c.title);
const newKey = () => (typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`);

/* ---------- 거래처에 요청할 것: 한 목록 ---------- */
interface ChecklistProps {
  ctx: BundleContext;
  isMaskingEnabled: boolean;
  canEdit: boolean;
  onOpenDocumentId: (documentId: number) => void;
  onMake: (items: BundleCandidate[], reviewed: Set<string>) => void;
}

export const RequestChecklist: React.FC<ChecklistProps> = ({ ctx, isMaskingEnabled, canEdit, onOpenDocumentId, onMake }) => {
  const open = ctx.vendor_candidates.filter((c) => !c.already_requested);
  const waitingAlready = ctx.vendor_candidates.filter((c) => c.already_requested);
  // 빠진 서류는 기본 선택, 금액·번호 불일치는 원문을 본 뒤 직접 선택
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [reviewed, setReviewed] = useState<Set<string>>(new Set());
  const [expanded, setExpanded] = useState<string | null>(null);
  const basis = `${ctx.revision}|${ctx.fingerprint}|${open.map((c) => c.issue_key).join(',')}`;
  useEffect(() => {
    setPicked(new Set(open.filter((c) => !c.requires_original_review).map((c) => c.issue_key)));
    setReviewed(new Set());
    setExpanded(null);
    // 자료가 바뀌면 선택·원문 확인을 다시 받는다
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [basis]);
  const toggle = (set: Set<string>, key: string) => { const n = new Set(set); if (n.has(key)) n.delete(key); else n.add(key); return n; };
  const chosen = open.filter((c) => picked.has(c.issue_key) && (!c.requires_original_review || reviewed.has(c.issue_key)));

  if (!open.length && !waitingAlready.length) return null;
  return (
    <div className="space-y-2">
      {open.length > 0 && <div className="text-sm font-bold text-slate-900">거래처에 요청할 것 {open.length}건</div>}
      {open.length > 0 && (
        <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
          {open.map((c) => {
            const on = picked.has(c.issue_key);
            const needReview = c.requires_original_review && !reviewed.has(c.issue_key);
            return (
              <li key={c.issue_key} className="px-3 py-2 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <label className="flex min-w-0 flex-1 cursor-pointer items-center gap-2">
                    <input type="checkbox" checked={on} disabled={!canEdit} onChange={() => setPicked((s) => toggle(s, c.issue_key))} className="h-4 w-4 accent-indigo-600" />
                    <span className="font-semibold text-slate-900">{docName(c)}</span>
                    <span className="truncate text-slate-500">{c.document_id ? '내용 확인 후 다시 받기' : '아직 없음'}</span>
                  </label>
                  {c.document_id != null && (
                    <button onClick={() => onOpenDocumentId(c.document_id!)} className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-semibold text-indigo-700 hover:bg-indigo-50"><Eye className="h-3.5 w-3.5" />원문</button>
                  )}
                  <button onClick={() => setExpanded(expanded === c.issue_key ? null : c.issue_key)} aria-expanded={expanded === c.issue_key}
                    className="inline-flex items-center gap-0.5 rounded-lg px-2 py-1 text-xs text-slate-500 hover:bg-slate-100">
                    이유 {expanded === c.issue_key ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                  </button>
                </div>
                {expanded === c.issue_key && <p className="mt-1 whitespace-pre-wrap pl-6 text-xs text-slate-600">{mask(fixParticles(c.reason), isMaskingEnabled)}</p>}
                {c.requires_original_review && on && (
                  <label className={`mt-1 flex items-center gap-2 pl-6 text-xs ${needReview ? 'text-amber-800' : 'text-slate-600'}`}>
                    <input type="checkbox" checked={reviewed.has(c.issue_key)} onChange={() => setReviewed((s) => toggle(s, c.issue_key))} className="h-3.5 w-3.5 accent-emerald-600" />
                    원문을 보고, 원문에서도 틀린 것을 확인했어요 (앱이 잘못 읽은 거면 거래처가 아니라 ‘값 고치기’)
                  </label>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {waitingAlready.length > 0 && (
        <p className="text-xs text-slate-500">이미 요청해서 답을 기다리는 것: {waitingAlready.map(docName).join(', ')}</p>
      )}
      {open.length > 0 && canEdit && (
        <button onClick={() => onMake(chosen, reviewed)} disabled={chosen.length === 0}
          className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-40">
          <Copy className="h-4 w-4" /> 선택한 {chosen.length}건 요청 문구 만들기
        </button>
      )}
    </div>
  );
};

/* ---------- 한 번에 요청하기 ---------- */
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

interface DialogProps {
  contract: ContractDetail;
  /** 선택·원문 확인을 받은 기준 */
  basis: Basis;
  /** 지금 불러온 최신 기준 */
  latest: Basis | null;
  items: BundleCandidate[];
  reviewed: Set<string>;
  isMaskingEnabled: boolean;
  onClose: () => void;
  onRecorded: () => Promise<void>;
  onStale: () => Promise<void>;
}

export const BundleRequestDialog: React.FC<DialogProps> = ({ contract, basis, latest, items, reviewed, isMaskingEnabled, onClose, onRecorded, onStale }) => {
  const ref = useRef<HTMLDivElement>(null);
  useDialogA11y(ref, onClose);
  const [long, setLong] = useState(false);
  const draft = useMemo(() => buildText(contract, items, long), [contract, items, long]);
  const [text, setText] = useState(draft);
  useEffect(() => setText(draft), [draft]);
  const [copied, setCopied] = useState('');
  const [method, setMethod] = useState<ContactMethod>('KAKAO');
  const [due, setDue] = useState('');
  const [memo, setMemo] = useState(`${items.map(docName).join(', ')} 요청`);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [stale, setStale] = useState(false);
  // 같은 요청의 재시도에는 같은 키, 내용을 바꾸면 새 키
  const keyRef = useRef(newKey());
  const contentSig = `${method}|${due}|${memo}|${items.map((i) => i.issue_key).join(',')}`;
  const sigRef = useRef(contentSig);
  if (sigRef.current !== contentSig) { sigRef.current = contentSig; keyRef.current = newKey(); }

  const memoTooLong = memo.trim().length > 2000;
  const changed = !latest || !sameBasis(basis, latest);
  const record = async () => {
    setBusy(true); setError('');
    try {
      await bundleApi.create(contract.contract_id, {
        revision: basis.revision, fingerprint: basis.fingerprint, idempotency_key: keyRef.current,
        contact_method: method, due_on: due || null, memo: memo.trim(),
        items: items.map((c) => ({ issue_key: c.issue_key, reviewed_original: c.requires_original_review ? reviewed.has(c.issue_key) : false })),
      });
      await onRecorded();
      onClose();
    } catch (e) {
      const msg = e instanceof Error ? e.message : '기록하지 못했습니다.';
      setError(msg);
      if (/변경|이미|다시|최신/.test(msg)) setStale(true);
    } finally { setBusy(false); }
  };
  const copy = async () => {
    try { await navigator.clipboard.writeText(text); setCopied('복사했어요. 카카오톡·문자·이메일에 붙여 넣으세요.'); }
    catch { setCopied('복사하지 못했어요. 글을 선택해 Ctrl+C로 복사하세요.'); }
  };

  return (
    <div ref={ref} className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" role="dialog" aria-modal="true" aria-labelledby="bundle-title">
      <div className="max-h-full w-full max-w-xl overflow-auto rounded-2xl bg-white shadow-xl">
        <div className="flex items-center gap-2 border-b border-slate-100 px-5 py-4">
          <h2 id="bundle-title" className="font-bold text-slate-900">거래처에 한 번에 요청 · {items.length}건</h2>
          <button onClick={onClose} className="ml-auto rounded-lg p-1 text-slate-400 hover:bg-slate-100" aria-label="닫기"><X className="h-5 w-5" /></button>
        </div>
        <div className="space-y-3 px-5 py-4 text-sm">
          <div className="text-slate-600">{maskVendorName(contract.vendor_name, isMaskingEnabled)}에게 보낼 문구예요. {items.map(docName).join(' · ')}</div>
          <div className="inline-flex rounded-lg border border-slate-200 p-0.5 text-xs" role="tablist">
            <button role="tab" aria-selected={!long} onClick={() => setLong(false)} className={`rounded-md px-3 py-1.5 font-semibold ${!long ? 'bg-indigo-600 text-white' : 'text-slate-600'}`}>짧게 (카톡·문자)</button>
            <button role="tab" aria-selected={long} onClick={() => setLong(true)} className={`rounded-md px-3 py-1.5 font-semibold ${long ? 'bg-indigo-600 text-white' : 'text-slate-600'}`}>자세히 (이메일)</button>
          </div>
          <label htmlFor="bundle-text" className="sr-only">요청 문구</label>
          <textarea id="bundle-text" value={text} onChange={(e) => setText(e.target.value)} className="h-40 w-full rounded-xl border border-slate-200 bg-white p-3 leading-relaxed text-slate-800" />
          <div className="flex flex-wrap items-center gap-2">
            <button onClick={() => void copy()} className="rounded-lg border border-slate-200 px-3 py-1.5 font-semibold text-slate-700 hover:border-indigo-300">문구 복사</button>
            <span className="text-xs text-slate-500">{copied}</span>
          </div>
          {isMaskingEnabled && <p className="text-xs text-amber-700">거래처에 보낼 문구라 가림이 켜져 있어도 실제 거래처 이름이 들어가요. 복사만으로는 기록되지 않아요.</p>}

          <div className="space-y-2 rounded-xl bg-slate-50 p-3">
            <div className="font-semibold text-slate-800">보냈다면 한 번에 기록하기</div>
            <div className="flex flex-wrap gap-2">
              <label className="grid gap-1 text-xs text-slate-600">어떻게 요청했나요?
                <select value={method} onChange={(e) => setMethod(e.target.value as ContactMethod)} className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-800">
                  {(Object.keys(CONTACT_KO) as ContactMethod[]).map((m) => <option key={m} value={m}>{CONTACT_KO[m]}</option>)}
                </select></label>
              <label className="grid gap-1 text-xs text-slate-600">회신 기한 (선택)
                <input type="date" value={due} min={seoulToday()} onChange={(e) => setDue(e.target.value)} className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-800" /></label>
            </div>
            <label className="grid gap-1 text-xs text-slate-600">기록 메모
              <input value={memo} onChange={(e) => setMemo(e.target.value)} className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-800" /></label>
            {memoTooLong && <p className="text-xs text-rose-600">메모는 2,000자까지예요. 줄여 주세요.</p>}
            {changed && (
              <p role="alert" className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900">
                고른 뒤 계약 자료가 바뀌었어요. 이 선택과 원문 확인으로는 기록할 수 없어요. 창을 닫고 최신 목록에서 다시 골라 주세요.
                <button onClick={() => { void onStale().then(onClose); }} className="ml-2 font-semibold underline">닫고 다시 고르기</button>
              </p>
            )}
            <button onClick={() => void record()} disabled={busy || stale || changed || !memo.trim() || memoTooLong}
              className="rounded-lg bg-indigo-600 px-4 py-2 font-semibold text-white hover:bg-indigo-700 disabled:opacity-40">{busy ? '기록 중…' : `요청했어요 · ${items.length}건 한 번에 기록하기`}</button>
            <p className="text-[11px] text-slate-500">요청 1건에 서류 {items.length}개가 묶여 기록돼요. 이 계약은 ‘③ 보완’으로 넘어가요. 앱은 메시지를 보내지 않아요.</p>
          </div>
          {error && (
            <div role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-700">
              {error}
              {stale && <button onClick={() => { void onStale().then(onClose); }} className="ml-2 font-semibold underline">새로 불러오기</button>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

/* ---------- 받은 항목만 체크 ---------- */
interface ReplyProps {
  contract: ContractDetail;
  request: BundledRequest;
  canEdit: boolean;
  isMaskingEnabled: boolean;
  /** 요청 항목의 현재 서류를 연다(재발행으로 ID가 바뀐 경우 포함) */
  onOpenItem: (item: BundleItem, mode?: 'view' | 'reissue') => void;
  onUploadType: (type?: DocumentType) => void;
  onDone: () => Promise<void>;
}

export const BundleReplyPanel: React.FC<ReplyProps> = ({ contract, request, canEdit, isMaskingEnabled, onOpenItem, onUploadType, onDone }) => {
  const b = request.bundle!;
  const waitingItems = b.items.filter((i) => i.status === 'WAITING_RESPONSE');
  const [got, setGot] = useState<Set<number>>(new Set());
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  // 요청·자료가 바뀌면 이전 체크·메모는 쓰지 않는다(오류 안내는 남겨 이유를 보이게 한다)
  const basis = `${b.request_revision}|${contract.workflow?.revision}|${contract.workflow?.fingerprint}`;
  useEffect(() => { setGot(new Set()); setNote(''); }, [basis]);
  const late = request.due_on && request.due_on < seoulToday();
  const save = async (status: 'RECEIVED' | 'CANCELLED') => {
    setBusy(true); setError('');
    try {
      await bundleApi.resolve(contract.contract_id, request.request_id, {
        revision: contract.workflow?.revision, fingerprint: contract.workflow?.fingerprint, request_revision: b.request_revision,
        items: [...got].map((id) => ({ item_id: id, status, note: note.trim() })),
      });
      await onDone();
    } catch (e) {
      setError(`${e instanceof Error ? e.message : '기록하지 못했습니다.'} 최신 상태를 다시 불러왔어요. 다시 골라 주세요.`);
      await onDone();
    } finally { setBusy(false); }
  };
  return (
    <div className="space-y-2 rounded-xl bg-white px-3 py-3 text-sm">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="font-semibold text-slate-800">{request.requested_on.slice(5).replace('-', '/')} {CONTACT_VIA[request.contact_method]} 요청</span>
        {request.due_on && <span className={late ? 'font-bold text-rose-600' : 'text-slate-500'}>기한 {request.due_on.slice(5).replace('-', '/')}{late ? ' 지남' : ''}</span>}
        <span className="ml-auto text-xs font-semibold text-slate-600">{b.counts.total}건 요청 · {b.counts.received}건 받음 · {b.counts.waiting}건 기다림{b.counts.cancelled ? ` · ${b.counts.cancelled}건 취소` : ''}</span>
      </div>
      <ul className="space-y-1">
        {b.items.map((i) => (
          <li key={i.item_id} className="flex flex-wrap items-center gap-2">
            {i.status === 'WAITING_RESPONSE' && canEdit ? (
              <label className="flex flex-1 cursor-pointer items-center gap-2">
                <input type="checkbox" checked={got.has(i.item_id)} onChange={() => setGot((s) => { const n = new Set(s); if (n.has(i.item_id)) n.delete(i.item_id); else n.add(i.item_id); return n; })} className="h-4 w-4 accent-sky-600" />
                <span className="font-medium text-slate-800">{docName(i)}</span>

              </label>
            ) : (
              <span className={`flex-1 ${i.status === 'RECEIVED' ? 'text-emerald-700' : i.status === 'CANCELLED' ? 'text-slate-400 line-through' : 'text-slate-700'}`}>
                {i.status === 'RECEIVED' ? '✓ ' : ''}{docName(i)}{i.status === 'RECEIVED' ? ' 받음' : i.status === 'CANCELLED' ? ' 취소' : ' 기다림'}
                {i.resolution_note ? <span className="ml-1 text-xs text-slate-500">· {mask(fixParticles(i.resolution_note), isMaskingEnabled)}</span> : null}
              </span>
            )}
            {i.status === 'WAITING_RESPONSE' && canEdit && (
              i.document_id != null
                ? <button onClick={() => onOpenItem(i, 'reissue')} className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2 py-1 text-xs font-semibold text-slate-700 hover:border-indigo-300"><Upload className="h-3.5 w-3.5" />고친 본 올리기</button>
                : i.document_type && <button onClick={() => onUploadType(i.document_type!)} className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2 py-1 text-xs font-semibold text-slate-700 hover:border-indigo-300"><Upload className="h-3.5 w-3.5" />파일 올리기</button>
            )}
          </li>
        ))}
      </ul>
      {canEdit && waitingItems.length > 0 && (
        <div className="space-y-2 border-t border-slate-100 pt-2">
          <div className="text-xs text-slate-500">위에서 받은 항목(또는 잘못 요청해 취소할 항목)을 고르고 메모를 남기세요.</div>
          <div className="flex flex-wrap items-center gap-2">
            <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} aria-label="받은 내용 또는 취소 이유" placeholder="받은 내용 또는 취소 이유"
              className="min-w-0 flex-1 rounded-lg border border-slate-300 px-2 py-1 text-sm" />
            <button onClick={() => void save('RECEIVED')} disabled={busy || got.size === 0 || !note.trim()}
              className="rounded-lg bg-sky-600 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-40">{busy ? '기록 중…' : `받은 ${got.size}건 기록`}</button>
            <button onClick={() => void save('CANCELLED')} disabled={busy || got.size === 0 || !note.trim()}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-600 disabled:opacity-40">선택 {got.size}건 요청 취소</button>
          </div>
        </div>
      )}
      <p className="text-[11px] text-slate-500">받았다고 기록해도 검사 통과는 아니에요. 올린 서류로 다시 검사한 결과를 확인하세요.</p>
      {error && <p role="alert" className="text-xs text-rose-600">{error}</p>}
    </div>
  );
};
