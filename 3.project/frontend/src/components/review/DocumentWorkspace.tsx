import { DOCUMENT_LABEL as DOCUMENT_TYPE_KO } from '../../utils/documentLabels';
import React, { useEffect, useMemo, useState } from 'react';
import { fieldsForDocument } from '../../utils/documentFields';
import { josa } from '../../utils/korean';
import { maskForDisplay } from './ContractStageView';
import { AnalysisFields, DocumentResponse, ValidationCheck } from '../../types';
import { api, requestJson, downloadProtected } from '../../api/client';
import { isUnverifiedBusinessStatus } from '../../utils/reviewSummary';
import { maskBusinessNumber, maskAccountNumber, maskVendorName } from '../../utils/masking';
import { Check, Download, ChevronLeft, ChevronRight, Loader2, Upload, ArrowUpRight } from 'lucide-react';
import { kst } from './ActivityTimeline';
import { Badge, Surface } from '../ui/Surface';

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
  /** 'reissue'면 고친 본 올리기 칸을 펼친 채로 연다 */
  onRequest?: (documentId: number) => void;
  onReviewed?: () => void;
  reviewNextLabel?:string;
  onReissued?: (doc: DocumentResponse) => void;
  initialMode?: 'view' | 'reissue';
}

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
const fieldChecks = (key: string, checks: ValidationCheck[]) => checks.filter((c) =>
  c.rule_id === 'BUSINESS_NO_MATCH' && key === 'business_registration_no' ||
  c.rule_id === 'AMOUNT_COMPONENTS' && AMOUNT_KEYS.has(key) ||
  c.rule_id.startsWith('AMOUNT_MATCH_') && key === (c.message.includes('공급가액 기준') ? 'supply_amount' : 'total_amount') ||
  c.rule_id === 'PAYMENT_SCOPE' && key === 'amount_scope');

