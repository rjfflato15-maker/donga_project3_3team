import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createLatestGuard, replyNotice } from '../../utils/latest';
import { Basis, BundleCandidate, BundleContext, BundledRequest, BundleItem, BundleReplyPanel, BundleRequestDialog, RequestChecklist, bundleApi, currentDocumentFor } from './BundleRequest';
import { ContractDetail, DocumentResponse, DocumentType, ValidationStatus } from '../../types';
import { requestJson } from '../../api/client';
import { followUpApi, CONTACT_VIA } from '../../api/followUp';
import {
  buildReviewOverview, IssueGroup, plainMessage, showsValues, ruleLabel, isInternalDocument, DOCUMENT_TYPE_KO, STATUS_KO,
} from '../../utils/reviewSummary';
import { seoulToday } from '../../utils/date';
import { maskBusinessNumber, maskResidentNumber, maskVendorName } from '../../utils/masking';
import { fixParticles, josa } from '../../utils/korean';
import { Stage, stageOf, stepStates, STAGE_STEPS, STAGE_NO } from '../../utils/stage';
import { ApprovalPanel } from './ApprovalPanel';
import { AssignmentPanel } from './AssignmentPanel';
import { PilotReviewPanel } from '../PilotReviewPanel';
import { ArrowLeft, Check, CheckCircle2, ChevronDown, ChevronRight, Copy, Eye, MoreHorizontal, Upload } from 'lucide-react';

/** 화면 표시용 가림: 사업자번호·주민번호만. 쉼표가 있는 금액은 건드리지 않는다 */
export const maskForDisplay = (text: string, masked: boolean) => (masked ? maskResidentNumber(maskBusinessNumber(text)) : text);

const BLOCKED_KO: Record<string, string> = {
  FINAL_REVIEW_REQUIRED: '바뀐 자료로 대표 결재를 다시 받아야 재확인할 수 있어요.',
  SOURCE_VERSION_UNVERIFIED: '원본 파일이 등록 당시와 달라 확인할 수 없어요. 원본을 다시 등록하고 결재를 받아 주세요.',
  PAYEE_OR_AMOUNT_CHANGED: '거래처 사업자번호나 계약 금액·지급 방식이 바뀌어 기존 지급을 이 계약에 연결할 수 없어요. 실제 지급 내역을 따로 확인해 주세요.',
};

/**
 * 회사 안에서 확인할 것: 거래처 요청 후보가 아닌 문제.
 * 같은 서류에 거래처 문제(FAIL)와 판독 문제(REVIEW)가 함께 있으면 판독 문제만 따로 남긴다.
 */
export function splitInternalIssues(issues: IssueGroup[], vendorKeys: Set<string>): IssueGroup[] {
  const out: IssueGroup[] = [];
  for (const i of issues) {
    const vendorDoc = i.document ? vendorKeys.has(`d${i.document.document_id}`) : vendorKeys.has(`m${i.missingType}`);
    if (!vendorDoc) { out.push(i); continue; }
    const reviews = i.document ? i.checks.filter((c) => c.status === 'REVIEW') : [];
    if (reviews.length) out.push({ ...i, key: `${i.key}-review`, kind: 'reading', status: 'REVIEW', checks: reviews });
  }
  return out;
}

