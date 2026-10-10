import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Check, ChevronDown, ChevronLeft, ChevronRight, FileText, ArrowLeft, MoreHorizontal, Loader2, Pencil, Search, ShieldCheck, Download } from 'lucide-react';
import { api, requestJson, downloadProtected } from '../../api/client';
import { ContractDetail, DocumentResponse, DocumentType, ValidationCheck } from '../../types';
import { DOCUMENT_LABEL } from '../../utils/documentLabels';
import { maskAccountNumber, maskBusinessNumber, maskResidentNumber } from '../../utils/masking';
import { useVlmReread } from '../../hooks/useVlmReread';
import {buildReviewTasks,pendingReviewTasks,ReviewRequestStates,ReviewTask} from './reviewTasks';
import {ReviewFieldTable,ReviewFieldRow,criterion} from './ReviewFieldTable';
import { ReadingRecovery } from './ReadingRecovery';
import {BillingSummary} from './BillingSummary';
import { kst } from './ActivityTimeline';
import { Anchor, BBox, ReviewContext, Provenance, displayValue, editedValue, hasValue, reviewRows, checksForField, sensitiveField, sourceLabel } from './reviewFields';
import {DocumentChangeSummary,DocumentComparison} from './DocumentChangeSummary';
import {FocusedItemActions,FocusAction} from './FocusedItemActions';
import {focusItems,readFocusCursor,writeFocusCursor} from './focusNavigation';

interface Props {
  contract?:ContractDetail; initialField?:string; sharedContext?:ReviewContext|null;sharedContextError?:string;onRefreshContext?:()=>Promise<ReviewContext|null>;
  requestStates?:ReviewRequestStates;requestHint?:string;queuedRequests?:number;onOpenRequestDraft?:()=>void;onCheckBasis?:()=>void;onOpenTask?:(task:ReviewTask)=>void;
  doc:DocumentResponse; documents?:DocumentResponse[]; requiredTypes?:DocumentType[]; checks:ValidationCheck[]; revision:number;
  isMaskingEnabled:boolean; canEdit:boolean; onClose:()=>void; onChanged:()=>Promise<void>;
  onSelectDocument?:(doc:DocumentResponse,field?:string)=>void; onUploadType?:(type:DocumentType)=>void; onToggleMasking?:()=>void;
  onRequest?:(id:number)=>void; onReviewed?:()=>void; reviewNextLabel?:string;
  onReissued?:(doc:DocumentResponse)=>void; initialMode?:'view'|'reissue';
}
interface Version { document_id:number; version_number:number; is_current:boolean }
interface Undo { field:string; label:string; revision:number; confirmed_at:string }

/** Layout and copy follow the approved 4188 prototype. Server data determines values, checks and permissions. */
/** 확인 패널에서 "원문에서 볼 곳"으로 안내할 위치. 없는 항목은 항목 이름으로 안내한다. */
const LOOK_AT:Record<string,string>={
    amount_scope:'청구액과 계약 지급 조건 · 잔금 문구만으로 일부 청구를 판단하지 않아요',
  total_amount:'합계금액 칸', amount:'합계금액 칸', supply_amount:'공급가액 칸', tax_amount:'세액 칸',
  amount_basis:'금액 옆 부가세 포함·별도 표시', issue_date:'작성일자 칸',
  business_registration_no:'공급자 등록번호 칸', company_name:'공급자 상호 칸',
  account_number:'계좌번호 칸', bank_name:'은행명 칸', account_holder:'예금주 칸',
};

/** 글자 단위 근거 상자를 줄 단위 하나의 상자로 합쳐 "여기"가 한눈에 보이게 한다. */
function mergeLines(list:BBox[]):BBox[]{
  const lines:BBox[]=[];
  for(const box of [...list].sort((a,b)=>a.y-b.y||a.x-b.x)){
    const mid=box.y+box.height/2;
    const line=lines.find(item=>item.page===box.page&&Math.abs(item.y+item.height/2-mid)<=Math.max(item.height,box.height,0.006));
    if(!line){lines.push({...box});continue;}
    const right=Math.max(line.x+line.width,box.x+box.width),bottom=Math.max(line.y+line.height,box.y+box.height);
    line.x=Math.min(line.x,box.x);line.y=Math.min(line.y,box.y);line.width=right-line.x;line.height=bottom-line.y;
  }
  return lines;
}

