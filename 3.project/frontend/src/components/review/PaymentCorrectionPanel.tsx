import {useEffect,useRef,useState} from 'react';
import {ContractDetail,ContractPayment} from '../../types';
import {requestJson} from '../../api/client';
import {Surface} from '../ui/Surface';
import {seoulToday} from '../../utils/date';

export function PaymentCorrectionPanel({contract,payment,onClose,onChanged}:{contract:ContractDetail;payment:ContractPayment;onClose:()=>void;onChanged:()=>Promise<void>}){
 const [action,setAction]=useState<'CORRECT'|'VOID'>('CORRECT');
 const [paidOn,setPaidOn]=useState(payment.recorded_paid_on),[method,setMethod]=useState(payment.method),[note,setNote]=useState(payment.note),[reason,setReason]=useState('');
 const [basis,setBasis]=useState({workflow:contract.workflow,payment:payment as ContractPayment|null});
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[saved,setSaved]=useState(false);
 const [conflict,setConflict]=useState(false),[needsLatest,setNeedsLatest]=useState(false),[latestAck,setLatestAck]=useState(false);
 const panel=useRef<HTMLDivElement>(null),alive=useRef(true),readEpoch=useRef(0);
 const propVersion=[contract.workflow?.revision,contract.workflow?.fingerprint,payment.payment_id,payment.status,payment.correction_revision??0].join('|');
 const lastPropVersion=useRef(propVersion);
 useEffect(()=>{alive.current=true;panel.current?.scrollIntoView({block:'center'});panel.current?.focus();return()=>{alive.current=false;readEpoch.current++;};},[]);
 // A parent refresh must not remount this panel or discard any of the user's draft.
 useEffect(()=>{
  if(lastPropVersion.current===propVersion)return;
  lastPropVersion.current=propVersion;
  readEpoch.current++;
  setBasis({workflow:contract.workflow,payment});setConflict(true);setLatestAck(false);setNeedsLatest(false);
 },[propVersion,contract.workflow,payment]);
 const readLatest=async()=>{
  const epoch=++readEpoch.current;
  setNeedsLatest(true);setLatestAck(false);
  try{
   const latest=await requestJson<ContractDetail>(`/api/contracts/${contract.contract_id}`);
   if(!alive.current||epoch!==readEpoch.current)return;
   setBasis({workflow:latest.workflow,payment:latest.payment??null});setNeedsLatest(false);
  }catch(e){if(alive.current&&epoch===readEpoch.current)setError(`최신 지급 기록 조회에 실패했습니다. 작성한 내용은 유지됩니다. ${e instanceof Error?e.message:''}`);}
 };
 const refreshSaved=async()=>{
  setBusy(true);
  try{await onChanged();if(alive.current)onClose();}
  catch(e){if(alive.current)setError(`정정은 저장됐지만 최신 화면 조회에 실패했습니다. 다시 저장하지 말고 화면을 갱신해 주세요. ${e instanceof Error?e.message:''}`);}
  finally{if(alive.current)setBusy(false);}
 };
 const save=async()=>{
  if(busy||saved||needsLatest||(conflict&&!latestAck)||!basis.payment||basis.payment.status==='VOIDED')return;
  setBusy(true);setError('');
  try{
   await requestJson(`/api/pilot/contracts/${contract.contract_id}/payment/${basis.payment.payment_id}/corrections`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,revision:basis.workflow?.revision,fingerprint:basis.workflow?.fingerprint,payment_revision:basis.payment.correction_revision??0,reason,paid_on:action==='CORRECT'?paidOn:null,method:action==='CORRECT'?method:null,note})});
  }catch(e){
   if(!alive.current)return;
   setError(e instanceof Error?e.message:'정정하지 못했습니다.');
   if(e instanceof Error&&'status' in e&&e.status===409){setConflict(true);await readLatest();}
   if(alive.current)setBusy(false);
   return;
  }
  if(!alive.current)return;
  setSaved(true);
  await refreshSaved();
 };
 const unavailable=!basis.payment||basis.payment.status==='VOIDED';
 return <div ref={panel} tabIndex={-1}><Surface title="지급 기록 정정"><div className="story-form form-fields">
  <p>기존 기록과 정정 사유는 처리 기록에 보존됩니다.</p>
  <label>정정할 내용<select value={action} disabled={busy||saved} onChange={e=>setAction(e.target.value as typeof action)}><option value="CORRECT">지급일·방법·메모 수정</option><option value="VOID">잘못된 지급 완료 기록 취소</option></select></label>
  {action==='CORRECT'?<><label>지급일<input disabled={busy||saved} type="date" max={seoulToday()} value={paidOn} onChange={e=>setPaidOn(e.target.value)}/></label><label>지급 방법<select disabled={busy||saved} value={method} onChange={e=>setMethod(e.target.value as typeof method)}><option value="TRANSFER">계좌이체</option><option value="OTHER">기타</option></select></label><label>메모<input disabled={busy||saved} value={note} maxLength={2000} onChange={e=>setNote(e.target.value)}/></label></>:<p className="story-alert">지급 완료 상태를 취소합니다. 실제 송금은 취소되지 않습니다.</p>}
  <label>정정 사유<textarea disabled={busy||saved} value={reason} maxLength={2000} onChange={e=>setReason(e.target.value)} placeholder="잘못 기록한 내용을 3자 이상 입력하세요."/></label>
  {conflict&&!saved&&<div className="story-alert" role="status">
   <p>지급 기록이 바뀌었습니다. 작성한 지급일·방법·메모·사유는 유지했습니다.</p>
   {!needsLatest&&<>{basis.payment?<p>최신 기록: {basis.payment.recorded_paid_on} · {basis.payment.method==='TRANSFER'?'계좌이체':'기타'} · {basis.payment.note} · {basis.payment.status==='VOIDED'?'취소됨':`버전 ${basis.payment.correction_revision??0}`}</p>:<p>현재 지급 기록이 없습니다.</p>}
    {unavailable?<p>현재 상태에서는 이 기록을 정정할 수 없습니다. 사유를 확인한 뒤 닫아 주세요.</p>:<label className="check-label"><input type="checkbox" checked={latestAck} disabled={busy} onChange={e=>setLatestAck(e.target.checked)}/>최신 지급 내용을 확인했으며 작성한 내용으로 정정합니다</label>}</>}
   <button className="button" disabled={busy} onClick={async()=>{setBusy(true);await readLatest();if(alive.current)setBusy(false);}}>최신 지급 기록 다시 불러오기</button>
  </div>}
  {error&&<p role="alert" className="story-alert">{error}</p>}
 </div><div className="panel-footer"><button className="button" disabled={busy} onClick={onClose}>닫기</button>{saved?<button className="button primary" disabled={busy} onClick={()=>void refreshSaved()}>저장한 내용으로 화면 갱신</button>:<button className="button primary" disabled={busy||needsLatest||unavailable||(conflict&&!latestAck)||reason.trim().length<3||(action==='CORRECT'&&(!paidOn||paidOn>seoulToday()))} onClick={()=>void save()}>{busy?'저장 중…':action==='VOID'?'지급 완료 기록 취소':'지급 기록 정정 저장'}</button>}</div></Surface></div>;
}