export const DocumentWorkspace: React.FC<Props> = ({ doc, checks, revision, isMaskingEnabled, canEdit, onClose, onChanged, initialMode = 'view', onRequest, onReviewed, onReissued,reviewNextLabel }) => {
  const escRef = React.useRef<() => void>(onClose);
  const editable = canEdit && doc.version?.is_current !== false;
  const [sourcePane, setSourcePane] = useState<'original' | 'fields'>(initialMode === 'reissue' ? 'fields' : 'original');
  const [textError,setTextError] = useState('');
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<AnalysisFields>(doc.analysis.fields);
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  useEffect(() => { setEditing(false); setDraft(doc.analysis.fields); setNote(''); setSaveError(''); }, [doc.document_id, revision]);
  const [cmp, setCmp] = useState<Comparison | null>(null);
  const [cmpError, setCmpError] = useState(false);
  const [cmpKey, setCmpKey] = useState(0);
  const [reissueOpen, setReissueOpen] = useState(initialMode === 'reissue');
  const [reissueFile, setReissueFile] = useState<File | null>(null);
  const [reissueNote, setReissueNote] = useState('');
  const [reissuing, setReissuing] = useState(false);
  const [reissueError, setReissueError] = useState('');
  // 파일 입력은 다시 열 때마다 새로 만든다. 닫으면 고른 파일·사유·오류를 모두 비운다(닫은 폼의 파일이 몰래 전송되지 않게)
  const [fileInputKey, setFileInputKey] = useState(0);
  const resetReissue = () => { setReissueFile(null); setReissueNote(''); setReissueError(''); setFileInputKey((k) => k + 1); };
  // 모드 전환 포커스: 폼이 열리면 첫 입력, 닫히면 그 폼을 연 버튼으로
  const reissueRef = React.useRef<HTMLDivElement>(null);
  const editRef = React.useRef<HTMLDivElement>(null);
  const editBtnRef = React.useRef<HTMLButtonElement>(null);
  const reissueBtnRef = React.useRef<HTMLButtonElement>(null);
  const returnFocus = React.useRef<'edit' | 'reissue' | null>(null);
  const openReissue = () => { resetReissue(); setReissueOpen(true); };
  const closeReissue = () => { resetReissue(); setReissueOpen(false); returnFocus.current = 'reissue'; };
  useEffect(() => {
    const t = setTimeout(() => {
      if (reissueOpen) {
        reissueRef.current?.scrollIntoView({ block: 'nearest' });
        reissueRef.current?.querySelector<HTMLElement>('input[type="file"]')?.focus();
      } else if (editing) {
        editRef.current?.querySelector<HTMLElement>('input, select, textarea')?.focus();
      } else if (returnFocus.current) {
        (returnFocus.current === 'edit' ? editBtnRef : reissueBtnRef).current?.focus();
        returnFocus.current = null;
      }
    }, 30);
    return () => clearTimeout(t);
  }, [reissueOpen, editing]);
  escRef.current = reissueOpen ? closeReissue : editing ? () => { returnFocus.current = 'edit'; setEditing(false); setDraft(doc.analysis.fields); } : onClose;
  const versionNo = doc.version?.version_number ?? 1;
  useEffect(() => { resetReissue(); }, [doc.document_id]);
  // 비교는 저장된 현재 값을 기준으로 하므로 문서·revision·저장 뒤마다 다시 조회한다. 실패를 '같음'으로 보이지 않는다
  useEffect(() => {
    setCmp(null); setCmpError(false);
    if (versionNo < 2) return;
    const controller = new AbortController();
    requestJson<Comparison>(`/api/documents/${doc.document_id}/compare`, { signal: controller.signal })
      .then((r) => { if (!controller.signal.aborted) setCmp(r); })
      .catch(() => { if (!controller.signal.aborted) setCmpError(true); });
    return () => controller.abort();
  }, [doc.document_id, versionNo, revision, cmpKey]);
  const reissue = async () => {
    if (!reissueFile) return;
    setReissuing(true); setReissueError('');
    try {
      const result = await api.reissueDocument(doc.contract_id, reissueFile, doc.document_id, revision, reissueNote.trim());
      await onChanged();
      setReissueOpen(false); resetReissue();
      if (result[0] && onReissued) onReissued(result[0]); else onClose();
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
      returnFocus.current = 'edit';
      setEditing(false);
      setCmpKey((k) => k + 1);
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
  const passed = docChecks.filter((c) => c.status === 'PASS');
  // 같은 논리 문서의 이전 본 목록(조회만). 같은 종류의 별도 서류는 여기에 섞이지 않는다
  const [versions, setVersions] = useState<{ document_id: number; version_number: number; is_current: boolean; file_name?: string; change_note?: string | null; actor_name?: string | null; uploaded_at?: string | null }[] | null>(null);
  useEffect(() => {
    setVersions(null);
    if ((doc.version?.version_number ?? 1) < 2) return;
    const controller = new AbortController();
    requestJson<{ versions: NonNullable<typeof versions> }>(`/api/documents/${doc.document_id}/versions`, { signal: controller.signal })
      .then((r) => { if (!controller.signal.aborted) setVersions(r.versions); }).catch(() => undefined);
    return () => controller.abort();
  }, [doc.document_id, doc.version?.version_number]);

  useEffect(() => {
    const controller = new AbortController();
    setProv(null); setProvError('');
    requestJson<Provenance>(`/api/documents/${doc.document_id}/provenance`, { signal: controller.signal })
      .then((p) => { if (!controller.signal.aborted) setProv(p); })
      .catch((e) => { if (!controller.signal.aborted) setProvError(e.message); });
    return () => controller.abort();
  }, [doc.document_id, revision, cmpKey]);

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
    setText(''); setTextError('');
    if (!doc.file_available || visual) return;
    const controller = new AbortController();
    requestJson<{ text: string }>(`/api/documents/${doc.document_id}/text-preview?masked=${isMaskingEnabled}`, { signal: controller.signal })
      .then((v) => setText(v.text)).catch((e) => { if (!controller.signal.aborted) setTextError(e.message); });
    return () => controller.abort();
  }, [doc.document_id, doc.file_available, visual, isMaskingEnabled]);

  const fieldPriority=['total_amount','supply_amount','tax_amount','company_name','business_registration_no','account_number','bank_name','amount_scope','issue_date'];
  const rows = [...fieldsForDocument(doc.document_type)].sort((a,b)=>fieldPriority.indexOf(a.key)-fieldPriority.indexOf(b.key));
  const anchor: Anchor | undefined = selected ? prov?.fields[selected]?.evidence?.[0] : undefined;
  // 좌표는 백엔드가 원본 해시까지 확인한 경우에만 온다. 없으면 쪽·줄 안내만 한다.
  const validBox = (b?: BBox | null): b is BBox => !!b && (b.page ?? 1) === page + 1 && [b.x, b.y, b.width, b.height].every((v) => typeof v === 'number' && v >= 0 && v <= 1);
  const boxes: BBox[] = (anchor?.bboxes?.length ? anchor.bboxes : anchor?.bbox ? [anchor.bbox] : []).filter(validBox);

  const pick = (key: string) => {
    setSelected(key);
    const a = prov?.fields[key]?.evidence?.[0];
    if (a?.page && isPdf) setPage(a.page - 1);
    if (window.innerWidth <= 700) setSourcePane('original');
  };

  const quoteShown = anchor && !isMaskingEnabled ? anchor.quote : '';
  const highlightedText = useMemo(() => {
    if (!text || !anchor?.quote || isMaskingEnabled) return null;
    const i = text.indexOf(anchor.quote);
    if (i < 0) return null;
    return [text.slice(0, i), text.slice(i, i + anchor.quote.length), text.slice(i + anchor.quote.length)];
  }, [text, anchor, isMaskingEnabled]);


  const [originalAck,setOriginalAck]=useState(false);
  useEffect(()=>{setOriginalAck(false);},[doc.document_id,revision]);
  useEffect(()=>{const handler=(e:KeyboardEvent)=>{if(e.key==='Escape')escRef.current();};document.addEventListener('keydown',handler);return()=>document.removeEventListener('keydown',handler);},[]);
  const visibleRows=rows.filter(r=>{const v=prov?.fields[r.key]?.value;return v!==null&&v!==undefined&&v!==''&&v!=='UNKNOWN';});
  useEffect(()=>{if(!selected&&prov){setSelected(prov.fields.total_amount?.value!=null?'total_amount':visibleRows[0]?.key??null);}},[prov]);
  const confirmSelected=async()=>{if(!selected||!originalAck)return;setSaving(true);setSaveError('');try{await api.correctFields(doc.document_id,doc.analysis.fields,doc.document_type,revision,`원문과 같은 ${rows.find(r=>r.key===selected)?.label||selected} 확인`,[selected]);await onChanged();setCmpKey(k=>k+1);if(!problems.length)onReviewed?.();}catch(e){setSaveError(e instanceof Error?e.message:'확인 기록 실패');}finally{setSaving(false);}};
  const selectedCheck=selected?fieldChecks(selected,docChecks).find(c=>c.expected||c.actual):undefined;
  const selectedValue=selected?display(selected,prov?.fields[selected]?.value??null,isMaskingEnabled):'';
  const originalReady=doc.file_available&&(visual?!!imageUrl:!!text);
  const filePicker=React.useRef<HTMLInputElement>(null);
  const fieldLabel=(key:string)=>rows.find(r=>r.key===key)?.label||key;
  const mainKeys=new Set(['total_amount','supply_amount','tax_amount','company_name']);
  const amountDoc=['contract','estimate','tax_invoice'].includes(doc.document_type);
  const mainRows=visibleRows.filter(r=>!amountDoc||mainKeys.has(r.key));
  const moreRows=visibleRows.filter(r=>amountDoc&&!mainKeys.has(r.key));
  const renderField=(r:typeof rows[number])=>{const p=prov!.fields[r.key],c=fieldChecks(r.key,docChecks),a=p.evidence?.[0];return <button className={`field ${selected===r.key?'field-selected':''}`} key={r.key} onClick={()=>pick(r.key)}><div><strong>{r.key==='total_amount'?'합계':r.key==='tax_amount'?'부가세':r.key==='company_name'&&['estimate','tax_invoice'].includes(doc.document_type)?'공급자 상호':r.label}</strong><Badge>{p.source==='HUMAN_CONFIRMATION'?'사람 확인':p.source==='AI_SUPPLEMENT'?'AI 보완':p.source==='RULE'?'규칙':'출처 없음'}</Badge></div><div><b>{display(r.key,p.value,isMaskingEnabled)}</b><span className="evidence">{a?.page?`p.${a.page}`:a?.line?`본문 ${a.line}줄`:'근거 없음'}{a&&<ArrowUpRight size={13}/>}</span></div><small>검사 {c.some(t=>t.status==='FAIL')?'불일치':c.some(t=>t.status!=='PASS')?'확인 필요':c.length?'일치':'없음'} · 사람 확인 {p.human_confirmation?`${p.human_confirmation.actor_name} · ${kst(p.human_confirmation.at)}`:'미확인'}</small>{p.ai_decision?.accepted===false&&<small>AI 제안 미채택 · {p.ai_decision.reasons?.map(t=>REASON_KO[t]||'검증 실패').join(', ')}</small>}</button>;};
  const comparison=<>{cmpError?<p role="alert">비교하지 못했습니다.</p>:cmp&&cmp.changes.length>0?<div className="comparison-values">{cmp.changes.filter(c=>c.field!=='amount'||!cmp.changes.some(t=>t.field==='total_amount')).map(c=><div key={c.field}><span>{fieldLabel(c.field)}</span><del>{display(c.field,c.previous_value as FieldProvenance['value'],isMaskingEnabled)||'없음'}</del><span>→</span><b>{display(c.field,c.new_value as FieldProvenance['value'],isMaskingEnabled)||'읽지 못함'}</b></div>)}</div>:null}</>;
  if(reissueOpen)return <div className="docs-grid"><Surface title="고친 본 올리기" sub={`${DOCUMENT_TYPE_KO[doc.document_type]} · 같은 서류의 다음 본`}><div ref={reissueRef} className="story-form form-fields"><label>현재 본<input readOnly value={`${DOCUMENT_TYPE_KO[doc.document_type]} · ${versionNo}번째 본 · ${display('total_amount',doc.analysis.fields.total_amount??doc.analysis.fields.amount??null,isMaskingEnabled)||doc.original_file_name}`}/></label><label>도착한 고친 본<div className="file-control"><input readOnly value={reissueFile?.name||'파일 선택 전'}/><button className="button" disabled={reissuing} onClick={()=>filePicker.current?.click()}>파일 선택</button><input ref={filePicker} key={fileInputKey} type="file" className="sr-only" tabIndex={-1} aria-label="도착한 고친 본 파일" onChange={e=>{setReissueFile(e.target.files?.[0]??null);setReissueError('');}}/></div></label><label>교체 사유<textarea rows={3} value={reissueNote} onChange={e=>setReissueNote(e.target.value)} maxLength={2000}/></label><p>이전 본을 보관하고, 현재 본의 원문과 값을 다시 확인합니다.</p>{reissueError&&<p className="story-alert" role="alert">{reissueError}</p>}</div><div className="panel-footer"><button className="button" disabled={reissuing} onClick={closeReissue}>취소</button><button className="button primary" disabled={reissuing||!reissueFile||!reissueNote.trim()} onClick={()=>void reissue()}><Upload size={15}/>{reissuing?'등록 중…':`${josa(DOCUMENT_TYPE_KO[doc.document_type],'을/를')} 바꾸기`}</button></div></Surface><Surface title="원본 이력" className="next-panel"><div><Badge>현재 {versionNo}번째 본</Badge><h3>같은 서류의 수정본</h3><p>새 서류 추가와 구분해 등록합니다. 현재 본이 바뀌면 기존 확인과 결재는 다시 필요합니다.</p></div></Surface></div>;
  return <Surface title={`${DOCUMENT_TYPE_KO[doc.document_type]} · ${versionNo}번째 본`} sub={doc.version?.is_current===false?'이전 본 · 읽기 전용':'현재 본 · 원문과 저장값 대조'} className="story-source" action={<Badge tone={problems.length?'amber':passed.length?'green':'gray'}>{problems.length?'확인 필요':passed.length?'적용 검사 일치':'적용 검사 없음'}</Badge>}>
    <div className="source-mobile-tabs" role="tablist" aria-label="원문 대조 보기"><button role="tab" aria-selected={sourcePane==='original'} className={sourcePane==='original'?'selected':''} onClick={()=>setSourcePane('original')}>원문</button><button role="tab" aria-selected={sourcePane==='fields'} className={sourcePane==='fields'?'selected':''} onClick={()=>setSourcePane('fields')}>저장값·근거</button></div>
    <div className={`source-grid pane-${sourcePane}`}><div className="paper-area">
      {!doc.file_available?<p role="alert">원본 파일이 없습니다.</p>:visual?imageUrl?<div className="actual-paper"><img src={imageUrl} alt={`${DOCUMENT_TYPE_KO[doc.document_type]} 원문`}/>{boxes.map((box,i)=><span key={i} aria-hidden="true" className="source-highlight" style={{left:`${box.x*100}%`,top:`${box.y*100}%`,width:`${box.width*100}%`,height:`${box.height*100}%`}}/>)}</div>:imageError?<p role="alert">{imageError}</p>:<p role="status"><Loader2 size={18} className="animate-spin"/>원문 불러오는 중…</p>:<div className="actual-paper text-paper">{textError?<p role="alert">{textError}</p>:highlightedText?<>{highlightedText[0]}<mark>{highlightedText[1]}</mark>{highlightedText[2]}</>:text||'원문 불러오는 중…'}</div>}
      <div className="source-page-tools">{isPdf&&pages>1&&<><button className="icon" aria-label="이전 쪽" disabled={page===0} onClick={()=>setPage(p=>p-1)}><ChevronLeft size={16}/></button><small>페이지 {page+1}/{pages}</small><button className="icon" aria-label="다음 쪽" disabled={page+1>=pages} onClick={()=>setPage(p=>p+1)}><ChevronRight size={16}/></button></>}<small>{isMaskingEnabled?'자동 가림 · 일부 누락 가능':visual?'원본 표시':'본문 표시 · 쪽 배치 미보존'}</small></div>
      {anchor&&<small role="status">근거 {anchor.page?`${anchor.page}쪽 `:''}{anchor.line?`${anchor.line}번째 줄`:anchor.bbox?'표시 위치':'본문'}{quoteShown?` · ${quoteShown}`:''}</small>}
    </div><div className="source-fields"><div className="section-title"><div><h2>저장값과 원문 근거</h2><span>자동 검사와 사람 확인은 별도</span></div></div>
      {editing?<div ref={editRef} className="workspace-edit form-fields"><h3>읽은 값 수정</h3>{rows.map(r=><div key={r.key}><label>{r.label}{r.key==='amount_scope'?<select value={String((draft as Record<string,unknown>)[r.key]??'UNKNOWN')} onChange={e=>setDraft({...draft,[r.key]:e.target.value as AnalysisFields['amount_scope']})}><option value="UNKNOWN">미확인</option><option value="FULL">전액 청구</option><option value="PARTIAL">일부 청구</option></select>:<input value={String((draft as Record<string,unknown>)[r.key]??'')} type={r.key.endsWith('amount')?'number':'text'} onChange={e=>setDraft({...draft,[r.key]:r.key.endsWith('amount')?(e.target.value===''?null:Number(e.target.value)):e.target.value})}/>}</label><label className="check-label"><input type="checkbox" checked={confirmed.has(r.key)} onChange={()=>toggleConfirmed(r.key)}/>원문과 맞음</label></div>)}<label>수정·확인 사유<textarea value={note} onChange={e=>setNote(e.target.value)} rows={2}/></label><small>계약에 맞추지 않고 원문 값으로 수정합니다.</small><div className="story-button-row"><button className="button" disabled={saving} onClick={()=>{returnFocus.current='edit';setEditing(false);setDraft(doc.analysis.fields);}}>취소</button><button className="button primary" disabled={saving||!note.trim()||!(changedKeys.length||confirmedKeys.length)} onClick={()=>void save()}>{saving?'저장 중…':'수정 저장'}</button></div></div>:<div className="field-list">{provError?<p className="story-alert" role="alert">{provError}</p>:!prov?<p role="status">읽은 값 조회 중…</p>:<>{mainRows.map(renderField)}{moreRows.length>0&&<details className="more-fields"><summary>그 외 저장값 {moreRows.length}개</summary>{moreRows.map(renderField)}</details>}</>}</div>}
      {!editing&&<div className="source-actions">{comparison}<strong>{selectedCheck?`기준 ${maskForDisplay(selectedCheck.expected||'—',isMaskingEnabled)} / 저장 ${selectedValue}`:selected?`${fieldLabel(selected)} · ${selectedValue}`:'확인할 값을 선택하세요'}</strong><small>{problems.length?'계약에 맞추려고 저장값을 바꾸지 않습니다. 원문이 다르면 정정 요청을 합니다.':'적용된 자동 검사와 원문 사람 확인은 별도입니다.'}</small>{editable&&<label className="check-label"><input type="checkbox" checked={originalAck} disabled={!originalReady} onChange={e=>setOriginalAck(e.target.checked)}/><span>원문과 저장값이 같음을 확인</span></label>}
        {saveError&&<p className="story-alert" role="alert">{saveError}</p>}
        {editable&&<div><button ref={editBtnRef} className="button" onClick={()=>{setEditing(true);setDraft(doc.analysis.fields);}}>읽은 값 수정</button>{problems.length&&onRequest?<button className="button primary" disabled={!originalAck||!originalReady} onClick={()=>onRequest(doc.document_id)}>정정 요청 작성<ChevronRight size={14}/></button>:<button className="button primary" disabled={saving||!selected||!originalAck||!originalReady||!selectedValue} onClick={()=>void confirmSelected()}><Check size={15}/>{onReviewed&&!problems.length?(reviewNextLabel||'검토 후 대표 전달'):'원문과 같음'}</button>}</div>}
        {editable&&<div className="source-secondary"><button ref={reissueBtnRef} className="text-button" onClick={openReissue}>고친 본 올리기<Upload size={13}/></button></div>}
        <details><summary>원본·버전 정보</summary><small>{doc.original_file_name}</small>{versions?.map(v=><small key={v.document_id}>{v.version_number}번째 · {v.is_current?'현재 본':'이전 본'} · {v.actor_name||''}</small>)}<button className="text-button" onClick={()=>void downloadProtected(`/api/documents/${doc.document_id}/download?masked=true`,doc.original_file_name)}><Download size={13}/>가린 원본 받기</button></details>
      </div>}
    </div></div>
  </Surface>;
};
