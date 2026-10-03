import React, { useEffect, useMemo, useState } from 'react';
import { AnalysisFields, DocumentResponse, ValidationCheck } from '../../types';
import { api, requestJson, downloadProtected } from '../../api/client';
import { DOCUMENT_TYPE_KO, STATUS_KO, plainMessage, ruleLabel, isUnverifiedBusinessStatus } from '../../utils/reviewSummary';
import { maskBusinessNumber, maskAccountNumber, maskVendorName } from '../../utils/masking';
import { X, Pencil, Download, ChevronLeft, ChevronRight, Loader2, Save } from 'lucide-react';

interface BBox { page: number; x: number; y: number; width: number; height: number }
interface Anchor { page: number | null; line: number | null; quote: string; location_kind?: string; page_layout_verified?: boolean; bbox?: BBox | null; bboxes?: BBox[] }
interface Comparison { previous_version: number; new_version: number; changed_field_count: number; changes: { field: string; previous_value: unknown; new_value: unknown }[] }
interface FieldProvenance {
  value: string | number | null;
  source: 'RULE' | 'AI_SUPPLEMENT' | 'HUMAN_CONFIRMATION' | 'UNAVAILABLE';
  evidence: Anchor[];
  evidence_status: 'AVAILABLE' | 'AMBIGUOUS' | 'UNAVAILABLE';
  human_confirmation?: { actor_name: string; at: string } | null;
  ai_decision?: { proposal?: { value?: unknown }; accepted?: boolean; applied?: boolean; reasons?: string[] } | null;
}
interface Provenance { document_id: number; fields: Record<string, FieldProvenance> }

interface Props {
  doc: DocumentResponse;
  checks: ValidationCheck[];
  revision: number;
  isMaskingEnabled: boolean;
  canEdit: boolean;
  onClose: () => void;
  onChanged: () => Promise<void>;
}

const FIELD_ORDER: { key: string; label: string; types?: string[] }[] = [
  { key: 'company_name', label: '상호' },
  { key: 'business_registration_no', label: '사업자등록번호' },
  { key: 'bank_name', label: '은행', types: ['bank_account'] },
  { key: 'account_number', label: '계좌번호', types: ['bank_account'] },
  { key: 'supply_amount', label: '공급가액' },
  { key: 'tax_amount', label: '세액' },
  { key: 'total_amount', label: '합계금액' },
  { key: 'amount_scope', label: '청구 범위', types: ['tax_invoice', 'estimate', 'contract'] },
  { key: 'issue_date', label: '발행일' },
];

const NO_AMOUNT = new Set(['business_registration', 'bank_account']);

const REASON_KO: Record<string, string> = {
  PAGE_UNVERIFIED: '원문 위치를 확인하지 못함',
  EVIDENCE_NOT_FOUND: '원문에서 근거를 찾지 못함',
  FIELD_LABEL_OR_VALUE_MISMATCH: '항목 이름이나 값이 원문과 다름',
  WRONG_PARTY: '공급자가 아닌 쪽의 값',
  VALUE_NOT_IN_QUOTE: '근거 문구에 그 값이 없음',
  UNSUPPORTED_ABSTENTION: '판단 보류 근거가 부족함',
  SOURCE_ARITHMETIC_MISMATCH: '원문 금액 계산이 맞지 않음',
};

function display(key: string, value: FieldProvenance['value'], masked: boolean): string {
  if (value === null || value === undefined || value === '' || value === 'UNKNOWN') return '';
  if (typeof value === 'number' || (/amount$/.test(key) && !isNaN(Number(value)))) return `${Number(value).toLocaleString('ko-KR')}원`;
  if (key === 'amount_scope') return value === 'FULL' ? '전액 청구' : value === 'PARTIAL' ? '일부(분할) 청구' : String(value);
  if (key === 'business_registration_no') return masked ? maskBusinessNumber(String(value)) : String(value);
  if (key === 'account_number') return masked ? maskAccountNumber(String(value)) : String(value);
  if (key === 'company_name') return maskVendorName(String(value), masked);
  return String(value);
}

