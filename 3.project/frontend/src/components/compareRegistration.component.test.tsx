// @vitest-environment jsdom
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {CompareRegistration} from './CompareRegistration';
import {api} from '../api/client';
import {ContractDetail} from '../types';
vi.mock('../api/client',()=>({api:{autoParseBatchDocuments:vi.fn(),autoCreateBatchContract:vi.fn(),updateContract:vi.fn()}}));
const parsed={title:'가상 계약',vendor_name:'가상 업체',business_number:'000-00-00000',contract_amount:110,documents:[]};
beforeEach(()=>{URL.createObjectURL=vi.fn(()=> 'blob:original');URL.revokeObjectURL=vi.fn();vi.mocked(api.autoParseBatchDocuments).mockResolvedValue(parsed);vi.mocked(api.autoCreateBatchContract).mockResolvedValue({contract_id:8,workflow:{revision:1}} as ContractDetail);vi.mocked(api.updateContract).mockResolvedValue({contract_id:8} as ContractDetail);});
afterEach(()=>{cleanup();vi.resetAllMocks();vi.unstubAllGlobals();});
const select=()=>fireEvent.change(screen.getByLabelText('계약 등록 파일'),{target:{files:[new File(['synthetic'],'가상.pdf',{type:'application/pdf'})]}});
it('사내 HTTP 접속처럼 randomUUID가 없는 환경에서도 등록할 수 있다',async()=>{vi.stubGlobal('crypto',{});const done=vi.fn(async()=>{});render(<CompareRegistration onClose={()=>{}} onSuccess={done}/>);select();fireEvent.click(screen.getByRole('button',{name:/선택한 서류 1개로 계속/}));await screen.findByLabelText('계약명');fireEvent.click(screen.getByRole('button',{name:'계약 등록'}));await waitFor(()=>expect(done).toHaveBeenCalledWith(8));expect(vi.mocked(api.autoCreateBatchContract).mock.calls[0][2]?.requestKey).toEqual(expect.any(String));});
it('등록 전 기준 화면에서 선택한 원문을 열 수 있고 떠날 때 주소를 해제한다',async()=>{
 const view=render(<CompareRegistration onClose={()=>{}} onSuccess={async()=>{}}/>);select();fireEvent.click(screen.getByRole('button',{name:/선택한 서류 1개로 계속/}));await screen.findByLabelText('계약명');
 const original=screen.getByRole('link',{name:'계약서 원문 열기'});expect(original.getAttribute('href')).toBe('blob:original');expect(original.getAttribute('target')).toBe('_blank');
 expect(api.autoCreateBatchContract).not.toHaveBeenCalled();view.unmount();expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:original');
});
it('선택한 종류와 계약 기준을 등록 요청에 함께 담는다',async()=>{const done=vi.fn(async()=>{});render(<CompareRegistration onClose={()=>{}} onSuccess={done}/>);select();fireEvent.click(screen.getByRole('button',{name:/선택한 서류 1개로 계속/}));await screen.findByLabelText('계약명');expect(api.autoCreateBatchContract).not.toHaveBeenCalled();fireEvent.change(screen.getByLabelText('계약 금액 (원)'),{target:{value:'220'}});fireEvent.click(screen.getByRole('button',{name:'계약 등록'}));await waitFor(()=>expect(done).toHaveBeenCalledWith(8));expect(api.autoCreateBatchContract).toHaveBeenCalledWith(expect.objectContaining({contract_amount:220,amount_basis:'TOTAL',payment_mode:'FULL'}),expect.arrayContaining([expect.any(File)]),expect.objectContaining({documentTypes:['contract'],requestKey:expect.any(String)}));expect(api.updateContract).not.toHaveBeenCalled();});
it('일부 파일 실패 후 같은 등록 요청으로 이어 처리하고 기존 계약을 열 수 있다',async()=>{
 vi.mocked(api.autoCreateBatchContract).mockResolvedValueOnce({contract_id:8,registration:{request_key:'test',complete:false,failed_files:[{index:0,file_name:'가상.pdf',message:'파일 처리 실패'}]}} as ContractDetail);
 const done=vi.fn(async()=>{});render(<CompareRegistration onClose={()=>{}} onSuccess={done}/>);select();fireEvent.click(screen.getByRole('button',{name:/선택한 서류 1개로 계속/}));await screen.findByLabelText('계약명');fireEvent.click(screen.getByRole('button',{name:'계약 등록'}));await screen.findByRole('alert');expect(done).not.toHaveBeenCalled();expect(screen.queryByRole('button',{name:'계약 등록'})).toBeNull();expect(screen.getByRole('button',{name:'등록한 계약 확인'})).toBeTruthy();fireEvent.click(screen.getByRole('button',{name:'실패한 서류 다시 처리'}));await waitFor(()=>expect(done).toHaveBeenCalledWith(8));const calls=vi.mocked(api.autoCreateBatchContract).mock.calls;expect(calls[0][2]?.requestKey).toBe(calls[1][2]?.requestKey);
});
it('떠난 등록 화면의 늦은 분석 결과는 새 작업을 덮어쓰지 않는다',async()=>{let resolve!:(value:typeof parsed)=>void;vi.mocked(api.autoParseBatchDocuments).mockImplementation(()=>new Promise(r=>{resolve=r;}));const done=vi.fn(async()=>{});const view=render(<CompareRegistration onClose={()=>{}} onSuccess={done}/>);select();fireEvent.click(screen.getByRole('button',{name:/선택한 서류 1개로 계속/}));view.unmount();resolve(parsed);await Promise.resolve();expect(done).not.toHaveBeenCalled();expect(api.autoCreateBatchContract).not.toHaveBeenCalled();});

