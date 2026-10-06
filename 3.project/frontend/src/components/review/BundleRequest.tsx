import { DOCUMENT_LABEL as DOCUMENT_TYPE_KO } from '../../utils/documentLabels';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ContractDetail, DocumentType } from '../../types';
import { requestJson } from '../../api/client';
import { ContactMethod, CONTACT_KO, CONTACT_VIA, ResubmissionRequest } from '../../api/followUp';
import { Badge, Surface } from '../ui/Surface';
import { isUnverifiedBusinessStatus } from '../../utils/reviewSummary';
import { fixParticles, josa } from '../../utils/korean';
import { seoulToday } from '../../utils/date';
import { maskBusinessNumber, maskResidentNumber, maskVendorName } from '../../utils/masking';
import { Copy, Eye, Upload, Send } from 'lucide-react';

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
export function currentDocumentFor(item: { issue_key: string; document_id: number | null; document_type?: DocumentType | null }, docs: { document_id: number; document_type?: DocumentType; version?: { logical_document_id: number; is_current: boolean } | null }[]): number | null {
  if (item.issue_key.startsWith('missing:') && item.document_type) {
    const matches = docs.filter((d) => d.document_type === item.document_type && d.version?.is_current !== false);
    return matches.length === 1 ? matches[0].document_id : null;
  }
  const m = /^document:(\d+)$/.exec(item.issue_key);
  if (m) {
    const logical = Number(m[1]);
    const cur = docs.find((d) => (d.version?.logical_document_id ?? d.document_id) === logical && d.version?.is_current !== false);
    if (cur) return cur.document_id;
  }
  return item.document_id != null && docs.some((d) => d.document_id === item.document_id) ? item.document_id : null;
}

