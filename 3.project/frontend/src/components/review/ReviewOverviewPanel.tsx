import {ArrowRight,ChevronRight,CheckCheck,Clock3,MessageSquare} from 'lucide-react';
import {DOCUMENT_LABEL} from '../../utils/documentLabels';
import {ContractDetail} from '../../types';
import {Surface} from '../ui/Surface';
import {ReviewTask} from './reviewTasks';
import {isUnverifiedBusinessStatus} from '../../utils/reviewSummary';

interface Props {contract:ContractDetail;tasks:ReviewTask[];ready:boolean;error:string;queued:number;waiting:number;
  onOpen:(task:ReviewTask)=>void;onDraft:()=>void;onRequests:()=>void;onApproval:()=>void;onRetry:()=>void;onContinue?:()=>void;}
const purpose={contract:'계약 기준',bank_account:'송금 정보',tax_invoice:'청구 범위'};

export function ReviewOverviewPanel({contract,tasks,ready,error,queued,waiting,onOpen,onDraft,onRequests,onApproval,onRetry,onContinue}:Props){
  const problems=tasks.filter(task=>!task.routine),risk=tasks.filter(task=>task.routine);
  const riskGroups=[...new Map(risk.filter(task=>task.document).map(task=>[task.document!.document_id,task])).values()]
    .map(first=>({first,count:risk.filter(task=>task.document?.document_id===first.document!.document_id).length}));
  const gate=contract.workflow?.submission?.gate,automatic=gate?.automatic_review??[];
  const autoGroups=[...new Set(automatic.map(item=>item.document_type))];
  const human=gate?.blockers.filter(b=>['HUMAN_REVIEW_REQUIRED','FIELD_VALUE_REQUIRED'].includes(b.code)).length;
  const requiredDocs=new Set(gate?.blockers.filter(b=>['HUMAN_REVIEW_REQUIRED','FIELD_VALUE_REQUIRED'].includes(b.code)).map(b=>b.document_id)).size;
  const requiredJudgements=new Set(gate?.blockers.filter(b=>b.category==='RISK').map(b=>b.document_id)).size||riskGroups.length;
  const required=contract.required_document_types??[];
  const present=new Set((contract.documents??[]).filter(doc=>doc.version?.is_current!==false&&doc.file_available).map(doc=>doc.document_type));
  const checks=contract.checks??[],matched=checks.filter(c=>c.status==='PASS').length,unverified=checks.filter(isUnverifiedBusinessStatus).length;
  const handoff=contract.workflow?.submission?.current,returned=contract.workflow?.approval_status==='RETURNED'&&!handoff;
  const completed=contract.stage==='DONE'||(!contract.stage&&!!contract.payment?.paid_on);
  const EmptyIcon=returned?MessageSquare:waiting?Clock3:CheckCheck;
  const openNext=()=>queued?onDraft():problems.length?(onContinue?onContinue():onOpen(problems.find(task=>!task.deferral)||problems[0])):risk.length?onOpen(risk[0]):returned?onApproval():waiting?onRequests():onApproval();
  const nextLabel=queued?'요청 내용 작성':problems.length?(problems.every(task=>task.deferral)?'보류한 항목 확인':'문제·근거 확인하기'):risk.length?'필수 확인 시작':returned?'반려 사유·결재 이력 보기':waiting?'요청 내역 보기':completed?'결재·완료 기록 보기':'검토 완료·상신 조건 보기';
  const item=(task:ReviewTask)=><button key={task.id} className="flow-task-item" onClick={()=>onOpen(task)}><span><strong>{task.document?DOCUMENT_LABEL[task.document.document_type]:task.missingType?DOCUMENT_LABEL[task.missingType]:'계약'} · {task.label}</strong><small>{task.deferral?'판단 보류 · 추가 확인 필요':task.reason}</small></span><span className="flow-open-label">{task.kind==='missing'?'서류 보완':task.kind==='basis'?'기준 확인':'원문 확인'}<ChevronRight size={13}/></span></button>;
  return <Surface title="담당자 할 일" className="flow-tasks-card">
    <div className="flow-contract-results" aria-label="계약 전체 결과 요약">
      {required.length>0&&<span><strong>필수 증빙 {required.filter(type=>present.has(type)).length}/{required.length}종</strong></span>}
      <span><strong>자동 검사 {ready?matched:'…'}개 일치</strong>{unverified>0&&<small> · 국세청 미조회</small>}</span>
      <span><strong>담당자 필수 판단 {ready?requiredJudgements:'…'}가지</strong></span>
    </div>
    <details className="focus-background"><summary>자동 검사 범위·근거 보기</summary><p><strong>필수 사람 확인 {ready&&human!==undefined?human:'…'}개</strong><small> · {ready&&human!==undefined?requiredDocs:'…'}서류</small>. 필수 판단과 자동으로 검증하지 못한 근거만 포함합니다.</p>
      {ready&&automatic.length>0&&<><p><strong>원본 근거로 자동 대조한 반복값 {automatic.length}개</strong></p><ul>{autoGroups.map(type=><li key={type}>{DOCUMENT_LABEL[type]??'서류'} · {automatic.filter(item=>item.document_type===type).map(item=>item.field==='company_name'?'거래처':item.field==='business_registration_no'?'사업자번호':item.field==='supply_amount'?'공급가액':item.field==='tax_amount'?'세액':'합계').join(' · ')}</li>)}</ul>
      <p>원본 해시·거래처 귀속·계약 기준을 대조했습니다. {automatic.some(item=>item.source_method==='RASTER_OCR_ROW_CROP')?'스캔값은 OCR의 실제 위치와 원문 행 재판독 일치 조건을 적용했습니다. ':''}사람 확인 기록과는 별도이며, 원본이나 기준이 바뀌면 다시 검사합니다.</p>
      </>}
    </details>
    {(queued>0||waiting>0)&&<div className="flow-summary"><span>{queued>0&&<strong>요청 초안 {queued}건</strong>}{waiting>0&&<span>회신 대기 {waiting}건</span>}</span></div>}
    <div className="flow-task-list">{error?<div className="flow-empty" role="alert"><p>{error}</p><button className="button" onClick={onRetry}>확인 목록 다시 불러오기</button></div>:!ready?<div className="flow-empty" role="status">계약 전체 결과를 불러오는 중이에요.</div>:tasks.length?<>
      {problems.length>0?<><div className="flow-route-head flow-route-problem"><strong>먼저 확인할 내용 {problems.length}건</strong><p>항목을 선택해 해당 원문과 근거를 확인하세요.</p></div>{problems.map(item)}{riskGroups.length>0&&<p className="flow-after-problems">문제를 정리한 뒤 계약·송금·청구의 남은 필수 판단을 이어갑니다.</p>}</>:<div className="flow-route-head"><strong>{waiting?'요청한 서류는 회신 대기 중이에요':queued?'보완 요청 내용을 작성하세요':'지급·업무 판단을 확인하세요'}</strong><p>{waiting?'요청한 항목은 회신 대기 중이에요. 그동안 아래 지급·업무 정보를 확인할 수 있어요.':queued?'요청을 기록하고 남은 지급·업무 판단을 이어가세요.':'자동 대조에서 추가로 처리할 문제는 없어요. 아래 필수 판단만 진행하세요.'}</p></div>}
      {problems.length===0&&riskGroups.length>0&&<div className="flow-routine-group">
        {riskGroups.map(({first})=><button key={first.id} className="flow-task-item flow-routine-item" onClick={()=>onOpen(first)}><span><strong>{purpose[first.document!.document_type as keyof typeof purpose]??DOCUMENT_LABEL[first.document!.document_type]} 확인</strong><small>{first.reason}</small></span><span className="flow-open-label">확인하기<ChevronRight size={13}/></span></button>)}
      </div>}
    </>:<div className="flow-empty"><EmptyIcon size={26}/><strong>{handoff?'담당자 상신 완료 · 대표 판단 대기':returned?'대표가 수정을 요청했어요':waiting?'요청한 서류의 회신을 기다리고 있어요':gate?.requires_work_confirmation?'자료 대조 완료 · 실제 용역 완료를 확인하고 상신하세요':'확인할 항목을 정리했어요'}</strong>{returned&&<p>반려 사유를 확인하고 필요한 자료를 수정해 주세요.</p>}</div>}</div>
    <footer className="flow-queue-footer"><strong>{queued?`요청에 담긴 항목 ${queued}개`:returned&&!tasks.length?'반려 사유 확인 필요':waiting&&!tasks.length?`회신 대기 ${waiting}건`:ready?(problems.length?`문제·근거 확인 ${problems.length}건`:risk.length?`담당자 필수 판단 ${riskGroups.length}가지`:'남은 원문 확인 없음'):'결과 조회 중'}</strong><button className="button primary" disabled={!ready||!!error} onClick={openNext}>{nextLabel}<ArrowRight size={14}/></button></footer>
  </Surface>;
}
