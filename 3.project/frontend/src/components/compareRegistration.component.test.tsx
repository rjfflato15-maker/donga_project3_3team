// @vitest-environment jsdom
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {CompareRegistration} from './CompareRegistration';
import {api} from '../api/client';
import {ContractDetail} from '../types';
vi.mock('../api/client',()=>({api:{autoParseBatchDocuments:vi.fn(),autoCreateBatchContract:vi.fn(),updateContract:vi.fn()}}));
const parsed={title:'가상 계약',vendor_name:'가상 업체',business_number:'000-00-00000',contract_amount:110,documents:[]};
beforeEach(()=>{vi.mocked(api.autoParseBatchDocuments).mockResolvedValue(parsed);vi.mocked(api.autoCreateBatchContract).mockResolvedValue({contract_id:8,workflow:{revision:1}} as ContractDetail);vi.mocked(api.updateContract).mockResolvedValue({contract_id:8} as ContractDetail);});
afterEach(()=>{cleanup();vi.resetAllMocks();});
const select=()=>fireEvent.change(screen.getByLabelText('계약 등록 파일'),{target:{files:[new File(['synthetic'],'가상.pdf',{type:'application/pdf'})]}});
it('서류 선택은 저장하지 않으며 기준 확인 화면에서만 계약을 생성한다',async()=>{const done=vi.fn(async()=>{});render(<CompareRegistration onClose={()=>{}} onSuccess={done}/>);select();fireEvent.click(screen.getByRole('button',{name:/선택한 서류 1개로 계속/}));await screen.findByLabelText('계약명');expect(api.autoCreateBatchContract).not.toHaveBeenCalled();fireEvent.change(screen.getByLabelText('계약 금액 (원)'),{target:{value:'220'}});fireEvent.click(screen.getByRole('button',{name:'계약 등록'}));await waitFor(()=>expect(done).toHaveBeenCalledWith(8));expect(api.autoCreateBatchContract).toHaveBeenCalledWith(expect.objectContaining({contract_amount:220}),expect.arrayContaining([expect.any(File)]));});
it('기준 저장 실패 후 이미 만든 계약을 다시 생성하지 않는다',async()=>{vi.mocked(api.updateContract).mockRejectedValue(new Error('자료 충돌'));render(<CompareRegistration onClose={()=>{}} onSuccess={async()=>{}}/>);select();fireEvent.click(screen.getByRole('button',{name:/선택한 서류 1개로 계속/}));await screen.findByLabelText('계약명');fireEvent.click(screen.getByRole('button',{name:'계약 등록'}));await screen.findByRole('alert');expect(screen.queryByRole('button',{name:'계약 등록'})).toBeNull();expect(screen.getByRole('button',{name:'등록한 계약 확인'})).toBeTruthy();expect(api.autoCreateBatchContract).toHaveBeenCalledOnce();});
it('떠난 등록 화면의 늦은 분석 결과는 새 작업을 덮어쓰지 않는다',async()=>{let resolve!:(value:typeof parsed)=>void;vi.mocked(api.autoParseBatchDocuments).mockImplementation(()=>new Promise(r=>{resolve=r;}));const done=vi.fn(async()=>{});const view=render(<CompareRegistration onClose={()=>{}} onSuccess={done}/>);select();fireEvent.click(screen.getByRole('button',{name:/선택한 서류 1개로 계속/}));view.unmount();resolve(parsed);await Promise.resolve();expect(done).not.toHaveBeenCalled();expect(api.autoCreateBatchContract).not.toHaveBeenCalled();});
