// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {ReviewOverviewPanel} from './ReviewOverviewPanel';
import {ContractDetail} from '../../types';
import {ReviewTask} from './reviewTasks';
const contract={workflow:{approval_status:'PENDING'}} as ContractDetail;
const props={contract,tasks:[] as ReviewTask[],ready:true,error:'',queued:0,waiting:0,onOpen:vi.fn(),onDraft:vi.fn(),onRequests:vi.fn(),onApproval:vi.fn(),onRetry:vi.fn()};
afterEach(()=>{cleanup();vi.clearAllMocks();});
it('문제 경로는 해당 근거부터 열고 해결한 뒤 필수 판단을 보여 준다',()=>{
 const problem={id:'4:total_amount',document:{document_id:4,document_type:'estimate'},field:'total_amount',label:'합계',kind:'field',checks:[],value:120,expected:'110',reason:'계약 금액과 달라요'} as unknown as ReviewTask;
 const risk={...problem,id:'1:total_amount',document:{document_id:1,document_type:'contract'},routine:true,reason:'계약 기준 확인'} as unknown as ReviewTask;
 const {rerender}=render(<ReviewOverviewPanel {...props} tasks={[problem,risk]}/>);
 expect(screen.getByText('먼저 확인할 내용 1건')).toBeTruthy();expect(screen.queryByRole('button',{name:/계약 기준 확인/})).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'문제·근거 확인하기'}));expect(props.onOpen).toHaveBeenCalledWith(problem);
 rerender(<ReviewOverviewPanel {...props} tasks={[risk]}/>);
 expect(screen.queryByText('먼저 확인할 내용 1건')).toBeNull();expect(screen.getByRole('button',{name:/계약 기준 확인/})).toBeTruthy();
});
it('정상 계약은 계약·송금·청구 세 가지 행동만 보이고 자동 대조 서류를 다시 열게 하지 않는다',()=>{
 const task=(id:number,type:string,field:string)=>({id:`${id}:${field}`,document:{document_id:id,document_type:type},field,label:field,reason:'중요한 정보라 직접 확인',kind:'field',checks:[],expected:null,value:'synthetic',routine:true}) as unknown as ReviewTask;
 const tasks=[task(1,'contract','company_name'),task(1,'contract','business_registration_no'),task(1,'contract','total_amount'),task(2,'bank_account','company_name'),task(2,'bank_account','bank_name'),task(2,'bank_account','account_number'),task(3,'tax_invoice','amount_scope')];
 const value={...contract,workflow:{...contract.workflow,submission:{gate:{blockers:tasks.map(t=>({code:'HUMAN_REVIEW_REQUIRED',document_id:t.document!.document_id,field:t.field,category:'RISK'})),automatic_review:[],requires_work_confirmation:true}}}} as unknown as ContractDetail;
 render(<ReviewOverviewPanel {...props} tasks={tasks} contract={value}/>);
 expect(screen.getByRole('button',{name:/계약 기준 확인/})).toBeTruthy();expect(screen.getByRole('button',{name:/송금 정보 확인/})).toBeTruthy();expect(screen.getByRole('button',{name:/청구 범위 확인/})).toBeTruthy();
 expect(screen.queryByRole('button',{name:/견적서|사업자등록증|검수확인서/})).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'필수 확인 시작'}));expect(props.onOpen).toHaveBeenCalledWith(tasks[0]);
});
it('실제 gate의 생략 항목 개수만 업무 감소로 표시한다',()=>{
 const value={...contract,workflow:{...contract.workflow,submission:{gate:{blockers:[],automatic_review:[{document_id:4,document_type:'estimate',field:'business_registration_no'}]}}}} as unknown as ContractDetail;
 render(<ReviewOverviewPanel {...props} contract={value}/>);
 expect(screen.getByText('필수 사람 확인 0개')).toBeTruthy();expect(screen.getByText(/원본 근거로 자동 대조한 반복값 1개/)).toBeTruthy();
});
it('자동 일치와 상신 필수 사람 확인을 계약 전체에서 구분한다',()=>{
 const value={...contract,checks:[{rule_id:'BUSINESS_NO_MATCH',status:'PASS',field:'4',message:'일치'}],workflow:{...contract.workflow,submission:{gate:{blockers:[{code:'HUMAN_REVIEW_REQUIRED',document_id:4,field:'company_name'}]}}}} as unknown as ContractDetail;
 render(<ReviewOverviewPanel {...props} contract={value}/>);
 expect(screen.getByText('자동 검사 1개 일치')).toBeTruthy();expect(screen.getByText('필수 사람 확인 1개')).toBeTruthy();expect(screen.getByText(/1서류/)).toBeTruthy();
});
it('완료 계약은 기존 기록 화면을 열고, 자료 변경 뒤에는 상신 조건 안내로 돌아간다',()=>{
 const {rerender}=render(<ReviewOverviewPanel {...props} contract={{...contract,stage:'DONE'}}/>);
 fireEvent.click(screen.getByRole('button',{name:'결재·완료 기록 보기'}));expect(props.onApproval).toHaveBeenCalledOnce();
 expect(screen.queryByRole('button',{name:'검토 완료·상신 조건 보기'})).toBeNull();
 rerender(<ReviewOverviewPanel {...props} contract={{...contract,stage:'CHECK',payment:{status:'RECONFIRMATION_REQUIRED',paid_on:null,recorded_paid_on:'2026-10-10'} as ContractDetail['payment']}}/>);
 expect(screen.getByRole('button',{name:'검토 완료·상신 조건 보기'})).toBeTruthy();
 expect(screen.queryByRole('button',{name:'결재·완료 기록 보기'})).toBeNull();
});
it('회신만 남으면 확인을 독촉하지 않고 요청 내역으로 보낸다',()=>{
 render(<ReviewOverviewPanel {...props} waiting={1}/>);
 expect(screen.getByText('요청한 서류의 회신을 기다리고 있어요')).toBeTruthy();
 fireEvent.click(screen.getByRole('button',{name:'요청 내역 보기'}));expect(props.onRequests).toHaveBeenCalledOnce();
 expect(screen.queryByRole('button',{name:'확인 계속하기'})).toBeNull();
});
it('필수 위험 확인이 남아 있어도 회신 대기인 불일치를 정상 검사로 안내하지 않는다',()=>{
 const task={id:'1:total_amount',document:{document_id:1,document_type:'contract'},label:'합계',field:'total_amount',reason:'직접 확인',kind:'field',checks:[],expected:null,value:38500000,routine:true} as unknown as ReviewTask;
 render(<ReviewOverviewPanel {...props} tasks={[task]} waiting={1}/>);
 expect(screen.getByText(/요청한 항목은 회신 대기 중/)).toBeTruthy();
 expect(screen.queryByText(/발견된 문제는 없어요/)).toBeNull();
});
it('반려된 계약은 확인 완료 문구 대신 사유와 이력으로 안내한다',()=>{
 render(<ReviewOverviewPanel {...props} contract={{workflow:{approval_status:'RETURNED'}} as ContractDetail}/>);
 expect(screen.getByText('대표가 수정을 요청했어요')).toBeTruthy();expect(screen.queryByText('확인할 항목을 정리했어요')).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'반려 사유·결재 이력 보기'}));expect(props.onApproval).toHaveBeenCalledOnce();
});
it('보류만 남아도 해당 항목을 직접 열 수 있다',()=>{
 const task={id:'4:total_amount',label:'합계',field:'total_amount',reason:'확인 필요',kind:'field',checks:[],expected:null,value:110,deferral:{note:'담당 확인',actor_name:'담당자',at:'now'}} as ReviewTask;
 render(<ReviewOverviewPanel {...props} tasks={[task]}/>);
 fireEvent.click(screen.getByRole('button',{name:'보류한 항목 확인'}));expect(props.onOpen).toHaveBeenCalledWith(task);
});
