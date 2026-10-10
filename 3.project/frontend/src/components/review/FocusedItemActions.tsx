import {useEffect,useState} from 'react';

export type FocusAction='correct'|'request'|'basis'|'ok'|null;
interface Props {
  action:FocusAction;onAction:(action:FocusAction)=>void;busy:boolean;canAct:boolean;editable:boolean;
  reveal:boolean;hasValue:boolean;confirmed:boolean;issues:boolean;noIssue:boolean;technical:boolean;
  value:string;label:string;reason:string;lookAt:string;expected?:string|null;basis?:string|null;
  onCorrect:()=>void;onRequest?:()=>void;onBasis?:()=>void;onConfirm:()=>void;onAccept:()=>void;
  onReveal?:()=>void;form?:React.ReactNode;
}
/** Choosing an action reveals its own inputs; navigation never calls these callbacks. */
export function FocusedItemActions(p:Props){
  const [ack,setAck]=useState(false);
  useEffect(()=>setAck(false),[p.action,p.label,p.value,p.confirmed]);
  return <div className="focus-item">
    <div className="focus-value"><span>앱이 읽은 값</span><strong>{p.value}</strong>{p.basis&&<small className="focus-current-basis">등록된 계약 기준: {p.basis}</small>}{p.expected&&<small>검사 비교 기준: {p.expected}</small>}</div>
    <p className="focus-guidance"><strong>{p.reason}</strong><span>원문에서 볼 곳: {p.lookAt}</span></p>
    {p.confirmed&&<p className="focus-record" role="status">원문 확인 기록 있음{p.issues?' · 비교 문제는 별도 판단이 필요합니다.':''}</p>}
    {p.noIssue&&<p className="focus-record">문제없음 판단 기록 있음 · 자동 검사 결과는 유지됩니다.</p>}
    {p.reveal&&<p className="flow-reveal">가려진 값은 가림을 끄고 대조하세요.{p.onReveal&&<button className="text-button" onClick={p.onReveal}>가림 끄기</button>}</p>}
    {p.editable&&!p.technical&&<>
      <div className="focus-actions" role="group" aria-label="현재 항목 판단">
        <button className="button" aria-pressed={p.action==='correct'} disabled={!p.canAct||p.reveal} onClick={()=>{p.onAction('correct');p.onCorrect();}}>값 정정</button>
        <button className="button" aria-pressed={p.action==='request'} disabled={p.busy||!p.onRequest} onClick={()=>p.onAction('request')}>보완 필요</button>
        <button className="button" aria-pressed={p.action==='basis'} disabled={p.busy||!p.onBasis} onClick={()=>p.onAction('basis')}>계약 기준 수정</button>
        <button className="button" aria-pressed={p.action==='ok'} disabled={!p.canAct||p.reveal||!p.hasValue} onClick={()=>p.onAction('ok')}>문제없음</button>
      </div>
      {!p.action&&<p className="focus-help">원문과 읽은 값을 대조한 뒤 처리 방법을 고르세요. 이전·다음으로 이동해도 확인은 저장되지 않습니다.</p>}
      {p.action==='correct'&&<div className="focus-action-form"><p>앱이 원문을 잘못 읽었을 때만 읽은 값을 고칩니다.</p>{p.form}</div>}
      {p.action==='request'&&<div className="focus-action-form"><p>서류 자체의 오류·누락은 보완 요청에 담습니다. 여러 항목을 모아 기존 요청 화면에서 한 번에 기록하세요.</p><button className="button primary" disabled={p.busy} onClick={p.onRequest}>보완 요청에 담기</button></div>}
      {p.action==='basis'&&<div className="focus-action-form"><p>원문과 읽은 값은 맞지만 계약 금액·지급 기준이 잘못되었다면 기존 계약 정보 화면에서 기준을 수정하세요. 수정 후 이 항목에서 최신 기준으로 다시 확인합니다.</p><button className="button primary" disabled={p.busy} onClick={p.onBasis}>계약 정보 열기</button></div>}
      {p.action==='ok'&&<div className="focus-action-form">
        {p.issues?<><p>원문 값이 맞아도 비교 문제는 남을 수 있습니다. 먼저 원문 확인을 저장한 뒤, 문제가 아니라고 판단한 근거를 기록합니다.</p>{!p.confirmed?<><label className="check-label"><input type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)}/>원문에 이 값이 적힌 것을 직접 확인했습니다.</label><button className="button primary" disabled={!p.canAct||!ack} onClick={p.onConfirm}>원문 확인 저장</button></>:p.form||<button className="button primary" disabled={!p.canAct||p.noIssue} onClick={p.onAccept}>판단 근거 작성</button>}</>:<><p>원문과 앱이 읽은 값이 같음을 확인 기록으로 저장합니다.</p><button className="button primary" disabled={!p.canAct||p.confirmed} onClick={p.onConfirm}>{p.confirmed?'원문 확인 저장됨':'원문과 같음 · 확인 저장'}</button></>}
      </div>}
    </>}
    {!p.editable&&<p className="focus-help">조회 권한으로 원문과 기록을 확인하고 있습니다.</p>}
  </div>;
}