const AMOUNT_KEYS = new Set(['supply_amount', 'tax_amount', 'total_amount']);

export const DocumentReviewDialog: React.FC<Props> = ({ doc, checks, revision, isMaskingEnabled, canEdit, onClose, onChanged }) => {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<AnalysisFields>(doc.analysis.fields);
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  useEffect(() => { setEditing(false); setDraft(doc.analysis.fields); setNote(''); setSaveError(''); }, [doc.document_id, revision]);
  const [cmp, setCmp] = useState<Comparison | null>(null);
  const [reissueFile, setReissueFile] = useState<File | null>(null);
  const [reissueNote, setReissueNote] = useState('');
  const [reissuing, setReissuing] = useState(false);
  const [reissueError, setReissueError] = useState('');
  const versionNo = doc.version?.version_number ?? 1;
  useEffect(() => {
    setCmp(null); setReissueFile(null); setReissueNote(''); setReissueError('');
    if (versionNo < 2) return;
    const controller = new AbortController();
    requestJson<Comparison>(`/api/documents/${doc.document_id}/compare`, { signal: controller.signal }).then(setCmp).catch(() => undefined);
    return () => controller.abort();
  }, [doc.document_id, versionNo]);
  const reissue = async () => {
    if (!reissueFile) return;
    setReissuing(true); setReissueError('');
    try {
      await api.reissueDocument(doc.contract_id, reissueFile, doc.document_id, revision, reissueNote.trim());
      await onChanged();
      onClose();
    } catch (e) {
      setReissueError(e instanceof Error ? e.message : '재발행본을 올리지 못했습니다.');
    } finally {
      setReissuing(false);
    }
  };
  const changedKeys = Object.keys(draft).filter((k) => (draft as Record<string, unknown>)[k] !== (doc.analysis.fields as Record<string, unknown>)[k]);
  // 값을 바꾸지 않고 원문과 맞다고 확인한 칸. 바뀐 칸은 서버가 알아서 확인으로 기록한다
  const [confirmed, setConfirmed] = useState<Set<string>>(new Set());
  const confirmedKeys = [...confirmed].filter((k) => !changedKeys.includes(k));
  const toggleConfirmed = (key: string) => setConfirmed((prev) => { const next = new Set(prev); if (next.has(key)) next.delete(key); else next.add(key); return next; });
  useEffect(() => { setConfirmed(new Set()); }, [doc.document_id, editing]);
  const save = async () => {
    setSaving(true); setSaveError('');
    try {
      await api.correctFields(doc.document_id, draft, doc.document_type, revision, note.trim(), confirmedKeys);
      await onChanged();
      setEditing(false);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : '저장하지 못했습니다.');
    } finally {
      setSaving(false);
    }
  };
  const [prov, setProv] = useState<Provenance | null>(null);
  const [provError, setProvError] = useState('');
  const [page, setPage] = useState(0);
  const [pages, setPages] = useState(1);
  const [imageUrl, setImageUrl] = useState('');
  const [imageError, setImageError] = useState('');
  const [text, setText] = useState('');
  const [selected, setSelected] = useState<string | null>(null);
  const isPdf = /\.pdf$/i.test(doc.original_file_name);
  const isImage = /\.(png|jpe?g|webp|bmp|gif|tiff?)$/i.test(doc.original_file_name);
  const visual = isPdf || isImage;

  const docChecks = useMemo(
    () => checks.filter((c) => c.field === String(doc.document_id) && !isUnverifiedBusinessStatus(c)),
    [checks, doc.document_id]
  );
  const problems = docChecks.filter((c) => c.status !== 'PASS');

  useEffect(() => {
    const controller = new AbortController();
    setProv(null); setProvError('');
    requestJson<Provenance>(`/api/documents/${doc.document_id}/provenance`, { signal: controller.signal })
      .then(setProv)
      .catch((e) => { if (!controller.signal.aborted) setProvError(e.message); });
    return () => controller.abort();
  }, [doc.document_id, revision]);

  useEffect(() => {
    setPage(0); setPages(1);
    if (!doc.file_available || !isPdf) return;
    const controller = new AbortController();
    requestJson<{ total_pages: number }>(`/api/documents/${doc.document_id}/pages-info`, { signal: controller.signal })
      .then((v) => setPages(v.total_pages)).catch(() => undefined);
    return () => controller.abort();
  }, [doc.document_id, doc.file_available, isPdf]);

  useEffect(() => {
    setImageUrl(''); setImageError('');
    if (!doc.file_available || !visual) return;
    const controller = new AbortController();
    let url = '';
    fetch(`/api/documents/${doc.document_id}/preview-image?page=${page}&masked=${isMaskingEnabled}&revision=${revision}`, { credentials: 'same-origin', signal: controller.signal })
      .then(async (r) => { if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || '원문 그림을 만들지 못했습니다.'); return r.blob(); })
      .then((b) => { url = URL.createObjectURL(b); setImageUrl(url); })
      .catch((e) => { if (!controller.signal.aborted) setImageError(e.message); });
    return () => { controller.abort(); if (url) URL.revokeObjectURL(url); };
  }, [doc.document_id, doc.file_available, visual, page, isMaskingEnabled, revision]);

  useEffect(() => {
    setText('');
    if (!doc.file_available || visual) return;
    const controller = new AbortController();
    requestJson<{ text: string }>(`/api/documents/${doc.document_id}/text-preview?masked=${isMaskingEnabled}`, { signal: controller.signal })
      .then((v) => setText(v.text)).catch((e) => { if (!controller.signal.aborted) setText(e.message); });
    return () => controller.abort();
  }, [doc.document_id, doc.file_available, visual, isMaskingEnabled]);

  const rows = FIELD_ORDER.filter((f) => (!f.types || f.types.includes(doc.document_type)) && !(NO_AMOUNT.has(doc.document_type) && /amount|scope/.test(f.key)));
  const anchor: Anchor | undefined = selected ? prov?.fields[selected]?.evidence?.[0] : undefined;
  // 좌표는 백엔드가 원본 해시까지 확인한 경우에만 온다. 없으면 쪽·줄 안내만 한다.
  const validBox = (b?: BBox | null): b is BBox => !!b && (b.page ?? 1) === page + 1 && [b.x, b.y, b.width, b.height].every((v) => typeof v === 'number' && v >= 0 && v <= 1);
  const boxes: BBox[] = (anchor?.bboxes?.length ? anchor.bboxes : anchor?.bbox ? [anchor.bbox] : []).filter(validBox);

  const pick = (key: string) => {
    setSelected(key);
    const a = prov?.fields[key]?.evidence?.[0];
    if (a?.page && isPdf) setPage(a.page - 1);
  };

  const quoteShown = anchor && !isMaskingEnabled ? anchor.quote : '';
  const highlightedText = useMemo(() => {
    if (!text || !anchor?.quote || isMaskingEnabled) return null;
    const i = text.indexOf(anchor.quote);
    if (i < 0) return null;
    return [text.slice(0, i), text.slice(i, i + anchor.quote.length), text.slice(i + anchor.quote.length)];
  }, [text, anchor, isMaskingEnabled]);

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/50 flex items-center justify-center p-2 sm:p-4" role="dialog" aria-modal="true" aria-labelledby="doc-review-title">
      <div className="flex max-h-full w-full max-w-6xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
        <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 px-5 py-3">
          <h2 id="doc-review-title" className="font-bold text-slate-900">{DOCUMENT_TYPE_KO[doc.document_type]}</h2>
          <span className="truncate text-xs text-slate-500">{doc.original_file_name}</span>
          {versionNo > 1 && <span className="rounded-full bg-sky-100 px-2 py-0.5 text-xs font-bold text-sky-700">재발행본 · 버전 {versionNo}</span>}
          {problems.length > 0 ? (
            <span className="rounded-full bg-rose-100 px-2 py-0.5 text-xs font-bold text-rose-700">확인할 것 {problems.length}</span>
          ) : (
            <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-bold text-emerald-700">이상 없음</span>
          )}
          <div className="ml-auto flex items-center gap-2">
            {doc.file_available && (
              <button onClick={() => void downloadProtected(`/api/documents/${doc.document_id}/download?masked=true`, doc.original_file_name)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-semibold text-slate-700 hover:border-indigo-300">
                <Download className="h-4 w-4" /> 가린 원본 받기
              </button>
            )}
            <button onClick={onClose} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100" aria-label="닫기"><X className="h-5 w-5" /></button>
          </div>
        </div>

        <div className="grid min-h-0 flex-1 overflow-auto lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
          {/* 원문 */}
          <div className="min-w-0 bg-slate-500/90 p-4">
            <div className="mb-2 flex items-center gap-2 text-xs text-white/85">
              <span>원문{isPdf && pages > 1 ? ` ${page + 1} / ${pages}쪽` : ''}</span>
              {isMaskingEnabled && <span className="text-[11px] font-normal text-white/75" title="글자를 자동으로 찾아 가립니다. 일부 상호가 남거나 다른 칸이 가려질 수 있습니다.">자동 가림 · 빠진 곳이 있을 수 있음</span>}
              {isPdf && pages > 1 && (
                <span className="ml-auto flex gap-1">
                  <button disabled={page === 0} onClick={() => setPage((p) => p - 1)} className="rounded bg-white/15 p-1 disabled:opacity-40" aria-label="이전 쪽"><ChevronLeft className="h-4 w-4" /></button>
                  <button disabled={page >= pages - 1} onClick={() => setPage((p) => p + 1)} className="rounded bg-white/15 p-1 disabled:opacity-40" aria-label="다음 쪽"><ChevronRight className="h-4 w-4" /></button>
                </span>
              )}
            </div>
            {!doc.file_available ? (
              <div className="rounded-lg bg-white p-6 text-sm text-slate-600">원본 파일이 없습니다. 원본을 다시 등록하면 여기에 표시됩니다.</div>
            ) : visual ? (
              imageUrl ? (
                <div className="relative">
                  <img src={imageUrl} alt={`${DOCUMENT_TYPE_KO[doc.document_type]} 원문`} className="block w-full rounded bg-white shadow-lg" />
                  {boxes.map((box, i) => (
                    <div
                      key={i}
                      aria-hidden="true"
                      className="pointer-events-none absolute rounded-sm bg-amber-300/30 outline outline-2 outline-amber-500 transition-all"
                      style={{ left: `${box.x * 100}%`, top: `${box.y * 100}%`, width: `${box.width * 100}%`, height: `${box.height * 100}%` }}
                    />
                  ))}
                </div>
              ) : imageError ? (
                <div className="rounded-lg bg-white p-6 text-sm text-rose-600">{imageError}</div>
              ) : (
                <div className="flex items-center gap-2 rounded-lg bg-white p-6 text-sm text-slate-500"><Loader2 className="h-4 w-4 animate-spin" /> 원문을 불러오는 중…</div>
              )
            ) : (
              <div className="rounded-lg bg-white p-5 text-sm leading-7 text-slate-800 whitespace-pre-wrap break-words">
                <div className="mb-3 rounded bg-amber-50 px-2 py-1 text-xs text-amber-800">Word 등 글자 문서는 파일 속 글자를 보여 줍니다. 쪽 배치는 실제 문서와 다를 수 있습니다.</div>
                {highlightedText ? (<>{highlightedText[0]}<mark className="rounded bg-amber-200 px-0.5">{highlightedText[1]}</mark>{highlightedText[2]}</>) : text || '글자를 불러오는 중…'}
              </div>
            )}
            {anchor && (
              <div className="mt-3 rounded-lg bg-amber-100 px-3 py-2 text-sm text-amber-900" role="status">
                <b>근거</b> · {anchor.page ? `${anchor.page}쪽 ` : ''}{anchor.line ? `${anchor.line}번째 줄` : '본문'}{quoteShown ? `: "${quoteShown}"` : ' (개인정보 가림 중이라 문구는 숨김)'}
              </div>
            )}
          </div>

          {/* 읽은 값 */}
          <div className="min-w-0 space-y-3 p-5">
            {cmp && (
              <div className="rounded-xl border border-sky-200 bg-sky-50 p-3 text-sm">
                <div className="font-semibold text-sky-900">무엇이 바뀌었나 · 버전 {cmp.previous_version} → {cmp.new_version}</div>
                {cmp.changes.length === 0 ? <div className="text-sky-800">읽은 값은 이전 버전과 같습니다.</div> : (
                  <ul className="mt-1 space-y-1">
                    {cmp.changes.map((c) => {
                      const label = FIELD_ORDER.find((f) => f.key === c.field)?.label ?? c.field;
                      const fmt = (v: unknown) => display(c.field, v as FieldProvenance['value'], isMaskingEnabled);
                      const unread = !fmt(c.new_value);
                      return <li key={c.field} className="tabular-nums"><span className="text-slate-500">{label}</span> <span className="text-rose-600 line-through">{fmt(c.previous_value) || '없음'}</span> → {unread
                        ? <b className="text-amber-700">새 본에서 못 읽음 · 원문 확인 필요</b>
                        : <b className="text-emerald-700">{fmt(c.new_value)}</b>}</li>;
                    })}
                  </ul>
                )}
              </div>
            )}
            {problems.length > 0 && (
              <div className="space-y-2">
                {problems.map((c, i) => (
                  <div key={i} className="rounded-xl border border-rose-200 bg-rose-50/60 px-3 py-2 text-sm">
                    <div className="text-xs font-semibold text-rose-700">{STATUS_KO[c.status]} · {ruleLabel(c.rule_id)}</div>
                    <div className="text-slate-800">{plainMessage(c.message)}</div>
                  </div>
                ))}
              </div>
            )}
            <div className="flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
              값을 누르면 원문 근거를 보여 줍니다 ·
              <span className="rounded-full bg-violet-100 px-2 py-0.5 font-semibold text-violet-700">AI 보완</span>
              <span className="rounded-full bg-emerald-100 px-2 py-0.5 font-semibold text-emerald-700">사람 확인</span>
              <span>표시 없는 값은 규칙이 읽은 값</span>
            </div>
            {doc.llm?.status === 'FAILED' && <div className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">AI 보완을 시도했지만 실패해 규칙 값만 남았습니다{doc.llm.error ? ` (${doc.llm.error})` : ''}.</div>}
            {(doc.llm?.applied_value_field_count ?? 0) > 0 && <div className="rounded-lg bg-violet-50 px-3 py-2 text-xs text-violet-800">이 서류는 AI가 {doc.llm?.applied_value_field_count}칸을 보완했습니다. 원문 근거가 확인된 값만 채택했으니, 표시된 칸을 원문과 한 번 더 비교해 주세요.</div>}
            {provError && <div className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{provError}</div>}
            {!prov && !provError && <div className="flex items-center gap-2 text-sm text-slate-500"><Loader2 className="h-4 w-4 animate-spin" /> 값을 불러오는 중…</div>}
            {editing && (
              <div className="space-y-2 rounded-xl border-2 border-indigo-200 bg-indigo-50/40 p-3 text-sm">
                <div className="font-semibold text-indigo-900">원문을 보면서 틀린 값은 고치고, 맞는 값은 ‘원문과 맞음’에 체크하세요</div>
                <div className="text-[11px] text-slate-500">체크하거나 고친 칸만 ‘사람 확인’으로 표시됩니다. 손대지 않은 칸은 원래 출처(규칙·AI)로 남습니다.</div>
                {isMaskingEnabled && <div className="rounded-lg bg-amber-50 px-2.5 py-1.5 text-xs text-amber-800">개인정보 가림이 켜져 있어도 수정 칸에는 실제 값이 보입니다. 화면 공유 중이면 주의하세요.</div>}
                {rows.map(({ key, label }) => {
                  const v = (draft as Record<string, unknown>)[key];
                  const changed = changedKeys.includes(key);
                  const already = prov?.fields[key]?.source === 'HUMAN_CONFIRMATION';
                  return (
                    <div key={key} className="grid gap-1 text-xs text-slate-600">
                      <div className="flex items-center gap-2">
                        <span>{label}</span>
                        {changed ? <b className="text-indigo-700">· 바뀜 (사람 확인으로 기록)</b>
                          : already ? <span className="text-emerald-700">· 이미 사람 확인</span>
                          : v == null || v === '' || v === 'UNKNOWN' ? <span className="text-amber-700">· 비어 있음 — 원문을 보고 입력하세요</span>
                          : (
                            <label className="ml-auto inline-flex cursor-pointer items-center gap-1 text-[11px] text-slate-600">
                              <input type="checkbox" checked={confirmed.has(key)} onChange={() => toggleConfirmed(key)} className="h-3.5 w-3.5 accent-emerald-600" />
                              원문과 맞음
                            </label>
                          )}
                      </div>
                      {key === 'amount_scope' ? (
                        <select value={(v as string) || 'UNKNOWN'} onChange={(e) => setDraft({ ...draft, amount_scope: e.target.value as AnalysisFields['amount_scope'] })}
                          className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-800">
                          <option value="UNKNOWN">확인 필요</option><option value="FULL">전액 청구</option><option value="PARTIAL">일부(분할) 청구</option>
                        </select>
                      ) : (
                        <input
                          type={AMOUNT_KEYS.has(key) ? 'number' : key === 'issue_date' ? 'date' : 'text'}
                          min={AMOUNT_KEYS.has(key) ? 0 : undefined}
                          value={v == null ? '' : String(v)}
                          onChange={(e) => setDraft({ ...draft, [key]: AMOUNT_KEYS.has(key) ? (e.target.value === '' ? null : Number(e.target.value)) : (e.target.value || null) })}
                          aria-label={label}
                          className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-800" />
                      )}
                    </div>
                  );
                })}
                <label className="grid gap-1 text-xs text-slate-600">고친 이유·확인한 내용 (기록에 남습니다)
                  <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={1000}
                    placeholder="예: 원문 1쪽 합계금액 줄을 보고 2,200,000원으로 입력"
                    className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-800" />
                </label>
                <div className="flex flex-wrap gap-2">
                  <button onClick={() => void save()} disabled={saving || !note.trim() || changedKeys.length + confirmedKeys.length === 0}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 font-semibold text-white disabled:opacity-40">
                    <Save className="h-4 w-4" /> {saving ? '저장 중…' : `저장하고 다시 검사 (고친 칸 ${changedKeys.length} · 맞음 확인 ${confirmedKeys.length})`}
                  </button>
                  <button onClick={() => { setEditing(false); setDraft(doc.analysis.fields); }} className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-slate-600">취소</button>
                </div>
                {saveError && <p role="alert" className="text-xs text-rose-600">{saveError}</p>}
                <p className="text-[11px] text-slate-500">저장하면 고친 칸과 ‘원문과 맞음’에 체크한 칸만 확인한 사람·이유와 함께 ‘사람 확인’으로 표시됩니다. 이전 결재는 다시 확인이 필요해집니다.</p>
              </div>
            )}
            {prov && !editing && (
              <ul className="space-y-2">
                {rows.map(({ key, label }) => {
                  const f = prov.fields[key];
                  if (!f) return null;
                  const shown = display(key, f.value, isMaskingEnabled);
                  const ai = f.ai_decision;
                  const rejected = ai && ai.proposal && !ai.applied;
                  return (
                    <li key={key}>
                      <button
                        onClick={() => pick(key)}
                        className={`w-full rounded-xl border p-3 text-left text-sm transition ${selected === key ? 'border-indigo-400 ring-2 ring-indigo-200' : 'border-slate-200 hover:border-indigo-300'}`}
                      >
                        <div className="flex items-center gap-2">
                          <span className="text-slate-500">{label}</span>
                          {f.source === 'AI_SUPPLEMENT' && <span className="rounded-full bg-violet-100 px-2 py-0.5 text-[11px] font-semibold text-violet-700">AI 보완</span>}
                          {f.source === 'HUMAN_CONFIRMATION' && <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-700">사람 확인{f.human_confirmation ? ` · ${f.human_confirmation.actor_name}` : ''}</span>}
                          <span className="ml-auto text-xs text-slate-400">
                            {f.evidence_status === 'AVAILABLE' ? '근거 있음' : f.evidence_status === 'AMBIGUOUS' ? '후보 여러 개' : shown ? '근거 위치 없음' : ''}
                          </span>
                        </div>
                        <div className={`font-semibold tabular-nums ${shown ? 'text-slate-900' : 'text-amber-700'}`}>{shown || '못 읽음 · 원문 확인 필요'}</div>
                        {rejected && (
                          <div className="mt-1 rounded-lg bg-violet-50 px-2 py-1 text-xs text-violet-800">
                            AI 제안 "{String(ai!.proposal!.value ?? '')}"은 채택하지 않음
                            {ai!.reasons?.length ? ` · ${ai!.reasons.map((r) => REASON_KO[r] ?? r).join(', ')}` : ''}
                          </div>
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
            {canEdit && !editing && doc.version?.is_current !== false && (
              <div className="rounded-xl border border-dashed border-sky-300 p-3 text-sm space-y-2">
                <div className="text-slate-600">거래처에서 <b>고쳐서 다시 보낸 서류</b>를 받았다면 여기서 바꿔 올리세요. 이전 서류는 보관되고 검사에서 빠지며, 결재는 다시 받아야 합니다.</div>
                <input type="file" aria-label="재발행본 파일" onChange={(e) => setReissueFile(e.target.files?.[0] ?? null)} className="block w-full text-xs text-slate-600" />
                {reissueFile && (
                  <>
                    <input value={reissueNote} onChange={(e) => setReissueNote(e.target.value)} maxLength={500} placeholder="무엇을 고친 재발행본인지 (예: 합계 금액 정정)"
                      className="w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-800" />
                    <button onClick={() => void reissue()} disabled={reissuing || !reissueNote.trim()}
                      className="rounded-lg bg-sky-600 px-3 py-1.5 font-semibold text-white disabled:opacity-40">{reissuing ? '올리는 중… (서류를 읽고 있어요)' : '재발행본으로 바꾸기'}</button>
                  </>
                )}
                {reissueError && <p role="alert" className="text-xs text-rose-600">{reissueError}</p>}
              </div>
            )}
            {canEdit && !editing && (
              <div className="rounded-xl border border-dashed border-slate-300 p-3 text-sm">
                <div className="mb-2 text-slate-600">값이 원문과 다르거나 못 읽은 값이 있으면 여기서 바로 고칩니다. 고친 사람과 이유가 기록되고 검사가 다시 돌아갑니다.</div>
                <button onClick={() => setEditing(true)} className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 font-semibold text-white hover:bg-indigo-700">
                  <Pencil className="h-4 w-4" /> 값 고치기
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
