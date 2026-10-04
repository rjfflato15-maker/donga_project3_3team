import { ContractDetail, DocumentResponse, DocumentType, ValidationCheck, ValidationStatus } from '../types';
import { fixParticles } from './korean';

export const DOCUMENT_TYPE_KO: Record<DocumentType, string> = {
  contract: '외주용역 계약서',
  estimate: '견적서',
  business_registration: '사업자등록증',
  bank_account: '통장사본',
  tax_invoice: '전자세금계산서',
  inspection_confirmation: '납품 검수확인서',
  unknown: '미분류 문서',
};

export const STATUS_KO: Record<ValidationStatus, string> = {
  PASS: '일치',
  FAIL: '불일치',
  MISSING: '미제출',
  REVIEW: '확인 필요',
};

// 검사 이름을 업무 용어로
const RULE_KO: Record<string, string> = {
  REQUIRED_DOCUMENTS: '필수 서류 제출',
  BUSINESS_NO_MATCH: '사업자번호 대조',
  BUSINESS_STATUS: '사업자 영업 상태',
  AMOUNT_BASIS: '계약 금액 기준',
  AMOUNT_COMPONENTS: '서류 안의 금액 계산',
  AMOUNT_EXTRACTION: '금액 읽기',
  AMOUNT_MATCH_ESTIMATE: '견적 금액과 계약 금액',
  AMOUNT_MATCH_TAX_INVOICE: '세금계산서 금액과 계약 금액',
  PAYMENT_SCOPE: '청구 범위(전액·분할)',
  INSTALLMENT_TOTAL: '분할 청구 누적 금액',
  DUPLICATE_INVOICE: '세금계산서 중복',
  ORIGINAL_FILE: '원본 파일',
  DOCUMENT_TYPE: '문서 종류',
  DOCUMENT_PROCESSING: '글자 인식',
};

export const ruleLabel = (ruleId: string) => RULE_KO[ruleId] ?? ruleId;

/** 회사 안에서 만드는 서류라 거래처에 요청할 대상이 아닌 종류 */
export const INTERNAL_DOCUMENT_TYPES: DocumentType[] = ['inspection_confirmation'];
export const isInternalDocument = (t?: DocumentType) => !!t && INTERNAL_DOCUMENT_TYPES.includes(t);

/** 카드 제목에 서류 이름이 있으므로 메시지 앞의 '파일명: '은 뺀다. */
export const plainMessage = (message: string) => fixParticles(message.replace(/^[^:：]{1,80}\.(pdf|png|jpe?g|docx?|hwp|tiff?)\s*[:：]\s*/i, ''));

/** 기준·서류 값을 보여 줄 의미가 있는 검사인지 */
export const showsValues = (ruleId: string) => !['REQUIRED_DOCUMENTS', 'AMOUNT_EXTRACTION', 'DOCUMENT_TYPE', 'DOCUMENT_PROCESSING', 'ORIGINAL_FILE'].includes(ruleId);

const SEVERITY: Record<ValidationStatus, number> = { FAIL: 0, MISSING: 1, REVIEW: 2, PASS: 3 };

/** 외부 조회를 하지 않는 환경에서 항상 나오는 사업자 상태 '확인 필요'는 할 일이 아니라 안내로 보낸다. */
export const isUnverifiedBusinessStatus = (check: ValidationCheck) =>
  check.rule_id === 'BUSINESS_STATUS' && check.status === 'REVIEW';

/** 거래처 서류의 문제가 아니라, 앱이 원문을 제대로 읽지 못해 사람이 값을 확인해야 하는 검사 */
const READING_RULES = new Set(['AMOUNT_EXTRACTION', 'DOCUMENT_TYPE', 'DOCUMENT_PROCESSING', 'ORIGINAL_FILE']);
export const isReadingCheck = (c: ValidationCheck) =>
  READING_RULES.has(c.rule_id) || (c.rule_id === 'BUSINESS_NO_MATCH' && c.status === 'REVIEW');

export type IssueKind = 'missing' | 'vendor' | 'reading' | 'contract';