const won = (n?: number | null) => (n == null ? '-' : `${Math.round(n).toLocaleString('ko-KR')}원`);
const num = (s?: string | null) => {
  if (!s) return null;
  const m = s.replace(/[,\s원]/g, '').match(/^-?\d+(\.\d+)?$/);
  return m ? Number(m[0]) : null;
};
const today = () => seoulToday();


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
}
const IssueBlock: React.FC<IssueBlockProps> = ({ issue, primary, canEdit, masked, onOpenDocument, onUploadType }) => {
  const show = (t?: string | null) => (t ? maskForDisplay(t, masked) : t);
  const check = issue.checks[0];
  const a = num(check.expected), b = num(check.actual);
  const diff = a != null && b != null && a !== b ? Math.abs(a - b) : null;
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
  onOpenDocument: (doc: DocumentResponse, mode?: 'view' | 'reissue') => void;
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
  const [requests, setRequests] = useState<BundledRequest[]>([]);
  const [followError, setFollowError] = useState('');
  // 가장 최근에 보낸 조회만 반영한다(같은 계약의 느린 응답·다른 계약의 응답 모두 버림). 성공 여부를 돌려준다
  const reqGuard = useRef(createLatestGuard()).current;
  const ctxGuard = useRef(createLatestGuard()).current;
  const loadRequests = async (): Promise<boolean> => {
    const t = reqGuard.next();
    try { const list = await followUpApi.list(contract.contract_id); if (reqGuard.isLatest(t)) { setRequests(list); setFollowError(''); } return true; }
    catch (e) { if (reqGuard.isLatest(t)) setFollowError(e instanceof Error ? e.message : '요청 기록을 불러오지 못했습니다.'); return false; }
  };
  // 계약이 바뀌면 이전 계약의 목록·선택을 비우고 그 조회를 버린다. 아래 조회 effect보다 먼저 선언해야 새 조회를 버리지 않는다
  useEffect(() => {
    reqGuard.invalidate(); ctxGuard.invalidate();
    setCtx(null); setRequests([]); setBundleFor(null); setCtxError(''); setReplyMsg(null); setListStale(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contract.contract_id]);
  useEffect(() => { void loadRequests(); }, [contract.contract_id, contract.updated_at]);
  const waiting = requests.filter((r) => r.status === 'WAITING_RESPONSE');
  // 묶음 요청 후보: 거래처에 요청할 것 / 회사 안에서 확인할 것
  const [ctx, setCtx] = useState<BundleContext | null>(null);
  const [ctxError, setCtxError] = useState('');
  const loadCtx = async (): Promise<boolean> => {
    const cid = contract.contract_id;
    const t = ctxGuard.next();
    try { const c = await bundleApi.context(cid); if (ctxGuard.isLatest(t) && c.contract_id === cid) { setCtx(c); setCtxError(''); } return true; }
    catch (e) { if (ctxGuard.isLatest(t)) { setCtx(null); setCtxError(e instanceof Error ? e.message : '요청 후보를 불러오지 못했습니다.'); } return false; }
  };
  useEffect(() => { void loadCtx(); }, [contract.contract_id, contract.updated_at, contract.workflow?.revision, contract.workflow?.fingerprint]);
  const refreshAll = async (): Promise<boolean> => {
    const [a, b] = await Promise.all([loadRequests(), loadCtx()]);
    let c = true;
    try { await onChanged(); } catch { c = false; }
    const ok = a && b && c;
    setListStale(!ok);
    return ok;
  };
  // 회신 저장 결과·충돌 이유는 패널이 사라져도(요청 종료) 계약 화면에 남긴다
  const [replyMsg, setReplyMsg] = useState<{ tone: 'ok' | 'warn' | 'error'; text: string } | null>(null);
  // 마지막 재조회가 실패했으면 이전 선택·동의로 다시 저장하지 못하게 잠근다
  const [listStale, setListStale] = useState(false);
  const afterReply = async (saved: boolean, error?: string) => {
    const refreshed = await refreshAll();
    setReplyMsg(replyNotice(saved, refreshed, error));
  };
  // 기록하면 요청 버튼이 사라지므로, 창을 닫은 뒤 '답을 기다리는 중'으로 포커스를 옮긴다
  const waitingRef = useRef<HTMLDivElement>(null);
  const [bundleFor, setBundleFor] = useState<{ items: BundleCandidate[]; reviewed: Set<string>; basis: Basis } | null>(null);
  const latestBasis: Basis | null = ctx ? { contractId: ctx.contract_id, revision: ctx.revision, fingerprint: ctx.fingerprint } : null;
  const openItem = (item: BundleItem, mode: 'view' | 'reissue' = 'view') => {
    const id = currentDocumentFor(item, contract.documents);
    if (id != null) openDocId(id, mode); else onUploadType(item.document_type ?? undefined);
  };
  const openDocId = (id: number, mode: 'view' | 'reissue' = 'view') => { const d = contract.documents.find((x) => x.document_id === id); if (d) onOpenDocument(d, mode); };

  const wf = contract.workflow;
  const payment = contract.payment ?? null;
  // 자료가 바뀌어 다시 확인해야 하는 과거 지급 사실: 다시 지급하라고 안내하지 않는다
  const paidBefore = payment && payment.status === 'RECONFIRMATION_REQUIRED' ? payment : null;
  const missingIssues = overview.issues.filter((i) => i.kind === 'missing');
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
      setPayError(/not found|not allowed|404|405/i.test(msg) ? '지급 기록 기능을 쓸 수 없어요. 서버를 새 버전으로 다시 시작해야 해요.' : msg || '기록하지 못했습니다.');
    } finally { setPayBusy(false); }
  };
  // 같은 지급 사실 재확인(새 지급을 만들지 않음)
  const [sameAck, setSameAck] = useState(false);
  const [reNote, setReNote] = useState('');
  // 이전 자료에 대해 한 체크·메모를 새 자료에 그대로 쓰지 않는다
  const lastReview = wf?.reviews?.length ? Math.max(...wf.reviews.map((r) => r.review_id)) : null;
  const paymentBasis = [contract.contract_id, wf?.revision, wf?.fingerprint, wf?.approval_status, lastReview, payment?.payment_id, payment?.status, payment?.reconfirmation_allowed].join('|');
  useEffect(() => {
    setSameAck(false); setReNote(''); setPayError(''); setPayNote(''); setPaidOn(today()); setPayMethod('TRANSFER');
  }, [paymentBasis]);
  const reconfirm = async () => {
    if (!paidBefore) return;
    setPayBusy(true); setPayError('');
    try {
      await requestJson(`/api/pilot/contracts/${contract.contract_id}/payment/${paidBefore.payment_id}/reconfirm`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ revision: wf?.revision, note: reNote.trim(), acknowledge_same_payment: true }),
      });
      setSameAck(false); setReNote('');
      await onChanged();
    } catch (e) {
      setPayError(e instanceof Error ? e.message : '재확인하지 못했습니다.');
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


  const blockProps = { canEdit, masked: isMaskingEnabled, onOpenDocument, onUploadType, };
  const vendorKeys = new Set((ctx?.vendor_candidates ?? []).map((c) => (c.document_id != null ? `d${c.document_id}` : `m${c.document_type}`)));
  const internalIssues = splitInternalIssues(overview.issues, vendorKeys);

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
          {paidBefore && stage !== 'PAYMENT' && (
            <p role="status" className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              이 계약은 <b>{paidBefore.recorded_paid_on}</b>에 계약 전체 지급 완료로 기록돼 있어요. 자료가 바뀌어 다시 확인 중이에요. <b>다시 지급하지 말고</b>, 확인·결재가 끝나면 같은 지급인지 재확인하세요.
            </p>
          )}
          {/* 지금 할 일 */}
          {stage === 'DONE' ? (
            <div className="space-y-2 rounded-2xl border-2 border-emerald-300 bg-emerald-50 p-5">
              <div className="flex items-center gap-2 text-xl font-bold text-emerald-900"><CheckCircle2 className="h-6 w-6" /> 끝났어요</div>
              <p className="text-sm text-emerald-800">{payment?.paid_on} 계약 전체 지급 완료{payment?.method === 'TRANSFER' ? ' (계좌이체)' : ''}{payment?.note ? ` · ${payment.note}` : ''}. 이 계약은 ‘할 일’에서 빠지고 ‘지난 계약 찾기’에 남아요.</p>
              {brief && <button onClick={copyBrief} className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-300 bg-white px-3 py-1.5 text-sm font-semibold text-emerald-800"><Copy className="h-4 w-4" />{copied ? '복사했어요' : '요약 복사'}</button>}
            </div>
          ) : (
            <section className="space-y-3 rounded-2xl border-2 border-indigo-500 bg-indigo-50/40 p-5" aria-labelledby="now-title">
              <div id="now-title" className="text-sm font-bold text-indigo-700">지금 할 일</div>

              {(stage === 'RECEIVING' || stage === 'CHECK' || stage === 'WAITING') && (
                <div className="space-y-4">
                  <div className="text-base font-semibold text-slate-800">
                    필요 {ctx?.document_counts.required ?? required.length}종 · 받은 {ctx?.document_counts.received ?? required.filter((t) => submittedTypes.has(t)).length}종
                    {(ctx?.document_counts.missing ?? 0) > 0 && <span className="text-rose-600"> · 빠진 {ctx!.document_counts.missing}종</span>}
                  </div>
                  {wf?.approval_status === 'RETURNED' && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">대표가 돌려보낸 계약이에요. 처리 기록에서 이유를 확인하세요.</p>}

                  {replyMsg && (
                    <div role="alert" className={`flex items-start gap-2 rounded-lg px-3 py-2 text-sm ${replyMsg.tone === 'error' ? 'bg-rose-50 text-rose-700' : 'bg-amber-50 text-amber-900'}`}>
                      <span className="flex-1">{replyMsg.text}</span>
                      <button onClick={() => setReplyMsg(null)} className="text-xs underline">닫기</button>
                    </div>
                  )}
                  {waiting.length > 0 && (
                    <div className="space-y-2">
                      <div ref={waitingRef} tabIndex={-1} className="text-sm font-bold text-slate-900 outline-none focus:underline">거래처 답을 기다리는 중</div>
                      {waiting.map((r) => r.bundle ? (
                        <BundleReplyPanel key={r.request_id} contract={contract} request={r} canEdit={canEdit} isMaskingEnabled={isMaskingEnabled}
                          onOpenItem={openItem} onUploadType={onUploadType} onSaved={afterReply} locked={listStale} />
                      ) : (() => {
                        const late = r.due_on && r.due_on < today();
                        return (
                          <div key={r.request_id} className="rounded-xl bg-white px-3 py-2 text-sm">
                            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                              <span className="font-semibold text-slate-800">{r.requested_on.slice(5).replace('-', '/')} {CONTACT_VIA[r.contact_method]} 요청</span>
                              {r.due_on && <span className={late ? 'font-bold text-rose-600' : 'text-slate-500'}>기한 {r.due_on.slice(5).replace('-', '/')}{late ? ' 지남' : ''}</span>}
                              <span className="text-xs text-slate-400">이전 방식 기록</span>
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
                      })())}
                      {canEdit && <button onClick={() => onUploadType()} className="text-xs font-semibold text-indigo-600 hover:underline">받은 서류 올리기</button>}
                    </div>
                  )}

                  {ctx ? (
                    <RequestChecklist ctx={ctx} isMaskingEnabled={isMaskingEnabled} canEdit={canEdit} onOpenDocumentId={(id) => openDocId(id)}
                      onMake={(items, reviewed) => latestBasis && setBundleFor({ items, reviewed, basis: latestBasis })} />
                  ) : ctxError && (
                    <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">거래처 요청 목록을 불러오지 못했어요. 서버를 새 버전으로 다시 시작해야 할 수 있어요. ({ctxError})</p>
                  )}

                  {internalIssues.length > 0 && (
                    <div className="space-y-2">
                      <div className="text-sm font-bold text-slate-900">회사 안에서 확인할 것 {internalIssues.length}건</div>
                      {internalIssues.map((i) => <IssueBlock key={i.key} issue={i} {...blockProps} />)}
                    </div>
                  )}
                  {stage === 'WAITING' && overview.issues.length === 0 && waiting.length > 0 && (
                    <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">올린 서류로 검사 문제가 모두 풀렸어요. 받은 항목을 체크해 요청을 닫으면 결재 단계로 넘어가요.</p>
                  )}
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

              {stage === 'PAYMENT' && paidBefore && (
                <div className="space-y-3">
                  <div className="text-xl font-bold text-slate-900">이미 지급한 계약이에요. 같은 지급인지 확인해 주세요</div>
                  <p className="text-sm text-slate-700">{paidBefore.recorded_paid_on}에 <b>계약 전체 지급 완료</b>로 기록돼 있어요{paidBefore.actor_name ? ` (${paidBefore.actor_name})` : ''}. 그 뒤 서류나 계약 기준이 바뀌어 다시 결재했어요. <b>다시 지급하지 마세요.</b></p>
                  {paidBefore.reconfirmation_allowed ? (canEdit || representative) && (
                    <div className="space-y-2 rounded-xl bg-white p-3 text-sm">
                      <label className="flex items-start gap-2 text-slate-700">
                        <input type="checkbox" checked={sameAck} onChange={(e) => setSameAck(e.target.checked)} className="mt-1 h-4 w-4 accent-emerald-600" />
                        바뀐 자료를 다시 결재했고, 기존 지급이 이 계약 전체에 대한 같은 지급임을 확인합니다.
                      </label>
                      <textarea value={reNote} onChange={(e) => setReNote(e.target.value)} rows={2} maxLength={2000} placeholder="예: 견적서 정정본으로 재결재, 9/10 이체 내역이 같은 계약 전체 지급임을 확인"
                        className="w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5" aria-label="재확인 메모" />
                      <button onClick={() => void reconfirm()} disabled={payBusy || !sameAck || reNote.trim().length < 10}
                        className="rounded-lg bg-emerald-700 px-4 py-2 font-semibold text-white hover:bg-emerald-800 disabled:opacity-40">{payBusy ? '확인 중…' : '같은 지급으로 재확인'}</button>
                      <p className="text-xs text-slate-500">새 지급 기록을 만들지 않고, 기존 지급 사실을 지금 결재에 연결해요. 메모 10자 이상.</p>
                    </div>
                  ) : (
                    <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">{BLOCKED_KO[paidBefore.blocked_reason ?? ''] ?? '지금은 재확인할 수 없어요.'}</p>
                  )}
                  {payError && <p role="alert" className="text-sm text-rose-600">{payError}</p>}
                </div>
              )}

              {stage === 'PAYMENT' && !paidBefore && (
                <div className="space-y-3">
                  <div className="text-xl font-bold text-slate-900">대표 결재 끝. 계약 전체 지급을 마쳤나요?</div>
                  <p className="text-sm text-slate-600">{wf?.payment_mode === 'INSTALLMENT' ? '분할 지급 계약이에요. 모든 회차를 다 지급한 뒤에 기록하세요.' : '지급을 마친 날짜를 기록하세요.'}</p>
                  {canEdit || representative ? (
                    <div className="flex flex-wrap items-end gap-2 text-sm">
                      <label className="grid gap-1"><span className="text-xs text-slate-500">지급일</span>
                        <input type="date" value={paidOn} max={today()} onChange={(e) => setPaidOn(e.target.value)} className="rounded-lg border border-slate-300 bg-white px-2 py-1.5" /></label>
                      <label className="grid gap-1"><span className="text-xs text-slate-500">방법</span>
                        <select value={payMethod} onChange={(e) => setPayMethod(e.target.value as 'TRANSFER' | 'OTHER')} className="rounded-lg border border-slate-300 bg-white px-2 py-1.5">
                          <option value="TRANSFER">계좌이체</option><option value="OTHER">기타</option>
                        </select></label>
                      <label className="grid min-w-[180px] flex-1 gap-1"><span className="text-xs text-slate-500">메모 (선택)</span>
                        <input value={payNote} onChange={(e) => setPayNote(e.target.value)} maxLength={500} placeholder="예: 기업은행 이체" className="rounded-lg border border-slate-300 bg-white px-2 py-1.5" /></label>
                      <button onClick={() => void recordPayment()} disabled={payBusy || !paidOn} className="rounded-lg bg-emerald-700 px-4 py-2 font-semibold text-white hover:bg-emerald-800 disabled:opacity-40">{payBusy ? '기록 중…' : '계약 전체 지급 완료로 기록'}</button>
                    </div>
                  ) : <p className="text-sm text-slate-600">담당자가 지급하고 기록합니다.</p>}
                  <p className="text-xs text-slate-500">앱은 돈을 보내지 않아요. 지급했다는 기록만 남깁니다.</p>
                  {payError && <p role="alert" className="text-sm text-rose-600">{payError}</p>}
                </div>
              )}
            </section>
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

      {bundleFor && ctx && (
        <BundleRequestDialog contract={contract} basis={bundleFor.basis} latest={latestBasis} items={bundleFor.items} reviewed={bundleFor.reviewed} isMaskingEnabled={isMaskingEnabled}
          onClose={() => setBundleFor(null)} onStale={async () => { await refreshAll(); }}
          onRecorded={async () => { await refreshAll(); setTimeout(() => waitingRef.current?.focus(), 120); }} />
      )}
    </div>
  );
};
