// @vitest-environment jsdom
import {afterEach,expect,it,vi} from 'vitest';
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {PaymentCorrectionPanel} from './PaymentCorrectionPanel';
import {requestJson} from '../../api/client';
import {ContractDetail,ContractPayment} from '../../types';
vi.mock('../../api/client',()=>({requestJson:vi.fn()}));
const contract={contract_id:1,workflow:{revision:3,fingerprint:'a'.repeat(64)}} as ContractDetail;
const payment={payment_id:8,recorded_paid_on:'2026-01-02',method:'TRANSFER',note:'원래 메모',correction_revision:4} as ContractPayment;
afterEach(()=>{cleanup();vi.resetAllMocks();});
it('정정 실패 시 입력과 이유를 유지하고 현재 지급 기록의 버전을 보낸다',async()=>{
 HTMLElement.prototype.scrollIntoView=vi.fn();vi.mocked(requestJson).mockRejectedValue(new Error('동시 수정 충돌'));
 const changed=vi.fn(async()=>{});render(<PaymentCorrectionPanel contract={contract} payment={payment} onClose={()=>{}} onChanged={changed}/>);
 fireEvent.change(screen.getByLabelText('지급일'),{target:{value:'2026-01-03'}});fireEvent.change(screen.getByLabelText('정정 사유'),{target:{value:'지급일 오기입 정정'}});fireEvent.click(screen.getByRole('button',{name:'지급 기록 정정 저장'}));await screen.findByRole('alert');
 expect((screen.getByLabelText('정정 사유') as HTMLTextAreaElement).value).toBe('지급일 오기입 정정');expect(changed).not.toHaveBeenCalled();
 const body=JSON.parse(vi.mocked(requestJson).mock.calls[0][1]?.body as string);expect(body).toMatchObject({payment_revision:4,revision:3,paid_on:'2026-01-03',action:'CORRECT'});
});
it('잘못된 지급 완료 기록 취소 성공 후 계약 상태를 갱신한다',async()=>{
 HTMLElement.prototype.scrollIntoView=vi.fn();vi.mocked(requestJson).mockResolvedValue({status:'VOIDED'});const changed=vi.fn(async()=>{}),close=vi.fn();render(<PaymentCorrectionPanel contract={contract} payment={payment} onClose={close} onChanged={changed}/>);
 fireEvent.change(screen.getByLabelText('정정할 내용'),{target:{value:'VOID'}});fireEvent.change(screen.getByLabelText('정정 사유'),{target:{value:'지급 전 완료로 오기입'}});fireEvent.click(screen.getByRole('button',{name:'지급 완료 기록 취소'}));await waitFor(()=>expect(changed).toHaveBeenCalledOnce());expect(close).toHaveBeenCalledOnce();
});

