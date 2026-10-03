import React, { useEffect, useMemo, useState } from 'react';
import { ContractDetail, DocumentResponse, DocumentType, ValidationStatus } from '../../types';
import {
  buildReviewOverview,
  verdictText,
  ruleLabel,
  STATUS_KO,
  DOCUMENT_TYPE_KO,
  IssueGroup,
  plainMessage,
  showsValues,
  isInternalDocument,
} from '../../utils/reviewSummary';
import { maskVendorName } from '../../utils/masking';
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronRight, Copy, Eye, Info, Upload } from 'lucide-react';
import { RequestDraftDialog } from './RequestDraftDialog';
import { AssistantPreview, AssignDraft } from './AssistantPreview';
import { followUpApi, ResubmissionRequest, CONTACT_VIA } from '../../api/followUp';
import { requestJson } from '../../api/client';

interface Props {
  contract: ContractDetail;
  isMaskingEnabled: boolean;
  canEdit: boolean;
  ntsMode?: string;
  onOpenDocument: (doc: DocumentResponse) => void;
  onUploadType: (type: DocumentType) => void;
  pilot?: boolean;
  onChanged?: () => Promise<void>;
  recentUploadNames?: string[];
  onAssign?: (draft: AssignDraft) => void;
}

const STATUS_STYLE: Record<ValidationStatus, string> = {
  FAIL: 'bg-rose-100 text-rose-700',
  MISSING: 'bg-amber-100 text-amber-800',
  REVIEW: 'bg-amber-100 text-amber-800',
  PASS: 'bg-emerald-100 text-emerald-700',
};

const DOT: Record<ValidationStatus, string> = {
  FAIL: 'bg-rose-500',
  MISSING: 'bg-amber-500',
  REVIEW: 'bg-amber-500',
  PASS: 'bg-emerald-500',
};

const won = (n?: number | null) => (n == null ? '-' : `${Math.round(n).toLocaleString('ko-KR')}원`);

