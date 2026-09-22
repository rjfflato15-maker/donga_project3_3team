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
  created_at: string;
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
