import {ArrowRight,ChevronRight,CheckCheck,Clock3,MessageSquare} from 'lucide-react';
import {DOCUMENT_LABEL} from '../../utils/documentLabels';
import {ContractDetail} from '../../types';
import {Surface} from '../ui/Surface';
import {ReviewTask} from './reviewTasks';

interface Props {contract:ContractDetail;tasks:ReviewTask[];ready:boolean;error:string;queued:number;waiting:number;
  onOpen:(task:ReviewTask)=>void;onDraft:()=>void;onRequests:()=>void;onApproval:()=>void;onRetry:()=>void;onContinue?:()=>void;}
export function ReviewOverviewPanel({contract,tasks,ready,error,queued,waiting,onOpen,onDraft,onRequests,onApproval,onRetry,onContinue}:Props){
  const deferred=tasks.filter(task=>task.deferral).length;
  const handoff=contract.workflow?.submission?.current;
  const returned=contract.workflow?.approval_status==='RETURNED'&&!handoff;
  const EmptyIcon=returned?MessageSquare:waiting?Clock3:CheckCheck;
  return <Surface title="확인이 필요한 내용" action={<span className="flow-count">{ready?tasks.length:'…'}</span>} className="flow-tasks-card">
    <div className="flow-summary"><span><strong>확인 남음 {ready?tasks.length:'…'}건</strong>{deferred>0&&<small>보류 {deferred}건 포함</small>}</span><span>요청 초안 {queued}건{waiting>0&&<small> · 회신 대기 {waiting}건</small>}</span></div>
    <div className="flow-task-list">{error?<div className="flow-empty" role="alert"><p>{error}</p><button className="button" onClick={onRetry}>확인 목록 다시 불러오기</button></div>:!ready?<div className="flow-empty" role="status">확인할 항목을 불러오는 중이에요.</div>:tasks.length?tasks.map(task=><button key={task.id} className="flow-task-item" onClick={()=>onOpen(task)}><span><strong>{task.document?DOCUMENT_LABEL[task.document.document_type]:task.missingType?DOCUMENT_LABEL[task.missingType]:'계약'} · {task.label}</strong><small>{task.deferral?'판단 보류 · 추가 확인 필요':task.reason}</small></span><span className="flow-open-label">{task.kind==='missing'?'서류 확인':task.kind==='basis'?'기준 확인':'원문 확인'}<ChevronRight size={13}/></span></button>):<div className="flow-empty"><EmptyIcon size={26}/><strong>{handoff?'담당자 상신 완료 · 대표 판단 대기':returned?'대표가 수정을 요청했어요':waiting?'요청한 서류의 회신을 기다리고 있어요':'확인할 항목을 정리했어요'}</strong>{returned&&<p>반려 사유를 확인하고 필요한 자료를 수정해 주세요.</p>}</div>}</div>
    <footer className="flow-queue-footer"><strong>{queued?`요청에 담긴 항목 ${queued}개`:returned&&!tasks.length?'반려 사유 확인 필요':waiting&&!tasks.length?`회신 대기 ${waiting}건`:ready?`확인 남음 ${tasks.length}건`:'확인 목록 조회 중'}</strong><button className="button primary" disabled={!ready||!!error} onClick={()=>queued?onDraft():tasks.length?(onContinue?onContinue():onOpen(tasks.find(task=>!task.deferral)||tasks[0])):returned?onApproval():waiting?onRequests():onApproval()}>{queued?'요청 내용 작성':tasks.length?(tasks.every(task=>task.deferral)?'보류한 항목 확인':'확인 계속하기'):returned?'반려 사유·결재 이력 보기':waiting?'요청 내역 보기':'검토 완료·상신 조건 보기'}<ArrowRight size={14}/></button></footer>
  </Surface>;
}