export const DocumentWorkspace:React.FC<Props>=({contract,initialField,sharedContext,sharedContextError,onRefreshContext,requestStates={},requestHint,queuedRequests=0,onOpenRequestDraft,onCheckBasis,onOpenTask,doc,documents=[doc],requiredTypes=[],checks,revision,isMaskingEnabled:masked,canEdit,onClose,onChanged,onSelectDocument,onUploadType,onToggleMasking,onRequest,onReissued,initialMode='view'})=>{
  const editable=canEdit&&doc.version?.is_current!==false;
  const [focusAction,setFocusAction]=useState<FocusAction>(null);
  const [mobilePane,setMobilePane]=useState<'original'|'fields'>('fields');
  const [context,setContext]=useState<ReviewContext|null>(null),[contextError,setContextError]=useState('');
  const [historical,setHistorical]=useState<Provenance|null>(null);
  const [selected,setSelected]=useState<string|null>(null),[editing,setEditing]=useState(false),[editValue,setEditValue]=useState(''),[note,setNote]=useState('');
  const [saving,setSaving]=useState(false),[saveError,setSaveError]=useState(''),[undo,setUndo]=useState<Undo|null>(null),[notice,setNotice]=useState('');
  const [page,setPage]=useState(0),[pages,setPages]=useState(1),[imageUrl,setImageUrl]=useState(''),[imageReady,setImageReady]=useState(false),[imageError,setImageError]=useState('');
  const [text,setText]=useState(''),[textReady,setTextReady]=useState(false),[textError,setTextError]=useState('');
  const [anchor,setAnchor]=useState<Anchor|null>(null),[comparison,setComparison]=useState<DocumentComparison|null>(null),[compareError,setCompareError]=useState('');
  const [comparisonLoading,setComparisonLoading]=useState(false),[compareReload,setCompareReload]=useState(0);
  const [versions,setVersions]=useState<Version[]>([]),[versionsError,setVersionsError]=useState('');
  const [reissueOpen,setReissueOpen]=useState(initialMode==='reissue'),[reissueFile,setReissueFile]=useState<File|null>(null),[reissueNote,setReissueNote]=useState(''),[reissuing,setReissuing]=useState(false);
  const [reissueError,setReissueError]=useState('');
  const [allRows,setAllRows]=useState(!contract),[itemMenu,setItemMenu]=useState(false),[deferOpen,setDeferOpen]=useState(false),[deferKind,setDeferKind]=useState<'DEFER'|'NO_ISSUE'>('DEFER'),[deferNote,setDeferNote]=useState(''),[basisOpen,setBasisOpen]=useState(false),[previewRetry,setPreviewRetry]=useState(0),[restoring,setRestoring]=useState(false),[picked,setPicked]=useState(new Set<string>()),[quoteOpen,setQuoteOpen]=useState(false);
  const [batchAck,setBatchAck]=useState(false),[singleField,setSingleField]=useState<string|null>(null);
  const [typeOpen,setTypeOpen]=useState(false),[correctType,setCorrectType]=useState<DocumentType>(doc.document_type),[typeNote,setTypeNote]=useState('');
  const menuRef=useRef<HTMLDivElement>(null),actionRef=useRef<HTMLElement>(null);
  const paperRef=useRef<HTMLDivElement>(null),editRef=useRef<HTMLFormElement>(null),reissueRef=useRef<HTMLDivElement>(null);
  const activeId=useRef(doc.document_id);activeId.current=doc.document_id;
  const isPdf=/\.pdf$/i.test(doc.original_file_name),visual=isPdf||/\.(png|jpe?g|webp|bmp|gif|tiff?)$/i.test(doc.original_file_name);
  const originalReady=!!doc.file_available&&(visual?imageReady:textReady);
  const effectiveContext=sharedContext===undefined?context:sharedContext;
  const effectiveError=sharedContext===undefined?contextError:sharedContextError||'';
  const provenance=doc.version?.is_current===false?historical:effectiveContext?.documents.find(item=>item.document_id===doc.document_id);
  const rows=reviewRows(doc),values=doc.analysis.fields as Record<string,unknown>,label=(key:string)=>key==='__document__'?'서류 원문':rows.find(row=>row.key===key)?.label||key;
  const currentDocs=documents.filter(item=>item.version?.is_current!==false);
  const orderedDocs=[...currentDocs].sort((a,b)=>{const rank=(item:DocumentResponse)=>requiredTypes.includes(item.document_type)?requiredTypes.indexOf(item.document_type):999;return rank(a)-rank(b);});
  const tasks=useMemo(()=>buildReviewTasks(currentDocs,checks,effectiveContext,contract?.workflow?.submission?.gate?.blockers),[documents,checks,effectiveContext,contract?.workflow?.submission]);
  const pendingTasks=pendingReviewTasks(tasks,effectiveContext,requestStates);
  // 이동 순서도 실제 문제를 먼저, 단순 값 대조를 뒤에 둔다.
  const navigation=useMemo(()=>{const rank=(item:ReviewTask)=>tasks.some(task=>task.id===item.id&&!task.routine)?0:1;return focusItems(orderedDocs,tasks,effectiveContext).map((item,index)=>({item,index})).sort((a,b)=>rank(a.item)-rank(b.item)||a.index-b.index).map(({item})=>item);},[documents,tasks,effectiveContext]);
  const focusIndex=navigation.findIndex(item=>item.id===`${doc.document_id}:${selected}`);
  const cursorLoaded=useRef(false);
  const optionalRows:ReviewFieldRow[]=rows.map(row=>({id:`${doc.document_id}:${row.key}`,document:doc,field:row.key,label:row.label,value:values[row.key],expected:contract?checksForField(row.key,checks.filter(check=>check.field===String(doc.document_id))).find(check=>check.expected)?.expected??null:null,checks:contract?checksForField(row.key,checks.filter(check=>check.field===String(doc.document_id))):[]}));
  const problemRows:ReviewFieldRow[]=tasks.filter(task=>task.document).map(task=>({...task,document:task.document!}));
  const baseRows=contract?[...problemRows,...optionalRows.filter(row=>!problemRows.some(other=>other.id===row.id))]:allRows?[...problemRows,...optionalRows.filter(row=>!problemRows.some(other=>other.id===row.id))]:problemRows;
  const selectedRow=baseRows.find(row=>row.document.document_id===doc.document_id&&row.field===selected)||optionalRows.find(row=>row.field===selected);
  const proof=selected?provenance?.fields[selected]:undefined;
  const deferral=selected?provenance?.deferrals?.[selected]:undefined;
  const noIssue=selected?provenance?.no_issue?.[selected]:undefined;
  const mismatch=selectedRow?.checks.some(check=>check.status==='FAIL');
  // 원문 값을 확인한 뒤에도 남는 검사(불일치·검토)는 판단이 필요한 이유를 먼저 보여 준다.
  const issues=selectedRow?.checks.filter(check=>check.status!=='PASS')||[];
  const needsDecision=issues.length>0&&!!proof?.human_confirmation;
  const classification=selectedRow?.checks.some(check=>check.rule_id==='DOCUMENT_TYPE');
  const canAct=editable&&originalReady&&revision>0&&!!provenance&&provenance.source_version_verified!==false&&!saving&&!reissuing&&(!effectiveContext||effectiveContext.revision===revision);
  const requiresReveal=(key:string)=>masked&&sensitiveField(key);
  // 이 서류에서 계약 기준과 같은 값을 원문과 한 번 더 대조할 항목. 한 화면에서 한 번에 저장한다.
  const routineHere=pendingTasks.filter(task=>task.routine&&task.document?.document_id===doc.document_id&&!provenance?.fields[task.field]?.human_confirmation);
  const batchMode=!!contract&&!!selected&&selected!==singleField&&routineHere.some(task=>task.field===selected);
  const batchReveal=routineHere.some(task=>requiresReveal(task.field));
  const vlm=useVlmReread({documentId:doc.document_id,documentType:doc.document_type,revision,page:page+1,masked,enabled:editable&&visual&&!!doc.file_available});
  const candidates=vlm.result?.candidates.filter(item=>item.changed??displayValue(item.field,item.value,masked)!==displayValue(item.field,values[item.field],masked))||[];
  const tableRows=[...baseRows,...optionalRows.filter(row=>(candidates.some(item=>item.field===row.field)||row.field===selected)&&!baseRows.some(other=>other.id===row.id))];
  const pickedFields=[...picked].filter(key=>candidates.some(item=>item.field===key&&item.usable)&&!requiresReveal(key));
  const readyToRead=canAct&&visual&&!!vlm.status?.ready&&!vlm.busy;
  // VLM이 꺼진 환경에서는 비활성 버튼 대신 AI 재판독 진입점을 숨긴다.
  const vlmOn=!!vlm.status?.ready;


  useEffect(()=>{
    const controller=new AbortController();setContext(null);setHistorical(null);setContextError('');
    if(sharedContext===undefined)void requestJson<ReviewContext>(`/api/contracts/${doc.contract_id}/review-context?evidence_document_id=${doc.document_id}`,{signal:controller.signal}).then(value=>{
      if(controller.signal.aborted)return;
      if(value.revision!==revision)throw new Error('자료가 변경되었습니다. 최신 계약을 불러온 뒤 확인하세요.');
      setContext(value);
    }).catch(reason=>{if(!controller.signal.aborted)setContextError(reason.message);});
    if(doc.version?.is_current===false)void requestJson<Provenance>(`/api/documents/${doc.document_id}/provenance`,{signal:controller.signal}).then(value=>{if(!controller.signal.aborted)setHistorical(value);}).catch(reason=>{if(!controller.signal.aborted)setContextError(reason.message);});
    return ()=>controller.abort();
  },[doc.contract_id,doc.document_id,doc.version?.is_current,revision,sharedContext===undefined]);
  useEffect(()=>{setBatchAck(false);setSingleField(null);},[doc.document_id,revision]);
  useEffect(()=>{setFocusAction(null);cursorLoaded.current=false;setSelected(initialField??null);setEditing(false);setNote('');setSaveError('');setPage(0);setAnchor(null);setUndo(null);setNotice('');setReissueFile(null);setReissueNote('');setReissueOpen(initialMode==='reissue');setAllRows(!contract);setTypeOpen(false);setTypeNote('');setCorrectType(doc.document_type);setDeferOpen(false);setItemMenu(false);setBasisOpen(false);},[doc.document_id]);
  useEffect(()=>{setFocusAction(null);setEditing(false);setNote('');setAnchor(null);setDeferOpen(false);setItemMenu(false);setPicked(new Set());},[revision,masked]);
  useEffect(()=>{if(!undo)return;const timer=setTimeout(()=>setUndo(null),10000);return()=>clearTimeout(timer);},[undo]);
  useEffect(()=>{if(!notice)return;const timer=setTimeout(()=>setNotice(''),4000);return()=>clearTimeout(timer);},[notice]);
  useEffect(()=>{editRef.current?.querySelector<HTMLInputElement>('input,select')?.focus();},[editing]);
  useEffect(()=>{if(reissueOpen)reissueRef.current?.querySelector<HTMLInputElement>('input[type=file]')?.focus();},[reissueOpen]);
  useEffect(()=>{
    const controller=new AbortController();setPages(1);
    if(isPdf&&doc.file_available)void requestJson<{total_pages:number}>(`/api/documents/${doc.document_id}/pages-info`,{signal:controller.signal}).then(value=>{if(!controller.signal.aborted)setPages(value.total_pages);}).catch(()=>undefined);
    return()=>controller.abort();
  },[doc.document_id,isPdf,doc.file_available]);
  useEffect(()=>{
    setImageUrl('');setImageReady(false);setImageError('');if(!visual||!doc.file_available)return;
    const controller=new AbortController();let url='';
    void fetch(`/api/documents/${doc.document_id}/preview-image?page=${page}&masked=${masked}&revision=${revision}`,{credentials:'same-origin',signal:controller.signal})
      .then(async response=>{if(!response.ok)throw new Error((await response.json().catch(()=>({}))).detail||'원문 그림을 불러오지 못했습니다.');return response.blob();})
      .then(blob=>{if(controller.signal.aborted)return;url=URL.createObjectURL(blob);setImageUrl(url);})
      .catch(reason=>{if(!controller.signal.aborted)setImageError(reason.message);});
    return()=>{controller.abort();if(url)URL.revokeObjectURL(url);};
  },[doc.document_id,page,masked,revision,visual,doc.file_available,previewRetry]);
  useEffect(()=>{
    setText('');setTextReady(false);setTextError('');if(visual||!doc.file_available)return;
    const controller=new AbortController();void requestJson<{text:string}>(`/api/documents/${doc.document_id}/text-preview?masked=${masked}`,{signal:controller.signal})
      .then(value=>{if(!controller.signal.aborted){setText(value.text);setTextReady(!!value.text);}}).catch(reason=>{if(!controller.signal.aborted)setTextError(reason.message);});
    return()=>controller.abort();
  },[doc.document_id,masked,revision,visual,doc.file_available,previewRetry]);
  const version=doc.version?.version_number||1;
  const activeComparison=comparison?.new_document_id===doc.document_id&&comparison.revision===revision?comparison:null;
  useEffect(()=>{
    const controller=new AbortController();setVersions([]);setComparison(null);setCompareError('');setVersionsError('');setComparisonLoading(version>=2);
    if(version>=2)void Promise.all([
      requestJson<{versions:Version[]}>(`/api/documents/${doc.document_id}/versions`,{signal:controller.signal}).then(value=>{if(!controller.signal.aborted)setVersions(value.versions);}).catch(()=>{if(!controller.signal.aborted)setVersionsError('버전 이력을 불러오지 못했습니다.');}),
      requestJson<DocumentComparison>(`/api/documents/${doc.document_id}/compare`,{signal:controller.signal}).then(value=>{
        if(controller.signal.aborted)return;
        if(value.new_document_id!==doc.document_id||value.revision!==revision||value.new_version!==version)throw new Error('자료가 변경되었어요. 최신 계약을 불러온 뒤 비교해 주세요.');
        if(!Array.isArray(value.changes)||!value.previous_fields||!value.new_fields||!Number.isInteger(value.previous_document_id)||value.previous_document_id<1||!Number.isInteger(value.previous_version)||value.previous_version<1||value.previous_version>=version)throw new Error('이전 본의 비교 정보를 읽지 못했습니다.');
        setComparison(value);
      }).catch(reason=>{if(!controller.signal.aborted)setCompareError(reason instanceof Error?reason.message:'이전 본과 비교하지 못했습니다.');}).finally(()=>{if(!controller.signal.aborted)setComparisonLoading(false);}),
    ]);
    return()=>controller.abort();
  },[doc.document_id,version,revision,compareReload]);
  const openPrevious=async()=>{
    if(!activeComparison||!onSelectDocument||saving||reissuing)return;
    const id=doc.document_id;setSaving(true);setSaveError('');
    try{const previous=await api.getDocument(activeComparison.previous_document_id);if(activeId.current===id)onSelectDocument(previous);}
    catch(reason){if(activeId.current===id)setSaveError(reason instanceof Error?reason.message:'이전 본을 불러오지 못했습니다.');}
    finally{if(activeId.current===id)setSaving(false);}
  };
  const selectField=(key:string)=>{setFocusAction(null);setSelected(key);setEditing(false);setTypeOpen(false);setDeferOpen(false);setBasisOpen(false);setItemMenu(false);setNote('');setSaveError('');setQuoteOpen(false);const evidence=provenance?.fields[key]?.evidence?.[0];setAnchor(evidence||null);if(evidence?.page&&isPdf)setPage(evidence.page-1);requestAnimationFrame(()=>actionRef.current?.scrollIntoView({block:'nearest',behavior:'smooth'}));};
  // 항목을 고르면(처음 열 때 포함) 원문 위치를 자동으로 표시한다. 근거가 늦게 도착해도 다시 시도한다.
  const autoAnchor=selected?provenance?.fields[selected]?.evidence?.[0]:undefined;
  useEffect(()=>{if(!autoAnchor)return;setAnchor(autoAnchor);if(autoAnchor.page&&isPdf)setPage(autoAnchor.page-1);},[selected,autoAnchor,isPdf]);
  const showEvidence=(key:string)=>{
    const evidence=provenance?.fields[key]?.evidence?.[0];if(!evidence)return;
    setAnchor(evidence);if(evidence.page&&isPdf)setPage(evidence.page-1);setMobilePane('original');
    requestAnimationFrame(()=>paperRef.current?.scrollIntoView({block:'start',behavior:'smooth'}));
  };
  const confirmBatch=async()=>{
    if(!canAct||!batchAck||batchReveal||saving||!routineHere.length)return;
    const id=doc.document_id,fields=routineHere.map(task=>task.field);setSaving(true);setSaveError('');setUndo(null);
    try{
      await requestJson(`/api/documents/${id}/confirm-fields`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({fields,revision})});
      if(activeId.current!==id)return;
      const fresh=await afterSave();if(activeId.current!==id)return;
      setBatchAck(false);setNotice(`${DOCUMENT_LABEL[doc.document_type]} 값 ${fields.length}개의 원문 확인을 저장했어요.`);
      if(fresh&&onOpenTask){
        const liveDocs=currentDocs.map(item=>{const metadata=fresh.documents.find(p=>p.document_id===item.document_id);return metadata?{...item,analysis:{...item.analysis,fields:{...item.analysis.fields,...Object.fromEntries(Object.entries(metadata.fields).map(([key,field])=>[key,field.value]))}}}:item;});
        const next=buildReviewTasks(liveDocs,fresh.checks??checks,fresh,fresh.workflow?.submission?.gate?.blockers).find(task=>!task.deferral);
        if(next)onOpenTask(next);
      }
    }catch(reason){if(activeId.current===id)setSaveError(reason instanceof Error?reason.message:'원문 확인을 저장하지 못했습니다.');}
    finally{if(activeId.current===id)setSaving(false);}
  };
  const confirmField=async()=>{
    if(!selected||saving||!editable||!originalReady||!provenance||requiresReveal(selected)||!hasValue(values[selected])||provenance.fields[selected]?.human_confirmation)return;
    const key=selected,id=doc.document_id;setSaving(true);setSaveError('');setUndo(null);
    try{
      const response=await requestJson<Omit<Undo,'label'>>(`/api/documents/${id}/confirm-field`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({field:key,revision})});
      if(activeId.current!==id)return;
      setUndo({...response,label:label(key)});
      await onChanged();if(activeId.current!==id)return;
      if(contract){setNotice('원문 확인을 저장했어요.');return;}
      if(selectedRow?.checks.some(check=>check.status==='FAIL'))return;
      const eligible=rows.filter(row=>row.key!==key&&hasValue(values[row.key])&&!requiresReveal(row.key)&&!provenance.fields[row.key]?.human_confirmation);
      const index=rows.findIndex(row=>row.key===key),next=eligible.find(row=>rows.indexOf(row)>index)||eligible[0];setSelected(next?.key||key);
    }catch(reason){if(activeId.current===id)setSaveError(reason instanceof Error?reason.message:'확인 기록을 저장하지 못했습니다.');}
    finally{if(activeId.current===id)setSaving(false);}
  };
  const undoConfirmation=async()=>{
    if(!undo||saving)return;const id=doc.document_id,previous=undo;setSaving(true);setSaveError('');
    try{await requestJson(`/api/documents/${id}/undo-field-confirmation`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({field:previous.field,revision:previous.revision,confirmed_at:previous.confirmed_at})});
      if(activeId.current!==id)return;setUndo(null);await onChanged();if(activeId.current===id){setSelected(previous.field);setNotice(`${previous.label} 확인을 되돌렸어요. 읽은 값은 유지됩니다.`);}
    }catch(reason){if(activeId.current===id)setSaveError(reason instanceof Error?reason.message:'확인을 되돌리지 못했습니다.');}
    finally{if(activeId.current===id)setSaving(false);}
  };
  const saveEdit=async(event:React.FormEvent)=>{
    event.preventDefault();if(!selected||!canAct||requiresReveal(selected)||!editValue.trim()||!note.trim())return;
    const id=doc.document_id,key=selected;setSaving(true);setSaveError('');setUndo(null);
    try{await api.correctFields(id,editedValue(key,editValue),doc.document_type,revision,note.trim(),[key]);const fresh=await afterSave();if(activeId.current===id){setEditing(false);advanceAfterSave(fresh,[key]);setNotice(`${label(key)} 수정과 원문 확인을 기록했어요.`);}}
    catch(reason){if(activeId.current===id)setSaveError(reason instanceof Error?reason.message:'수정값을 저장하지 못했습니다.');}
    finally{if(activeId.current===id)setSaving(false);}
  };
  const saveDocumentType=async(event:React.FormEvent)=>{
    event.preventDefault();if(!canAct||correctType===doc.document_type||correctType==='unknown'||!typeNote.trim())return;
    const id=doc.document_id;setSaving(true);setSaveError('');
    try{
      const updated=await api.correctFields(id,{},correctType,revision,typeNote.trim(),[]);
      await afterSave();
      if(activeId.current===id){setTypeOpen(false);setTypeNote('');setNotice('서류 종류를 수정하고 자동 검사를 다시 했어요.');onSelectDocument?.(updated);}
    }catch(reason){if(activeId.current===id)setSaveError(reason instanceof Error?reason.message:'서류 종류를 저장하지 못했습니다.');}
    finally{if(activeId.current===id)setSaving(false);}
  };
  const reissue=async()=>{
    if(!reissueFile||!reissueNote.trim()||reissuing)return;const id=doc.document_id;setReissuing(true);setReissueError('');
    try{const result=await api.reissueDocument(doc.contract_id,reissueFile,id,revision,reissueNote.trim());await onChanged();if(activeId.current===id){setReissueOpen(false);setReissueFile(null);setReissueNote('');if(result[0])onReissued?.(result[0]);}}
    catch(reason){if(activeId.current===id)setReissueError(reason instanceof Error?reason.message:'수정본을 올리지 못했습니다.');}
    finally{if(activeId.current===id)setReissuing(false);}
  };
  const refreshEvidence=async()=>{if(onRefreshContext)return onRefreshContext();const value=await requestJson<ReviewContext>(`/api/contracts/${doc.contract_id}/review-context?evidence_document_id=${doc.document_id}`);if(activeId.current===doc.document_id)setContext(value);return value;};
  const afterSave=async()=>{await onChanged();return refreshEvidence();};
  const advanceAfterSave=(fresh:ReviewContext|null,applied:string[])=>{
    if(!fresh||contract)return;
    const liveDocs=currentDocs.map(item=>{const metadata=fresh.documents.find(p=>p.document_id===item.document_id);return metadata?{...item,analysis:{...item.analysis,fields:{...item.analysis.fields,...Object.fromEntries(Object.entries(metadata.fields).map(([key,field])=>[key,field.value]))}}}:item;});
    const remaining=buildReviewTasks(liveDocs,fresh.checks??checks,fresh,fresh.workflow?.submission?.gate?.blockers);
    if(remaining.some(task=>task.document?.document_id===doc.document_id&&applied.includes(task.field)))return;
    const next=remaining.find(task=>task.document?.document_id===doc.document_id&&task.kind==='field'&&!task.deferral&&!requiresReveal(task.field));
    if(next)selectField(next.field);
  };
  const beginEdit=()=>{setFocusAction('correct');if(!selected||!canAct||requiresReveal(selected))return;setEditValue(String(values[selected]??''));setEditing(true);setNote('');setUndo(null);setPicked(new Set());setItemMenu(false);};
  const chooseRow=(row:ReviewFieldRow)=>{if(contract)setAllRows(false);if(row.document.document_id===doc.document_id)selectField(row.field);else onSelectDocument?.(row.document,row.field);};
  useEffect(()=>{if(initialField)selectField(initialField);},[initialField]);
  useEffect(()=>{if(!contract&&!selected&&!initialField){const first=problemRows.find(row=>row.document.document_id===doc.document_id);if(first)setSelected(first.field);}},[doc.document_id,initialField,problemRows.map(row=>row.id).join('|')]);
  useEffect(()=>{
    if(!contract||!effectiveContext||effectiveContext.revision!==revision||cursorLoaded.current)return;
    cursorLoaded.current=true;
    if(initialField)return;
    const remembered=readFocusCursor(contract,navigation);
    const first=remembered?.document?.document_id===doc.document_id?remembered:navigation.find(item=>item.document?.document_id===doc.document_id&&pendingTasks.some(task=>task.id===item.id))||navigation.find(item=>item.document?.document_id===doc.document_id);
    if(first)selectField(first.field);
  },[doc.document_id,initialField,effectiveContext,revision,navigation]);
  useEffect(()=>{if(contract&&selected&&effectiveContext?.revision===revision&&cursorLoaded.current)writeFocusCursor(contract,`${doc.document_id}:${selected}`);},[contract,selected,effectiveContext?.revision,revision]);
  useEffect(()=>()=>{activeId.current=-1;},[]);
  useEffect(()=>{setPicked(new Set(candidates.filter(item=>item.usable&&!requiresReveal(item.field)).map(item=>item.field)));setQuoteOpen(false);},[vlm.result?.run_id]);
  useEffect(()=>{if(!itemMenu)return;const close=(event:PointerEvent)=>{if(!menuRef.current?.contains(event.target as Node))setItemMenu(false);};const key=(event:KeyboardEvent)=>{if(event.key==='Escape'){setItemMenu(false);menuRef.current?.querySelector<HTMLButtonElement>('[aria-haspopup="menu"]')?.focus();}};document.addEventListener('pointerdown',close);document.addEventListener('keydown',key);return()=>{document.removeEventListener('pointerdown',close);document.removeEventListener('keydown',key);};},[itemMenu]);
  const read=(field?:string)=>{setUndo(null);setItemMenu(false);setPicked(new Set());void vlm.reread(field&&field!=='__document__'?[field]:undefined);};
  const saveCandidates=async()=>{
    if(!canAct||vlm.busy||!vlm.result||!pickedFields.length)return;const id=doc.document_id;setSaving(true);setSaveError('');setUndo(null);
    try{await requestJson(`/api/documents/${id}/vlm-confirm`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({run_id:vlm.result.run_id,revision,fields:pickedFields,acknowledge_original:true,note:`${page+1}쪽 원문을 직접 대조하고 ${pickedFields.map(label).join(', ')} AI 후보를 선택함`})});if(activeId.current!==id)return;const fresh=await afterSave();if(activeId.current===id){advanceAfterSave(fresh,pickedFields);setPicked(new Set());setNotice('선택한 값과 원문 확인을 저장했어요.');}}
    catch(reason){if(activeId.current===id)setSaveError(reason instanceof Error?reason.message:'선택한 값을 반영하지 못했습니다.');}finally{if(activeId.current===id)setSaving(false);}
  };
  const saveDeferral=async(clear=false)=>{
    if(!selected||!editable||saving||(!clear&&!deferNote.trim()))return;const id=doc.document_id;setSaving(true);setSaveError('');
    try{await requestJson(`/api/documents/${id}/${clear?'clear-field-deferral':'defer-field'}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(clear?{field:selected,revision,deferred_at:(noIssue||deferral)?.at}:{field:selected,revision,note:deferNote.trim(),kind:deferKind})});if(activeId.current!==id)return;await afterSave();if(activeId.current===id){setDeferOpen(false);if(!clear&&deferKind==='NO_ISSUE'){setNotice('문제 없음으로 기록했어요. 자동 검사 결과는 그대로 남고 결재 때 함께 보여요.');}else setNotice(clear?'보류를 해제했어요.':'다음에 확인할 내용을 저장했어요.');}}
    catch(reason){if(activeId.current===id)setSaveError(reason instanceof Error?reason.message:'보류 기록을 저장하지 못했습니다.');}finally{if(activeId.current===id)setSaving(false);}
  };
  const confirmAbsent=async()=>{if(!selected||!canAct||requiresReveal(selected))return;const id=doc.document_id;setSaving(true);setSaveError('');try{await api.correctFields(id,{[selected]:values[selected]??null},doc.document_type,revision,`원문에 ${label(selected)} 항목이 없음을 직접 확인`,[selected]);if(activeId.current===id){await afterSave();setNotice('원문에 없는 항목임을 기록했어요. 자동 검사 결과는 유지돼요.');}}catch(reason){if(activeId.current===id)setSaveError(reason instanceof Error?reason.message:'확인 기록을 저장하지 못했습니다.');}finally{if(activeId.current===id)setSaving(false);}};
  const restore=async(file:File)=>{const id=doc.document_id;setRestoring(true);setSaveError('');try{await api.restoreOriginal(id,file);await onChanged();setPreviewRetry(value=>value+1);}catch(reason){if(activeId.current===id)setSaveError(reason instanceof Error?reason.message:'원본을 복구하지 못했습니다.');}finally{if(activeId.current===id)setRestoring(false);}};
  const validBox=(box:BBox)=>box.page===page+1&&[box.x,box.y,box.width,box.height].every(value=>Number.isFinite(value)&&value>=0&&value<=1)&&box.width>0&&box.height>0;
  const boxes=mergeLines((anchor?.bboxes?.length?anchor.bboxes:anchor?.bbox?[anchor.bbox]:[]).filter(validBox));
  const protectText=(input:string)=>masked?maskResidentNumber(maskAccountNumber(maskBusinessNumber(input))):input;
  const nextTask=pendingTasks.find(task=>task.id!==`${doc.document_id}:${selected}`&&!task.deferral)||pendingTasks.find(task=>task.id!==`${doc.document_id}:${selected}`);
  const originalImage=<>{!doc.file_available?<p role="alert">원본 파일이 없습니다. 확인·저장은 할 수 없어요.</p>:visual?imageError?<p role="alert">{imageError}</p>:imageUrl?<div className="source-paper"><img className="document-image" src={imageUrl} alt={`${DOCUMENT_LABEL[doc.document_type]} 원문 ${page+1}쪽 · ${masked?'개인정보 가림':'원본 표시'}`} onLoad={()=>setImageReady(true)} onError={()=>{setImageReady(false);setImageError('원문을 불러오지 못했어요. 확인·저장은 할 수 없어요.');}}/>{boxes.map((box,index)=><span key={index} className={`evidence-highlight${issues.length?' issue':''}`} aria-hidden="true" style={{left:`${box.x*100}%`,top:`${box.y*100}%`,width:`${box.width*100}%`,height:`${box.height*100}%`}}/>)}{issues.length>0&&boxes[0]&&<span className="evidence-callout" style={{left:`${boxes[0].x*100}%`,top:`${boxes[0].y*100}%`}}>여기를 다시 보세요 · {label(selected!)}</span>}</div>:<p role="status">원문 불러오는 중…</p>:<div className="source-paper text-paper">{textError?<p role="alert">{textError}</p>:text||'원문 불러오는 중…'}</div>}</>;

  return <section className="review-frame flow-review" aria-label={`${DOCUMENT_LABEL[doc.document_type]} 검수`}>
    <div className="flow-workspace-head"><button className="text-button" onClick={onClose}><ArrowLeft size={14}/>서류 목록</button><div className="flow-summary"><strong>{effectiveContext?`문제 ${pendingTasks.filter(task=>!task.routine).length}건 · 값 대조 ${pendingTasks.filter(task=>task.routine).length}건`:'확인 목록 조회 중'}</strong>{tasks.some(task=>task.deferral)&&<small>보류 {tasks.filter(task=>task.deferral).length}건 포함</small>}<span>요청 초안 {queuedRequests}건</span></div></div>
    <div className="flow-current-document"><FileText size={14}/><strong>{DOCUMENT_LABEL[doc.document_type]}</strong><span>{version}차본</span>{doc.version?.is_current===false&&<small>이전 본 · 읽기 전용</small>}
      <label className="flow-document-select">다른 서류<select aria-label="다른 서류 보기" value={doc.document_id} disabled={saving||reissuing} onChange={event=>{const item=orderedDocs.find(item=>item.document_id===Number(event.target.value));if(item)onSelectDocument?.(item);}}>{!orderedDocs.some(item=>item.document_id===doc.document_id)&&<option value={doc.document_id}>{DOCUMENT_LABEL[doc.document_type]} · {version}차본</option>}{orderedDocs.map(item=><option key={item.document_id} value={item.document_id}>{DOCUMENT_LABEL[item.document_type]} · {item.version?.version_number??1}차본</option>)}</select></label>
    </div>
    {reissueOpen&&editable&&<div className="review-reissue" ref={reissueRef}><h3>수정본 올리기</h3><label>도착한 수정본 파일<input type="file" aria-label="도착한 수정본 파일" disabled={reissuing} onChange={event=>setReissueFile(event.target.files?.[0]||null)}/></label><label>교체 사유<textarea value={reissueNote} onChange={event=>setReissueNote(event.target.value)} maxLength={2000} disabled={reissuing}/></label>{reissueError&&<p role="alert">{reissueError}</p>}<div className="flow-buttons"><button className="button" disabled={reissuing} onClick={()=>setReissueOpen(false)}>취소</button><button className="button primary" disabled={reissuing||!reissueFile||!reissueNote.trim()} onClick={()=>void reissue()}>{reissuing?'등록 중…':'수정본 등록'}</button></div></div>}
    <div className="mobile-view" role="group" aria-label="작은 화면의 대조 보기"><button aria-pressed={mobilePane==='original'} className={mobilePane==='original'?'active':''} onClick={()=>setMobilePane('original')}>원문</button><button aria-pressed={mobilePane==='fields'} className={mobilePane==='fields'?'active':''} onClick={()=>setMobilePane('fields')}>확인할 항목</button>{onToggleMasking&&<button className="flow-mobile-mask" onClick={onToggleMasking}><ShieldCheck size={13}/>가림 {masked?'ON':'OFF'}</button>}</div>
    <div className={`flow-grid show-${mobilePane}`}><div className="flow-paper"><div className="flow-paper-title"><FileText size={14}/>{DOCUMENT_LABEL[doc.document_type]} 원문 · {page+1}쪽{editable&&visual&&vlmOn&&<button className="text-button" disabled={!readyToRead} title={vlm.status?.message} onClick={()=>read()}>{vlm.busy?<Loader2 size={13} className="spin"/>:<Search size={13}/>}현재 쪽 함께 읽기</button>}</div><div className="flow-paper-scroll" ref={paperRef}>{!doc.file_available?<div className="flow-source-empty" role="alert"><strong>원본 파일이 없어요</strong>{editable&&<label className="button">{restoring?'복구 중…':'원본 다시 올리기'}<input type="file" aria-label="복구할 원본 파일" disabled={restoring} onChange={event=>{if(event.target.files?.[0])void restore(event.target.files[0]);}}/></label>}</div>:imageError||textError?<div className="flow-source-empty" role="alert"><p>{imageError||textError}</p><button className="button primary" onClick={()=>setPreviewRetry(value=>value+1)}>원문 다시 불러오기</button></div>:originalImage}</div><div className="flow-paper-footer"><span>원문 {page+1}쪽{isPdf&&pages>1&&<> / {pages}<button aria-label="이전 쪽" disabled={page===0||saving} onClick={()=>{setPage(page-1);setAnchor(null);}}><ChevronLeft size={14}/></button><button aria-label="다음 쪽" disabled={page+1>=pages||saving} onClick={()=>{setPage(page+1);setAnchor(null);}}><ChevronRight size={14}/></button></>}</span><small>{masked?'자동 가림 · 일부 누락 가능':visual?'원본 표시':'본문 표시 · 쪽 배치 미보존'}</small></div></div>
      <div className="flow-results">{contract?<>
          <div className="focus-progress"><div><small>현재 항목</small><strong>{batchMode?`값 대조 · ${DOCUMENT_LABEL[doc.document_type]} ${routineHere.length}개`:focusIndex>=0?`확인할 항목 ${focusIndex+1}/${navigation.length}`:'추가 항목 확인'}</strong></div><button className="text-button" aria-expanded={allRows} onClick={()=>setAllRows(value=>!value)}>전체 항목 {allRows?'접기':'보기'}<ChevronDown size={14}/></button></div>
          {allRows&&<nav className="focus-all-items" aria-label="전체 확인 항목">{navigation.map((item,index)=>{const meta=effectiveContext?.documents.find(p=>p.document_id===item.document?.document_id);const waiting=item.document&&requestStates[item.document.document_id];const status=item.deferral?'보류':waiting==='waiting'?'회신 대기':waiting==='draft'?'요청 초안':pendingTasks.some(task=>task.id===item.id)?'확인 필요':meta?.fields[item.field]?.human_confirmation?'확인 기록 있음':meta?.no_issue?.[item.field]?'판단 기록 있음':'원문 확인';return <button key={item.id} aria-current={item.id===`${doc.document_id}:${selected}`?'step':undefined} disabled={saving||reissuing} onClick={()=>{if(item.document)chooseRow({...item,document:item.document});else onOpenTask?.(item);}}><span>{index+1}. {item.document?DOCUMENT_LABEL[item.document.document_type]:item.missingType?DOCUMENT_LABEL[item.missingType]:'계약'} · {item.label}</span><small>{status}</small></button>;})}</nav>}
          <div className="focus-position" role="group" aria-label="항목 이동"><button className="button" disabled={saving||reissuing||focusIndex<=0} onClick={()=>onOpenTask?.(navigation[focusIndex-1])}><ChevronLeft size={14}/>이전 항목</button><span>이동만으로 확인이 저장되지 않습니다.</span><button className="button" disabled={saving||reissuing||focusIndex<0||focusIndex>=navigation.length-1} onClick={()=>onOpenTask?.(navigation[focusIndex+1])}>다음 항목<ChevronRight size={14}/></button></div>
        </>:<div className="flow-results-head"><strong>계약 전체의 확인 항목</strong><button className="text-button" onClick={()=>setAllRows(value=>!value)}>{allRows?'확인 남은 항목만 보기':'이 서류의 전체 값도 보기'}</button></div>}
        {contract&&<details className="focus-background"><summary>금액 기준·서류 변경 내역</summary><BillingSummary contract={contract} doc={doc}/>{version>=2&&<DocumentChangeSummary key={doc.document_id} doc={doc} comparison={activeComparison} loading={comparisonLoading||!activeComparison&&!compareError} error={compareError} masked={masked} selected={selected} busy={saving||reissuing} onSelect={selectField} onPrevious={onSelectDocument?()=>void openPrevious():undefined} onRetry={()=>setCompareReload(value=>value+1)}/>}</details>}
        {!contract&&version>=2&&<DocumentChangeSummary key={doc.document_id} doc={doc} comparison={activeComparison} loading={comparisonLoading||!activeComparison&&!compareError} error={compareError} masked={masked} selected={selected} busy={saving||reissuing} onSelect={selectField} onPrevious={onSelectDocument?()=>void openPrevious():undefined} onRetry={()=>setCompareReload(value=>value+1)}/>}
        {vlm.result&&!vlm.busy&&<div className="flow-ai-bar" role="status"><div><strong>{candidates.length?`현재 쪽의 AI 제안 ${candidates.length}개`:vlm.result.candidates.some(item=>item.usable)?'다시 읽기 완료 · 변경 없음':'다시 읽기 완료 · 적용할 값 없음'}</strong><small>{vlm.result?.model.name} · {vlm.result&&kst(vlm.result.created_at)}</small></div>{candidates.length>0&&<button className="button primary" disabled={!canAct||vlm.busy||!pickedFields.length} onClick={()=>void saveCandidates()}>원문 확인 후 {pickedFields.length}개 적용<Check size={13}/></button>}</div>}
        {batchMode&&<section className="flow-batch" ref={actionRef} aria-label="값 대조">
          <h3>{DOCUMENT_LABEL[doc.document_type]} · 값 대조 {routineHere.length}개</h3>
          <p>검사에서 걸린 값은 아니에요. 상신 전에 왼쪽 원문과 아래 값이 같은지 한 번에 확인해 주세요.</p>
          <ul>{routineHere.map(task=><li key={task.id}><button className="text-button" onClick={()=>showEvidence(task.field)}>{task.label}</button><strong>{displayValue(task.field,values[task.field],masked)}</strong>{editable&&<button className="text-button flow-batch-diff" disabled={saving} onClick={()=>{setSingleField(task.field);selectField(task.field);}}>다르게 적혀 있음</button>}</li>)}</ul>
          {batchReveal&&<p className="flow-reveal"><ShieldCheck size={14}/>가려진 값이 있어요. 가림을 끄고 대조하세요.{onToggleMasking&&<button className="text-button" onClick={onToggleMasking}>가림 끄기</button>}</p>}
          {editable&&<><label className="check-label"><input type="checkbox" checked={batchAck} disabled={saving||batchReveal} onChange={event=>setBatchAck(event.target.checked)}/>원문에서 위 값 {routineHere.length}개를 직접 확인했습니다.</label>
          <div className="flow-buttons"><button className="button primary" disabled={!canAct||!batchAck||batchReveal||saving} onClick={()=>void confirmBatch()}><Check size={14}/>{saving?'저장 중…':'모두 원문과 같음 · 저장'}</button></div></>}
          {saveError&&<p className="flow-read-error" role="alert">{saveError}</p>}
        </section>}
        {selected&&selectedRow&&!batchMode&&<section className="flow-action-panel" ref={actionRef} aria-label="선택한 항목 처리"><div className="flow-action-heading"><strong>{DOCUMENT_LABEL[doc.document_type]} · {label(selected)}</strong><span>{sourceLabel(proof)}</span>{editable&&<div className="flow-item-menu" ref={menuRef}><button className="icon-button" aria-label="선택 항목 더보기" aria-haspopup="menu" aria-expanded={itemMenu} onClick={()=>setItemMenu(value=>!value)}><MoreHorizontal size={18}/></button>{itemMenu&&<div className="dropdown" role="menu">{visual&&vlmOn&&<button role="menuitem" disabled={!readyToRead} onClick={()=>read(selected)}>이 값 AI로 다시 읽기</button>}{selected!=='__document__'&&<button role="menuitem" disabled={!canAct||requiresReveal(selected)} onClick={beginEdit}>값 직접 수정</button>}<button role="menuitem" disabled={!canAct} onClick={()=>{setTypeOpen(true);setCorrectType(doc.document_type);setTypeNote('');setItemMenu(false);}}>서류 종류 수정</button><button role="menuitem" onClick={()=>{setBasisOpen(true);setItemMenu(false);}}>비교 기준 확인</button><button role="menuitem" onClick={()=>{setDeferKind('DEFER');setDeferNote(deferral?.note||'');setDeferOpen(true);setEditing(false);setItemMenu(false);}}>판단 보류</button><button role="menuitem" onClick={()=>{setReissueOpen(true);setItemMenu(false);}}>수정본 올리기</button></div>}</div>}</div>
          {requestHint&&<p className="flow-context-hint" role="status">{protectText(requestHint)}</p>}
          {vlm.busy&&<p role="status" className="flow-inline-loading"><Loader2 size={15} className="spin"/>현재 쪽을 다시 읽고 있어요.</p>}
          {vlm.error&&<div className="flow-read-error" role="alert"><p>{vlm.error}</p><button className="button" disabled={!readyToRead} onClick={()=>read(selected)}>AI 다시 시도</button></div>}
          {deferral&&<p className="flow-deferral">{contract?'판단 보류 중':'보류'} · {protectText(deferral.note)} <button className="text-button" disabled={saving} onClick={()=>void saveDeferral(true)}>{contract?'보류 해제·다시 검토':'보류 해제'}</button></p>}
          {basisOpen&&<div className="flow-basis">{selectedRow.checks.length?selectedRow.checks.map(check=><p key={check.rule_id}>{protectText(check.message)}{check.expected&&<small>기준 {criterion(selected,check.expected,masked)}</small>}</p>):<p>이 항목에 연결된 자동 검사 기준이 없어요.</p>}{onCheckBasis&&<button className="button" onClick={onCheckBasis}>기존 계약 정보 확인·수정</button>}</div>}
          {typeOpen&&<form className="flow-editor" onSubmit={saveDocumentType}><label>원문에 적힌 서류 종류<select aria-label="서류 종류 수정" value={correctType} disabled={saving} onChange={event=>setCorrectType(event.target.value as DocumentType)}>{Object.entries(DOCUMENT_LABEL).map(([kind,name])=><option key={kind} value={kind}>{name}</option>)}</select></label><label>수정 사유<input aria-label="서류 종류 수정 사유" value={typeNote} disabled={saving} maxLength={1000} onChange={event=>setTypeNote(event.target.value)}/></label><div className="flow-buttons"><button type="button" className="button" disabled={saving} onClick={()=>setTypeOpen(false)}>취소</button><button className="button primary" disabled={!canAct||correctType===doc.document_type||correctType==='unknown'||!typeNote.trim()}>서류 종류 저장</button></div></form>}
          {contract?<>
            {selected==='__document__'?classification?<div><p>원문에 적힌 서류 종류를 확인하세요.</p><button className="button primary" disabled={!canAct} onClick={()=>{setTypeOpen(true);setCorrectType(doc.document_type);}}>서류 종류 수정</button></div>:<ReadingRecovery failed canReissue={editable} onReissue={()=>setReissueOpen(true)}/>:<FocusedItemActions action={focusAction} onAction={action=>{setFocusAction(action);setEditing(action==='correct');setDeferOpen(false);setBasisOpen(false);setNote('');setSaveError('');}} busy={saving||reissuing} canAct={canAct} editable={editable} reveal={requiresReveal(selected)} hasValue={hasValue(values[selected])} confirmed={!!proof?.human_confirmation} issues={issues.length>0} noIssue={!!noIssue} technical={false} value={displayValue(selected,values[selected],masked)} label={label(selected)} reason={issues.length?protectText(issues.map(check=>check.message).join(' · ')):hasValue(values[selected])?'원문과 읽은 값이 같은지 확인하세요.':'읽지 못한 값을 원문에서 확인하세요.'} lookAt={LOOK_AT[selected]||`'${label(selected)}' 부분`} basis={selected.endsWith('amount')?`${contract.workflow?.amount_basis==='SUPPLY'?'공급가액':contract.workflow?.amount_basis==='TOTAL'?'부가세 포함 합계':'금액 기준 미확인'} · ${Number(contract.contract_amount).toLocaleString('ko-KR')}원`:selected==='company_name'?displayValue(selected,contract.vendor_name,masked):selected==='business_registration_no'?displayValue(selected,contract.business_number,masked):null} expected={selectedRow.expected?criterion(selected,selectedRow.expected,masked):null} onCorrect={beginEdit} onRequest={onRequest?()=>onRequest(doc.document_id):undefined} onBasis={onCheckBasis} onConfirm={()=>void confirmField()} onAccept={()=>{setDeferKind('NO_ISSUE');setDeferNote('');setDeferOpen(true);}} onReveal={onToggleMasking} form={editing?<form ref={editRef} className="flow-editor" onSubmit={saveEdit}><label>원문에 적힌 {label(selected)}{selected==='amount_scope'?<select aria-label={`${label(selected)} 수정값`} value={editValue} onChange={event=>setEditValue(event.target.value)}><option value="UNKNOWN">미확인</option><option value="FULL">전액 청구</option><option value="PARTIAL">일부 청구</option></select>:<input aria-label={`${label(selected)} 수정값`} type={selected.endsWith('amount')?'number':'text'} min={selected.endsWith('amount')?0:undefined} step="any" value={editValue} disabled={saving} onChange={event=>setEditValue(event.target.value)}/>}</label><label>수정 사유<input aria-label="수정 사유" value={note} disabled={saving} maxLength={1000} onChange={event=>setNote(event.target.value)}/></label><div className="flow-buttons"><button type="button" className="button" disabled={saving} onClick={()=>setEditing(false)}>취소</button><button className="button primary" disabled={!canAct||requiresReveal(selected)||!editValue.trim()||!note.trim()}>원문 값으로 저장</button></div></form>:deferOpen&&deferKind==='NO_ISSUE'?<form className="flow-editor" onSubmit={event=>{event.preventDefault();void saveDeferral();}}><label>{deferKind==='NO_ISSUE'?'문제가 아니라고 판단한 이유':'나중에 확인할 내용'}<input aria-label={deferKind==='NO_ISSUE'?'문제 없음 판단 이유':'보류할 내용'} placeholder={deferKind==='NO_ISSUE'?'예: 거래처와 통화해 잔금 문구 오기재, 금액은 계약대로 확인':undefined} value={deferNote} disabled={saving} maxLength={1000} onChange={event=>setDeferNote(event.target.value)}/></label><div className="flow-buttons"><button type="button" className="button" disabled={saving} onClick={()=>setDeferOpen(false)}>취소</button><button className="button primary" disabled={saving||!deferNote.trim()}>{deferKind==='NO_ISSUE'?'문제 없음으로 기록':'판단 보류'}</button></div></form>:null}/>} 
            {noIssue&&<p className="flow-no-issue"><strong>현재 판단 근거</strong> {protectText(noIssue.note)} <small>{noIssue.actor_name} · {kst(noIssue.at)}</small>{editable&&<button className="text-button" disabled={saving} onClick={()=>void saveDeferral(true)}>판단 기록 취소</button>}</p>}
            {deferOpen&&[deferKind].includes('DEFER')&&<form className="flow-editor" onSubmit={event=>{event.preventDefault();void saveDeferral();}}><label>{deferKind==='NO_ISSUE'?'문제가 아니라고 판단한 이유':'나중에 확인할 내용'}<input aria-label={deferKind==='NO_ISSUE'?'문제 없음 판단 이유':'보류할 내용'} placeholder={deferKind==='NO_ISSUE'?'예: 거래처와 통화해 잔금 문구 오기재, 금액은 계약대로 확인':undefined} value={deferNote} disabled={saving} maxLength={1000} onChange={event=>setDeferNote(event.target.value)}/></label><div className="flow-buttons"><button type="button" className="button" disabled={saving} onClick={()=>setDeferOpen(false)}>취소</button><button className="button primary" disabled={saving||!deferNote.trim()}>{deferKind==='NO_ISSUE'?'문제 없음으로 기록':'판단 보류'}</button></div></form>}
            {!hasValue(values[selected])&&provenance?.ai_review?.manual_review_required&&editable&&<button className="text-button" disabled={!canAct||requiresReveal(selected)} onClick={()=>void confirmAbsent()}>원문에도 없음 확인</button>}
          </>:typeOpen?null:deferOpen?<form className="flow-editor" onSubmit={event=>{event.preventDefault();void saveDeferral();}}><label>{deferKind==='NO_ISSUE'?'문제가 아니라고 판단한 이유':'나중에 확인할 내용'}<input aria-label={deferKind==='NO_ISSUE'?'문제 없음 판단 이유':'보류할 내용'} placeholder={deferKind==='NO_ISSUE'?'예: 거래처와 통화해 잔금 문구 오기재, 금액은 계약대로 확인':undefined} value={deferNote} disabled={saving} maxLength={1000} onChange={event=>setDeferNote(event.target.value)}/></label><div className="flow-buttons"><button type="button" className="button" disabled={saving} onClick={()=>setDeferOpen(false)}>취소</button><button className="button primary" disabled={saving||!deferNote.trim()}>{deferKind==='NO_ISSUE'?'문제 없음으로 기록':'판단 보류'}</button></div></form>:editing?<form ref={editRef} className="flow-editor" onSubmit={saveEdit}><label>원문에 적힌 {label(selected)}{selected==='amount_scope'?<select aria-label={`${label(selected)} 수정값`} value={editValue} onChange={event=>setEditValue(event.target.value)}><option value="UNKNOWN">미확인</option><option value="FULL">전액 청구</option><option value="PARTIAL">일부 청구</option></select>:<input aria-label={`${label(selected)} 수정값`} type={selected.endsWith('amount')?'number':'text'} min={selected.endsWith('amount')?0:undefined} step="any" value={editValue} disabled={saving} onChange={event=>setEditValue(event.target.value)}/>}</label><label>수정 사유<input aria-label="수정 사유" value={note} disabled={saving} maxLength={1000} onChange={event=>setNote(event.target.value)}/></label><div className="flow-buttons"><button type="button" className="button" disabled={saving} onClick={()=>setEditing(false)}>취소</button><button className="button primary" disabled={!canAct||requiresReveal(selected)||!editValue.trim()||!note.trim()}>원문 값으로 저장</button></div></form>:selected==='__document__'?classification?<div><p className="flow-question">서류 종류를 확인해 주세요.</p><p className="flow-context-hint">현재 분류: {DOCUMENT_LABEL[doc.document_type]}</p>{editable&&<button className="button primary" disabled={!canAct} onClick={()=>{setTypeOpen(true);setCorrectType(doc.document_type);setTypeNote('');}}>서류 종류 수정</button>}</div>:<ReadingRecovery failed canReissue={editable} onReissue={()=>setReissueOpen(true)}/>:candidates.length?null:<>
            {requiresReveal(selected)&&<p className="flow-reveal"><ShieldCheck size={14}/>가려진 항목은 가림을 끄고 확인하세요.{onToggleMasking&&<button className="text-button" onClick={onToggleMasking}>가림 끄기</button>}</p>}
            {issues.length>0&&<div className="flow-issue-reason" role="note"><strong>{needsDecision?'원문은 확인했어요 · 남은 문제':'무엇이 문제인가요'}</strong>{issues.map(check=><p key={check.rule_id}>{protectText(check.message)}</p>)}</div>}
            {selected!=='__document__'&&<p className="flow-look-at"><span>원문에서 볼 곳</span>{LOOK_AT[selected]||`원문의 '${label(selected)}' 부분`}</p>}
            {!noIssue&&<p className="flow-question">{needsDecision?'원인에 맞는 처리를 하나 고르세요.':hasValue(values[selected])?(requiresReveal(selected)?'원문에도 이 값이 적혀 있나요?':`원문에 '${displayValue(selected,values[selected],masked)}'(으)로 적혀 있나요?`):`원문에서 '${label(selected)}' 값을 확인할 수 있나요?`}</p>}
            {noIssue&&<p className="flow-no-issue"><strong>문제 없음으로 기록됨</strong> {protectText(noIssue.note)} <small>{noIssue.actor_name} · {kst(noIssue.at)}</small>{editable&&<button className="text-button" disabled={saving} onClick={()=>void saveDeferral(true)}>기록 취소</button>}</p>}
            {editable&&needsDecision&&!noIssue&&<ul className="flow-choices" aria-label="원인별 처리 방법">
              <li><span>거래처가 잘못 적었다면</span>{onRequest?<button className="button" disabled={!canAct||requiresReveal(selected)} onClick={()=>onRequest(doc.document_id)}>정정 요청에 담기</button>:<button className="button" disabled={!canAct} onClick={()=>setReissueOpen(true)}>고친 서류 올리기</button>}</li>
              <li><span>앱이 잘못 읽었다면</span><button className="button" disabled={!canAct||requiresReveal(selected)} onClick={beginEdit}><Pencil size={13}/>읽은 값 고치기</button></li>
              <li><span>계약 정보가 틀렸다면</span><button className="button" onClick={()=>onCheckBasis?onCheckBasis():setBasisOpen(true)}>계약 기준 고치기</button></li>
              {!deferral&&<li><span>아직 판단하기 어렵다면</span><button className="button" onClick={()=>{setDeferKind('DEFER');setDeferNote('');setDeferOpen(true);setEditing(false);}}>판단 보류</button></li>}
              <li className="flow-choice-ok"><span>모두 맞다면 (오류가 아니라면)</span><button className="button" disabled={!canAct} onClick={()=>{setDeferKind('NO_ISSUE');setDeferNote('');setDeferOpen(true);setEditing(false);}}>문제 없음으로 기록</button></li>
            </ul>}
            {editable&&!noIssue&&<div className="flow-buttons">{needsDecision?null:<><button className="button primary" disabled={!canAct||requiresReveal(selected)} onClick={beginEdit}><Pencil size={13}/>{hasValue(values[selected])?'다르게 적혀 있어요 · 값 수정':'직접 입력'}</button>{hasValue(values[selected])&&<button className="button" disabled={!canAct||requiresReveal(selected)||!!proof?.human_confirmation||!provenance} onClick={()=>void confirmField()}>{mismatch?'원문에도 이 값이에요':'원문과 같음'}</button>}</> }</div>}
            {!hasValue(values[selected])&&editable&&visual&&vlmOn&&<button className="text-button flow-single-read" disabled={!readyToRead} title={vlm.status?.message} onClick={()=>read(selected)}><Search size={13}/>AI로 다시 읽기</button>}
            {!hasValue(values[selected])&&provenance?.ai_review?.manual_review_required&&editable&&<button className="text-button" disabled={!canAct||requiresReveal(selected)} onClick={()=>void confirmAbsent()}>원문에도 없음 확인</button>}
          </>}
          {vlm.result&&selected&&vlm.result.candidates.some(item=>item.field===selected)&&<><button className="text-button flow-quote-button" aria-expanded={quoteOpen} onClick={()=>setQuoteOpen(value=>!value)}>AI 문구 보기<ChevronDown size={12}/></button>{quoteOpen&&<p className="flow-quote">{requiresReveal(selected)?'가림 정보가 포함된 문구입니다.':vlm.result.candidates.find(item=>item.field===selected)?.quote}<small>AI 문구는 검증된 원문 근거가 아닙니다.</small></p>}</>}
          {!!proof?.evidence?.length&&<button className="text-button flow-evidence" onClick={()=>showEvidence(selected)}>원문 위치 보기</button>}
        </section>}
        {effectiveError?<p className="flow-read-error" role="alert">{effectiveError}<button className="text-button" onClick={()=>void refreshEvidence()}>확인 기록 다시 불러오기</button></p>:!provenance?<p className="flow-loading" role="status">원문 확인 기록 조회 중…</p>:contract?null:tableRows.length?<ReviewFieldTable rows={tableRows} doc={doc} selected={selected} requestStates={requestStates} proofs={doc.version?.is_current===false&&historical?[historical]:effectiveContext?.documents||[]} masked={masked} busy={saving||reissuing} candidates={candidates} picked={picked} canPick={field=>canAct&&!vlm.busy&&!requiresReveal(field)&&!!candidates.find(item=>item.field===field)?.usable} onPick={field=>setPicked(old=>{const next=new Set(old);next.has(field)?next.delete(field):next.add(field);return next;})} onSelect={chooseRow}/>:<div className="flow-empty"><Check size={25}/><strong>현재 확인할 항목을 정리했어요</strong><button className="text-button" onClick={()=>setAllRows(true)}>이 서류의 전체 값 보기</button></div>}
        {!contract&&tasks.filter(task=>!task.document).map(task=><button key={task.id} className="flow-related-task" onClick={()=>onOpenTask?onOpenTask(task):task.missingType?onUploadType?.(task.missingType):onCheckBasis?.()}>{task.missingType?DOCUMENT_LABEL[task.missingType]:'계약'} · {task.label}<ChevronRight size={13}/></button>)}
        <details className="flow-details"><summary>원본·버전·전체 값</summary><small>{doc.original_file_name}</small>{rows.map(row=><button className="flow-optional-value" key={row.key} onClick={()=>selectField(row.key)}>{row.label}<span>{displayValue(row.key,values[row.key],masked)}</span></button>)}{versions.length>1&&<select aria-label="서류 버전" value={doc.document_id} onChange={event=>{void api.getDocument(Number(event.target.value)).then(item=>onSelectDocument?.(item)).catch(reason=>setSaveError(reason.message));}}>{versions.map(item=><option key={item.document_id} value={item.document_id}>{item.version_number}차본{item.is_current?' · 현재':' · 이전'}</option>)}</select>}{versionsError&&<p role="alert">{versionsError}</p>}<button className="text-button" onClick={()=>void downloadProtected(`/api/documents/${doc.document_id}/download?masked=true`,doc.original_file_name)}><Download size={13}/>가린 원본 받기</button></details>
        {saveError&&<p className="flow-read-error" role="alert">{saveError}</p>}<footer className="flow-queue-footer"><strong>{queuedRequests?`요청에 담긴 서류 ${queuedRequests}종`:`${effectiveContext?`문제 ${pendingTasks.filter(task=>!task.routine).length}건 · 값 대조 ${pendingTasks.filter(task=>task.routine).length}건`:'확인 목록 조회 중'}`}</strong><button className="button primary" disabled={saving||reissuing||!effectiveContext} onClick={()=>queuedRequests&&onOpenRequestDraft?onOpenRequestDraft():nextTask&&onOpenTask?onOpenTask(nextTask):onClose()}>{queuedRequests?'요청 내용 작성':nextTask?(contract?'다음 확인할 항목 보기':'확인 계속하기'):(contract?'검토 요약 보기':'서류 목록')}<ChevronRight size={14}/></button></footer>
      </div></div>
    {undo&&<div className="review-undo" role="status"><span>{undo.label} 원문 확인 기록</span><button className="text-button" disabled={saving} onClick={()=>void undoConfirmation()}>되돌리기</button></div>}{notice&&<div className="review-notice" role="status">{notice}</div>}
  </section>;
};