const slots=['계약서','견적서','사업자등록증','통장사본','세금계산서','검수확인서'];
const kinds=['contract','estimate','business_registration','bank_account','tax_invoice','inspection_confirmation'];
function selectSlot(index:number){
 const row=screen.getByText(slots[index],{selector:'strong'}).parentElement!;
 fireEvent.click(row.querySelector('button')!);
 fireEvent.change(screen.getByLabelText('계약 등록 파일'),{target:{files:[new File([`synthetic ${index}`],`${kinds[index]}.txt`,{type:'text/plain'})]}});
}
async function submitSelected(count:number){
 fireEvent.click(screen.getByRole('button',{name:new RegExp(`선택한 서류 ${count}개로 계속`)}));
 await screen.findByLabelText('계약명');fireEvent.click(screen.getByRole('button',{name:'계약 등록'}));
 await waitFor(()=>expect(api.autoCreateBatchContract).toHaveBeenCalled());
}
it.each([{order:[3,0]},{order:[5,3,1,4,0,2]}])('파일을 $order 순서로 선택해도 파일과 종류는 같은 슬롯에 묶인다',async({order})=>{
 render(<CompareRegistration onClose={()=>{}} onSuccess={async()=>{}}/>);
 order.forEach(selectSlot);await submitSelected(order.length);
 const [,files,options]=vi.mocked(api.autoCreateBatchContract).mock.calls[0];
 expect(files.map((file,index)=>[file.name,options!.documentTypes[index]])).toEqual([...order].sort((a,b)=>a-b).map(i=>[`${kinds[i]}.txt`,kinds[i]]));
});
it('선택 취소와 재선택 및 부분 실패 재시도에도 파일 쌍과 요청 키를 유지한다',async()=>{
 vi.mocked(api.autoCreateBatchContract).mockResolvedValueOnce({contract_id:8,registration:{request_key:'test',complete:false,failed_files:[{index:1,file_name:'bank_account.txt',message:'재시도'}]}} as ContractDetail);
 render(<CompareRegistration onClose={()=>{}} onSuccess={async()=>{}}/>);
 selectSlot(3);selectSlot(0);fireEvent.click(screen.getByRole('button',{name:'계약서 선택 취소'}));selectSlot(0);
 await submitSelected(2);await screen.findByRole('button',{name:'실패한 서류 다시 처리'});
 fireEvent.click(screen.getByRole('button',{name:'실패한 서류 다시 처리'}));
 await waitFor(()=>expect(api.autoCreateBatchContract).toHaveBeenCalledTimes(2));
 const calls=vi.mocked(api.autoCreateBatchContract).mock.calls;
 expect(calls[0][1].map((f,i)=>[f.name,calls[0][2]!.documentTypes[i]])).toEqual([['contract.txt','contract'],['bank_account.txt','bank_account']]);
 expect(calls[1]).toEqual(calls[0]);
});
