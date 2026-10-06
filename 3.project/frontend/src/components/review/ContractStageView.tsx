import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createLatestGuard, replyNotice } from '../../utils/latest';
import { Basis, BundleCandidate, BundleContext, BundledRequest, BundleItem, BundleReplyPanel, BundleRequestPage, RequestChecklist, bundleApi, currentDocumentFor } from './BundleRequest';
import { ContractDetail, DocumentResponse, DocumentType } from '../../types';
import { requestJson } from '../../api/client';
import { followUpApi } from '../../api/followUp';
import {
  buildReviewOverview, IssueGroup,
} from '../../utils/reviewSummary';
import { seoulToday } from '../../utils/date';
import { maskBusinessNumber, maskResidentNumber, maskVendorName } from '../../utils/masking';
import { fixParticles } from '../../utils/korean';
import { Stage, stageOf, NextAction, isMyTurn, approvalWaitingFor } from '../../utils/stage';
import { ApprovalPanel } from './ApprovalPanel';
import { AssignmentPanel } from './AssignmentPanel';
import { ActivityTimeline } from './ActivityTimeline';
import { Surface, Badge } from '../ui/Surface';
import { DocumentTable } from './DocumentTable';
import { DocumentWorkspace } from './DocumentWorkspace';
import { DocumentUploadPage } from '../DocumentUploadPage';
import { ArrowLeft, Check, X, CheckCircle2, ChevronRight, Copy, Eye, MoreHorizontal, Upload } from 'lucide-react';

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
const today = () => seoulToday();




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
  sourceDocument?: DocumentResponse|null;
  onReissuedDocument?:(doc:DocumentResponse)=>void;
  sourceMode?: 'view'|'reissue';
  onCloseSource?:()=>void;
  uploadOpen?:boolean;uploadLoading?:boolean;uploadTarget?:string|null;onCloseUpload?:()=>void;onUploadFiles?:(files:File[],type?:string)=>Promise<void>;
}