/** 요청 뒤에 그 서류가 올라왔는지: 빠진 서류는 그 종류가 생겼는지, 서류 보완은 같은 논리 문서의 현재 본이 바뀌었는지 */
export function itemArrived(i: { issue_key: string; document_id: number | null; document_type: DocumentType | null }, docs: { document_id: number; document_type: DocumentType; version?: { logical_document_id: number; is_current: boolean } | null }[]): boolean {
  if (i.issue_key.startsWith('missing:')) return docs.some((d) => d.document_type === i.document_type && d.version?.is_current !== false);
  const cur = currentDocumentFor(i, docs);
  return cur != null && i.document_id != null && cur !== i.document_id;
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


  if(!open.length&&!waitingAlready.length)return null;
  return <><Badge tone="amber">거래처 보완 {open.length}건</Badge><h3>{open.some(c=>c.document_id)?'빠진 서류와 서류 정정':'거래처에 한 번에 요청'}</h3>
    {open.map(c=><div key={c.issue_key}><div className="request-choice"><label className="check-label"><input type="checkbox" checked={picked.has(c.issue_key)} disabled={!canEdit||c.requires_original_review&&!reviewed.has(c.issue_key)} onChange={()=>setPicked(s=>toggle(s,c.issue_key))}/><span>{docName(c)}<small>{c.document_id?'원문 확인 후 선택':'아직 등록되지 않음'}</small></span></label><button className="icon" aria-label={`${docName(c)} 사유 보기`} aria-expanded={expanded===c.issue_key} onClick={()=>setExpanded(expanded===c.issue_key?null:c.issue_key)}>ⓘ</button></div>{expanded===c.issue_key&&<p>{mask(fixParticles(c.reason),isMaskingEnabled)}</p>}</div>)}
    {open.filter(c=>c.document_id!=null).map(c=><button key={c.issue_key} className="button" onClick={()=>onOpenDocumentId(c.document_id!)}>{docName(c)} 원문 확인<Eye size={14}/></button>)}
    {canEdit&&open.length>0&&<button className="button primary" disabled={!chosen.length} onClick={()=>onMake(chosen,reviewed)}>{chosen.length}건 요청 작성</button>}{waitingAlready.length>0&&<small>{waitingAlready.length}항목은 이미 요청해 회신 대기 중입니다.</small>}
  </>;
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

interface RequestPageProps {
  contract: ContractDetail;
  /** 선택·원문 확인을 받은 기준 */
  basis: Basis;
  /** 지금 불러온 최신 기준 */
  latest: Basis | null;
  items: BundleCandidate[];
  reviewed: Set<string>;
  isMaskingEnabled: boolean;
  onClose: () => void;
  onRecorded: (recorded?: BundledRequest) => Promise<void>;
  onStale: () => Promise<void>;
}

export const BundleRequestPage: React.FC<RequestPageProps> = ({ contract, basis, latest, items:availableItems, reviewed, isMaskingEnabled, onClose, onRecorded, onStale }) => {
  const alive=useRef(true);useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
  const [pickedItems,setPickedItems]=useState(()=>new Set(availableItems.map(i=>i.issue_key)));
  const items=availableItems.filter(i=>pickedItems.has(i.issue_key));
  const [due, setDue] = useState('');
  const [long, setLong] = useState(true);
  const draft = useMemo(() => buildText(contract, items, long)+(due?'\n\n회신 기한: '+due:''), [contract, items, long,due]);
  const [text, setText] = useState(draft);
  useEffect(() => setText(draft), [draft]);
  const [copied, setCopied] = useState('');
  const [method, setMethod] = useState<ContactMethod>('EMAIL');
  const [memo, setMemo] = useState(`${items.map(docName).join(', ')} 요청`);
  const defaultMemo=items.map(docName).join(', ')+' 요청';
  const previousMemo=useRef(defaultMemo);
  useEffect(()=>{setMemo(old=>old===previousMemo.current?defaultMemo:old);previousMemo.current=defaultMemo;},[defaultMemo]);
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
      const recorded=await bundleApi.create(contract.contract_id, {
        revision: basis.revision, fingerprint: basis.fingerprint, idempotency_key: keyRef.current,
        contact_method: method, due_on: due || null, memo: memo.trim(),
        items: items.map((c) => ({ issue_key: c.issue_key, reviewed_original: c.requires_original_review ? reviewed.has(c.issue_key) : false })),
      });
      if(!alive.current)return;
      await onRecorded(recorded);
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


  const itemSummary=(item:BundleCandidate)=>{
    if(item.issue_key.startsWith('missing:'))return '미제출';
    const checks=(contract.checks??[]).filter(c=>c.field===String(item.document_id)&&c.status==='FAIL'&&c.expected&&c.actual);
    const first=checks[0];
    return first?`기준 ${mask(first.expected!,isMaskingEnabled)} / 저장 ${mask(first.actual!,isMaskingEnabled)}${checks.length>1?` · 외 ${checks.length-1}건`:''}`:mask(fixParticles(item.reason),isMaskingEnabled);
  };
  return <Surface title="거래처 요청 작성" sub="선택한 항목을 문구 하나로" className="story-request">
    <div className="story-form"><div className="request-form"><div><small>받는 곳</small><strong>{maskVendorName(contract.vendor_name,isMaskingEnabled)}</strong></div><label>연락 방법<select value={method} onChange={e=>setMethod(e.target.value as ContactMethod)}>{(Object.keys(CONTACT_KO) as ContactMethod[]).map(m=><option key={m} value={m}>{CONTACT_KO[m]}</option>)}</select></label><label>회신 기한<input type="date" value={due} min={seoulToday()} onChange={e=>setDue(e.target.value)}/></label></div>
      <div className="request-items"><h3>요청 항목 <small>{items.length}건</small></h3>{availableItems.map(item=><div className="story-request-item" key={item.issue_key}><input type="checkbox" aria-label={`${docName(item)} 요청 선택`} checked={pickedItems.has(item.issue_key)} disabled={busy||changed} onChange={()=>setPickedItems(old=>{const next=new Set(old);if(next.has(item.issue_key))next.delete(item.issue_key);else next.add(item.issue_key);return next;})}/><strong>{docName(item)}{item.requires_original_review?' 정정':''}</strong><small title={mask(fixParticles(item.reason),isMaskingEnabled)}>{itemSummary(item)}</small></div>)}</div>
      <div className="request-text-heading"><label className="field-label" htmlFor="bundle-text">보낼 문구</label><div className="tabs"><button className={!long?'selected':''} onClick={()=>setLong(false)}>짧게</button><button className={long?'selected':''} onClick={()=>setLong(true)}>자세히</button></div></div><textarea id="bundle-text" rows={7} value={text} onChange={e=>setText(e.target.value)}/>
      {isMaskingEnabled&&<small>보낼 문구에는 실제 거래처 이름이 들어갑니다.</small>}
      <details className="record-memo"><summary>기록 메모</summary><label>기록 메모<input value={memo} maxLength={2000} onChange={e=>setMemo(e.target.value)}/></label></details>
      {copied&&<p role="status">{copied}</p>}{memoTooLong&&<p className="story-alert" role="alert">메모는 2,000자까지입니다.</p>}{changed&&<p className="story-alert" role="alert">고른 뒤 자료가 바뀌었습니다. 최신 목록에서 다시 고르세요.<button className="text-button" onClick={()=>void onStale().then(onClose)}>닫고 다시 고르기</button></p>}{error&&<p className="story-alert" role="alert">{error}{stale&&<button className="text-button" onClick={()=>void onStale().then(onClose)}>최신 자료 불러오기</button>}</p>}
    </div><div className="panel-footer"><span>외부에서 요청한 뒤 기록합니다.</span><div className="story-button-row"><button className="button" onClick={onClose}>취소</button><button className="button" onClick={()=>void copy()}><Copy size={15}/>문구 복사</button><button className="button primary" disabled={busy||stale||changed||!items.length||!memo.trim()||memoTooLong} onClick={()=>void record()}><Send size={15}/>{busy?'기록 중…':`요청했어요 · ${items.length}건 기록`}</button></div></div>
  </Surface>;
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
  /** 저장 결과를 계약 화면에 알린다. 계약 화면이 다시 불러오고 안내를 남긴다 */
  onSaved: (saved: boolean, error?: string) => Promise<void>;
  /** 마지막 재조회 실패로 이전 선택으로 저장하면 안 될 때 */
  locked?: boolean;
}

export const BundleReplyPanel: React.FC<ReplyProps> = ({ contract, request, canEdit, isMaskingEnabled, onOpenItem, onUploadType, onSaved, locked = false }) => {
  const b = request.bundle!;
  const waitingItems = b.items.filter((i) => i.status === 'WAITING_RESPONSE');
  const [got, setGot] = useState<Set<number>>(new Set());
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  // 요청·자료가 바뀌면 이전 체크·메모는 쓰지 않는다(오류 안내는 계약 화면이 보관한다)
  const basis = `${b.request_revision}|${contract.workflow?.revision}|${contract.workflow?.fingerprint}`;
  useEffect(() => { setGot(new Set()); setNote(''); }, [basis]);
  const late = request.due_on && request.due_on < seoulToday();
  const arrived = (i: BundleItem) => itemArrived(i, contract.documents);
  const save = async (status: 'RECEIVED' | 'CANCELLED') => {
    setBusy(true);
    let saved = false; let error: string | undefined;
    try {
      await bundleApi.resolve(contract.contract_id, request.request_id, {
        revision: contract.workflow?.revision, fingerprint: contract.workflow?.fingerprint, request_revision: b.request_revision,
        items: [...got].map((id) => ({ item_id: id, status, note: note.trim() })),
      });
      saved = true;
    } catch (e) {
      error = e instanceof Error ? e.message : '기록하지 못했습니다.';
    }
    try { await onSaved(saved, error); } finally { setBusy(false); }
  };
  return <article className="request-record">
    <div className="request-header"><div><strong>요청 #{request.request_id}</strong><Badge tone={b.counts.waiting ? 'amber' : b.counts.cancelled === b.counts.total ? 'gray' : 'green'}>{`${b.counts.total}건 요청 · ${b.counts.received}건 받음 · ${b.counts.waiting}건 대기`}</Badge>{b.counts.cancelled > 0 && <Badge>취소 {b.counts.cancelled}</Badge>}</div><small>{CONTACT_VIA[request.contact_method]} · {request.requested_on}{request.due_on ? ` · 기한 ${request.due_on}${late ? ' 지남' : ''}` : ''}</small></div>
    <div className="table-wrap"><table className="reply-table"><thead><tr><th>선택</th><th>요청 항목</th><th>회신</th><th>자동 검사</th><th /></tr></thead><tbody>{b.items.map((item) => {
      const logicalId = currentDocumentFor(item,contract.documents);
      const doc = logicalId != null ? contract.documents.find((d) => d.document_id === logicalId) : undefined;
      const checks = doc ? contract.checks.filter((c) => c.field === String(doc.document_id) && !isUnverifiedBusinessStatus(c)) : [];
      const checkLabel = !doc || !checks.length ? '—' : checks.some((c) => c.status === 'FAIL') ? '불일치' : checks.some((c) => c.status !== 'PASS') ? '확인 필요' : '일치';
      return <tr key={item.item_id}><td>{<input disabled={item.status!=='WAITING_RESPONSE'||!canEdit} type="checkbox" aria-label={`${docName(item)} 선택`} checked={got.has(item.item_id)} onChange={() => setGot((s) => { const n=new Set(s);if(n.has(item.item_id))n.delete(item.item_id);else n.add(item.item_id);return n; })}/>}</td><td><strong>{docName(item)}</strong><small className="sub">{mask(fixParticles(item.reason),isMaskingEnabled)}</small>{arrived(item) && item.status === 'WAITING_RESPONSE' && <small className="sub text-emerald-700">서류 도착 · 받은 항목만 체크</small>}{item.resolution_note && <small className="sub">{mask(fixParticles(item.resolution_note),isMaskingEnabled)}</small>}</td><td><Badge tone={item.status === 'RECEIVED' ? 'green' : item.status === 'CANCELLED' ? 'gray' : 'amber'}>{item.status === 'RECEIVED' ? '받음' : item.status === 'CANCELLED' ? '취소' : '대기'}</Badge></td><td><Badge tone={checkLabel === '일치' ? 'green' : checkLabel === '불일치' ? 'red' : 'gray'}>{checkLabel}</Badge></td><td><div className="row-actions">{doc && <button className="text-button" onClick={() => onOpenItem(item,'view')}><Eye size={14}/>원문 대조</button>}{item.status === 'WAITING_RESPONSE' && canEdit && (item.document_id != null && !arrived(item) ? <button className="text-button" onClick={() => onOpenItem(item,'reissue')}><Upload size={14}/>고친 본 올리기</button> : !doc && <button className="text-button" onClick={() => onUploadType(item.document_type ?? undefined)}><Upload size={14}/>파일 올리기</button>)}</div></td></tr>;
    })}</tbody></table></div>
    <div className="panel-footer"><span>수령 기록과 자동 검사 결과는 별도</span></div>
    {canEdit && waitingItems.length > 0 && <div className="reply-actions"><label>받은 내용 또는 취소 이유<input value={note} maxLength={2000} onChange={(e) => setNote(e.target.value)} placeholder="받은 내용 또는 취소 이유"/></label><div><button className="button" disabled={busy || locked || !got.size || !note.trim()} onClick={() => void save('CANCELLED')}>선택 {got.size}건 요청 취소</button><button className="button primary" disabled={busy || locked || !got.size || !note.trim()} onClick={() => void save('RECEIVED')}>{busy ? '기록 중…' : `받은 ${got.size}건 기록`}</button></div></div>}
  </article>;
};
