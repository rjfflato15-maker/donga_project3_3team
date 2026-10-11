// @vitest-environment jsdom
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {act,cleanup,fireEvent,render,screen} from '@testing-library/react';
import {ContractDetail,ReviewBlocker} from '../../types';
import {SubmissionPanel} from './SubmissionPanel';
import {ApprovalPanel} from './ApprovalPanel';
import {requestJson} from '../../api/client';

let role='operator';
vi.mock('../../context/AuthContext',()=>({useAuth:()=>({user:{role,display_name:'합성 담당자'}})}));
vi.mock('../../api/client',()=>({api:{review:vi.fn()},requestJson:vi.fn()}));
const blocker:ReviewBlocker={code:'HUMAN_REVIEW_REQUIRED',document_id:1,document_type:'contract',field:'total_amount',label:'계약서 · 합계금액',reason:'자동으로 읽은 값을 담당자가 아직 원문과 대조하지 않았습니다.',action:'원문 대조·값 확인 또는 오독 정정',owner:'operator'};
function fixture(blockers:ReviewBlocker[]=[]):ContractDetail{return {
  contract_id:1,title:'합성 계약',vendor_name:'가상 업체',business_number:'',contract_amount:110,
  review_status:'PASS',required_document_types:['contract'],documents:[],checks:[],
  summary:{required_document_count:1,submitted_document_count:1,completeness_rate:100,pass_count:1,fail_count:0,review_count:0,missing_count:0},
  created_at:'2026-10-10',updated_at:'2026-10-10',workflow:{revision:1,fingerprint:'a'.repeat(64),amount_basis:'TOTAL',tax_amount:10,payment_mode:'FULL',approval_status:'PENDING',reviews:[],
    submission:{status:'NOT_SUBMITTED',current:false,event_id:null,actor_name:null,submitted_at:null,note:null,exception_reason:null,exception_items:[],next_owner:'operator',legacy_completed_approval:false,
      gate:{blockers,exception_items:[],can_submit:!blockers.length,can_submit_exception:false,completion:'필수 원본과 원문 대조·회신 처리를 끝내고 상신합니다.',fingerprint:'gate1'}}}};}
