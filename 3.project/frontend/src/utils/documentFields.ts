export const FIELD_ORDER: { key:string; label:string; types?:string[] }[] = [
  {key:'company_name',label:'상호'}, {key:'business_registration_no',label:'사업자등록번호'},
  {key:'bank_name',label:'은행',types:['bank_account']}, {key:'account_number',label:'계좌번호',types:['bank_account']},
  {key:'supply_amount',label:'공급가액'}, {key:'tax_amount',label:'세액'}, {key:'total_amount',label:'합계금액'},
  {key:'amount_scope',label:'청구 범위',types:['tax_invoice','estimate','contract']}, {key:'issue_date',label:'발행일'},
];
export const NO_AMOUNT = new Set(['business_registration','bank_account']);
export const fieldsForDocument = (type:string) => FIELD_ORDER.filter((f) => (!f.types || f.types.includes(type)) && !(NO_AMOUNT.has(type) && /amount|scope/.test(f.key)));
