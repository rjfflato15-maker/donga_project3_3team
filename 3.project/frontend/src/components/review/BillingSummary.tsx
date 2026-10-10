import {ContractDetail,DocumentResponse} from '../../types';

/** Invoice amount comparison and recorded payment are independent facts. */
export function BillingSummary({contract,doc}:{contract:ContractDetail;doc:DocumentResponse}) {
  if(doc.document_type!=='tax_invoice')return null;
  const fields=doc.analysis.fields;
  const amount=fields.total_amount??(fields.supply_amount!=null&&fields.tax_amount!=null?fields.supply_amount+fields.tax_amount:null);
  const basis=contract.workflow?.amount_basis;
  const expected=basis==='TOTAL'?contract.contract_amount:basis==='SUPPLY'&&contract.workflow?.tax_amount!=null?contract.contract_amount+contract.workflow.tax_amount:null;
  const won=(value:number|null)=>value==null?'미확인':`${value.toLocaleString('ko-KR')}원`;
  const payment=contract.payment;
  const state=!payment?'지급 완료 미기록':payment.status==='RECONFIRMATION_REQUIRED'?'이전 지급 기록 있음 · 재확인 필요':payment.status==='VOIDED'?'지급 기록 취소됨':`지급 기록 완료${payment.paid_on?` · ${payment.paid_on}`:''}`;
  return <div className="billing-summary" aria-label="청구액과 지급 기록">
    <p><strong>청구액</strong> {won(amount)} · 계약 총액 {won(expected)}{amount!=null&&expected!=null&&amount===expected?' · 금액 일치':''}</p>
    <p><strong>지급 기록</strong> {state}</p>
    <small>청구액·외상미수금·잔금 문구만으로 지급 완료를 판단하지 않아요.</small>
  </div>;
}