const props=()=>({masked:true,onChanged:vi.fn(async()=>{}),onOpen:vi.fn(),onApproval:vi.fn()});
beforeEach(()=>{role='operator';vi.mocked(requestJson).mockResolvedValue({});});
afterEach(()=>{cleanup();vi.resetAllMocks();});
describe('담당자 검토와 대표 결재 인계',()=>{
  it('문서 존재와 실제 용역 완료는 분리하고, 재진입·차수 변경 뒤 업무 판단을 다시 받는다',async()=>{
    const contract=fixture();contract.workflow!.submission!.gate!.requires_work_confirmation=true;
    const p=props();const view=render(<SubmissionPanel contract={contract} {...p}/>);
    fireEvent.change(screen.getByLabelText('담당자 검토 의견'),{target:{value:'합성 용역의 결과물을 확인했습니다.'}});
    expect(screen.getByRole('button',{name:'검토 완료·결재 상신'})).toHaveProperty('disabled',true);
    fireEvent.click(screen.getByRole('checkbox',{name:'실제 납품·용역 검수가 완료된 것을 확인했습니다.'}));
    expect(screen.getByRole('button',{name:'검토 완료·결재 상신'})).toHaveProperty('disabled',false);
    view.rerender(<SubmissionPanel contract={{...contract,workflow:{...contract.workflow!,revision:2}}} {...p}/>);
    expect(screen.getByLabelText('담당자 검토 의견')).toHaveProperty('value','합성 용역의 결과물을 확인했습니다.');
    expect(screen.getByRole('checkbox',{name:'실제 납품·용역 검수가 완료된 것을 확인했습니다.'})).toHaveProperty('checked',false);
    fireEvent.click(screen.getByRole('checkbox',{name:'실제 납품·용역 검수가 완료된 것을 확인했습니다.'}));
    fireEvent.click(screen.getByRole('button',{name:'검토 완료·결재 상신'}));
    await act(async()=>{});
    const body=vi.mocked(requestJson).mock.calls.find(([,args])=>args?.method==='POST')?.[1]?.body;
    expect(JSON.parse(String(body)).acknowledge_work_completed).toBe(true);
  });
  it('확인 이유와 필드·행동을 표시하고 필수 원문 검토가 남으면 상신하지 않는다',()=>{
    const p=props();render(<SubmissionPanel contract={fixture([blocker])} {...p}/>);
    expect(screen.getByText('계약서 · 합계금액')).toBeTruthy();
    expect(screen.getByText(blocker.reason)).toBeTruthy();
    expect(screen.queryByLabelText('담당자 검토 의견')).toBeNull();
    expect(screen.queryByRole('button',{name:'검토 완료·결재 상신'})).toBeNull();
    fireEvent.click(screen.getByRole('button',{name: /원문 대조·값 확인/}));
    expect(p.onOpen).toHaveBeenCalledWith(blocker);expect(vi.mocked(requestJson).mock.calls.filter(([,args])=>args?.method==='POST')).toHaveLength(0);
  });
  it('중복 클릭은 한 번만 저장하고 새로고침 실패 시 저장 완료를 분명히 알린다',async()=>{
    let resolve:(value:unknown)=>void=()=>{};
    vi.mocked(requestJson).mockImplementation((_url,args)=>args?.method==='POST'?new Promise(r=>{resolve=r;}):Promise.resolve({steps:[{role:'representative',label:'최종 결재'}]}));
    const p=props();p.onChanged.mockRejectedValue(new Error('조회 실패'));
    render(<SubmissionPanel contract={fixture()} {...p}/>);
    fireEvent.change(screen.getByLabelText('담당자 검토 의견'),{target:{value:'원문과 회신 내용을 모두 확인했습니다.'}});
    const button=screen.getByRole('button',{name:'검토 완료·결재 상신'});
    fireEvent.click(button);fireEvent.click(button);
    expect(vi.mocked(requestJson).mock.calls.filter(([,args])=>args?.method==='POST')).toHaveLength(1);
    await act(async()=>{resolve({});});
    expect(await screen.findByText(/상신은 저장했습니다/)).toBeTruthy();
    expect(screen.getByRole('button',{name:'상신 저장 완료'})).toHaveProperty('disabled',true);
  });
  it('상신 전 대표에게 승인 폼을 제공하지 않는다',async()=>{
    role='representative';vi.mocked(requestJson).mockImplementation(async(url)=>url.includes('/activity')?{items:[]}:{steps:[{role:'representative',label:'최종 결재'}],next_step:1,completed_steps:0,status:'PENDING',history:[]});
    render(<ApprovalPanel contract={fixture()} onChanged={async()=>{}}/>);
    expect(await screen.findByText('담당자 검토·상신 대기')).toBeTruthy();
    expect(screen.queryByRole('button',{name:'승인'})).toBeNull();
  });
  it('기술적 실패는 예외 사유와 동의를 입력해도 상신할 수 없다',()=>{
    const c=fixture([{...blocker,code:'READING_FAILED',field:null,reason:'문서를 읽지 못했습니다.',action:'읽을 수 있는 수정본 등록'}]);
    c.workflow!.submission!.gate!.exception_items=[{key:'AMOUNT:1',document_id:1,rule_id:'AMOUNT',reason:'합계금액 불일치',status:'FAIL'}];
    render(<SubmissionPanel contract={c} {...props()}/>);
    expect(screen.queryByLabelText('담당자 검토 의견')).toBeNull();
    expect(screen.queryByLabelText('예외 상신 사유')).toBeNull();
    expect(screen.queryByRole('button',{name:'예외 검토 요청·상신'})).toBeNull();
    expect(vi.mocked(requestJson).mock.calls.filter(([,args])=>args?.method==='POST')).toHaveLength(0);
  });
  it('상신 후 다음 담당자와 예외 사유를 표시하고 일반 미해결로 반복 안내하지 않는다',()=>{
    const c=fixture();Object.assign(c.workflow!.submission!,{current:true,status:'SUBMITTED',actor_name:'합성 담당자',submitted_at:'2026-10-10T00:00:00',note:'원문 확인 완료',exception_reason:'계약 조건 해석에 대한 대표 판단을 요청합니다.',exception_items:['AMOUNT:1']});
    render(<SubmissionPanel contract={c} {...props()}/>);
    expect(screen.getByText('다음 담당자: 대표')).toBeTruthy();
    expect(screen.getByText(/예외 검토 요청 1건/)).toBeTruthy();
    expect(screen.queryByLabelText('담당자 검토 의견')).toBeNull();
    expect(screen.queryByText(/지금 상신할 수 없는 이유/)).toBeNull();
  });
});

it('대표 1단계에서는 담당자 준비가 공식 1차 결재가 아니라고 표시한다',async()=>{
 vi.mocked(requestJson).mockResolvedValue({steps:[{role:'representative',label:'최종 결재'}]});render(<SubmissionPanel contract={fixture()} {...props()}/>);expect(await screen.findByText(/담당자의 서류 준비·검토·결재 요청은 공식 1차 결재가 아닙니다/)).toBeTruthy();expect(screen.queryByText('담당 검토·1차 결재')).toBeNull();
});
it('2단계 설정에서만 담당 검토 1차와 대표 2차 결재를 표시한다',async()=>{
 vi.mocked(requestJson).mockResolvedValue({steps:[{role:'operator',label:'담당 검토'},{role:'representative',label:'최종 결재'}]});render(<SubmissionPanel contract={fixture()} {...props()}/>);expect(await screen.findByText('담당 검토·1차 결재')).toBeTruthy();expect(screen.getByText('대표 최종·2차 결재')).toBeTruthy();
});
