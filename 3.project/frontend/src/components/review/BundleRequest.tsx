import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ContractDetail, DocumentType } from '../../types';
import { bundleApi } from '../../features/requests/api';
import { Basis, BundleCandidate, BundledRequest, BundleItem, sameBasis, currentDocumentFor, itemArrived, docName, buildText } from '../../features/requests/model';
import { ContactMethod, CONTACT_KO, CONTACT_VIA } from '../../api/followUp';
import { Badge, Surface } from '../ui/Surface';
import { isUnverifiedBusinessStatus } from '../../utils/reviewSummary';
import { fixParticles } from '../../utils/korean';
import { seoulToday } from '../../utils/date';
import { maskBusinessNumber, maskResidentNumber, maskVendorName } from '../../utils/masking';
import { Copy, Eye, Upload, Send } from 'lucide-react';

const mask = (t: string, on: boolean) => (on ? maskResidentNumber(maskBusinessNumber(t)) : t);
const newKey = () => (typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`);

/* ---------- 한 번에 요청하기 ---------- */
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
  onBusyChange?: (busy:boolean)=>void;
}

export const BundleRequestPage: React.FC<RequestPageProps> = ({ contract, basis, latest, items:availableItems, reviewed, isMaskingEnabled, onClose, onRecorded, onStale,onBusyChange }) => {
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
  useEffect(()=>{onBusyChange?.(busy);return()=>onBusyChange?.(false);},[busy,onBusyChange]);
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
    </div><div className="panel-footer"><span>외부에서 요청한 뒤 기록합니다.</span><div className="story-button-row"><button className="button" disabled={busy} onClick={onClose}>취소</button><button className="button" onClick={()=>void copy()}><Copy size={15}/>문구 복사</button><button className="button primary" disabled={busy||stale||changed||!items.length||!memo.trim()||memoTooLong} onClick={()=>void record()}><Send size={15}/>{busy?'기록 중…':`요청했어요 · ${items.length}건 기록`}</button></div></div>
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
  const [correcting,setCorrecting]=useState<BundleItem|null>(null);
  const [correctStatus,setCorrectStatus]=useState<BundleItem['status']>('WAITING_RESPONSE');
  const [correctNote,setCorrectNote]=useState('');
  const basis = `${b.request_revision}|${contract.workflow?.revision}|${contract.workflow?.fingerprint}`;
  useEffect(() => { setGot(new Set()); setNote(''); setCorrecting(null);setCorrectNote(''); }, [basis]);
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
  const correct=async()=>{
    if(!correcting)return;setBusy(true);let saved=false,error:string|undefined;
    try{await bundleApi.correct(contract.contract_id,request.request_id,{revision:contract.workflow?.revision,fingerprint:contract.workflow?.fingerprint,request_revision:b.request_revision,items:[{item_id:correcting.item_id,status:correctStatus,note:correctNote.trim()}]});saved=true;setCorrecting(null);setCorrectNote('');}
    catch(e){error=e instanceof Error?e.message:'정정하지 못했습니다.';}
    try{await onSaved(saved,error);}finally{setBusy(false);}
  };
  return <article className="request-record">
    {b.counts.received>0&&<p className="focus-policy">회신을 받은 기록과 원문 확인은 별도입니다. 받은 서류의 ‘원문 대조’를 열어 해당 항목을 다시 확인하세요. 남은 회신은 계속 대기로 유지됩니다.</p>}
    <div className="request-header"><div><strong>요청 #{request.request_id}</strong><Badge tone={b.counts.waiting ? 'amber' : b.counts.cancelled === b.counts.total ? 'gray' : 'green'}>{`${b.counts.total}건 요청 · ${b.counts.received}건 받음 · ${b.counts.waiting}건 대기`}</Badge>{b.counts.cancelled > 0 && <Badge>취소 {b.counts.cancelled}</Badge>}</div><small>{CONTACT_VIA[request.contact_method]} · {request.requested_on}{request.due_on ? ` · 기한 ${request.due_on}${late ? ' 지남' : ''}` : ''}</small></div>
    <div className="table-wrap"><table className="reply-table"><thead><tr><th>선택</th><th>요청 항목</th><th>회신</th><th>자동 검사</th><th /></tr></thead><tbody>{b.items.map((item) => {
      const logicalId = currentDocumentFor(item,contract.documents);
      const doc = logicalId != null ? contract.documents.find((d) => d.document_id === logicalId) : undefined;
      const checks = doc ? contract.checks.filter((c) => c.field === String(doc.document_id) && !isUnverifiedBusinessStatus(c)) : [];
      const checkLabel = !doc || !checks.length ? '—' : checks.some((c) => c.status === 'FAIL') ? '불일치' : checks.some((c) => c.status !== 'PASS') ? '확인 필요' : '일치';
      return <tr key={item.item_id}><td>{<input disabled={item.status!=='WAITING_RESPONSE'||!canEdit} type="checkbox" aria-label={`${docName(item)} 선택`} checked={got.has(item.item_id)} onChange={() => setGot((s) => { const n=new Set(s);if(n.has(item.item_id))n.delete(item.item_id);else n.add(item.item_id);return n; })}/>}</td><td><strong>{docName(item)}</strong><small className="sub">{mask(fixParticles(item.reason),isMaskingEnabled)}</small>{arrived(item) && item.status === 'WAITING_RESPONSE' && <small className="sub text-emerald-700">서류 도착 · 받은 항목만 체크</small>}{item.resolution_note && <small className="sub">{mask(fixParticles(item.resolution_note),isMaskingEnabled)}</small>}</td><td><Badge tone={item.status === 'RECEIVED' ? 'green' : item.status === 'CANCELLED' ? 'gray' : 'amber'}>{item.status === 'RECEIVED' ? '받음' : item.status === 'CANCELLED' ? '취소' : '대기'}</Badge></td><td><Badge tone={checkLabel === '일치' ? 'green' : checkLabel === '불일치' ? 'red' : checkLabel === '확인 필요' ? 'amber' : 'gray'}>{checkLabel}</Badge></td><td><div className="row-actions">{doc && <button className="text-button" onClick={() => onOpenItem(item,'view')}><Eye size={14}/>원문 대조</button>}{item.status === 'WAITING_RESPONSE' && canEdit && (item.document_id != null && !arrived(item) ? <button className="text-button" onClick={() => onOpenItem(item,'reissue')}><Upload size={14}/>고친 본 올리기</button> : !doc && <button className="text-button" onClick={() => onUploadType(item.document_type ?? undefined)}><Upload size={14}/>파일 올리기</button>)}</div></td></tr>;
    })}</tbody></table></div>
    <div className="panel-footer"><span>수령 기록과 자동 검사 결과는 별도</span>{canEdit&&b.items.some(i=>i.status!=='WAITING_RESPONSE')&&<div className="row-actions">{b.items.filter(i=>i.status!=='WAITING_RESPONSE').map(item=><button key={item.item_id} className="text-button" disabled={busy||locked} onClick={()=>{setCorrecting(item);setCorrectStatus('WAITING_RESPONSE');setCorrectNote('');}}>{docName(item)} 회신 기록 정정</button>)}</div>}</div>
    {correcting&&<div className="reply-actions"><strong>{docName(correcting)} 회신 기록 정정</strong><label>정정 상태<select value={correctStatus} onChange={e=>setCorrectStatus(e.target.value as BundleItem['status'])}><option value="WAITING_RESPONSE">회신 대기로 되돌리기</option><option value="RECEIVED">받음</option><option value="CANCELLED">요청 취소</option></select></label><label>정정 사유<input maxLength={2000} value={correctNote} onChange={e=>setCorrectNote(e.target.value)} placeholder="정정 사유 3자 이상"/></label><span>이전 기록과 정정 사유는 처리 기록에 보존됩니다.</span><div><button className="button" disabled={busy} onClick={()=>setCorrecting(null)}>닫기</button><button className="button primary" disabled={busy||locked||correctNote.trim().length<3} onClick={()=>void correct()}>회신 정정 저장</button></div></div>}
    {canEdit && waitingItems.length > 0 && <div className="reply-actions"><label>받은 내용 또는 취소 이유<input value={note} maxLength={2000} onChange={(e) => setNote(e.target.value)} placeholder="받은 내용 또는 취소 이유"/></label><div><button className="button" disabled={busy || locked || !got.size || !note.trim()} onClick={() => void save('CANCELLED')}>선택 {got.size}건 요청 취소</button><button className="button primary" disabled={busy || locked || !got.size || !note.trim()} onClick={() => void save('RECEIVED')}>{busy ? '기록 중…' : `받은 ${got.size}건 기록`}</button></div></div>}
  </article>;
};