export const ContractReviewOverview: React.FC<Props> = ({
  contract,
  isMaskingEnabled,
  canEdit,
  ntsMode,
  onOpenDocument,
  onUploadType,
  pilot = false,
  onChanged,
  recentUploadNames,
  onAssign,
}) => {
  const [requests, setRequests] = useState<ResubmissionRequest[]>([]);
  const [resolving, setResolving] = useState<{ id: number; status: 'RECEIVED' | 'CANCELLED' } | null>(null);
  const [resolveNote, setResolveNote] = useState('');
  const [followError, setFollowError] = useState('');
  const loadRequests = async () => {
    if (!pilot) return;
    try { setRequests(await followUpApi.list(contract.contract_id)); setFollowError(''); }
    catch (e) { setFollowError(e instanceof Error ? e.message : '요청 기록을 불러오지 못했습니다.'); }
  };
  useEffect(() => { void loadRequests(); }, [contract.contract_id, contract.updated_at, pilot]);
  const waiting = requests.filter((r) => r.status === 'WAITING_RESPONSE');
  const submitResolve = async () => {
    if (!resolving || !resolveNote.trim()) return;
    try {
      await followUpApi.resolve(contract.contract_id, resolving.id, resolving.status, resolveNote.trim());
      setResolving(null); setResolveNote('');
      await loadRequests();
      await onChanged?.();
    } catch (e) { setFollowError(e instanceof Error ? e.message : '처리하지 못했습니다.'); }
  };
  // 보고용 한 줄 요약: 숫자는 코드가 채운 문장(LLM 미사용). 가림 모드면 거래처 이름을 가린다.
  const [brief, setBrief] = useState<{ text: string; vendor?: string } | null>(null);
  const [briefCopied, setBriefCopied] = useState(false);
  useEffect(() => {
    if (!pilot) return;
    const controller = new AbortController();
    setBrief(null); setBriefCopied(false);
    requestJson<{ text: string; facts?: { vendor_name?: string } }>(`/api/contracts/${contract.contract_id}/summary?style=brief`, { signal: controller.signal })
      .then((r) => setBrief({ text: r.text, vendor: r.facts?.vendor_name }))
      .catch(() => undefined);
    return () => controller.abort();
  }, [contract.contract_id, contract.updated_at, contract.workflow?.revision, pilot]);
  const overview = useMemo(() => buildReviewOverview(contract), [contract]);
  // 서버 요약은 검사 항목 단위로 센다. 화면은 서류별 카드로 묶으므로 카드 수로 맞춘다.
  const briefText = brief
    ? (isMaskingEnabled && brief.vendor ? brief.text.split(brief.vendor).join(maskVendorName(brief.vendor, true)) : brief.text)
        .replace(/확인할 항목은 \d+건/, `확인할 항목은 ${overview.issues.length}건`)
    : '';
  const verdict = verdictText(overview);
  const [showPassed, setShowPassed] = useState(false);
  const [draftFor, setDraftFor] = useState<IssueGroup | null>(null);
  const clean = overview.issues.length === 0;
  const wf = contract.workflow;
  const basis = wf?.amount_basis === 'SUPPLY' ? '공급가액 기준' : wf?.amount_basis === 'TOTAL' ? '합계 기준' : '금액 기준 미확인';
  const pay = wf?.payment_mode === 'INSTALLMENT' ? '분할 지급' : '일시 지급';
  const required = contract.required_document_types ?? [];
  const submittedTypes = new Set(contract.documents.map((d) => d.document_type));

  return (
    <div className="space-y-4">
      {/* 계약 요약 */}
      <div className="bg-white rounded-2xl border border-slate-200 px-5 py-4 flex flex-wrap gap-x-8 gap-y-2 text-sm">
        <div className="min-w-0">
          <div className="text-xs text-slate-500">계약</div>
          <div className="font-bold text-slate-900 truncate max-w-[22rem]" title={contract.title}>{contract.title}</div>
        </div>
        <div>
          <div className="text-xs text-slate-500">거래처</div>
          <div className="font-bold text-slate-900">{maskVendorName(contract.vendor_name, isMaskingEnabled)}</div>
        </div>
        <div>
          <div className="text-xs text-slate-500">계약 금액</div>
          <div className="font-bold text-slate-900 tabular-nums">
            {won(contract.contract_amount)} <span className="text-xs font-normal text-slate-400">{basis} · {pay}</span>
          </div>
        </div>
        <div>
          <div className="text-xs text-slate-500">서류</div>
          <div className="font-bold text-slate-900">{contract.summary.submitted_document_count} / {contract.summary.required_document_count}종</div>
        </div>
        {briefText && (
          <div className="basis-full flex flex-wrap items-start gap-2 border-t border-slate-100 pt-2">
            <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">보고용 한 줄</span>
            <p className="min-w-0 flex-1 text-slate-700">{briefText}</p>
            <button
              onClick={() => { void navigator.clipboard?.writeText(briefText).then(() => setBriefCopied(true)).catch(() => undefined); }}
              className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-slate-200 px-2 py-1 text-xs text-slate-600 hover:bg-slate-50"
            >
              <Copy className="w-3.5 h-3.5" /> {briefCopied ? '복사됨' : '복사'}
            </button>
          </div>
        )}
      </div>

      {/* 결론 한 줄 */}
      <div
        className={`rounded-2xl border-2 px-5 py-4 flex items-start gap-3 ${
          clean ? 'border-emerald-300 bg-emerald-50' : 'border-amber-300 bg-amber-50'
        }`}
        role="status"
      >
        {clean ? (
          <CheckCircle2 className="w-7 h-7 text-emerald-600 shrink-0" />
        ) : (
          <AlertTriangle className="w-7 h-7 text-amber-600 shrink-0" />
        )}
        <div className="min-w-0">
          <div className={`text-lg font-bold ${clean ? 'text-emerald-900' : 'text-amber-900'}`}>{verdict.title}</div>
          <div className={`text-sm ${clean ? 'text-emerald-800' : 'text-amber-800'}`}>{verdict.detail}</div>
        </div>
      </div>
      {waiting.length > 0 && (
        <div className="rounded-2xl border-2 border-sky-300 bg-sky-50 px-5 py-4 space-y-2">
          <div className="font-bold text-sky-900">회신 대기 {waiting.length}건</div>
          {recentUploadNames && recentUploadNames.length > 0 && canEdit && (
            <div className="flex flex-wrap items-center gap-2 rounded-xl bg-white px-3 py-2 text-sm text-sky-900">
              <span>방금 올린 서류: <b className="break-all">{recentUploadNames.join(', ')}</b>. 요청한 서류를 받은 거라면 회신 받음으로 기록하세요.</span>
              <button onClick={() => { setResolving({ id: waiting[0].request_id, status: 'RECEIVED' }); setResolveNote(`회신 서류 등록: ${recentUploadNames.join(', ')}`.slice(0, 2000)); }}
                className="rounded-lg bg-sky-600 px-2.5 py-1 text-xs font-semibold text-white">{waiting.length > 1 ? '가장 오래된 요청을 회신 받음으로' : '회신 받음으로 기록'}</button>
            </div>
          )}
          {waiting.map((r) => (
            <div key={r.request_id} className="rounded-xl bg-white/80 px-3 py-2 text-sm">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <span className="font-semibold text-slate-800">{r.requested_on} {CONTACT_VIA[r.contact_method]} 요청</span>
                {r.due_on && <span className={`text-xs ${r.due_on < new Date().toISOString().slice(0, 10) ? 'font-bold text-rose-600' : 'text-slate-500'}`}>기한 {r.due_on}</span>}
                <span className="text-xs text-slate-400">{r.actor_name}</span>
                {canEdit && (
                  <span className="ml-auto flex gap-1.5">
                    <button onClick={() => { setResolving({ id: r.request_id, status: 'RECEIVED' }); setResolveNote('보완 서류를 받음'); }} className="rounded-lg bg-sky-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-sky-700">회신 받음</button>
                    <button onClick={() => { setResolving({ id: r.request_id, status: 'CANCELLED' }); setResolveNote(''); }} className="rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-600">요청 취소</button>
                  </span>
                )}
              </div>
              <div className="text-xs text-slate-600 mt-0.5 break-words">{r.memo}</div>
              {resolving?.id === r.request_id && (
                <div className="mt-2 flex flex-wrap gap-2">
                  <input value={resolveNote} onChange={(e) => setResolveNote(e.target.value)} placeholder={resolving.status === 'RECEIVED' ? '받은 내용 (예: 수정 세금계산서 받음)' : '취소 이유'} className="min-w-0 flex-1 rounded-lg border border-slate-200 px-2 py-1 text-sm" aria-label="처리 메모" />
                  <button onClick={submitResolve} disabled={!resolveNote.trim()} className="rounded-lg bg-slate-900 px-3 py-1 text-xs font-semibold text-white disabled:opacity-40">{resolving.status === 'RECEIVED' ? '회신 받음으로 기록' : '취소 기록'}</button>
                  <button onClick={() => setResolving(null)} className="text-xs text-slate-500">닫기</button>
                </div>
              )}
            </div>
          ))}
          <p className="text-xs text-sky-800">새 서류를 받았다면 '서류 추가'로 올리면 자동으로 다시 검사합니다. 회신 처리는 따로 눌러 기록합니다.</p>
        </div>
      )}
      {followError && <p className="text-xs text-rose-600">{followError}</p>}
      {pilot && contract.llm?.current_state && (() => {
        const st = contract.llm.current_state;
        const applied = contract.llm.applied_value_field_count ?? 0;
        const readingCount = overview.issues.filter((i) => i.kind === 'reading').length;
        const on = st.configured_enabled;
        const ready = on && st.ready_for_inference;
        return (
          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 font-semibold ${ready ? 'bg-violet-100 text-violet-700' : on ? 'bg-amber-100 text-amber-800' : 'bg-slate-100 text-slate-600'}`}>
              AI 보완 {ready ? '켜짐' : on ? '켜짐 · 연결 안 됨' : '꺼짐'}
            </span>
            {applied > 0 && <span className="rounded-full bg-violet-50 px-2.5 py-1 font-semibold text-violet-700">이 계약에서 AI가 채운 칸 {applied}개</span>}
            <span>
              {ready
                ? '규칙이 못 읽은 값만 PC 안의 AI가 다시 읽고, 원문 근거가 확인된 값만 채택합니다.'
                : on
                  ? 'AI 서버나 모델을 찾지 못해 규칙만 사용했습니다. 업무 설정에서 상태를 확인하세요.'
                  : readingCount > 0
                    ? `규칙만 사용 중입니다. AI 보완을 켜면 '원문 확인' ${readingCount}건 중 일부를 AI가 다시 읽어 봅니다.`
                    : '규칙만 사용 중입니다.'}
            </span>
          </div>
        );
      })()}
      {overview.notices.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 font-semibold text-slate-600">
            <Info className="w-3.5 h-3.5" /> 국세청 사업자 상태 조회 {ntsMode === 'disabled' ? '미연동' : '확인 못함'}
          </span>
          <span>사내망 모드에서는 조회하지 않으며, 확인할 항목 수에 넣지 않았습니다.</span>
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_280px]">
        {/* 확인할 것 */}
        <div className="min-w-0 space-y-3">
          {!clean && (
            <h2 className="font-bold text-slate-900">
              확인할 것 <span className="text-sm font-normal text-slate-400">위험한 순서</span>
            </h2>
          )}
          {!clean && pilot && (
            <AssistantPreview
              contract={contract}
              canEdit={canEdit}
              onAssign={onAssign}
              onOpenDocument={(id) => { const d = contract.documents.find((x) => x.document_id === id); if (d) onOpenDocument(d); }}
              onRequest={({ document_id, field }) => {
                const g = overview.issues.find((i) => (document_id != null && i.document?.document_id === document_id) || i.missingType === field);
                if (g) setDraftFor(g);
              }}
            />
          )}
          {overview.issues.map((issue) => (
            <article key={issue.key} className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
              <div className="px-5 pt-4 flex items-start gap-3">
                <span className={`shrink-0 rounded-md px-2 py-0.5 text-xs font-bold ${STATUS_STYLE[issue.status]}`}>
                  {STATUS_KO[issue.status]}
                </span>
                <div className="min-w-0">
                  <div className="font-bold text-slate-900">{issue.title}</div>
                  {issue.document && (
                    <div className="text-xs text-slate-500 truncate">{issue.document.original_file_name}</div>
                  )}
                </div>
              </div>
              <ul className="px-5 py-3 grid gap-2 text-sm">
                {issue.checks.map((check, i) => (
                  <li key={i} className="rounded-xl bg-slate-50 px-3 py-2">
                    <div className="text-xs text-slate-500">{ruleLabel(check.rule_id)}</div>
                    <div className="text-slate-800">{plainMessage(check.message)}</div>
                    {(check.expected || check.actual) && showsValues(check.rule_id) && (
                      <div className="mt-1 flex flex-wrap gap-x-4 text-xs tabular-nums">
                        {check.expected && <span className="text-slate-500">기준 <b className="text-slate-800">{check.expected}</b></span>}
                        {check.actual && <span className="text-slate-500">서류 <b className={issue.status === 'FAIL' ? 'text-rose-600' : 'text-slate-800'}>{check.actual}</b></span>}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
              {issue.kind === 'missing' && isInternalDocument(issue.missingType) && (
                <p className="px-5 pb-2 text-xs text-slate-500">회사 안에서 작성하는 서류입니다. 거래처에 요청하지 않고, 작성한 파일을 올리면 됩니다.</p>
              )}
              {issue.kind === 'reading' && (
                <p className="px-5 pb-2 text-xs text-slate-500">앱이 원문에서 값을 정확히 읽지 못한 항목입니다. 거래처에 요청하기 전에 원문을 보고 값을 확인해 주세요.</p>
              )}
              <div className="px-5 py-3 bg-slate-50 border-t border-slate-100 flex flex-wrap gap-2">
                {issue.document && (
                  <button
                    onClick={() => onOpenDocument(issue.document!)}
                    className={issue.kind === 'reading'
                      ? 'inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-indigo-700'
                      : 'inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 hover:border-indigo-300'}
                  >
                    <Eye className="w-4 h-4" /> {issue.kind === 'reading' ? '원문 보고 값 확인' : '원문에서 보기'}
                  </button>
                )}
                {issue.missingType && canEdit && (
                  <button
                    onClick={() => onUploadType(issue.missingType!)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 hover:border-indigo-300"
                  >
                    <Upload className="w-4 h-4" /> 파일 올리기
                  </button>
                )}
                {(issue.kind === 'vendor' || (issue.kind === 'missing' && !isInternalDocument(issue.missingType))) && canEdit && (
                  <button
                    onClick={() => setDraftFor(issue)}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-indigo-700"
                  >
                    <Copy className="w-4 h-4" /> 재제출 요청 문구
                  </button>
                )}
              </div>
            </article>
          ))}

          {/* 정상 항목 */}
          {overview.passed.length > 0 && (
            <div className="bg-white rounded-2xl border border-slate-200">
              <button
                onClick={() => setShowPassed((v) => !v)}
                className="w-full px-5 py-3 flex items-center gap-2 text-left text-sm"
                aria-expanded={showPassed}
              >
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <b className="text-slate-900">정상 항목 {overview.passed.reduce((n, g) => n + g.count, 0)}개</b>
                <span className="text-slate-500 truncate">{overview.passed.map((g) => g.label).join(' · ')}</span>
                {showPassed ? <ChevronDown className="ml-auto w-4 h-4 text-slate-400" /> : <ChevronRight className="ml-auto w-4 h-4 text-slate-400" />}
              </button>
              {showPassed && (
                <ul className="px-5 pb-3 text-sm divide-y divide-slate-100">
                  {overview.passed.map((g) => (
                    <li key={g.ruleId} className="py-2 flex gap-2">
                      <span className="text-emerald-600">✓</span>
                      <span className="text-slate-700">
                        <b>{g.label}</b>
                        {g.count > 1 ? ` · ${g.count}개 서류 모두 일치` : ` · ${plainMessage(g.messages[0])}`}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>

        {/* 서류 목록 */}
        <aside className="min-w-0">
          <h2 className="font-bold text-slate-900 mb-2">서류 {required.length || contract.documents.length}종</h2>
          <div className="bg-white rounded-2xl border border-slate-200 divide-y divide-slate-100 text-sm">
            {contract.documents.map((doc) => {
              const st = overview.documentStatus.get(doc.document_id) ?? 'PASS';
              return (
                <button
                  key={doc.document_id}
                  onClick={() => onOpenDocument(doc)}
                  className={`w-full px-4 py-3 flex items-center gap-2 text-left hover:bg-slate-50 ${st !== 'PASS' ? 'bg-rose-50/60' : ''}`}
                >
                  <span className={`w-2 h-2 rounded-full shrink-0 ${DOT[st]}`} />
                  <span className={`truncate ${st !== 'PASS' ? 'font-bold text-slate-900' : 'text-slate-700'}`}>
                    {DOCUMENT_TYPE_KO[doc.document_type]}
                  </span>
                  {st !== 'PASS' && <span className="ml-auto shrink-0 text-xs font-semibold text-rose-600">{STATUS_KO[st]} →</span>}
                </button>
              );
            })}
            {required
              .filter((t) => !submittedTypes.has(t))
              .map((t) => (
                <div key={t} className="px-4 py-3 flex items-center gap-2 bg-amber-50/60">
                  <span className={`w-2 h-2 rounded-full shrink-0 ${DOT.MISSING}`} />
                  <span className="font-bold text-slate-900 truncate">{DOCUMENT_TYPE_KO[t]}</span>
                  {canEdit ? (
                    <button onClick={() => onUploadType(t)} className="ml-auto shrink-0 text-xs font-semibold text-indigo-600 hover:underline">
                      올리기
                    </button>
                  ) : (
                    <span className="ml-auto shrink-0 text-xs font-semibold text-amber-700">미제출</span>
                  )}
                </div>
              ))}
          </div>
          <p className="mt-2 text-xs text-slate-500">서류를 누르면 원문과 읽은 값을 확인합니다.</p>
        </aside>
      </div>

      {draftFor && (
        <RequestDraftDialog
          contract={contract}
          issue={draftFor}
          isMaskingEnabled={isMaskingEnabled}
          canRecord={pilot && canEdit}
          onClose={() => setDraftFor(null)}
          onRecorded={async () => { await loadRequests(); await onChanged?.(); }}
        />
      )}
    </div>
  );
};
