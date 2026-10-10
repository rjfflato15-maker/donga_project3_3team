// @vitest-environment jsdom
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react';
import {DocumentWorkspace} from './DocumentWorkspace';
import {ContractDetail,DocumentResponse} from '../../types';
import {requestJson} from '../../api/client';
vi.mock('../../api/client',()=>({api:{correctFields:vi.fn()},requestJson:vi.fn(),downloadProtected:vi.fn()}));
const doc={document_id:4,contract_id:1,document_type:'estimate',original_file_name:'synthetic.txt',file_available:true,processing_status:'COMPLETED',analysis:{fields:{total_amount:110,company_name:'synthetic',business_registration_no:'synthetic'},warnings:[]}} as unknown as DocumentResponse;
const contract={contract_id:1,documents:[doc],checks:[],contract_amount:110,workflow:{revision:3,fingerprint:'v3',amount_basis:'TOTAL'}} as unknown as ContractDetail;
const context={revision:3,documents:[{document_id:4,source_version_verified:true,fields:{total_amount:{value:110,source:'RULE',evidence:[]},company_name:{value:'synthetic',source:'RULE',evidence:[]}}}]};
beforeEach(()=>{sessionStorage.clear();HTMLElement.prototype.scrollIntoView=vi.fn();vi.mocked(requestJson).mockImplementation(async url=>url.includes('text-preview')?{text:'synthetic original 110'}:{revision:3,documents:context.documents});});
afterEach(()=>{cleanup();vi.resetAllMocks();});
const props={contract,doc,checks:[],revision:3,sharedContext:context,isMaskingEnabled:false,canEdit:true,onClose:vi.fn(),onChanged:vi.fn(async()=>{})};
it('one field is focused; next, previous and arbitrary list navigation never send a write',async()=>{
 const open=vi.fn();render(<DocumentWorkspace {...props} onOpenTask={open}/>);await screen.findByText('앱이 읽은 값');
 expect(screen.queryByRole('table')).toBeNull();expect(screen.queryByLabelText('수정 사유')).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'다음 항목'}));expect(open).toHaveBeenCalledWith(expect.objectContaining({id:'4:company_name'}));
 fireEvent.click(screen.getByRole('button',{name:'전체 항목 보기'}));fireEvent.click(within(screen.getByRole('navigation',{name:'전체 확인 항목'})).getByRole('button',{name:/사업자번호/}));
 expect(vi.mocked(requestJson).mock.calls.filter(([,args])=>args?.method&&args.method!=='GET')).toHaveLength(0);
});
it('four choices reveal only relevant inputs and deferral remains in more',async()=>{
 render(<DocumentWorkspace {...props} onRequest={()=>{}} onCheckBasis={()=>{}}/>);await screen.findByText('앱이 읽은 값');
 expect(within(screen.getByRole('group',{name:'현재 항목 판단'})).getAllByRole('button').map(b=>b.textContent)).toEqual(['값 정정','보완 필요','계약 기준 수정','문제없음']);
 expect(screen.queryByRole('button',{name:'판단 보류'})).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'값 정정'}));expect(screen.getByLabelText('합계 수정값')).toBeTruthy();
 fireEvent.click(screen.getByRole('button',{name:'보완 필요'}));expect(screen.queryByLabelText('합계 수정값')).toBeNull();expect(screen.getByRole('button',{name:'보완 요청에 담기'})).toBeTruthy();
 fireEvent.click(screen.getByRole('button',{name:'계약 기준 수정'}));expect(screen.getByRole('button',{name:'계약 정보 열기'})).toBeTruthy();expect(screen.queryByRole('button',{name:'보완 요청에 담기'})).toBeNull();
});
it('problem-free choice alone is not confirmation, explicit save uses the existing field endpoint',async()=>{
 render(<DocumentWorkspace {...props}/>);await screen.findByText('synthetic original 110');await screen.findByText('앱이 읽은 값');
 fireEvent.click(screen.getByRole('button',{name:'문제없음'}));
 expect(vi.mocked(requestJson).mock.calls.some(([url])=>url.endsWith('/confirm-field'))).toBe(false);
 fireEvent.click(screen.getByRole('button',{name:'원문과 같음 · 확인 저장'}));
 await waitFor(()=>expect(props.onChanged).toHaveBeenCalled());
 const call=vi.mocked(requestJson).mock.calls.find(([url])=>url.endsWith('/confirm-field'))!;
 expect(JSON.parse(String(call[1]?.body))).toEqual({field:'total_amount',revision:3});
});
