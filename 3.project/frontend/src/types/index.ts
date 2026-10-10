export type DocumentType =
  | 'contract'
  | 'estimate'
  | 'business_registration'
  | 'bank_account'
  | 'tax_invoice'
  | 'inspection_confirmation'
  | 'unknown';

export type ProcessingStatus =
  | 'UPLOADED'
  | 'PREPROCESSING'
  | 'ANALYZING'
  | 'COMPLETED'
  | 'REVIEW'
  | 'FAILED';

export type MaskStatus =
  | 'NOT_STARTED'
  | 'MASKED'
  | 'REVIEW_NEEDED'
  | 'FAILED';

export type ValidationStatus =
  | 'PASS'
  | 'REVIEW'
  | 'MISSING'
  | 'FAIL';

export interface AnalysisFields {
  company_name?: string | null;
  business_registration_no?: string | null;
  amount?: number | null;
  issue_date?: string | null;
  contract_period_start?: string | null;
  contract_period_end?: string | null;
  account_number?: string | null;
  bank_name?: string | null;
  supply_amount?: number | null;
  tax_amount?: number | null;
  total_amount?: number | null;
  amount_basis?: 'TOTAL' | 'SUPPLY' | 'UNKNOWN';
  amount_scope?: 'FULL' | 'PARTIAL' | 'UNKNOWN';
}

export interface DocumentResponse {
  document_id: number;
  contract_id: number;
  original_file_name: string;
  document_type: DocumentType;
  confidence: number;
  processing_status: ProcessingStatus;
  mask_status: MaskStatus;
  analysis: {
    fields: AnalysisFields;
    warnings: string[];
  };
  raw_text?: string | null;
  masked_text?: string | null;
  business_status?: string | null;
  file_available?: boolean;
  file_size?: number | null;
  version?: { logical_document_id: number; version_number: number; is_current: boolean; previous_document_id: number | null } | null;
  llm?: DocumentLlm | null;
}

export interface DocumentLlm {
  configured_enabled_at_analysis?: boolean | null;
  status?: string;
  inference_invoked?: boolean | null;
  invocation_count?: number | null;
  error?: string | null;
  applied_value_field_count?: number;
  current_matching_ai_value_field_count?: number;
  human_confirmed?: boolean;
  manual_review_required?: boolean;
}

export interface ValidationCheck {
  rule_id: string;
  status: ValidationStatus;
  field: string;
  expected?: string | null;
  actual?: string | null;
  message: string;
}

export interface ValidationSummary {
  required_document_count: number;
  submitted_document_count: number;
  completeness_rate: number;
  pass_count: number;
  fail_count: number;
  review_count: number;
  missing_count: number;
  match_rate?: number | null;
  mismatch_rate?: number | null;
}

export interface ValidationReportResponse {
  contract_id: number;
  summary: ValidationSummary;
  checks: ValidationCheck[];
}

export interface ContractDetail {
  stage?: string | null;
  work_state?: { counts?: { waiting_requests?: number } };
  contract_id: number;
  title: string;
  vendor_name: string;
  business_number: string;
  contract_amount: number;
  review_status: string;
  required_document_types: DocumentType[];
  documents: DocumentResponse[];
  summary: ValidationSummary;
  checks: ValidationCheck[];
  created_at: string;
  updated_at: string;
  workflow?: Workflow;
  llm?: ContractLlm | null;
  payment?: ContractPayment | null;
  registration?: {request_key:string;complete:boolean;failed_files:{index:number|null;file_name:string|null;message:string}[]} | null;
}

/** 계약 전체 지급 완료 사실(송금 아님). paid_on은 현재 결재에 연결된 경우에만 채워진다 */
export interface ContractPayment {
  payment_id: number;
  scope: 'WHOLE_CONTRACT';
  status: 'RECORDED' | 'RECONFIRMATION_REQUIRED' | 'VOIDED';
  correction_revision?: number;
  paid_on: string | null;
  recorded_paid_on: string;
  method: 'TRANSFER' | 'OTHER';
  note: string;
  actor_name?: string;
  reconfirmation_allowed?: boolean;
  blocked_reason?: 'FINAL_REVIEW_REQUIRED' | 'SOURCE_VERSION_UNVERIFIED' | 'PAYEE_OR_AMOUNT_CHANGED' | null;
}

