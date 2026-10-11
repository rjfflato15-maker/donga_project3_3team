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
it('UNKNOWN은 범위 입력을 바로 열고 미확인 그대로 저장하거나 정상 확인하지 않는다',async()=>{
 const invoice={...doc,document_type:'tax_invoice' as const,analysis:{...doc.analysis,fields:{...doc.analysis.fields,amount_scope:'UNKNOWN' as const}}};
 const proof={...context,documents:[{...context.documents[0],fields:{...context.documents[0].fields,amount_scope:{value:'UNKNOWN',source:'RULE',evidence:[]}}}]};
 render(<DocumentWorkspace {...props} doc={invoice} initialField="amount_scope" sharedContext={proof}/>);
 expect(await screen.findByLabelText('청구 범위 수정값')).toBeTruthy();
 fireEvent.change(screen.getByLabelText('수정 사유'),{target:{value:'계약 조건과 원문 대조'}});
 expect(screen.getByRole('button',{name:'원문 값으로 저장'})).toHaveProperty('disabled',true);
 expect(screen.getByRole('button',{name:'문제없음'})).toHaveProperty('disabled',true);
 fireEvent.change(screen.getByLabelText('청구 범위 수정값'),{target:{value:'FULL'}});
 expect(screen.getByRole('button',{name:'원문 값으로 저장'})).toHaveProperty('disabled',false);
});
it.each([false,true])('원문 확인 성공 후 동일 차수·값·기록일 때만 판단 선택을 이어간다 changed=%s',async changedValue=>{
 const issue=[{field:'4',rule_id:'AMOUNT_MATCH_ESTIMATE',status:'FAIL' as const,expected:'220',actual:'110',message:'합계 불일치'}];
 const fresh={...context,revision:4,documents:[{...context.documents[0],fields:{...context.documents[0].fields,total_amount:{value:changedValue?120:110,source:'RULE',evidence:[],human_confirmation:{actor_name:'synthetic',at:'just-saved'}}}}]};
 vi.mocked(requestJson).mockImplementation(async url=>url.endsWith('/confirm-field')?{field:'total_amount',revision:4,confirmed_at:'just-saved'}:url.includes('text-preview')?{text:'synthetic original 110'}:fresh);
 const view=render(<DocumentWorkspace {...props} checks={issue} onRefreshContext={async()=>fresh}/>);
 await screen.findByText('synthetic original 110');fireEvent.click(screen.getByRole('button',{name:'문제없음'}));
 fireEvent.click(screen.getByLabelText('원문에 이 값이 적힌 것을 직접 확인했습니다.'));fireEvent.click(screen.getByRole('button',{name:'원문 확인 저장'}));
 await waitFor(()=>expect(props.onChanged).toHaveBeenCalled());
 view.rerender(<DocumentWorkspace {...props} revision={4} sharedContext={fresh} checks={issue} onRefreshContext={async()=>fresh}/>);
 await waitFor(()=>expect(screen.getByRole('button',{name:'문제없음'}).getAttribute('aria-pressed')).toBe(String(!changedValue)));
 if(!changedValue)expect(screen.getByRole('button',{name:'판단 근거 작성'})).toBeTruthy();
});
it('원문 확인한 정상값은 완료 문구를 보이되 비교 문제가 남으면 경고를 유지한다',async()=>{
 const confirmed={...context,documents:[{...context.documents[0],fields:{...context.documents[0].fields,total_amount:{...context.documents[0].fields.total_amount,human_confirmation:{actor_name:'가상 담당자',at:'2026-10-10',revision:3}}}}]};
 const {rerender}=render(<DocumentWorkspace {...props} sharedContext={confirmed}/>);
 await screen.findByText('원문 확인을 완료한 값입니다.');expect(screen.queryByText('원문과 읽은 값이 같은지 확인하세요.')).toBeNull();
 rerender(<DocumentWorkspace {...props} sharedContext={confirmed} checks={[{field:'4',rule_id:'AMOUNT_MATCH_ESTIMATE',status:'FAIL',expected:'220',actual:'110',message:'합계가 계약 기준과 다릅니다.'}]}/>);
 expect(screen.getByText('합계가 계약 기준과 다릅니다.')).toBeTruthy();expect(screen.queryByText('원문 확인을 완료한 값입니다.')).toBeNull();
 expect(screen.getByRole('status').textContent).toContain('비교 문제는 별도 판단');
});
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
 fireEvent.click(screen.getByRole('button',{name:'보완 필요'}));expect(screen.queryByLabelText('합계 수정값')).toBeNull();expect(screen.getByRole('button',{name:'원문 확인 후 보완 요청에 담기'})).toBeTruthy();
 fireEvent.click(screen.getByRole('button',{name:'계약 기준 수정'}));expect(screen.getByRole('button',{name:'계약 정보 열기'})).toBeTruthy();expect(screen.queryByRole('button',{name:'원문 확인 후 보완 요청에 담기'})).toBeNull();
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
it('보완 요청은 원문 확인을 저장하고 최신 확인 결과로 담으며 불일치를 문제없음으로 바꾸지 않는다',async()=>{
 const request=vi.fn(),changed=vi.fn(async()=>{});
 const fresh={...context,revision:4,documents:[{...context.documents[0],fields:{...context.documents[0].fields,total_amount:{...context.documents[0].fields.total_amount,human_confirmation:{actor_name:'합성 담당자',at:'2026-10-10',revision:4}}}}]};
 render(<DocumentWorkspace {...props} onChanged={changed} onRequest={request} onRefreshContext={async()=>fresh} checks={[{field:'4',rule_id:'AMOUNT_MATCH_ESTIMATE',status:'FAIL',expected:'220',actual:'110',message:'합계 불일치'}]}/>);
 await screen.findByText('synthetic original 110');
 fireEvent.click(screen.getByRole('button',{name:'보완 필요'}));
 expect(request).not.toHaveBeenCalled();
 fireEvent.click(screen.getByRole('button',{name:'원문 확인 후 보완 요청에 담기'}));
 await waitFor(()=>expect(request).toHaveBeenCalledWith(4,fresh));
 expect(changed).toHaveBeenCalledOnce();
 const writes=vi.mocked(requestJson).mock.calls.filter(([,args])=>args?.method==='POST');
 expect(writes).toHaveLength(1);expect(writes[0][0]).toBe('/api/documents/4/confirm-field');
 expect(JSON.parse(String(writes[0][1]?.body))).toEqual({field:'total_amount',revision:3});
});
it('원문 확인 저장 실패는 요청 초안을 만들지 않고 오류를 남긴다',async()=>{
 const request=vi.fn(),changed=vi.fn(async()=>{});
 vi.mocked(requestJson).mockImplementation(async url=>{if(url.endsWith('/confirm-field'))throw new Error('자료가 변경됐습니다');return url.includes('text-preview')?{text:'synthetic original 110'}:context;});
 render(<DocumentWorkspace {...props} onChanged={changed} onRequest={request}/>);await screen.findByText('synthetic original 110');
 fireEvent.click(screen.getByRole('button',{name:'보완 필요'}));fireEvent.click(screen.getByRole('button',{name:'원문 확인 후 보완 요청에 담기'}));
 expect(await screen.findByRole('alert')).toHaveProperty('textContent',expect.stringContaining('자료가 변경됐습니다'));
 expect(request).not.toHaveBeenCalled();expect(changed).not.toHaveBeenCalled();
});
it('가려진 항목은 보완 요청에서도 가림 해제와 실제 원문 대조를 요구한다',async()=>{
 const request=vi.fn();render(<DocumentWorkspace {...props} initialField="company_name" isMaskingEnabled onRequest={request}/>);
 await screen.findByText('synthetic original 110');fireEvent.click(screen.getByRole('button',{name:'보완 필요'}));
 expect(screen.getByRole('button',{name:'원문 확인 후 보완 요청에 담기'})).toHaveProperty('disabled',true);
 expect(request).not.toHaveBeenCalled();
});