const conflict=()=>Object.assign(new Error('다른 사용자가 지급 기록을 수정했습니다.'),{status:409});
const changedPayment={...payment,status:'RECORDED' as const,recorded_paid_on:'2026-01-05',method:'OTHER' as const,note:'다른 사용자의 메모',correction_revision:5};
const writeDraft=()=>{
 fireEvent.change(screen.getByLabelText('지급일'),{target:{value:'2026-01-03'}});
 fireEvent.change(screen.getByLabelText('메모'),{target:{value:'내 메모'}});
 fireEvent.change(screen.getByLabelText('정정 사유'),{target:{value:'지급일 오기입 정정'}});
};
const postCalls=()=>vi.mocked(requestJson).mock.calls.filter(([,init])=>init?.method==='POST');
it('409 후 최신 지급을 비교하고 입력·이유를 유지한 채 명시적으로 재시도한다',async()=>{
 HTMLElement.prototype.scrollIntoView=vi.fn();
 vi.mocked(requestJson).mockRejectedValueOnce(conflict()).mockResolvedValueOnce({...contract,payment:changedPayment}).mockResolvedValueOnce(changedPayment);
 const changed=vi.fn(async()=>{}),close=vi.fn();render(<PaymentCorrectionPanel contract={contract} payment={payment} onClose={close} onChanged={changed}/>);
 writeDraft();fireEvent.click(screen.getByRole('button',{name:'지급 기록 정정 저장'}));
 await screen.findByText(/최신 기록: 2026-01-05/);
 expect((screen.getByLabelText('지급일') as HTMLInputElement).value).toBe('2026-01-03');expect((screen.getByLabelText('메모') as HTMLInputElement).value).toBe('내 메모');expect((screen.getByLabelText('정정 사유') as HTMLTextAreaElement).value).toBe('지급일 오기입 정정');
 expect((screen.getByRole('button',{name:'지급 기록 정정 저장'}) as HTMLButtonElement).disabled).toBe(true);
 fireEvent.click(screen.getByRole('checkbox',{name:/최신 지급 내용을 확인/}));fireEvent.click(screen.getByRole('button',{name:'지급 기록 정정 저장'}));
 await waitFor(()=>expect(close).toHaveBeenCalledOnce());
 expect(postCalls().map(([,init])=>JSON.parse(init!.body as string).payment_revision)).toEqual([4,5]);
 expect(JSON.parse(postCalls()[1][1]!.body as string)).toMatchObject({paid_on:'2026-01-03',note:'내 메모',reason:'지급일 오기입 정정'});
});
it('충돌 후 최신 조회 실패 때 저장을 잠그고 조회만 재시도한다',async()=>{
 HTMLElement.prototype.scrollIntoView=vi.fn();
 vi.mocked(requestJson).mockRejectedValueOnce(conflict()).mockRejectedValueOnce(new Error('network down')).mockResolvedValueOnce({...contract,payment:changedPayment});
 render(<PaymentCorrectionPanel contract={contract} payment={payment} onClose={()=>{}} onChanged={async()=>{}}/>);
 writeDraft();fireEvent.click(screen.getByRole('button',{name:'지급 기록 정정 저장'}));
 await screen.findByText(/최신 지급 기록 조회에 실패했습니다/);
 expect((screen.getByRole('button',{name:'지급 기록 정정 저장'}) as HTMLButtonElement).disabled).toBe(true);
 fireEvent.click(screen.getByRole('button',{name:'최신 지급 기록 다시 불러오기'}));await screen.findByText(/최신 기록: 2026-01-05/);
 expect(postCalls()).toHaveLength(1);expect((screen.getByLabelText('정정 사유') as HTMLTextAreaElement).value).toBe('지급일 오기입 정정');
});
it('저장은 성공했으나 화면 조회가 실패하면 다시 POST하지 않고 화면만 갱신한다',async()=>{
 HTMLElement.prototype.scrollIntoView=vi.fn();vi.mocked(requestJson).mockResolvedValue(changedPayment);
 const changed=vi.fn().mockRejectedValueOnce(new Error('목록 조회 실패')).mockResolvedValueOnce(undefined),close=vi.fn();
 render(<PaymentCorrectionPanel contract={contract} payment={payment} onClose={close} onChanged={changed}/>);
 writeDraft();fireEvent.click(screen.getByRole('button',{name:'지급 기록 정정 저장'}));await screen.findByText(/정정은 저장됐지만 최신 화면 조회에 실패했습니다/);
 expect(screen.queryByRole('button',{name:'지급 기록 정정 저장'})).toBeNull();expect(close).not.toHaveBeenCalled();
 fireEvent.click(screen.getByRole('button',{name:'저장한 내용으로 화면 갱신'}));await waitFor(()=>expect(close).toHaveBeenCalledOnce());expect(postCalls()).toHaveLength(1);
});
it('상위 화면의 지급 버전 갱신은 작성 사유를 버리지 않고 재확인을 요구한다',async()=>{
 HTMLElement.prototype.scrollIntoView=vi.fn();
 const props={contract,payment,onClose:()=>{},onChanged:async()=>{}};const view=render(<PaymentCorrectionPanel {...props}/>);writeDraft();
 view.rerender(<PaymentCorrectionPanel {...props} contract={{...contract,payment:changedPayment}} payment={changedPayment}/>);
 expect((screen.getByLabelText('정정 사유') as HTMLTextAreaElement).value).toBe('지급일 오기입 정정');
 expect(screen.getByText(/최신 기록: 2026-01-05/)).toBeTruthy();expect((screen.getByRole('button',{name:'지급 기록 정정 저장'}) as HTMLButtonElement).disabled).toBe(true);
});
it('다른 사용자가 취소한 기록은 최신 상태를 보여주고 정정을 막는다',async()=>{
 HTMLElement.prototype.scrollIntoView=vi.fn();vi.mocked(requestJson).mockRejectedValueOnce(conflict()).mockResolvedValueOnce({...contract,payment:{...changedPayment,status:'VOIDED'}});
 render(<PaymentCorrectionPanel contract={contract} payment={payment} onClose={()=>{}} onChanged={async()=>{}}/>);writeDraft();fireEvent.click(screen.getByRole('button',{name:'지급 기록 정정 저장'}));
 await screen.findByText(/현재 상태에서는 이 기록을 정정할 수 없습니다/);expect(screen.queryByRole('checkbox')).toBeNull();expect((screen.getByRole('button',{name:'지급 기록 정정 저장'}) as HTMLButtonElement).disabled).toBe(true);
});

it('늦은 충돌 복구 조회는 상위 화면에서 받은 더 최신 지급 상태를 덮어쓰지 않는다',async()=>{
 HTMLElement.prototype.scrollIntoView=vi.fn();let resolve!:(v:ContractDetail)=>void;
 vi.mocked(requestJson).mockRejectedValueOnce(conflict()).mockImplementationOnce(()=>new Promise(r=>{resolve=r;}));
 const props={contract,payment,onClose:()=>{},onChanged:async()=>{}};const view=render(<PaymentCorrectionPanel {...props}/>);writeDraft();fireEvent.click(screen.getByRole('button',{name:'지급 기록 정정 저장'}));
 await waitFor(()=>expect(requestJson).toHaveBeenCalledTimes(2));
 const newest={...changedPayment,correction_revision:6,note:'가장 최신 메모'};
 view.rerender(<PaymentCorrectionPanel {...props} payment={newest} contract={{...contract,payment:newest}}/>);
 await act(async()=>resolve({...contract,payment:changedPayment}));
 expect(screen.getByText(/최신 기록:.*가장 최신 메모/)).toBeTruthy();expect(screen.queryByText(/최신 기록:.*다른 사용자의 메모/)).toBeNull();expect((screen.getByLabelText('정정 사유') as HTMLTextAreaElement).value).toBe('지급일 오기입 정정');
});
