// @vitest-environment jsdom
import {afterEach,describe,expect,it} from 'vitest';
import {cleanup,render,screen} from '@testing-library/react';
import {BillingSummary} from './BillingSummary';
import {ContractDetail,DocumentResponse} from '../../types';

const doc={document_type:'tax_invoice',analysis:{fields:{total_amount:38500000,amount_scope:'PARTIAL'}}} as DocumentResponse;
const contract={contract_amount:38500000,workflow:{amount_basis:'TOTAL'},payment:null} as ContractDetail;
afterEach(cleanup);
describe('청구액과 지급 사실 분리',()=>{
  it('청구액이 전액과 같아도 지급을 완료로 표시하지 않는다',()=>{
    render(<BillingSummary doc={doc} contract={contract}/>);
    expect(screen.getByText(/금액 일치/)).toBeTruthy();
    expect(screen.getByText('지급 완료 미기록')).toBeTruthy();
    expect(screen.queryByText(/^지급 기록 완료/)).toBeNull();
  });
  it('등록된 기록 상태를 그대로 구분한다',()=>{
    const {rerender}=render(<BillingSummary doc={doc} contract={{...contract,payment:{status:'RECORDED',paid_on:'2026-10-10'} as ContractDetail['payment']}}/>);
    expect(screen.getByText(/지급 기록 완료 · 2026-10-10/)).toBeTruthy();
    rerender(<BillingSummary doc={doc} contract={{...contract,payment:{status:'RECONFIRMATION_REQUIRED'} as ContractDetail['payment']}}/>);
    expect(screen.getByText('이전 지급 기록 있음 · 재확인 필요')).toBeTruthy();
    rerender(<BillingSummary doc={doc} contract={{...contract,payment:{status:'VOIDED'} as ContractDetail['payment']}}/>);
    expect(screen.getByText('지급 기록 취소됨')).toBeTruthy();
  });
  it('부가세 별도 기준은 등록된 세액만 더하며 모르는 기준을 추정하지 않는다',()=>{
    const {rerender}=render(<BillingSummary doc={doc} contract={{...contract,contract_amount:35000000,workflow:{...contract.workflow!,amount_basis:'SUPPLY',tax_amount:3500000}}}/>);
    expect(screen.getByText(/금액 일치/)).toBeTruthy();
    rerender(<BillingSummary doc={doc} contract={{...contract,workflow:{...contract.workflow!,amount_basis:'UNKNOWN'}}}/>);
    expect(screen.queryByText(/금액 일치/)).toBeNull();
    expect(screen.getByText(/계약 총액 미확인/)).toBeTruthy();
  });
});