export interface LlmStatus {
  configured_enabled: boolean;
  model?: string;
  connection_state?: string;
  connected: boolean | null;
  model_installed?: boolean | null;
  ready_for_inference: boolean;
  checked_at?: string | null;
  error?: string | null;
}

export interface ContractLlm {
  current_state?: LlmStatus;
  document_count?: number;
  invoked_document_count?: number;
  failed_document_count?: number;
  applied_value_field_count?: number;
  current_matching_ai_value_field_count?: number;
}

export interface PilotPerformance {
  contracts: { contract_id: number; human_correction_save_count: number; human_field_edit_count: number; human_changed_unique_field_count: number; ai_applied_value_field_count: number; ai_current_matching_value_field_count: number; resubmission_request_count: number }[];
  totals: { contract_count: number; currently_confirmed_contract_count: number; mean_registration_to_current_final_confirmation_elapsed_seconds: number | null };
}

export interface ContractListItem {
  contract_id: number;
  title: string;
  vendor_name: string;
  business_number: string;
  contract_amount: number;
  review_status: string;
  completeness_rate: number;
  submitted_docs_count: number;
  total_docs_count: number;
  submitted_document_types?: string[];
  created_at: string;
  approval_status?: string;
  revision?: number;
  missing_original_count?: number;
}

export interface PipelineStep {
  step: number;
  title: string;
  status: string;
  message: string;
  details: any;
}

export interface PipelineSimulationResponse {
  contract_id: number;
  simulated_at: string;
  steps: PipelineStep[];
}

export interface AutoContractParseItem {
  file_name: string;
  document_type: DocumentType;
  confidence: number;
  title?: string | null;
  company_name?: string | null;
  business_registration_no?: string | null;
  amount?: number | null;
  issue_date?: string | null;
}

export interface AutoContractSynthesisResponse {
  title: string;
  vendor_name: string;
  business_number: string;
  contract_amount: number;
  issue_date?: string | null;
  documents: AutoContractParseItem[];
}

export interface Workflow {
  submission?: SubmissionState;
  revision: number;
  amount_basis: 'TOTAL' | 'SUPPLY' | 'UNKNOWN';
  tax_amount: number | null;
  payment_mode: 'FULL' | 'INSTALLMENT';
  approval_status: string;
  fingerprint: string;
  reviews: { review_id: number; revision: number; actor_name: string; decision: string; note: string; created_at: string }[];
}

export interface ReviewBlocker {
  code: string; document_id: number | null; document_type: DocumentType | null;
  field: string | null; label: string; reason: string; action: string; owner: string;
}
export interface SubmissionState {
  status: 'NOT_SUBMITTED' | 'SUBMITTED' | 'RETURNED' | 'STALE' | 'APPROVED';
  current: boolean; event_id: number | null; actor_name: string | null;
  submitted_at: string | null; note: string | null; exception_reason: string | null;
  exception_items: string[]; next_owner: string; legacy_completed_approval: boolean;
  gate: { blockers: ReviewBlocker[]; exception_items: {key:string;rule_id:string;document_id:number|null;reason:string;status:string}[];
    can_submit: boolean; can_submit_exception: boolean; completion: string; fingerprint: string } | null;
}

export interface PilotInfo {
  company_name: string;
  deployment_mode: string;
  local_database: boolean;
  nts_mode: string;
  llm_connected: boolean;
  required_document_types: DocumentType[];
}

export interface AuditEntry {
  event_id: number; actor_name: string; action: string; contract_id: number | null;
  document_id: number | null; details: Record<string, unknown>; created_at: string;
}

export interface PilotMetrics {
  contract_count: number;
  confirmed_count: number;
  awaiting_confirmation_count: number;
  timed_contract_count: number;
  mean_elapsed_seconds: number | null;
  median_elapsed_seconds: number | null;
  document_registration_count: number;
  field_correction_count: number;
  measurement: string;
  limitation: string;
}

