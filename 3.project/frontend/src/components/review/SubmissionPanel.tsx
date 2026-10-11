import {useEffect,useRef,useState} from 'react';
import {ArrowRight,CheckCircle2,Clock3,Send} from 'lucide-react';
import {ContractDetail,ReviewBlocker} from '../../types';
import {requestJson} from '../../api/client';
import {useAuth} from '../../context/AuthContext';
import {Badge,Surface} from '../ui/Surface';
import {maskBusinessNumber,maskResidentNumber} from '../../utils/masking';
import {kst} from './ActivityTimeline';
import type {ApprovalState} from './ApprovalPanel';

interface Props {contract:ContractDetail;masked:boolean;onChanged:()=>Promise<void>;onOpen:(item:ReviewBlocker)=>void;onApproval:()=>void;}

/** The hand-off is a saved server action. A copied message is never a submission. */
export function SubmissionPanel({contract,masked,onChanged,onOpen,onApproval}:Props){
  const {user}=useAuth();
  const wf=contract.workflow,submission=wf?.submission,gate=submission?.gate;
  const [note,setNote]=useState(''),[exception,setException]=useState(''),[ack,setAck]=useState(false);
  const [workCompleted,setWorkCompleted]=useState(false);
  const [busy,setBusy]=useState(false),[saved,setSaved]=useState(false),[error,setError]=useState('');
  const [steps,setSteps]=useState<ApprovalState['steps']|null>(null),[policyError,setPolicyError]=useState('');
  const lock=useRef(false),attempt=useRef<{signature:string;key:string}|null>(null);
  const active=useRef(contract.contract_id);active.current=contract.contract_id;
  const previousContract=useRef(contract.contract_id);
  const basis=[contract.contract_id,wf?.revision,wf?.fingerprint,gate?.fingerprint,submission?.status].join('|');
  useEffect(()=>{
    if(previousContract.current!==contract.contract_id){setNote('');setException('');setError('');previousContract.current=contract.contract_id;}
    setAck(false);setWorkCompleted(false);setSaved(false);attempt.current=null;
  },[basis]);
  useEffect(()=>{
    const controller=new AbortController();setSteps(null);setPolicyError('');
    void requestJson<ApprovalState>(`/api/pilot/contracts/${contract.contract_id}/approvals`,{signal:controller.signal}).then(value=>{if(!controller.signal.aborted&&Array.isArray(value.steps))setSteps(value.steps);}).catch(()=>{if(!controller.signal.aborted)setPolicyError('결재 단계 설정을 조회하지 못했습니다. 결재 화면에서 최신 설정을 확인하세요.');});
    return()=>controller.abort();
  },[contract.contract_id,contract.updated_at,wf?.revision,wf?.fingerprint]);
  if(!wf||!submission||!gate)return null;
  const canEdit=user?.role==='operator'||user?.role==='admin';
  const approved=wf.approval_status==='CONFIRMED';
  const pending=submission.current&&!approved;
  const returned=submission.status==='RETURNED';
  const stale=submission.status==='STALE'||wf.approval_status==='STALE'&&!pending;
  const ready=gate.can_submit;
  const display=(text:string)=>masked?maskResidentNumber(maskBusinessNumber(text)):text;
  const send=async()=>{
    if(lock.current||saved||!canEdit||gate.blockers.length||note.trim().length<3)return;
    if(gate.exception_items.length&&(!ack||exception.trim().length<10))return;
    if(gate.requires_work_confirmation&&!workCompleted)return;
    lock.current=true;setBusy(true);setError('');
    const cid=contract.contract_id;
    const body={review_cycle:wf.reviews[0]?.review_id??0,revision:wf.revision,fingerprint:wf.fingerprint,note:note.trim(),
      exception_reason:gate.exception_items.length?exception.trim():'',
      acknowledge_exception:gate.exception_items.length?ack:false,
      acknowledge_work_completed:gate.requires_work_confirmation?workCompleted:false,
      exception_items:gate.exception_items.map(item=>item.key)};
    const signature=JSON.stringify({...body,gate:gate.fingerprint});
    if(attempt.current?.signature!==signature)attempt.current={signature,key:typeof crypto.randomUUID==='function'?crypto.randomUUID():`${Date.now()}-${Math.random().toString(36).slice(2)}`};
    try{
      await requestJson(`/api/pilot/contracts/${cid}/submission`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...body,idempotency_key:attempt.current.key})});
      if(active.current!==cid)return;
      setSaved(true);
      try{await onChanged();}catch{if(active.current===cid)setError('상신은 저장했습니다. 최신 화면을 다시 불러오세요. 중복 상신하지 마세요.');}
    }catch(e){
      if(active.current!==cid)return;
      setError(e instanceof Error?e.message:'상신하지 못했습니다. 최신 상태를 확인하세요.');
      setAck(false);
      try{await onChanged();}catch{if(active.current===cid)setError('처리 결과를 확인하지 못했습니다. 최신 화면을 불러온 후 다시 확인하세요.');}
    }finally{lock.current=false;if(active.current===cid)setBusy(false);}
  };
  const reading=gate.blockers.some(b=>['READING_FAILED','READING_INCOMPLETE','SOURCE_UNVERIFIED'].includes(b.code));
  const missing=gate.blockers.some(b=>b.code==='MISSING_DOCUMENT');
  const title=approved?'대표 승인 완료':pending?'대표 결재 대기':returned?'반려 · 담당자 재검토':stale?'자료 변경 · 재검토·재상신 필요':reading?'읽지 못함 · 원본·판독 확인 필요':missing?'서류 누락 · 보완 필요':gate.blockers.some(b=>b.code==='WAITING_VENDOR')?'거래처 회신 대기':ready?'담당자 검토 완료·결재 상신':!gate.blockers.length&&gate.exception_items.some(i=>i.status==='FAIL')?'실제 불일치 · 보완 판단':'담당자 원문 확인';
  return <Surface title={title} action={<Badge tone={approved?'green':pending?'violet':ready?'blue':'amber'}>{approved?'승인 완료':pending?'다음 담당자: 대표':'현재 담당자: 담당자'}</Badge>} className="submission-panel">
    <div className="submission-body">
      <p className="focus-policy">{steps?.length===1?'공식 결재: 대표 1단계 · 담당자의 서류 준비·검토·결재 요청은 공식 1차 결재가 아닙니다.':steps?.length===2?'공식 결재: 담당 검토 1차 → 대표 최종 2차 · 현재 설정에서는 담당자의 상신이 1차 결재도 기록합니다.':'공식 결재 단계 설정 조회 중…'}</p>
      <ol className={`submission-flow${steps?.length===1?' single-approval':''}`} aria-label="준비와 결재 진행"><li className={approved||pending?'complete':'active'}>{steps?.length===2?'담당 검토·1차 결재':'담당자 준비·결재 요청'}</li><li className={approved?'complete':pending?'active':''}>{steps?.length===2?'대표 최종·2차 결재':'대표 최종 결재'}</li></ol>
      {policyError&&<p role="alert">{policyError}</p>}
      {approved?<p><CheckCircle2 size={17}/> 대표 승인을 기록했습니다. 자료가 바뀌면 담당자 재검토와 재상신이 필요합니다.</p>:pending?<><p><Clock3 size={17}/> {submission.actor_name} 담당자가 {kst(submission.submitted_at||'')} 상신했습니다. 다음 행동은 대표의 승인 또는 사유를 남긴 반려입니다.</p><p className="review-note">검토 의견: {display(submission.note||'')}</p>{submission.exception_reason&&<p className="story-alert">예외 검토 요청 {submission.exception_items.length}건 · {display(submission.exception_reason)}<br/>자동 검사 결과는 유지됩니다. 대표가 사유와 항목을 확인한 후 판단합니다.</p>}<button className="button" onClick={onApproval}>결재 요약·의견 보기<ArrowRight size={14}/></button></>:<>
        {returned&&<p className="story-alert">반려 사유: {display(wf.reviews.find(r=>r.decision==='RETURNED')?.note||'결재 이력에서 사유를 확인하세요.')}<br/>필요한 자료를 고치고 검토 의견을 다시 기록해 재상신하세요.</p>}
        {stale&&<p className="story-alert">이전 상신·결재는 변경 전 자료의 기록입니다. 변경된 원문과 아래 항목을 확인한 후 재상신하세요.</p>}
        <p>{gate.completion}</p>
        {gate.blockers.length>0&&<div className="submission-blockers"><strong>지금 상신할 수 없는 이유 · {gate.blockers.length}건</strong><ul>{gate.blockers.slice(0,1).map((item,i)=><li key={`${item.code}:${item.document_id}:${item.field}:${i}`}><div><strong>{item.label}</strong><small>{item.reason}</small></div><button className="button" onClick={()=>onOpen(item)}>{item.action}<ArrowRight size={13}/></button></li>)}</ul>{gate.blockers.length>1&&<details><summary>남은 {gate.blockers.length-1}건 보기</summary><ul>{gate.blockers.slice(1).map((item,i)=><li key={i}><div><strong>{item.label}</strong><small>{item.reason}</small></div><button className="button" onClick={()=>onOpen(item)}>{item.action}</button></li>)}</ul></details>}</div>}
        {canEdit&&gate.blockers.length===0&&<div className="submission-form">
          {gate.requires_work_confirmation&&<label className="check-label"><input type="checkbox" checked={workCompleted} disabled={busy||saved} onChange={e=>setWorkCompleted(e.target.checked)}/>실제 납품·용역 검수가 완료된 것을 확인했습니다.</label>}
          <label>담당자 검토 의견<textarea rows={2} maxLength={2000} value={note} onChange={e=>setNote(e.target.value)} placeholder="실제 업무 확인 근거와 대표에게 전달할 내용 (3자 이상)"/></label>
          {gate.exception_items.length>0&&<details className="submission-exception"><summary>일반 상신을 막는 불일치·미확인 {gate.exception_items.length}건 · 예외 검토 요청</summary><p>먼저 오독 정정·실제 보완을 진행하세요. 근거가 있어도 해결할 수 없는 업무상 예외만 사유를 남겨 대표 판단을 요청합니다. 판독 실패·필수 검토 누락은 이 경로로 넘길 수 없습니다.</p><ul>{gate.exception_items.map(item=><li key={item.key}>{display(item.reason)}</li>)}</ul><label>예외 상신 사유<textarea rows={3} maxLength={2000} value={exception} onChange={e=>setException(e.target.value)} placeholder="남은 각 항목의 사유와 확인 근거 (10자 이상)"/></label><label className="check-label"><input type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)}/>위 항목이 미해결임을 확인했고 대표의 예외 판단을 요청합니다.</label></details>}
          <div className="submission-footer"><span>{gate.blockers.length?'위 필수 검토·회신 처리를 먼저 완료하세요.':gate.exception_items.length?'불일치·미확인은 자동으로 해결되지 않습니다.':'상신하면 대표 결재 대기로 바뀝니다.'}</span><button className="button primary" disabled={busy||saved||note.trim().length<3||gate.blockers.length>0||gate.requires_work_confirmation&&!workCompleted||gate.exception_items.length>0&&(!ack||exception.trim().length<10)} onClick={()=>void send()}><Send size={15}/>{busy?'상신 저장 중…':saved?'상신 저장 완료':gate.exception_items.length?'예외 검토 요청·상신':returned||stale?'검토 완료·재상신':'검토 완료·결재 상신'}</button></div>
        </div>}
        {!canEdit&&<p className="review-note">담당자가 원문 검토와 상신을 완료해야 대표가 결재할 수 있습니다.</p>}
      </>}
      {error&&<p role="alert" className="story-alert">{error}<button className="text-button" disabled={busy} onClick={()=>void onChanged().catch(()=>setError('최신 화면을 불러오지 못했습니다. 다시 시도하세요.'))}>최신 화면 불러오기</button></p>}
    </div>
  </Surface>;
}
