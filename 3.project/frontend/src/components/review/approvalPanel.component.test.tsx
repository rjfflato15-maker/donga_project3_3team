// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ApprovalPanel, ApprovalState } from './ApprovalPanel';
import { ContractDetail } from '../../types';
import { api, requestJson } from '../../api/client';
import { BundledRequest } from '../../features/requests/model';
vi.mock('../../api/client', () => ({ api:{review:vi.fn()}, requestJson: vi.fn() }));
let role = 'representative';
vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ user:{ role } }) }));
const single:ApprovalState = {steps:[{role:'representative',label:'최종 확인'}],completed_steps:0,next_step:1,status:'PENDING',history:[]};
const fixture = (unverified=false):ContractDetail => ({ contract_id:1,title:'가상 계약',vendor_name:'가상 업체',business_number:'',contract_amount:110,review_status:'PASS',required_document_types:['contract'],documents:[{document_id:1,contract_id:1,document_type:'contract',original_file_name:'가상.txt',file_available:true,confidence:1,processing_status:'COMPLETED',mask_status:'MASKED',analysis:{fields:{},warnings:[]}}],summary:{required_document_count:1,submitted_document_count:1,completeness_rate:100,pass_count:1,fail_count:0,review_count:0,missing_count:0},checks:unverified?[{rule_id:'BUSINESS_STATUS',status:'REVIEW',field:'1',message:'미조회'}]:[],created_at:'2026-10-01',updated_at:'2026-10-01',workflow:{revision:1,fingerprint:'basis1',amount_basis:'TOTAL',tax_amount:10,payment_mode:'FULL',approval_status:'PENDING',reviews:[]} });
beforeEach(() => {role='representative';vi.mocked(requestJson).mockImplementation(async (url) => url.includes('/activity') ? {items:[]} : single);});
afterEach(() => {cleanup();vi.resetAllMocks();});
describe('새 결재 화면의 실제 활성 조건', () => {
  it('반려 의견이 있으면 결재 이력에 의견이 없다는 문구를 함께 표시하지 않는다',async()=>{
    const contract=fixture();contract.workflow={...contract.workflow!,approval_status:'RETURNED',reviews:[{review_id:1,decision:'RETURNED',note:'기준 금액 확인 요청',revision:1,actor_name:'대표',created_at:'2026-10-08T00:00:00Z'}]};
    render(<ApprovalPanel contract={contract} onChanged={async()=>{}}/>);
    expect(await screen.findByText('기준 금액 확인 요청')).toBeTruthy();expect(screen.queryByText('아직 결정된 의견이 없습니다.')).toBeNull();
  });
  it('결재 요약의 수령 기록은 받은 항목만 표시하고 자동 검사로 바꾸지 않는다', async () => {
    const request={request_id:3,bundle:{items:[{item_id:1,issue_key:'missing:bank_account',document_id:null,document_type:'bank_account',title:'통장사본',status:'RECEIVED'},{item_id:2,issue_key:'missing:tax_invoice',document_id:null,document_type:'tax_invoice',title:'세금계산서',status:'CANCELLED'}]}} as BundledRequest;
    render(<ApprovalPanel contract={fixture()} onChanged={async()=>{}} requests={[request]}/>);
    expect(await screen.findByText('받음 기록')).toBeTruthy();
    expect(screen.getByText('자동 검사와 별도')).toBeTruthy();
    expect(screen.queryByText('세금계산서')).toBeNull();
  });
  it('일반 승인에는 의견 3자, 반려는 최종 단계에서만 가능', async () => {
    render(<ApprovalPanel contract={fixture()} onChanged={async () => {}} />);
    const note=await screen.findByLabelText(/결재 의견/);
    expect((screen.getByRole('button',{name:'승인'}) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(note,{target:{value:'원문 확인'}});
    expect((screen.getByRole('button',{name:'승인'}) as HTMLButtonElement).disabled).toBe(false);
    expect(screen.getByRole('button',{name:'반려'})).toBeTruthy();
  });
  it('국세청 미조회 등 미확인이 있으면 동의와 의견 10자 이상', async () => {
    render(<ApprovalPanel contract={fixture(true)} onChanged={async () => {}} />);
    const note=await screen.findByLabelText(/결재 의견/);
    fireEvent.change(note,{target:{value:'확인'}});fireEvent.click(screen.getByRole('checkbox'));
    expect((screen.getByRole('button',{name:'승인'}) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(note,{target:{value:'원문과 미조회 사항을 모두 확인했습니다'}});
    expect((screen.getByRole('button',{name:'승인'}) as HTMLButtonElement).disabled).toBe(false);
  });
  it('2단계 담당 검토에서는 반려를 노출하지 않는다', async () => {
    role='operator';vi.mocked(requestJson).mockImplementation(async (url) => url.includes('/activity')?{items:[]}:{...single,steps:[{role:'operator',label:'담당 검토'},{role:'representative',label:'최종 결재'}]});
    render(<ApprovalPanel contract={fixture()} onChanged={async () => {}} />);
    await screen.findByLabelText(/결재 의견/);
    expect(screen.getByRole('button',{name:'담당 검토 완료'})).toBeTruthy();
    expect(screen.queryByRole('button',{name:'반려'})).toBeNull();
  });
  it('자료 충돌 뒤 최신 조회가 끝나도 오류는 남고 동의를 재사용하지 않는다', async () => {
    vi.mocked(requestJson).mockImplementation(async (url, options) => {if(options?.method==='POST') throw new Error('다른 사용자가 자료를 변경했습니다');return url.includes('/activity')?{items:[]}:single;});
    render(<ApprovalPanel contract={fixture(true)} onChanged={async () => {}} />);
    fireEvent.change(await screen.findByLabelText(/결재 의견/),{target:{value:'현재 원문 자료를 충분히 확인했습니다'}});fireEvent.click(screen.getByRole('checkbox'));fireEvent.click(screen.getByRole('button',{name:'승인'}));
    await screen.findByText(/저장하지 못했습니다/);
    await waitFor(() => expect((screen.getByLabelText(/결재 의견/) as HTMLTextAreaElement).value).toBe('현재 원문 자료를 충분히 확인했습니다'));
    expect((screen.getByRole('checkbox') as HTMLInputElement).checked).toBe(false);
    expect((screen.getByRole('button',{name:'승인'}) as HTMLButtonElement).disabled).toBe(true);
  });
  it('대표 반려는 reviews API로 보내고 실패한 의견은 다시 조회한 뒤에도 보존한다', async () => {
    vi.mocked(api.review).mockRejectedValue(new Error('반려 기록 실패'));
    render(<ApprovalPanel contract={fixture()} onChanged={async()=>{}}/>);
    fireEvent.change(await screen.findByLabelText(/결재 의견/),{target:{value:'금액 기준을 다시 확인해 주세요'}});
    fireEvent.click(screen.getByRole('button',{name:'반려'}));
    await screen.findByText(/반려 기록 실패/);
    await waitFor(()=>expect(screen.getByRole('button',{name:'반려'})).toHaveProperty('disabled',false));
    expect(api.review).toHaveBeenCalledWith(1,{review_cycle:0,submission_event_id:undefined,decision:'RETURNED',note:'금액 기준을 다시 확인해 주세요',revision:1,fingerprint:'basis1',acknowledge_unverified:false});
    expect(vi.mocked(requestJson).mock.calls.some(([,options])=>options?.method==='POST')).toBe(false);
    expect(screen.getByLabelText(/결재 의견/)).toHaveProperty('value','금액 기준을 다시 확인해 주세요');
  });
});
