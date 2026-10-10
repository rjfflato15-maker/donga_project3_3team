// @vitest-environment jsdom
import {useState} from 'react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {ContractStageView} from './ContractStageView';
import {ContractDetail,ContractPayment} from '../../types';
import {requestJson} from '../../api/client';
vi.mock('../../api/client',()=>({requestJson:vi.fn()}));
vi.mock('./ApprovalPanel',()=>({ApprovalPanel:()=>null}));
vi.mock('./ActivityTimeline',()=>({ActivityTimeline:()=>null}));
vi.mock('./AssignmentPanel',()=>({AssignmentPanel:()=>null}));
vi.mock('../../context/AuthContext',()=>({useAuth:()=>({user:{user_id:1,role:'operator'}})}));
const base:ContractDetail={contract_id:1,title:'가상 계약',vendor_name:'가상 업체',business_number:'',contract_amount:110,review_status:'PASS',stage:'PAYMENT',required_document_types:[],documents:[],summary:{required_document_count:0,submitted_document_count:0,completeness_rate:100,pass_count:0,fail_count:0,review_count:0,missing_count:0},checks:[],created_at:'2026-01-01',updated_at:'2026-01-01',workflow:{revision:3,fingerprint:'basis',amount_basis:'TOTAL',tax_amount:10,payment_mode:'FULL',approval_status:'APPROVED',reviews:[]}};
const payment:ContractPayment={payment_id:8,scope:'WHOLE_CONTRACT',status:'RECORDED',correction_revision:0,paid_on:'2026-01-03',recorded_paid_on:'2026-01-03',method:'TRANSFER',note:'내 지급 메모'};
const voided={...payment,status:'VOIDED' as const,paid_on:null,correction_revision:1};
const props={isMaskingEnabled:true,canEdit:true,representative:false,onBack:()=>{},onOpenDocument:()=>{},onUploadType:()=>{},menu:[]};
const post=vi.fn();
beforeEach(()=>{
 sessionStorage.clear();HTMLElement.prototype.scrollIntoView=vi.fn();
 post.mockResolvedValue(payment);
 vi.mocked(requestJson).mockImplementation(async(url,init)=>{
  if(url.endsWith('/payment')&&init?.method==='POST')return post(JSON.parse(init.body as string));
  if(url.endsWith('/resubmission-requests'))return [];
  if(url.endsWith('/bundle-context'))return {contract_id:1,revision:3,fingerprint:'basis',vendor_candidates:[],internal_items:[],reading_items:[],pending_items:[],document_counts:{required:0,received:0,missing:0},legacy_pending_request_count:0};
  if(url.split('?')[0].endsWith('/review-context'))return {revision:3,documents:[]};
  return {text:''};
 });
});
afterEach(()=>{cleanup();vi.resetAllMocks();});
const fill=()=>{fireEvent.change(screen.getByLabelText('지급일'),{target:{value:'2026-01-03'}});fireEvent.change(screen.getByLabelText('메모'),{target:{value:'내 지급 메모'}});};
const save=()=>screen.getByRole('button',{name:'계약 전체 지급 완료로 기록'}) as HTMLButtonElement;
it('최초 지급은 버전 0과 요청 키를 보내며 불확실한 네트워크 재시도는 같은 요청을 쓴다',async()=>{
 post.mockRejectedValueOnce(new TypeError('network failed')).mockResolvedValueOnce(payment);
 render(<ContractStageView {...props} contract={base} onChanged={async()=>{}}/>);fill();fireEvent.click(save());await screen.findByText('network failed');fireEvent.click(save());
 await waitFor(()=>expect(post).toHaveBeenCalledTimes(2));expect(post.mock.calls[0][0]).toEqual(post.mock.calls[1][0]);expect(post.mock.calls[0][0]).toMatchObject({payment_revision:0,acknowledge_new_payment:false,revision:3,idempotency_key:expect.any(String)});expect(post.mock.calls[0][0].idempotency_key.length).toBeGreaterThanOrEqual(8);
});
it('취소된 지급을 새로 기록하려면 현재 버전과 명시적 재기록 확인이 필요하다',async()=>{
 render(<ContractStageView {...props} contract={{...base,payment:voided}} onChanged={async()=>{}}/>);fill();expect(save().disabled).toBe(true);
 fireEvent.click(screen.getByRole('checkbox',{name:/취소 이후 실제 지급 사실/}));fireEvent.click(save());await waitFor(()=>expect(post).toHaveBeenCalledOnce());expect(post.mock.calls[0][0]).toMatchObject({payment_revision:1,acknowledge_new_payment:true});
});
it('오래된 지급 화면의 충돌은 최신 취소 상태를 읽고 작성 내용을 유지하며 새 동의를 요구한다',async()=>{
 post.mockRejectedValueOnce(Object.assign(new Error('오래된 지급 상태'),{status:409})).mockResolvedValueOnce({...payment,correction_revision:2});
 function Wrapper(){const [contract,setContract]=useState(base);return <ContractStageView {...props} contract={contract} onChanged={async()=>{setContract({...base,payment:voided});}}/>;}
 render(<Wrapper/>);fill();fireEvent.click(save());await screen.findByRole('checkbox',{name:/취소 이후 실제 지급 사실/});
 expect((screen.getByLabelText('메모') as HTMLInputElement).value).toBe('내 지급 메모');expect((screen.getByLabelText('지급일') as HTMLInputElement).value).toBe('2026-01-03');expect(save().disabled).toBe(true);
 fireEvent.click(screen.getByRole('checkbox',{name:/취소 이후 실제 지급 사실/}));expect(save().disabled).toBe(true);fireEvent.click(screen.getByRole('checkbox',{name:/최신 지급 상태와 작성 내용을/}));fireEvent.click(save());
 await waitFor(()=>expect(post).toHaveBeenCalledTimes(2));expect(post.mock.calls[1][0]).toMatchObject({payment_revision:1,acknowledge_new_payment:true,note:'내 지급 메모'});expect(post.mock.calls[1][0].idempotency_key).not.toBe(post.mock.calls[0][0].idempotency_key);
});
it('저장 성공 후 조회 실패는 POST 재전송 대신 화면 조회만 재시도한다',async()=>{
 const changed=vi.fn().mockRejectedValueOnce(new Error('list failed')).mockResolvedValueOnce(undefined);
 render(<ContractStageView {...props} contract={base} onChanged={changed}/>);fill();fireEvent.click(save());await screen.findByText(/지급 요청은 처리됐지만 최신 화면 조회에 실패했습니다/);expect(save().disabled).toBe(true);
 fireEvent.click(screen.getByRole('button',{name:'최신 지급 화면 불러오기'}));await waitFor(()=>expect(changed).toHaveBeenCalledTimes(2));expect(post).toHaveBeenCalledOnce();
});
it('같은 계약에서 기록→완료→취소 뒤에도 새 동의로 재기록할 수 있다',async()=>{
 let calls=0;
 function Wrapper(){const [contract,setContract]=useState(base);return <><button onClick={()=>setContract({...base,payment:voided})}>Apply VOID</button><ContractStageView {...props} contract={contract} onChanged={async()=>{calls++;setContract({...base,stage:'DONE',payment:{...payment,correction_revision:calls===1?0:2}});}}/></>;}
 render(<Wrapper/>);fill();fireEvent.click(save());await screen.findByText('계약 전체 지급 기록 완료');fireEvent.click(screen.getByRole('button',{name:'Apply VOID'}));
 expect(save().disabled).toBe(true);const ack=screen.getByRole('checkbox',{name:/취소 이후 실제 지급 사실/}) as HTMLInputElement;expect(ack.disabled).toBe(false);fireEvent.click(ack);expect(save().disabled).toBe(false);fireEvent.click(save());
 await waitFor(()=>expect(post).toHaveBeenCalledTimes(2));expect(post.mock.calls[1][0].idempotency_key).not.toBe(post.mock.calls[0][0].idempotency_key);expect(post.mock.calls[1][0]).toMatchObject({payment_revision:1,acknowledge_new_payment:true});
});
it('이전 요청의 성공 응답이 이미 취소된 상태여도 새 지급 성공으로 간주하지 않는다',async()=>{
 post.mockResolvedValueOnce(voided);
 function Wrapper(){const [contract,setContract]=useState(base);return <ContractStageView {...props} contract={contract} onChanged={async()=>setContract({...base,payment:voided})}/>;}
 render(<Wrapper/>);fill();fireEvent.click(save());await screen.findByRole('checkbox',{name:/취소 이후 실제 지급 사실/});expect(screen.queryByText('계약 전체 지급 기록 완료')).toBeNull();expect(save().disabled).toBe(true);expect(post).toHaveBeenCalledOnce();
});
it('계약 화면 전체를 갱신해도 열린 정정 패널과 작성 이유를 유지한다',async()=>{
 const recorded={...base,stage:'DONE',payment};
 const view=render(<ContractStageView {...props} contract={recorded} onChanged={async()=>{}}/>);
 fireEvent.click(screen.getByRole('button',{name:'더보기'}));fireEvent.click(screen.getByRole('menuitem',{name:'지급 기록 정정'}));
 fireEvent.change(screen.getByLabelText('정정 사유'),{target:{value:'내가 확인한 지급일 오류'}});
 view.rerender(<ContractStageView {...props} contract={{...recorded,payment:{...payment,correction_revision:1,note:'다른 사용자의 수정'}}} onChanged={async()=>{}}/>);
 expect((screen.getByLabelText('정정 사유') as HTMLTextAreaElement).value).toBe('내가 확인한 지급일 오류');expect(screen.getByText(/최신 기록:.*다른 사용자의 수정/)).toBeTruthy();
 expect((screen.getByRole('button',{name:'지급 기록 정정 저장'}) as HTMLButtonElement).disabled).toBe(true);
});

it('늦은 지급 POST 성공은 이미 조회한 더 최신 취소 상태를 잠그지 않는다',async()=>{
 let resolve!:(value:ContractPayment)=>void;post.mockImplementationOnce(()=>new Promise(r=>{resolve=r;}));
 const view=render(<ContractStageView {...props} contract={base} onChanged={async()=>{}}/>);fill();fireEvent.click(save());
 view.rerender(<ContractStageView {...props} contract={{...base,payment:voided}} onChanged={async()=>{}}/>);
 await act(async()=>resolve(payment));
 const ack=screen.getByRole('checkbox',{name:/취소 이후 실제 지급 사실/}) as HTMLInputElement;
 expect(ack.disabled).toBe(false);fireEvent.click(ack);fireEvent.click(screen.getByRole('checkbox',{name:/최신 지급 상태와 작성 내용을/}));expect(save().disabled).toBe(false);
 fireEvent.click(save());await waitFor(()=>expect(post).toHaveBeenCalledTimes(2));expect(post.mock.calls[1][0]).toMatchObject({payment_revision:1,acknowledge_new_payment:true});
});
