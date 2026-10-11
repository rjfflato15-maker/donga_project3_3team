// @vitest-environment jsdom
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {DocumentWorkspace} from './DocumentWorkspace';
import {DocumentResponse} from '../../types';
import {api,requestJson} from '../../api/client';
import {useVlmReread,VlmResult} from '../../hooks/useVlmReread';
vi.mock('../../api/client',()=>({api:{correctFields:vi.fn()},requestJson:vi.fn(),downloadProtected:vi.fn()}));
vi.mock('../../hooks/useVlmReread',()=>({useVlmReread:vi.fn()}));
const doc:DocumentResponse={document_id:4,contract_id:1,document_type:'estimate',original_file_name:'example.pdf',file_available:true,confidence:1,processing_status:'COMPLETED',mask_status:'MASKED',analysis:{fields:{supply_amount:null,tax_amount:null,total_amount:110},warnings:[]}};
const proof={document_id:4,source_version_verified:true,fields:{supply_amount:{value:null,source:'UNAVAILABLE',evidence:[]},tax_amount:{value:null,source:'UNAVAILABLE',evidence:[]},total_amount:{value:110,source:'RULE',evidence:[]}}};
const result:VlmResult={run_id:8,page:1,model:{name:'test model'},created_at:'2026-10-07T00:00:00Z',candidates:[{field:'supply_amount',value:100,quote:'supply:100',usable:true,reason:'',changed:true},{field:'tax_amount',value:10,quote:'tax:10',usable:true,reason:'',changed:true},{field:'business_registration_no',value:'123-45-67890',quote:'id',usable:true,reason:'',changed:true}]};
const reread=vi.fn(async()=>true);
const hook=()=>({status:{ready:true,model:'test',message:''},result,busy:false,error:'',reread,refresh:vi.fn()});
beforeEach(()=>{
 HTMLElement.prototype.scrollIntoView=vi.fn();URL.createObjectURL=vi.fn(()=> 'blob:test');URL.revokeObjectURL=vi.fn();
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,blob:async()=>new Blob(['source'])})));
 vi.mocked(useVlmReread).mockReturnValue(hook());
 vi.mocked(requestJson).mockImplementation(async url=>url.includes('pages-info')?{total_pages:1}:{revision:3,documents:[proof]});
});
afterEach(()=>{cleanup();vi.resetAllMocks();vi.unstubAllGlobals();});
async function loaded(){const image=await screen.findByRole('img');fireEvent.load(image);await screen.findByRole('button',{name:'공급가액 상세 보기'});}
const props={doc,checks:[],revision:3,isMaskingEnabled:true,canEdit:true,onClose:()=>{},onChanged:async()=>{}};
it('AI 제안은 원문을 불러온 뒤 선택한 금액만 명시적 적용 버튼으로 저장한다',async()=>{
 const changed=vi.fn(async()=>{});render(<DocumentWorkspace {...props} onChanged={changed}/>);
 expect((screen.getByRole('button',{name:'원문 확인 후 2개 적용'}) as HTMLButtonElement).disabled).toBe(true);
 await loaded();
 fireEvent.click(screen.getByRole('checkbox',{name:'부가세 AI 제안 선택'}));
 fireEvent.click(screen.getByRole('button',{name:'원문 확인 후 1개 적용'}));
 await waitFor(()=>expect(changed).toHaveBeenCalledOnce());
 const call=vi.mocked(requestJson).mock.calls.find(([url])=>url.endsWith('/vlm-confirm'))!;
 expect(JSON.parse(String(call[1]?.body))).toMatchObject({run_id:8,revision:3,fields:['supply_amount'],acknowledge_original:true});
});
it('저장 충돌이면 제안과 오류를 남기고 화면을 성공 상태로 넘기지 않는다',async()=>{
 const changed=vi.fn(async()=>{});vi.mocked(requestJson).mockImplementation(async url=>{if(url.endsWith('/vlm-confirm'))throw new Error('자료 변경 · 다시 확인');return url.includes('pages-info')?{total_pages:1}:{revision:3,documents:[proof]};});
 render(<DocumentWorkspace {...props} onChanged={changed}/>);await loaded();fireEvent.click(screen.getByRole('button',{name:'원문 확인 후 2개 적용'}));
 await screen.findByRole('alert');expect(screen.getByRole('alert').textContent).toContain('자료 변경');expect(changed).not.toHaveBeenCalled();expect(screen.getByRole('checkbox',{name:'공급가액 AI 제안 선택'})).toHaveProperty('checked',true);
});
it('판단 보류는 값 수정 없이 저장하고 새 확인 목록을 다시 읽는다',async()=>{
 vi.mocked(useVlmReread).mockReturnValue({...hook(),result:null});const changed=vi.fn(async()=>{});
 render(<DocumentWorkspace {...props} onChanged={changed}/>);await loaded();fireEvent.click(screen.getByRole('button',{name:'공급가액 상세 보기'}));fireEvent.click(screen.getByRole('button',{name:'선택 항목 더보기'}));fireEvent.click(screen.getByRole('menuitem',{name:'판단 보류'}));
 fireEvent.change(screen.getByLabelText('보류할 내용'),{target:{value:'계약 담당자 확인 필요'}});fireEvent.click(screen.getByRole('button',{name:'판단 보류'}));
 await waitFor(()=>expect(changed).toHaveBeenCalledOnce());const call=vi.mocked(requestJson).mock.calls.find(([url])=>url.endsWith('/defer-field'))!;
 expect(JSON.parse(String(call[1]?.body))).toEqual({field:'supply_amount',revision:3,note:'계약 담당자 확인 필요',kind:'DEFER'});
});
it('항목별 AI 읽기는 그 필드만 보내고 메뉴는 바깥 클릭과 Escape로 닫힌다',async()=>{
 vi.mocked(useVlmReread).mockReturnValue({...hook(),result:null});render(<DocumentWorkspace {...props}/>);await loaded();fireEvent.click(screen.getByRole('button',{name:'공급가액 상세 보기'}));fireEvent.click(screen.getByRole('button',{name:'AI로 다시 읽기'}));expect(reread).toHaveBeenCalledWith(['supply_amount']);
 fireEvent.click(screen.getByRole('button',{name:'선택 항목 더보기'}));fireEvent.pointerDown(document.body);expect(screen.queryByRole('menu')).toBeNull();fireEvent.click(screen.getByRole('button',{name:'선택 항목 더보기'}));fireEvent.keyDown(document,{key:'Escape'});expect(screen.queryByRole('menu')).toBeNull();
});
it('다른 서류에서 지정한 항목은 그 서류의 첫 문제로 덮어쓰지 않는다',async()=>{
 vi.mocked(useVlmReread).mockReturnValue({...hook(),result:null});
 render(<DocumentWorkspace {...props} initialField="tax_amount" checks={[{field:'4',rule_id:'AMOUNT_EXTRACTION',status:'REVIEW',message:'금액 누락'}]}/>);await loaded();
 expect(screen.getByRole('button',{name:'부가세 상세 보기'}).getAttribute('aria-pressed')).toBe('true');
});
it('오분류된 원문은 종류만 수정하며 값과 원문 확인을 임의로 덮어쓰지 않는다',async()=>{
 vi.mocked(useVlmReread).mockReturnValue({...hook(),result:null});
 const changed=vi.fn(async()=>{}),select=vi.fn();
 vi.mocked(api.correctFields).mockResolvedValue({...doc,document_type:'estimate'});
 render(<DocumentWorkspace {...props} doc={{...doc,document_type:'unknown'}} checks={[{field:'4',rule_id:'DOCUMENT_TYPE',status:'REVIEW',message:'종류 확인'}]} onChanged={changed} onSelectDocument={select}/>);
 await screen.findByRole('img');fireEvent.load(screen.getByRole('img'));
 fireEvent.click(await screen.findByRole('button',{name:/^서류 종류 수정$/}));
 fireEvent.change(screen.getByLabelText('서류 종류 수정'),{target:{value:'estimate'}});
 fireEvent.change(screen.getByLabelText('서류 종류 수정 사유'),{target:{value:'원문 제목이 견적서입니다'}});
 fireEvent.click(screen.getByRole('button',{name:'서류 종류 저장'}));
 await waitFor(()=>expect(changed).toHaveBeenCalledOnce());
 expect(api.correctFields).toHaveBeenCalledWith(4,{},'estimate',3,'원문 제목이 견적서입니다',[]);
 expect(select).toHaveBeenCalledWith(expect.objectContaining({document_type:'estimate'}));
});
it('AI가 같은 값을 읽으면 모델과 완료 안내를 보여 주고 적용 버튼은 만들지 않는다',async()=>{
 vi.mocked(useVlmReread).mockReturnValue({...hook(),result:{...result,candidates:[{...result.candidates[0],field:'total_amount',value:110,changed:false}]}});
 render(<DocumentWorkspace {...props}/>);await loaded();
 expect(screen.getByText('다시 읽기 완료 · 변경 없음')).toBeTruthy();expect(screen.getByText(/test model/)).toBeTruthy();
 expect(screen.queryByRole('button',{name:/원문 확인 후.*적용/})).toBeNull();
});
it('마지막 미해결 항목에서는 같은 항목을 다시 열지 않고 서류 목록으로 돌아간다',async()=>{
 vi.mocked(useVlmReread).mockReturnValue({...hook(),result:null});
 const close=vi.fn(),open=vi.fn();
 const invoice={...doc,document_type:'tax_invoice' as const,analysis:{fields:{supply_amount:100,tax_amount:10,total_amount:110,amount_scope:'PARTIAL' as const},warnings:[]}};
 render(<DocumentWorkspace {...props} doc={invoice} initialField="amount_scope" checks={[{field:'contract',rule_id:'PAYMENT_SCOPE',status:'REVIEW',message:'청구 범위 확인',expected:'FULL',actual:'PARTIAL'}]} onClose={close} onOpenTask={open}/>);
 const image=await screen.findByRole('img');fireEvent.load(image);
 await screen.findByRole('button',{name:'청구 범위 상세 보기'});
 expect(screen.queryByRole('button',{name:'확인 계속하기'})).toBeNull();
 expect(screen.getAllByText('문제 1건 · 필수 판단 0가지').length).toBeGreaterThan(0);
 const listButtons=screen.getAllByRole('button',{name:'서류 목록'});
 fireEvent.click(listButtons[listButtons.length-1]);
 expect(close).toHaveBeenCalledOnce();expect(open).not.toHaveBeenCalled();
});
it('다른 미해결 항목이 있으면 확인 계속하기로 그 항목을 열며 현재 문제는 유지한다',async()=>{
 vi.mocked(useVlmReread).mockReturnValue({...hook(),result:null});
 const close=vi.fn(),open=vi.fn();
 render(<DocumentWorkspace {...props} initialField="supply_amount" checks={[{field:'4',rule_id:'AMOUNT_EXTRACTION',status:'REVIEW',message:'금액 누락'}]} onClose={close} onOpenTask={open}/>);
 await loaded();fireEvent.click(screen.getByRole('button',{name:'확인 계속하기'}));
 expect(open).toHaveBeenCalledWith(expect.objectContaining({id:'4:tax_amount',field:'tax_amount'}));
 expect(close).not.toHaveBeenCalled();expect(api.correctFields).not.toHaveBeenCalled();
});
