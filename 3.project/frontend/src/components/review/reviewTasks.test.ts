import {expect,it} from 'vitest';
import {buildReviewTasks,pendingReviewTasks} from './reviewTasks';
import {DocumentResponse,ValidationCheck} from '../../types';
const doc={document_id:4,document_type:'estimate',file_available:true,processing_status:'COMPLETED',analysis:{fields:{total_amount:100,supply_amount:90,tax_amount:10},warnings:[]}} as unknown as DocumentResponse;
it('회차 청구 문제는 해당 계산서에만 붙이고 누적 문제만 전체 계산서에 붙인다',()=>{
  const invoices=[{...doc,document_id:4,document_type:'tax_invoice' as const},{...doc,document_id:5,document_type:'tax_invoice' as const}];
  expect(buildReviewTasks(invoices,[{rule_id:'PAYMENT_SCOPE',field:'4',status:'REVIEW',message:'잔금 금액 확인'}]).map(t=>t.document?.document_id)).toEqual([4]);
  expect(buildReviewTasks(invoices,[{rule_id:'PAYMENT_SCOPE',field:'tax_invoice',status:'REVIEW',message:'청구 중복 확인'}]).map(t=>t.document?.document_id)).toEqual([4,5]);
});
it('정상값과 선택적 미확인은 할 일 수에 넣지 않는다',()=>{
  expect(buildReviewTasks([doc],[],{revision:1,documents:[{document_id:4,fields:{}}]})).toEqual([]);
});
it('산술 검사 하나를 세 필드 불일치로 부풀리지 않고 실제 기준만 표시한다',()=>{
  const checks=[{rule_id:'AMOUNT_COMPONENTS',field:'4',status:'FAIL',expected:'공급가액 + 세액 = 합계',actual:'다름',message:'계산 불일치'}] as ValidationCheck[];
  const tasks=buildReviewTasks([doc],checks);expect(tasks).toHaveLength(1);expect(tasks[0].field).toBe('total_amount');expect(tasks[0].expected).toBe('공급가액 + 세액 = 합계');
});
it('못 읽은 필수 금액만 나누고 날짜 등 선택 필드를 끼워 넣지 않는다',()=>{
  const empty={...doc,analysis:{fields:{total_amount:100},warnings:[]}};
  const tasks=buildReviewTasks([empty],[{field:'4',rule_id:'AMOUNT_EXTRACTION',status:'REVIEW',message:'금액 읽기 확인'}]);
  expect(tasks.map(t=>t.field)).toEqual(['supply_amount','tax_amount']);
});
it('AI 확인 대상과 보류는 유지하지만 이전 본과 미조회 국세청 안내는 세지 않는다',()=>{
  const tasks=buildReviewTasks([doc,{...doc,document_id:5,version:{logical_document_id:4,version_number:1,is_current:false,previous_document_id:null}}],
    [{field:'4',rule_id:'BUSINESS_STATUS',status:'REVIEW',message:'미조회'}],{revision:1,documents:[{document_id:4,fields:{},ai_review:{manual_review_required:true,targets:['total_amount']},deferrals:{supply_amount:{note:'확인 필요',actor_name:'담당',at:'now'}}}]});
  expect(tasks.map(t=>t.field)).toEqual(['total_amount','supply_amount']);expect(tasks[1].deferral?.note).toBe('확인 필요');
});
it('요청에 담은 불일치만 남은 확인에서 빼고 확인하지 않은 문제는 유지한다',()=>{
  const tasks=buildReviewTasks([doc],[{field:'4',rule_id:'BUSINESS_NO_MATCH',status:'FAIL',message:'번호 다름'},{field:'4',rule_id:'AMOUNT_COMPONENTS',status:'FAIL',message:'산술 확인'}]);
  const context={revision:1,documents:[{document_id:4,fields:{business_registration_no:{value:'123',source:'RULE',evidence:[],human_confirmation:{actor_name:'담당',at:'now'}}}}]};
  expect(pendingReviewTasks(tasks,context,{4:'draft'}).map(t=>t.field)).toEqual(['total_amount']);
  expect(pendingReviewTasks(tasks,context,{})).toHaveLength(2);
});
it('회신 대기와 초안에 담긴 미제출만 제외하고 새 미제출과 보류는 남긴다',()=>{
  const tasks=buildReviewTasks([doc],[{rule_id:'REQUIRED_DOCUMENTS',field:'bank_account',status:'FAIL',message:'누락'},{rule_id:'REQUIRED_DOCUMENTS',field:'tax_invoice',status:'FAIL',message:'누락'}],{revision:1,documents:[{document_id:4,fields:{},deferrals:{total_amount:{note:'추가 확인',actor_name:'담당',at:'now'}}}]});
  expect(tasks.map(task=>task.id)).toContain('missing:bank_account');
  expect(pendingReviewTasks(tasks,null,{'missing:bank_account':'waiting'}).map(task=>task.id)).toEqual(['missing:tax_invoice','4:total_amount']);
  expect(pendingReviewTasks(tasks,null,{'missing:bank_account':'draft','missing:tax_invoice':'waiting','4':'draft'}).map(task=>task.id)).toEqual(['4:total_amount']);
});
it('상신 전 값 대조는 문제와 구분해 뒤로 보내고, 같은 칸의 실제 문제는 문제로 남긴다',()=>{
  const blockers=[
    {code:'HUMAN_REVIEW_REQUIRED',reason:'대조 필요',document_id:4,field:'company_name'},
    {code:'HUMAN_REVIEW_REQUIRED',reason:'대조 필요',document_id:4,field:'total_amount'},
  ] as never;
  const tasks=buildReviewTasks([{...doc,analysis:{fields:{...doc.analysis.fields,company_name:'가상'},warnings:[]}} as DocumentResponse],
    [{field:'4',rule_id:'AMOUNT_COMPONENTS',status:'FAIL',message:'계산 불일치'}],null,blockers);
  expect(tasks.map(t=>[t.field,!!t.routine])).toEqual([['total_amount',false],['company_name',true]]);
});
