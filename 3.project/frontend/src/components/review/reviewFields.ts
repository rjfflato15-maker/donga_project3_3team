import { AnalysisFields, DocumentResponse, ValidationCheck, SubmissionState } from '../../types';
import { fieldsForDocument } from '../../utils/documentFields';
import { maskAccountNumber, maskBusinessNumber, maskVendorName } from '../../utils/masking';

export interface BBox { page: number; x: number; y: number; width: number; height: number }
export interface Anchor { page: number | null; line: number | null; quote: string; bbox?: BBox | null; bboxes?: BBox[] }
export interface FieldProof { actor_id?: number; actor_name: string; at: string; method?: string; run_id?: number }
export interface FieldProvenance {
  value: string | number | null; source: string; original_source?: string;
  evidence: Anchor[]; human_confirmation?: FieldProof | null;
}
export interface FieldDeferral { note:string; actor_id?:number|null; actor_name:string; at:string; kind?:'DEFER'|'NO_ISSUE' }
export interface Provenance { document_id: number; fields: Record<string, FieldProvenance>; deferrals?:Record<string,FieldDeferral>; no_issue?:Record<string,FieldDeferral>; source_version_verified?:boolean;
  ai_review?:{manual_review_required?:boolean;targets?:string[];human_unconfirmed_fields?:string[]} }
export interface ReviewContext { revision: number; documents: Provenance[]; checks?:ValidationCheck[]; workflow?:{submission?:SubmissionState} }
export const sensitiveField = (key: string) => ['company_name', 'business_registration_no', 'account_number'].includes(key);
export const hasValue = (value: unknown) => value !== null && value !== undefined && value !== '' && value !== 'UNKNOWN';

export function displayValue(key: string, value: unknown, masked: boolean): string {
  if (key === 'amount_scope' && !hasValue(value)) return '범위 확인 필요';
  if (!hasValue(value)) return '못 읽음';
  if (value === '[가림]') return '[가림]';
  if (key.endsWith('amount') && Number.isFinite(Number(value))) return `${Number(value).toLocaleString('ko-KR')}원`;
  if (key === 'amount_scope') return value === 'FULL' ? '전액 청구' : value === 'PARTIAL' ? '일부 청구' : String(value);
  if (key === 'company_name') return maskVendorName(String(value), masked);
  if (masked && key === 'business_registration_no') return maskBusinessNumber(String(value));
  if (masked && key === 'account_number') return maskAccountNumber(String(value));
  return String(value);
}
const priority = ['total_amount','supply_amount','tax_amount','company_name','business_registration_no','account_number','bank_name','amount_scope','issue_date'];
export function reviewRows(doc: DocumentResponse) {
  return [...fieldsForDocument(doc.document_type)].map(row=>row.key==='total_amount'&&doc.analysis.fields.total_amount==null&&doc.analysis.fields.amount!=null?{...row,key:'amount',label:'금액 (기존 추출값)'}:row).sort((a,b) => priority.indexOf(a.key) - priority.indexOf(b.key)).map(row => ({...row,
    label: ({total_amount:'합계',tax_amount:'부가세',company_name:doc.document_type==='bank_account'?'예금주':'거래처',business_registration_no:'사업자번호',account_number:'입금 계좌',issue_date:doc.document_type === 'contract' ? '계약일' : '발행일'} as Record<string,string>)[row.key] || row.label}));
}
export function checksForField(key: string, checks: ValidationCheck[]) {
  const amount = ['supply_amount','tax_amount','total_amount'].includes(key);
  return checks.filter(check => check.rule_id === 'BUSINESS_NO_MATCH' && key === 'business_registration_no'
    || check.rule_id === 'ACCOUNT_HOLDER_MATCH' && key === 'company_name'
    || check.rule_id === 'VENDOR_NAME_MATCH' && key === 'company_name'
    || check.rule_id === `SOURCE_VALUE_MATCH_${key.toUpperCase()}`
    || ['AMOUNT_COMPONENTS','AMOUNT_EXTRACTION'].includes(check.rule_id) && amount
    || check.rule_id.startsWith('AMOUNT_MATCH_') && key === (check.message.includes('공급가액 기준') ? 'supply_amount' : 'total_amount')
    || check.rule_id === 'PAYMENT_SCOPE' && key === 'amount_scope'
    || check.rule_id === 'INSTALLMENT_TOTAL' && key === 'total_amount');
}
export function checkState(checks: ValidationCheck[]) {
  if (!checks.length) return {label:'결과 없음',tone:'neutral'};
  if (checks.some(check => check.status === 'FAIL')) return {label:'불일치',tone:'red'};
  if (checks.some(check => check.status !== 'PASS')) return {label:'확인 필요',tone:'amber'};
  return {label:'일치',tone:'green'};
}
export function sourceLabel(proof?: FieldProvenance) {
  if (!proof || proof.source === 'UNAVAILABLE') return '출처 없음';
  if (proof.human_confirmation?.method === 'VLM_ORIGINAL_CONFIRMED') return 'AI 후보·사람 선택';
  if (['CHANGED_VALUE','LEGACY_CHANGED_VALUE'].includes(proof.human_confirmation?.method || '')) return '사람 수정';
  return (proof.original_source || proof.source) === 'AI_SUPPLEMENT' ? 'AI' : '자동 읽기';
}
export function documentStats(doc: DocumentResponse, provenance: Provenance | undefined, checks: ValidationCheck[]) {
  const rows = reviewRows(doc);
  const values = doc.analysis.fields as Record<string, unknown>;
  const docChecks = checks.filter(check => check.field === String(doc.document_id));
  return {total:rows.length,confirmed:provenance ? rows.filter(row => provenance.fields[row.key]?.human_confirmation).length : null,
    failed:rows.filter(row => !hasValue(values[row.key])).length,
    mismatched:rows.filter(row => checkState(checksForField(row.key,docChecks)).label === '불일치').length,
    unconfirmed:provenance ? rows.filter(row => hasValue(values[row.key]) && !provenance.fields[row.key]?.human_confirmation).length : null};
}
export function editedValue(key: string, input: string): AnalysisFields {
  return {[key]:key.endsWith('amount') ? input.trim() === '' ? null : Number(input) : input.trim()};
}
