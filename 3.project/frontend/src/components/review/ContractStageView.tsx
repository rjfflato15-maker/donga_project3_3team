import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ContractDetail, DocumentResponse, DocumentType, ValidationStatus } from '../../types';
import { requestJson } from '../../api/client';
import { followUpApi, ResubmissionRequest, CONTACT_VIA } from '../../api/followUp';
import {
  buildReviewOverview, IssueGroup, plainMessage, showsValues, ruleLabel, isInternalDocument, DOCUMENT_TYPE_KO, STATUS_KO,
} from '../../utils/reviewSummary';
import { maskBusinessNumber, maskResidentNumber, maskVendorName } from '../../utils/masking';
import { fixParticles, josa } from '../../utils/korean';
import { Stage, stageOf, stepStates, STAGE_STEPS, STAGE_NO } from '../../utils/stage';
import { RequestDraftDialog } from './RequestDraftDialog';
import { ApprovalPanel } from './ApprovalPanel';
import { AssignmentPanel } from './AssignmentPanel';
import { PilotReviewPanel } from '../PilotReviewPanel';
import { ArrowLeft, Check, CheckCircle2, ChevronDown, ChevronRight, Copy, Eye, MoreHorizontal, Upload } from 'lucide-react';

/** 화면 표시용 가림: 사업자번호·주민번호만. 쉼표가 있는 금액은 건드리지 않는다 */
export const maskForDisplay = (text: string, masked: boolean) => (masked ? maskResidentNumber(maskBusinessNumber(text)) : text);

const won = (n?: number | null) => (n == null ? '-' : `${Math.round(n).toLocaleString('ko-KR')}원`);
const num = (s?: string | null) => {
  if (!s) return null;
  const m = s.replace(/[,\s원]/g, '').match(/^-?\d+(\.\d+)?$/);
  return m ? Number(m[0]) : null;
};
const today = () => new Date().toISOString().slice(0, 10);

const KIND_KO: Record<string, string> = { missing: '빠진 서류', vendor: '서류 내용 확인', reading: '원문 확인', contract: '계약 기준 확인' };
const kindCounts = (list: IssueGroup[]) => Object.entries(list.reduce<Record<string, number>>((m, i) => ({ ...m, [i.kind]: (m[i.kind] ?? 0) + 1 }), {}))
  .map(([k, n]) => `${KIND_KO[k] ?? k} ${n}건`).join(' · ');

/** 문제 제목은 짧게: 자세한 설명은 상자 안에서 */
const SHORT: Record<string, string> = {
  AMOUNT_COMPONENTS: '금액 계산이 안 맞아요',
  AMOUNT_MATCH_ESTIMATE: '금액이 계약과 달라요',
  AMOUNT_MATCH_TAX_INVOICE: '금액이 계약과 달라요',
  INSTALLMENT_TOTAL: '분할 금액 합계가 계약과 달라요',
  PAYMENT_SCOPE: '청구 범위를 확인해야 해요',
  BUSINESS_NO_MATCH: '사업자번호가 달라요',
  DUPLICATE_INVOICE: '이미 쓴 세금계산서예요',
  ORIGINAL_FILE: '원본 파일이 없어요',
  DOCUMENT_TYPE: '서류 종류를 확인해야 해요',
  DOCUMENT_PROCESSING: '서류를 읽지 못했어요',
};

const DOT: Record<ValidationStatus, string> = { FAIL: 'bg-rose-500', MISSING: 'bg-amber-500', REVIEW: 'bg-amber-500', PASS: 'bg-emerald-500' };

