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
  revision: number;
  amount_basis: 'TOTAL' | 'SUPPLY' | 'UNKNOWN';
  tax_amount: number | null;
  payment_mode: 'FULL' | 'INSTALLMENT';
  approval_status: string;
  fingerprint: string;
  reviews: { review_id: number; revision: number; actor_name: string; decision: string; note: string; created_at: string }[];
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