export interface IssueGroup {
  key: string;
  kind: IssueKind;
  title: string;
  /** 문서에 붙은 문제면 그 문서 */
  document?: DocumentResponse;
  /** 미제출 서류 종류 */
  missingType?: DocumentType;
  status: ValidationStatus;
  checks: ValidationCheck[];
}

export interface PassedGroup {
  ruleId: string;
  label: string;
  count: number;
  messages: string[];
}

export interface ReviewOverview {
  issues: IssueGroup[];
  passed: PassedGroup[];
  notices: ValidationCheck[];
  worst: ValidationStatus | null;
  documentStatus: Map<number, ValidationStatus>;
}

const worstOf = (checks: ValidationCheck[]): ValidationStatus =>
  checks.reduce<ValidationStatus>((acc, c) => (SEVERITY[c.status] < SEVERITY[acc] ? c.status : acc), 'PASS');

export function buildReviewOverview(contract: ContractDetail): ReviewOverview {
  const docsById = new Map(contract.documents.map((d) => [String(d.document_id), d]));
  const notices = contract.checks.filter(isUnverifiedBusinessStatus);
  const actionable = contract.checks.filter((c) => c.status !== 'PASS' && !isUnverifiedBusinessStatus(c));

  const groups = new Map<string, IssueGroup>();
  for (const check of actionable) {
    const doc = docsById.get(check.field);
    let key: string;
    let title: string;
    let missingType: DocumentType | undefined;
    if (doc) {
      key = `doc-${doc.document_id}`;
      title = DOCUMENT_TYPE_KO[doc.document_type] ?? doc.original_file_name;
    } else if (check.rule_id === 'REQUIRED_DOCUMENTS') {
      key = `missing-${check.field}`;
      missingType = check.field as DocumentType;
      title = `${DOCUMENT_TYPE_KO[missingType] ?? check.field} 미제출`;
    } else {
      key = `contract-${check.rule_id}`;
      title = ruleLabel(check.rule_id);
    }
    const group = groups.get(key) ?? { key, kind: 'contract' as IssueKind, title, document: doc, missingType, status: check.status, checks: [] };
    group.checks.push(check);
    group.status = worstOf(group.checks);
    group.kind = missingType ? 'missing' : !doc ? 'contract' : group.checks.every(isReadingCheck) ? 'reading' : 'vendor';
    groups.set(key, group);
  }
  const issues = [...groups.values()].sort((a, b) => SEVERITY[a.status] - SEVERITY[b.status]);

  const passedMap = new Map<string, PassedGroup>();
  for (const check of contract.checks.filter((c) => c.status === 'PASS')) {
    const group = passedMap.get(check.rule_id) ?? { ruleId: check.rule_id, label: ruleLabel(check.rule_id), count: 0, messages: [] };
    group.count += 1;
    group.messages.push(check.message);
    passedMap.set(check.rule_id, group);
  }

  const documentStatus = new Map<number, ValidationStatus>();
  for (const doc of contract.documents) {
    const related = actionable.filter((c) => c.field === String(doc.document_id));
    documentStatus.set(doc.document_id, related.length ? worstOf(related) : 'PASS');
  }

  return {
    issues,
    passed: [...passedMap.values()],
    notices,
    worst: issues.length ? issues[0].status : null,
    documentStatus,
  };
}

/** 계약 상단에 보여 줄 결론 문장 */
export function verdictText(overview: ReviewOverview): { title: string; detail: string } {
  const { issues } = overview;
  if (!issues.length) {
    return { title: '확인할 항목이 없습니다', detail: '모든 검사가 일치합니다. 결재를 요청할 수 있습니다.' };
  }
  const count = (k: IssueKind) => issues.filter((i) => i.kind === k).length;
  const parts: string[] = [];
  if (count('missing')) parts.push(`빠진 서류 ${count('missing')}종`);
  if (count('vendor')) parts.push(`서류 내용 확인 ${count('vendor')}건`);
  if (count('reading')) parts.push(`원문 확인 ${count('reading')}건`);
  if (count('contract')) parts.push(`계약 기준 확인 ${count('contract')}건`);
  const first = issues[0];
  return { title: `지급 전에 확인할 것: ${parts.join(', ')}`, detail: `${first.title}: ${plainMessage(first.checks[0].message)}` };
}