/** 문제 하나를 보여 주는 상자. primary면 크게 */
interface IssueBlockProps {
  issue: IssueGroup;
  primary?: boolean;
  canEdit: boolean;
  masked: boolean;
  onOpenDocument: (doc: DocumentResponse) => void;
  onUploadType: (type?: DocumentType) => void;
  onDraft: (issue: IssueGroup) => void;
}
const IssueBlock: React.FC<IssueBlockProps> = ({ issue, primary, canEdit, masked, onOpenDocument, onUploadType, onDraft }) => {
  const show = (t?: string | null) => (t ? maskForDisplay(t, masked) : t);
  const check = issue.checks[0];
  const a = num(check.expected), b = num(check.actual);
  const diff = a != null && b != null && a !== b ? Math.abs(a - b) : null;
  const external = issue.kind === 'vendor' || (issue.kind === 'missing' && !isInternalDocument(issue.missingType));
  const missingName = issue.missingType ? DOCUMENT_TYPE_KO[issue.missingType] ?? issue.title : issue.title;
  const title = issue.kind === 'missing'
    ? (isInternalDocument(issue.missingType) ? `${josa(missingName, '을/를')} 작성해서 올려 주세요` : `${josa(missingName, '이/가')} 아직 없어요`)
    : issue.kind === 'reading' ? `${issue.title}: 앱이 값을 정확히 못 읽었어요` : `${issue.title}: ${SHORT[check.rule_id] ?? show(plainMessage(check.message))}`;
  const btn = (on: boolean) => on
    ? 'inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-700'
    : 'inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:border-indigo-300';
  return (
    <div className={primary ? 'space-y-3' : 'space-y-2 rounded-xl border border-slate-200 bg-white p-3'}>
      <div className={primary ? 'text-xl font-bold text-slate-900' : 'font-semibold text-slate-900'}>{title}</div>
      {issue.kind !== 'missing' && primary && (issue.checks.length > 1 || SHORT[check.rule_id]) && (
        <ul className="space-y-1 text-sm text-slate-600">
          {issue.checks.map((c, i) => <li key={i}>· {ruleLabel(c.rule_id)}: {show(plainMessage(c.message))}</li>)}
        </ul>
      )}
      {primary && (check.expected || check.actual) && showsValues(check.rule_id) && (
        <div className="grid max-w-md grid-cols-3 gap-2 text-sm">
          <div className="rounded-lg border border-slate-200 bg-white p-2"><div className="text-xs text-slate-500">기준</div><b className="tabular-nums">{show(check.expected) || '-'}</b></div>
          <div className="rounded-lg border border-slate-200 bg-white p-2"><div className="text-xs text-slate-500">서류</div><b className="tabular-nums text-rose-600">{show(check.actual) || '-'}</b></div>
          {diff != null && <div className="rounded-lg border border-slate-200 bg-white p-2"><div className="text-xs text-slate-500">차이</div><b className="tabular-nums">{diff.toLocaleString('ko-KR')}원</b></div>}
        </div>
      )}
      {primary && (
        <p className="text-sm text-slate-600">
          {issue.kind === 'reading' && '원문을 보고 값을 직접 확인해 주세요. 거래처에 요청하기 전에 먼저 할 일이에요.'}
          {issue.kind === 'vendor' && '먼저 원문을 보고 앱이 제대로 읽었는지 확인하세요. 원문도 같다면 거래처에 고쳐 달라고 요청합니다.'}
          {issue.kind === 'missing' && (isInternalDocument(issue.missingType) ? '회사 안에서 작성하는 서류라 거래처에 요청하지 않아요.' : '거래처에게 받아야 하는 서류예요.')}
          {issue.kind === 'contract' && '등록한 계약 기준(금액·방식)이 맞는지 확인하세요.'}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {issue.document && <button onClick={() => onOpenDocument(issue.document!)} className={btn(issue.kind === 'reading' || primary === true && issue.kind === 'vendor')}><Eye className="h-4 w-4" />{issue.kind === 'reading' ? '원문 보고 값 확인' : '원문 보기'}</button>}
        {external && canEdit && <button onClick={() => onDraft(issue)} className={btn(issue.kind === 'missing')}><Copy className="h-4 w-4" />{issue.kind === 'missing' ? '거래처에 요청 문구 만들기' : '거래처에 보완 요청'}</button>}
        {issue.missingType && canEdit && <button onClick={() => onUploadType(issue.missingType)} className={btn(isInternalDocument(issue.missingType))}><Upload className="h-4 w-4" />{isInternalDocument(issue.missingType) ? '작성한 파일 올리기' : '이미 받았어요 → 올리기'}</button>}
      </div>
    </div>
  );
};

interface MenuAction { label: string; onClick: () => void; danger?: boolean; hidden?: boolean }

interface Props {
  contract: ContractDetail;
  isMaskingEnabled: boolean;
  canEdit: boolean;
  representative: boolean;
  ntsMode?: string;
  onBack: () => void;
  onOpenDocument: (doc: DocumentResponse) => void;
  onUploadType: (type?: DocumentType) => void;
  onChanged: () => Promise<void>;
  recentUploadNames?: string[];
  menu: MenuAction[];
}

/** 계약 화면: 단계 표시 + '지금 할 일' 상자 하나 + 서류 목록. 가끔 쓰는 기능은 ··· 메뉴 */
export const ContractStageView: React.FC<Props> = ({
  contract, isMaskingEnabled, canEdit, representative, ntsMode, onBack, onOpenDocument, onUploadType, onChanged, recentUploadNames, menu,
}) => {
  const overview = useMemo(() => buildReviewOverview(contract), [contract]);
  const [requests, setRequests] = useState<ResubmissionRequest[]>([]);
  const [followError, setFollowError] = useState('');
  const loadRequests = async () => {
    try { setRequests(await followUpApi.list(contract.contract_id)); setFollowError(''); }
    catch (e) { setFollowError(e instanceof Error ? e.message : '요청 기록을 불러오지 못했습니다.'); }
  };
  useEffect(() => { void loadRequests(); }, [contract.contract_id, contract.updated_at]);
  const waiting = requests.filter((r) => r.status === 'WAITING_RESPONSE');

  const wf = contract.workflow;
  const payment = (contract as { payment?: { paid_on?: string; method?: string; note?: string } | null }).payment ?? null;
  const missingIssues = overview.issues.filter((i) => i.kind === 'missing');
  const otherIssues = overview.issues.filter((i) => i.kind !== 'missing');
  const stage: Stage = stageOf({
    stage: (contract as { stage?: string }).stage,
    approval_status: wf?.approval_status,
    paid_on: payment?.paid_on,
    waiting_request_count: waiting.length,
    missing_count: missingIssues.length,
    open_issue_count: overview.issues.length,
  });
  const stageNo = STAGE_NO[stage];
  // 실제로 끝난 단계만 체크. 지금 단계보다 앞이어도 남은 일이 있으면 '남음', 요청한 적이 없으면 보완은 '해당 없음'
  const stepState = stepStates({ stage, missing: missingIssues.length, issues: overview.issues.length, waiting: waiting.length, requests: requests.length, approved: wf?.approval_status === 'CONFIRMED', paid: !!payment?.paid_on });

  const [draftFor, setDraftFor] = useState<IssueGroup | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showAssign, setShowAssign] = useState(false);
  const [showPassed, setShowPassed] = useState(false);
  const historyRef = useRef<HTMLDivElement>(null);
  useEffect(() => { setMenuOpen(false); setShowHistory(false); setShowAssign(false); }, [contract.contract_id]);

  // 회신 처리
  const [resolving, setResolving] = useState<{ id: number; status: 'RECEIVED' | 'CANCELLED' } | null>(null);
  const [resolveNote, setResolveNote] = useState('');
  const submitResolve = async () => {
    if (!resolving || !resolveNote.trim()) return;
    try {
      await followUpApi.resolve(contract.contract_id, resolving.id, resolving.status, resolveNote.trim());
      setResolving(null); setResolveNote('');
      await loadRequests();
      await onChanged();
    } catch (e) { setFollowError(e instanceof Error ? e.message : '처리하지 못했습니다.'); }
  };

  // 지급 기록
  const [paidOn, setPaidOn] = useState(today());
  const [payMethod, setPayMethod] = useState<'TRANSFER' | 'OTHER'>('TRANSFER');
  const [payNote, setPayNote] = useState('');
  const [payBusy, setPayBusy] = useState(false);
  const [payError, setPayError] = useState('');
  const recordPayment = async () => {
    setPayBusy(true); setPayError('');
    try {
      await requestJson(`/api/pilot/contracts/${contract.contract_id}/payment`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paid_on: paidOn, method: payMethod, note: payNote.trim(), revision: wf?.revision }),
      });
      await onChanged();
    } catch (e) {
      const msg = e instanceof Error ? e.message : '';
      setPayError(/not found|not allowed|404|405/i.test(msg) ? '지급 기록 기능은 아직 준비 중이에요. 지급은 평소대로 하시고, 기능이 연결되면 이 화면에서 기록할 수 있어요.' : msg || '기록하지 못했습니다.');
    } finally { setPayBusy(false); }
  };

  // 결재 요청용 요약 문장(코드가 채운 문장)
  const [brief, setBrief] = useState('');
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (stage !== 'APPROVAL' && stage !== 'DONE') return;
    const controller = new AbortController();
    setCopied(false);
    requestJson<{ text: string; facts?: { vendor_name?: string } }>(`/api/contracts/${contract.contract_id}/summary?style=brief`, { signal: controller.signal })
      .then((r) => {
        const v = r.facts?.vendor_name;
        setBrief(isMaskingEnabled && v ? r.text.split(v).join(maskVendorName(v, true)) : r.text);
      })
      .catch(() => undefined);
    return () => controller.abort();
  }, [contract.contract_id, contract.updated_at, wf?.approval_status, stage, isMaskingEnabled]);
  const copyBrief = () => { void navigator.clipboard?.writeText(brief).then(() => setCopied(true)).catch(() => undefined); };

  const basis = wf?.amount_basis === 'SUPPLY' ? '공급가액 기준' : wf?.amount_basis === 'TOTAL' ? '부가세 포함' : '금액 기준 미확인';
  const pay = wf?.payment_mode === 'INSTALLMENT' ? '분할 지급' : '일시 지급';
  const required = contract.required_document_types ?? [];
  const submittedTypes = new Set(contract.documents.map((d) => d.document_type));
  const llm = contract.llm?.current_state;
  const infoLine = `AI 보완 ${llm?.configured_enabled ? (llm.ready_for_inference ? '켜짐' : '켜짐·연결 안 됨') : '꺼짐'} · 국세청 조회 ${ntsMode === 'disabled' ? '미연동(확인할 것에 넣지 않음)' : '확인 못함'}`;

  const allMenu: MenuAction[] = [
    ...menu,
    { label: '처리 기록 보기', onClick: () => { setShowHistory(true); setTimeout(() => historyRef.current?.scrollIntoView({ behavior: 'smooth' }), 50); } },
    { label: '다른 담당자에게 맡기기', onClick: () => setShowAssign(true), hidden: !canEdit && !representative },
  ].filter((m) => !m.hidden);


  const blockProps = { canEdit, masked: isMaskingEnabled, onOpenDocument, onUploadType, onDraft: setDraftFor };
  const focusIssues = stage === 'RECEIVING' ? missingIssues : overview.issues;
  // 거래처에게 다시 받을 것: 서류 내용 문제 + 거래처가 내야 하는 빠진 서류
  const vendorIssues = overview.issues.filter((i) => i.kind === 'vendor' || (i.kind === 'missing' && !isInternalDocument(i.missingType)));
  const [first, ...rest] = focusIssues;
  const later = stage === 'RECEIVING' ? otherIssues : [];

  return (
    <div className="space-y-5">
      {/* 머리말 */}
      <div className="flex flex-wrap items-center gap-3">
        <button onClick={onBack} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 hover:border-indigo-300">
          <ArrowLeft className="h-4 w-4" /> 할 일
        </button>
        <div className="min-w-0">
          <h1 className="truncate text-xl font-bold text-slate-900" title={contract.title}>{contract.title}</h1>
          <div className="text-sm text-slate-500">
            {maskVendorName(contract.vendor_name, isMaskingEnabled)} · <b className="text-slate-700 tabular-nums">{won(contract.contract_amount)}</b> ({basis}) · {pay}
          </div>
        </div>
        <div className="relative ml-auto">
          <button onClick={() => setMenuOpen((v) => !v)} aria-expanded={menuOpen} aria-label="더 보기 메뉴"
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 hover:border-indigo-300">
            <MoreHorizontal className="h-4 w-4" /> 더 보기
          </button>
          {menuOpen && (
            <div className="absolute right-0 z-30 mt-1 w-64 rounded-xl border border-slate-200 bg-white p-1 text-sm shadow-lg" onMouseLeave={() => setMenuOpen(false)}>
              {allMenu.map((m) => (
                <button key={m.label} onClick={() => { setMenuOpen(false); m.onClick(); }}
                  className={`block w-full rounded-lg px-3 py-2 text-left hover:bg-slate-50 ${m.danger ? 'text-rose-600' : 'text-slate-700'}`}>{m.label}</button>
              ))}
              <div className="mt-1 border-t border-slate-100 px-3 py-2 text-xs text-slate-500">ⓘ {infoLine}</div>
            </div>
          )}
        </div>
      </div>

      {/* 단계 표시 */}
      <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4 sm:px-5">
        <ol className="flex items-center" aria-label="진행 단계">
          {STAGE_STEPS.map((s, i) => {
            const st = stepState[s.key];
            const done = st === 'done';
            const now = s.no === stageNo;
            const pending = st === 'pending' && !now;
            const skipped = st === 'skipped' && !now;
            return (
              <React.Fragment key={s.key}>
                {i > 0 && <li aria-hidden="true" className={`mx-1.5 h-0.5 min-w-[8px] flex-1 ${s.no <= stageNo ? 'bg-indigo-500' : 'bg-slate-200'}`} />}
                <li className={`flex shrink-0 items-center gap-2 text-sm font-semibold ${now ? 'text-indigo-700' : pending ? 'text-amber-700' : done ? 'text-slate-700' : 'text-slate-400'}`}
                  aria-current={now ? 'step' : undefined}
                  title={pending ? '아직 남은 일이 있어요' : skipped ? '이 계약은 해당 없음' : done ? '끝남' : undefined}>
                  <span className={`grid h-7 w-7 place-items-center rounded-full border-2 text-xs ${done && !now ? 'border-indigo-600 bg-indigo-600 text-white' : now ? 'border-indigo-600 bg-white text-indigo-700 ring-4 ring-indigo-100' : pending ? 'border-amber-500 bg-amber-50 text-amber-700' : skipped ? 'border-dashed border-slate-300 bg-white text-slate-400' : 'border-slate-300 bg-white text-slate-400'}`}>
                    {done && !now ? <Check className="h-3.5 w-3.5" /> : pending ? '!' : skipped ? '–' : s.no}
                  </span>
                  <span className={now ? '' : 'hidden md:inline'}>{s.label}{pending ? ' · 남음' : skipped ? ' · 해당 없음' : ''}</span>
                </li>
              </React.Fragment>
            );
          })}
        </ol>
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_260px]">
        <div className="min-w-0 space-y-4">
          {/* 지금 할 일 */}
          {stage === 'DONE' ? (
            <div className="space-y-2 rounded-2xl border-2 border-emerald-300 bg-emerald-50 p-5">
              <div className="flex items-center gap-2 text-xl font-bold text-emerald-900"><CheckCircle2 className="h-6 w-6" /> 끝났어요</div>
              <p className="text-sm text-emerald-800">{payment?.paid_on} 지급 완료{payment?.note ? ` · ${payment.note}` : ''}. 이 계약은 ‘할 일’에서 빠지고 ‘지난 계약 찾기’에 남아요.</p>
              {brief && <button onClick={copyBrief} className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-300 bg-white px-3 py-1.5 text-sm font-semibold text-emerald-800"><Copy className="h-4 w-4" />{copied ? '복사했어요' : '요약 복사'}</button>}
            </div>
          ) : (
            <section className="space-y-3 rounded-2xl border-2 border-indigo-500 bg-indigo-50/40 p-5" aria-labelledby="now-title">
              <div id="now-title" className="text-sm font-bold text-indigo-700">
                지금 할 일{(stage === 'CHECK' || stage === 'RECEIVING') && focusIssues.length > 1 ? ` · ${stage === 'RECEIVING' ? '빠진 서류' : '확인할 것'} ${focusIssues.length}건 중 1번째` : ''}
              </div>

              {(stage === 'RECEIVING' || stage === 'CHECK') && first && (
                <>
                  {wf?.approval_status === 'RETURNED' && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">대표가 돌려보낸 계약이에요. 처리 기록에서 이유를 확인하세요.</p>}
                  <IssueBlock issue={first} primary {...blockProps} />
                </>
              )}

              {stage === 'WAITING' && (
                <div className="space-y-3">
                  <div className="text-xl font-bold text-slate-900">거래처 답을 기다리는 중</div>
                  {waiting.map((r) => {
                    const late = r.due_on && r.due_on < today();
                    return (
                      <div key={r.request_id} className="rounded-xl bg-white px-3 py-2 text-sm">
                        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                          <span className="font-semibold text-slate-800">{r.requested_on.slice(5).replace('-', '/')} {CONTACT_VIA[r.contact_method]} 요청</span>
                          {r.due_on && <span className={late ? 'font-bold text-rose-600' : 'text-slate-500'}>기한 {r.due_on.slice(5).replace('-', '/')}{late ? ' 지남' : ''}</span>}
                          {canEdit && (
                            <span className="ml-auto flex gap-1.5">
                              <button onClick={() => { setResolving({ id: r.request_id, status: 'RECEIVED' }); setResolveNote(recentUploadNames?.length ? `받은 서류 올림: ${recentUploadNames.join(', ')}`.slice(0, 2000) : '고친 서류 받음'); }} className="rounded-lg bg-sky-600 px-2.5 py-1 text-xs font-semibold text-white">답 받음</button>
                              <button onClick={() => { setResolving({ id: r.request_id, status: 'CANCELLED' }); setResolveNote(''); }} className="rounded-lg border border-slate-200 px-2.5 py-1 text-xs text-slate-600">요청 취소</button>
                            </span>
                          )}
                        </div>
                        {r.memo && <div className="mt-0.5 line-clamp-2 text-xs text-slate-500">{maskForDisplay(fixParticles(r.memo), isMaskingEnabled)}</div>}
                        {resolving?.id === r.request_id && (
                          <div className="mt-2 flex flex-wrap gap-2">
                            <input value={resolveNote} onChange={(e) => setResolveNote(e.target.value)} aria-label="처리 메모" placeholder={resolving.status === 'RECEIVED' ? '받은 내용' : '취소 이유'}
                              className="min-w-0 flex-1 rounded-lg border border-slate-300 px-2 py-1 text-sm" />
                            <button onClick={submitResolve} disabled={!resolveNote.trim()} className="rounded-lg bg-slate-900 px-3 py-1 text-xs font-semibold text-white disabled:opacity-40">{resolving.status === 'RECEIVED' ? '답 받음으로 기록' : '취소 기록'}</button>
                            <button onClick={() => setResolving(null)} className="text-xs text-slate-500">닫기</button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                  {canEdit && vendorIssues.length > 0 && (
                    <div className="space-y-2">
                      <div className="text-sm font-semibold text-slate-700">고친 서류를 받았다면 올리세요</div>
                      <div className="flex flex-wrap gap-2">
                        {vendorIssues.map((i) => i.document
                          ? <button key={i.key} onClick={() => onOpenDocument(i.document!)} className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-700"><Upload className="h-4 w-4" />{DOCUMENT_TYPE_KO[i.document.document_type]} 고친 본 올리기</button>
                          : i.missingType ? <button key={i.key} onClick={() => onUploadType(i.missingType)} className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-700"><Upload className="h-4 w-4" />{DOCUMENT_TYPE_KO[i.missingType]} 올리기</button> : null)}
                      </div>
                      <p className="text-xs text-slate-500">올리면 이전 서류는 보관되고 새 서류로 자동으로 다시 확인해요. 그다음 ‘답 받음’을 눌러 요청을 닫으세요.</p>
                    </div>
                  )}
                  {canEdit && vendorIssues.length === 0 && (
                    <button onClick={() => onUploadType()} className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-700"><Upload className="h-4 w-4" />받은 서류 올리기</button>
                  )}
                  {canEdit && vendorIssues.length > 0 && (
                    <button onClick={() => onUploadType()} className="text-xs font-semibold text-indigo-600 hover:underline">다른 서류 올리기</button>
                  )}
                  {canEdit && overview.issues.length > vendorIssues.length && (
                    <p className="text-xs text-slate-500">거래처와 상관없이 확인할 것 {overview.issues.length - vendorIssues.length}건은 답을 받은 뒤 ‘② 확인’에서 처리해요.</p>
                  )}
                  {canEdit && overview.issues.length === 0 && <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">받은 서류로 문제가 모두 풀렸어요. ‘답 받음’을 눌러 요청을 닫으면 결재 단계로 넘어가요.</p>}
                </div>
              )}

              {stage === 'APPROVAL' && (
                <div className="space-y-3">
                  <div className="text-xl font-bold text-slate-900">{representative ? '결재할 차례예요' : '문제 없어요. 대표님 결재를 받으세요'}</div>
                  {!representative && brief && (
                    <div className="flex flex-wrap items-start gap-2 rounded-xl bg-white p-3 text-sm text-slate-700">
                      <p className="min-w-0 flex-1">{brief}</p>
                      <button onClick={copyBrief} className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-slate-200 px-2 py-1 text-xs text-slate-600"><Copy className="h-3.5 w-3.5" />{copied ? '복사했어요' : '대표님께 보낼 문장 복사'}</button>
                    </div>
                  )}
                  <ApprovalPanel contract={contract} onChanged={onChanged} embedded />
                </div>
              )}

              {stage === 'PAYMENT' && (
                <div className="space-y-3">
                  <div className="text-xl font-bold text-slate-900">대표 결재 끝. 지급하셨나요?</div>
                  {canEdit || representative ? (
                    <div className="flex flex-wrap items-end gap-2 text-sm">
                      <label className="grid gap-1"><span className="text-xs text-slate-500">지급일</span>
                        <input type="date" value={paidOn} onChange={(e) => setPaidOn(e.target.value)} className="rounded-lg border border-slate-300 bg-white px-2 py-1.5" /></label>
                      <label className="grid gap-1"><span className="text-xs text-slate-500">방법</span>
                        <select value={payMethod} onChange={(e) => setPayMethod(e.target.value as 'TRANSFER' | 'OTHER')} className="rounded-lg border border-slate-300 bg-white px-2 py-1.5">
                          <option value="TRANSFER">계좌이체</option><option value="OTHER">기타</option>
                        </select></label>
                      <label className="grid min-w-[180px] flex-1 gap-1"><span className="text-xs text-slate-500">메모 (선택)</span>
                        <input value={payNote} onChange={(e) => setPayNote(e.target.value)} maxLength={500} placeholder="예: 기업은행 이체" className="rounded-lg border border-slate-300 bg-white px-2 py-1.5" /></label>
                      <button onClick={() => void recordPayment()} disabled={payBusy || !paidOn} className="rounded-lg bg-emerald-700 px-4 py-2 font-semibold text-white hover:bg-emerald-800 disabled:opacity-40">{payBusy ? '기록 중…' : '지급 완료로 기록'}</button>
                    </div>
                  ) : <p className="text-sm text-slate-600">담당자가 지급하고 기록합니다.</p>}
                  <p className="text-xs text-slate-500">앱은 돈을 보내지 않아요. 지급했다는 기록만 남깁니다.</p>
                  {payError && <p role="alert" className="text-sm text-rose-600">{payError}</p>}
                </div>
              )}
            </section>
          )}

          {/* 그다음 할 일 */}
          {(stage === 'RECEIVING' || stage === 'CHECK') && (rest.length > 0 || later.length > 0) && (
            <div className="space-y-2">
              <div className="text-sm font-semibold text-slate-600">그다음 할 일 <span className="font-normal text-slate-500">· {kindCounts([...rest, ...later])}</span></div>
              {[...rest, ...later].map((i) => <IssueBlock key={i.key} issue={i} {...blockProps} />)}
            </div>
          )}
          {followError && <p className="text-xs text-rose-600">{followError}</p>}

          {/* 문제 없는 항목 */}
          {overview.passed.length > 0 && stage !== 'DONE' && (
            <div className="rounded-xl border border-slate-200 bg-white">
              <button onClick={() => setShowPassed((v) => !v)} aria-expanded={showPassed} className="flex w-full items-center gap-2 px-4 py-2.5 text-left text-sm text-slate-600">
                <CheckCircle2 className="h-4 w-4 text-emerald-600" /> 문제 없는 항목 {overview.passed.reduce((n, g) => n + g.count, 0)}개
                {showPassed ? <ChevronDown className="ml-auto h-4 w-4" /> : <ChevronRight className="ml-auto h-4 w-4" />}
              </button>
              {showPassed && (
                <ul className="divide-y divide-slate-100 px-4 pb-2 text-sm">
                  {overview.passed.map((g) => (
                    <li key={g.ruleId} className="py-1.5 text-slate-700"><span className="text-emerald-600">✓</span> <b>{g.label}</b>{g.count > 1 ? ` · ${g.count}개 서류 모두 일치` : ` · ${plainMessage(g.messages[0])}`}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>

        {/* 서류 목록 */}
        <aside className="min-w-0">
          <div className="rounded-2xl border border-slate-200 bg-white p-2">
            <div className="px-2 pb-1 pt-1 text-sm font-bold text-slate-900">
              {required.length ? <>필요 {required.length}종 · <span className={required.every((t) => submittedTypes.has(t)) ? 'text-emerald-700' : 'text-amber-700'}>받은 {required.filter((t) => submittedTypes.has(t)).length}종</span></> : `서류 ${contract.documents.length}개`}
            </div>
            {contract.documents.map((doc) => {
              const st = overview.documentStatus.get(doc.document_id) ?? 'PASS';
              return (
                <button key={doc.document_id} onClick={() => onOpenDocument(doc)} className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-sm hover:bg-slate-50">
                  <span className={`h-2 w-2 shrink-0 rounded-full ${DOT[st]}`} />
                  <span className={`truncate ${st !== 'PASS' ? 'font-semibold text-slate-900' : 'text-slate-700'}`}>{DOCUMENT_TYPE_KO[doc.document_type]}</span>
                  {(doc.version?.version_number ?? 1) > 1 && <span className="shrink-0 text-[11px] text-sky-700">고친 본</span>}
                  {st !== 'PASS' && <span className="ml-auto shrink-0 text-xs font-semibold text-amber-700">{STATUS_KO[st]}</span>}
                </button>
              );
            })}
            {required.filter((t) => !submittedTypes.has(t)).map((t) => (
              <div key={t} className="flex items-center gap-2 rounded-lg px-2 py-2 text-sm">
                <span className="h-2 w-2 shrink-0 rounded-full border-2 border-rose-500" />
                <span className="truncate font-semibold text-slate-900">{DOCUMENT_TYPE_KO[t]}</span>
                {canEdit ? <button onClick={() => onUploadType(t)} className="ml-auto shrink-0 text-xs font-semibold text-indigo-600 hover:underline">올리기</button>
                  : <span className="ml-auto shrink-0 text-xs font-semibold text-rose-600">없음</span>}
              </div>
            ))}
            <p className="px-2 pb-1 pt-2 text-xs text-slate-500">서류를 누르면 원문과 읽은 값을 나란히 봐요.</p>
          </div>
        </aside>
      </div>

      {showAssign && <AssignmentPanel contract={contract} />}
      {!showAssign && <AssignmentPanel contract={contract} hideWhenEmpty />}
      {showHistory && (
        <div ref={historyRef}>
          <PilotReviewPanel contract={contract} onChanged={onChanged} historyOnly />
        </div>
      )}

      {draftFor && (
        <RequestDraftDialog
          contract={contract}
          issue={draftFor}
          isMaskingEnabled={isMaskingEnabled}
          canRecord={canEdit}
          onClose={() => setDraftFor(null)}
          onRecorded={async () => { await loadRequests(); await onChanged(); }}
        />
      )}
    </div>
  );
};
