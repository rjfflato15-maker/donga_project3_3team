import React, { useMemo, useState } from 'react';
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
} from '../../utils/reviewSummary';
import { maskVendorName } from '../../utils/masking';
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronRight, Copy, Eye, Info, Upload } from 'lucide-react';
import { RequestDraftDialog } from './RequestDraftDialog';

interface Props {
  contract: ContractDetail;
  isMaskingEnabled: boolean;
  canEdit: boolean;
  ntsMode?: string;
  onOpenDocument: (doc: DocumentResponse) => void;
  onUploadType: (type: DocumentType) => void;
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
}) => {
  const overview = useMemo(() => buildReviewOverview(contract), [contract]);
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
                {(issue.kind === 'vendor' || issue.kind === 'missing') && canEdit && (
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
          onClose={() => setDraftFor(null)}
        />
      )}
    </div>
  );
};
