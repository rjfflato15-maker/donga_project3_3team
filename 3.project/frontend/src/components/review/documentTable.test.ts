import { describe, expect, it } from 'vitest';
import { confirmationCount } from './DocumentTable';
import { fieldsForDocument } from '../../utils/documentFields';
describe('원문 확인은 표시 대상 필드만 센다', () => {
  it('빈 값은 제외하고 0원도 확인 대상에 포함한다', () => {
    expect(confirmationCount({tax:{value:0,human_confirmation:{actor_name:'담당자'}},total:{value:100},empty:{value:null},unknown:{value:'UNKNOWN'}})).toEqual({total:2,confirmed:1});
  });
  it('통장사본의 은행·계좌를 포함하고 금액은 제외한다', () => {
    const keys=fieldsForDocument('bank_account').map((f) => f.key);
    expect(keys).toContain('account_number');expect(keys).toContain('bank_name');expect(keys).not.toContain('total_amount');
  });
});
