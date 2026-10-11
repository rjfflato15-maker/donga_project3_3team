import {expect,it} from 'vitest';
import {checksForField,checkState,reviewRows} from './reviewFields';
import type {DocumentResponse,ValidationCheck} from '../../types';
it('저장값끼리 일치해도 스캔 원문 재판독 불일치를 일치로 표시하지 않는다',()=>{
 const checks=[{rule_id:'BUSINESS_NO_MATCH',status:'PASS',field:'1'},
 {rule_id:'SOURCE_VALUE_MATCH_BUSINESS_REGISTRATION_NO',status:'REVIEW',field:'1',expected:'0000000000',actual:'1111111111'}] as ValidationCheck[];
 expect(checkState(checksForField('business_registration_no',checks)).label).toBe('확인 필요');
});
it('통장사본에서 계약 거래처와 대조할 사람은 예금주로 표시하고 상호 문제도 연결한다',()=>{
 const doc={document_type:'bank_account',analysis:{fields:{company_name:'가상 업체'}}} as DocumentResponse;
 expect(reviewRows(doc).find(row=>row.key==='company_name')?.label).toBe('예금주');
 expect(checksForField('company_name',[{rule_id:'VENDOR_NAME_MATCH',status:'REVIEW',field:'1'} as ValidationCheck])).toHaveLength(1);
});