/** 계약 화면: 단계 표시 + '지금 할 일' 상자 하나 + 서류 목록. 가끔 쓰는 기능은 ··· 메뉴 */
export const ContractStageView: React.FC<Props> = ({
  contract, isMaskingEnabled, canEdit, representative, ntsMode, onBack, onOpenDocument, onUploadType, onChanged, menu, sourceDocument, sourceMode, onCloseSource,onReissuedDocument,uploadOpen,uploadLoading,uploadTarget,onCloseUpload,onUploadFiles,
}) => {
  const activeContract=useRef(contract.contract_id);activeContract.current=contract.contract_id;
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
    if(activeContract.current!==contract.contract_id)return false;
    setListStale(!ok);
    return ok;
  };
  // 회신 저장 결과·충돌 이유는 패널이 사라져도(요청 종료) 계약 화면에 남긴다
  const [replyMsg, setReplyMsg] = useState<{ tone: 'ok' | 'warn' | 'error'; text: string } | null>(null);
  useEffect(()=>{if(replyMsg?.tone!=='ok')return;const timer=setTimeout(()=>setReplyMsg(null),6000);return()=>clearTimeout(timer);},[replyMsg]);
  // 마지막 재조회가 실패했으면 이전 선택·동의로 다시 저장하지 못하게 잠근다
  const [listStale, setListStale] = useState(false);
  const afterReply = async (saved: boolean, error?: string) => {
    if(activeContract.current!==contract.contract_id)return;
    const refreshed = await refreshAll();
    if(activeContract.current!==contract.contract_id)return;
    setReplyMsg(replyNotice(saved, refreshed, error) ?? {tone:'ok',text:'선택한 항목의 수령·취소를 기록했습니다. 자동 검사 결과는 따로 확인하세요.'});
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
  // 결재 차례: 서버 next_actions 기준(2단계 결재의 담당 검토 포함)
  const nextActions = (contract as { work_state?: { next_actions?: NextAction[] } | null }).work_state?.next_actions;
  const myApprovalTurn = isMyTurn(stage, nextActions, representative ? 'representative' : 'operator');
  const waitingFor = approvalWaitingFor(nextActions) ?? (representative ? null : 'representative');
  // 실제로 끝난 단계만 체크. 지금 단계보다 앞이어도 남은 일이 있으면 '남음', 요청한 적이 없으면 보완은 '해당 없음'

  const [menuOpen, setMenuOpen] = useState(false);
  const [showAssign, setShowAssign] = useState(false);
  useEffect(() => { setMenuOpen(false); setShowAssign(false); }, [contract.contract_id]);

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
    setBrief('');
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
  const llm = contract.llm?.current_state;
  const infoLine = `AI 보완 ${llm?.configured_enabled ? (llm.ready_for_inference ? '켜짐' : '켜짐·연결 안 됨') : '꺼짐'} · 국세청 조회 ${ntsMode === 'disabled' ? '미연동(확인할 것에 넣지 않음)' : '확인 못함'}`;

  const allMenu: MenuAction[] = [
    ...menu,
    { label: '처리 기록 보기', onClick: () => setDetailTab('history') },
    { label: '다른 담당자에게 맡기기', onClick: () => setShowAssign(true), hidden: !canEdit && !representative },
  ].filter((m) => !m.hidden);


  const vendorKeys = new Set((ctx?.vendor_candidates ?? []).map((c) => (c.document_id != null ? `d${c.document_id}` : `m${c.document_type}`)));
  const internalIssues = splitInternalIssues(overview.issues, vendorKeys);

  const [detailTab, setDetailTab] = useState<'documents' | 'requests' | 'approval' | 'history'>(() => ['APPROVAL','PAYMENT','DONE'].includes(stage) ? 'approval' : 'documents');
  // 팝업 대신 본문 화면을 바꿀 때 새 작업의 시작 위치를 보여 준다.
  useEffect(() => { document.querySelector('.topbar')?.scrollIntoView?.({block:'start'}); }, [contract.contract_id, detailTab, sourceDocument?.document_id, !!bundleFor, uploadOpen]);
  useEffect(() => { setDetailTab(['APPROVAL','PAYMENT','DONE'].includes(stage) ? 'approval' : 'documents'); }, [contract.contract_id]);
  const stageLabel = { RECEIVING:'확인 필요', CHECK:'확인 필요', WAITING:'회신 대기', APPROVAL:'결재 대기', PAYMENT:'지급 대기', DONE:'완료' }[stage];
  const returned = wf?.approval_status === 'RETURNED' ? [...wf.reviews].filter((r) => r.decision === 'RETURNED').sort((a,b) => b.review_id-a.review_id)[0] : null;

  const sourceRequest=sourceDocument&&ctx?.vendor_candidates.some(i=>i.document_id===sourceDocument.document_id&&!i.already_requested)?(id:number)=>{if(!ctx||!latestBasis)return;const list=ctx.vendor_candidates.filter(i=>!i.already_requested&&(!i.requires_original_review||i.document_id===id));setBundleFor({items:list,reviewed:new Set(list.filter(i=>i.document_id===id).map(i=>i.issue_key)),basis:latestBasis});}:undefined;
  const tabTo=(tab:typeof detailTab)=>{setBundleFor(null);onCloseSource?.();onCloseUpload?.();setDetailTab(tab);};
  return <div className="contract-workspace">
    <button className="back" onClick={onBack}><ArrowLeft size={15}/>업무함</button>
    <div className="contract-heading"><div><small className="eyebrow">계약 #{contract.contract_id}</small><div className="title-row"><h1>{contract.title}</h1><Badge tone={wf?.approval_status==='RETURNED'?'red':stage==='DONE'?'green':stage==='APPROVAL'?'blue':'amber'}>{wf?.approval_status==='RETURNED'?'반려':stageLabel}</Badge></div><div className="meta"><span>{maskVendorName(contract.vendor_name,isMaskingEnabled)}</span><span>등록 {contract.created_at.slice(0,10).replace(/-/g,'.')}</span></div></div><div className="contract-amount"><small>계약 금액 · {basis}</small><strong>{Math.round(contract.contract_amount).toLocaleString('ko-KR')}<span>원</span></strong><small>{pay}</small></div><div className="workspace-menu"><button className="icon" aria-label="더 보기 메뉴" aria-expanded={menuOpen} onClick={()=>setMenuOpen(v=>!v)}><MoreHorizontal size={19}/></button>{menuOpen&&<div className="workspace-dropdown">{allMenu.map(m=><button key={m.label} onClick={()=>{setMenuOpen(false);m.onClick();}}>{m.label}</button>)}<small>{infoLine}</small></div>}</div></div>
    {replyMsg&&replyMsg.tone!=='ok'&&<div role="alert" className="story-alert"><span>{replyMsg.text}</span><button className="text-button" onClick={()=>setReplyMsg(null)}>닫기</button></div>}
    {replyMsg?.tone==='ok'&&<div className="toast" role="status"><Check size={18}/><span>{replyMsg.text}</span><button className="icon" aria-label="완료 안내 닫기" onClick={()=>setReplyMsg(null)}><X size={15}/></button></div>}
    {paidBefore&&stage!=='PAYMENT'&&<p className="story-alert" role="status">이미 {paidBefore.recorded_paid_on} 지급 · 다시 지급하지 마세요. 자료 확인·재결재 후 같은 지급인지 재확인합니다.</p>}
    {returned&&<p className="story-alert" role="status">반려 · {returned.actor_name} · {maskForDisplay(returned.note,isMaskingEnabled)}</p>}
    <div className="tabs content-tabs" role="tablist" aria-label="계약 내용">{[['documents','서류',contract.documents.length],['requests','요청 내역',requests.length],['approval','결재',null],['history','처리 기록',null]].map(([key,label,n])=><button key={key} role="tab" className={(sourceDocument||bundleFor?'documents':detailTab)===key?'selected':''} aria-selected={(sourceDocument||bundleFor?'documents':detailTab)===key} onClick={()=>tabTo(key as typeof detailTab)}>{label}{n!==null&&<small>{n}</small>}</button>)}</div>
    {uploadOpen&&canEdit&&onUploadFiles?<DocumentUploadPage contractId={contract.contract_id} onClose={()=>onCloseUpload?.()} onUpload={onUploadFiles} loading={!!uploadLoading} initialTargetType={uploadTarget}/>:bundleFor&&ctx?<BundleRequestPage contract={contract} basis={bundleFor.basis} latest={latestBasis} items={bundleFor.items} reviewed={bundleFor.reviewed} isMaskingEnabled={isMaskingEnabled} onClose={()=>{setBundleFor(null);onCloseSource?.();}} onStale={async()=>{await refreshAll();}} onRecorded={async(recorded)=>{const ok=await refreshAll();setReplyMsg(ok?{tone:'ok',text:`요청 1건 · ${recorded?.bundle?.counts.total??bundleFor.items.length}항목을 기록했습니다.`}:{tone:'warn',text:'요청은 기록했습니다. 최신 목록 조회에 실패했습니다.'});onCloseSource?.();setDetailTab('requests');setTimeout(()=>waitingRef.current?.focus(),0);}}/>:sourceDocument?<DocumentWorkspace key={sourceDocument.document_id} doc={sourceDocument} checks={contract.checks} revision={wf?.revision??0} isMaskingEnabled={isMaskingEnabled} canEdit={canEdit} onClose={()=>onCloseSource?.()} onChanged={onChanged} initialMode={sourceMode} onRequest={sourceRequest} onReissued={doc=>onReissuedDocument?onReissuedDocument(doc):onOpenDocument(doc,'view')} reviewNextLabel={waiting.length?'회신 내역 확인':'검토 후 대표 전달'} onReviewed={()=>{if(activeContract.current!==contract.contract_id)return;onCloseSource?.();setDetailTab(waiting.length?'requests':'approval');}}/>:detailTab==='documents'?<div className="docs-grid"><DocumentTable contract={contract} canEdit={canEdit} onOpen={onOpenDocument} onUpload={onUploadType}/><Surface title="지금 확인할 것" sub="서류 내용과 판독 문제 구분" className="next-panel"><div>{ctx?<RequestChecklist ctx={ctx} isMaskingEnabled={isMaskingEnabled} canEdit={canEdit} onOpenDocumentId={id=>openDocId(id)} onMake={(items,reviewed)=>latestBasis&&setBundleFor({items,reviewed,basis:latestBasis})}/>:ctxError?<p className="story-alert" role="alert">{ctxError}</p>:<p role="status">확인할 항목 조회 중…</p>}{internalIssues.length>0&&<div className="internal-work"><h3>회사 안에서 확인할 것</h3>{internalIssues.map(i=><div key={i.key}><strong>{i.title}</strong><small>{i.kind==='missing'?'사내 작성 서류':i.kind==='reading'?'원문 판독 확인':'계약 기준 확인'}</small>{i.document&&<button className="text-button" onClick={()=>onOpenDocument(i.document!)}>원문 대조<Eye size={14}/></button>}{i.missingType&&canEdit&&<button className="text-button" onClick={()=>onUploadType(i.missingType)}>작성한 파일 올리기<Upload size={14}/></button>}</div>)}</div>}{ctx&&!overview.issues.length&&!ctx.vendor_candidates.length&&<><Badge tone="green">필수 서류 등록 완료</Badge><h3>다음 검토</h3><button className="button primary" onClick={()=>setDetailTab(waiting.length?'requests':'approval')}>{waiting.length?'회신 내역 확인':'결재 내용 보기'}<ChevronRight size={14}/></button></>}{waiting.length>0&&<button className="button" onClick={()=>setDetailTab('requests')}>요청 {waiting.length}건 회신 대기</button>}</div></Surface></div>:detailTab==='requests'?<Surface title="거래처 요청 내역" action={waiting.length>0&&<Badge tone="amber">회신 대기</Badge>}><div ref={waitingRef} tabIndex={-1} className="sr-only">거래처 요청 내역</div>{requests.map(r=>r.bundle?<BundleReplyPanel key={r.request_id} contract={contract} request={r} canEdit={canEdit} isMaskingEnabled={isMaskingEnabled} onOpenItem={openItem} onUploadType={onUploadType} onSaved={afterReply} locked={listStale}/>:<div className="request-record" key={r.request_id}><div className="request-header"><strong>요청 #{r.request_id}</strong><Badge>{r.status==='WAITING_RESPONSE'?'회신 대기':r.status==='RECEIVED'?'받음':'취소'}</Badge><small>이전 방식 기록</small></div><p>{maskForDisplay(fixParticles(r.memo),isMaskingEnabled)}</p>{canEdit&&r.status==='WAITING_RESPONSE'&&<button className="button" onClick={()=>{setResolving({id:r.request_id,status:'RECEIVED'});setResolveNote('고친 서류 받음');}}>답 받음</button>}</div>)}{!requests.length&&<div className="empty">기록된 요청이 없습니다.</div>}{followError&&<p role="alert" className="story-alert">{followError}</p>}{resolving&&<div className="story-form form-fields"><label>회신 기록 메모<input value={resolveNote} onChange={e=>setResolveNote(e.target.value)}/></label><button className="button primary" disabled={!resolveNote.trim()} onClick={()=>void submitResolve()}>회신 기록</button></div>}</Surface>:detailTab==='history'?<ActivityTimeline contractId={contract.contract_id} revision={wf?.revision} fingerprint={wf?.fingerprint} masked={isMaskingEnabled}/>:stage==='DONE'?<Surface title="완료 · 기록 보관"><div className="story-complete"><CheckCircle2 size={42}/><h2>계약 전체 지급 기록 완료</h2><p>{payment?.paid_on} · {payment?.method==='TRANSFER'?'계좌이체':'기타'} · {payment?.note}</p>{brief&&<button className="button" onClick={copyBrief}><Copy size={15}/>{copied?'복사 완료':'요약 복사'}</button>}</div><ActivityTimeline contractId={contract.contract_id} revision={wf?.revision} fingerprint={wf?.fingerprint} masked={isMaskingEnabled} compact/></Surface>:stage==='PAYMENT'?<div className="docs-grid"><Surface title={paidBefore?'같은 지급 재확인':'계약 전체 지급 기록'} sub="실제 송금 기능은 없음"><div className="story-form form-fields">{paidBefore?<><p className="story-alert">이미 {paidBefore.recorded_paid_on} 지급 · 다시 지급하지 마세요.</p>{paidBefore.reconfirmation_allowed?<><label>재확인 메모<textarea rows={3} value={reNote} maxLength={2000} onChange={e=>setReNote(e.target.value)} placeholder="기존 지급을 확인한 사유 10자 이상"/></label><label className="check-label"><input type="checkbox" checked={sameAck} onChange={e=>setSameAck(e.target.checked)}/><span>기존 지급 내역이 현재 자료와 일치함을 확인</span></label></>:<p className="story-alert">{BLOCKED_KO[paidBefore.blocked_reason||'']||'기존 지급을 재확인할 수 없습니다.'}</p>}</>:<><label>지급일<input type="date" value={paidOn} max={today()} onChange={e=>setPaidOn(e.target.value)}/></label><label>지급 방법<select value={payMethod} onChange={e=>setPayMethod(e.target.value as typeof payMethod)}><option value="TRANSFER">계좌이체</option><option value="OTHER">기타</option></select></label><label>메모<input value={payNote} maxLength={500} onChange={e=>setPayNote(e.target.value)}/></label><p>모든 회차의 지급을 마친 뒤 계약 전체 완료로 기록합니다.</p></>}{payError&&<p className="story-alert" role="alert">{payError}</p>}</div><div className="panel-footer"><span>{paidBefore?'새 지급 기록은 만들지 않음':'결재 완료 · 실제 지급 사실만 기록'}</span>{(canEdit||representative)&&(paidBefore?<button className="button primary" disabled={payBusy||!paidBefore.reconfirmation_allowed||!sameAck||reNote.trim().length<10} onClick={()=>void reconfirm()}>같은 지급으로 재확인</button>:<button className="button primary" disabled={payBusy||!paidOn||paidOn>today()} onClick={()=>void recordPayment()}>계약 전체 지급 완료로 기록</button>)}</div></Surface><Surface title="지급 대상" className="next-panel"><div><h3>{won(contract.contract_amount)}</h3><p>{maskVendorName(contract.vendor_name,isMaskingEnabled)}<br/>{pay} · {basis}</p><Badge tone="green">결재 완료</Badge></div></Surface></div>:!representative&&!myApprovalTurn&&waitingFor==='representative'&&stage==='APPROVAL'?<div className="docs-grid"><DocumentTable contract={contract} canEdit={canEdit} onOpen={onOpenDocument} onUpload={onUploadType}/><Surface title="다음 차례" className="next-panel"><div><Badge tone="blue">대표 결재</Badge><h3>대표에게 검토 내용 전달</h3><p>현재 서류 {contract.summary.submitted_document_count}/{contract.summary.required_document_count}종<br/>적용된 자동 검사 {contract.checks.filter(c=>c.status==='PASS').length}개 일치<br/>{overview.issues.length?'남은 확인 '+overview.issues.length+'건':'국세청 진위 조회는 별도 확인'}</p><button className="button" disabled={!brief} onClick={copyBrief}><Copy size={15}/>{copied?'복사 완료':'전달 문장 복사'}</button><details className="record-memo"><summary>전달 문장 보기</summary><p>{brief||'요약 조회 중…'}</p></details></div></Surface></div>:<ApprovalPanel contract={contract} onChanged={onChanged} masked={isMaskingEnabled} requests={requests} onOpenDocumentId={id=>openDocId(id)}/>}
    {showAssign&&<AssignmentPanel contract={contract}/>}<AssignmentPanel contract={contract} hideWhenEmpty/>
  </div>;
};
