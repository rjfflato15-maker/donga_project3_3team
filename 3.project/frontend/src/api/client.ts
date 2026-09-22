import {
  ContractDetail,
  ContractListItem,
  DocumentResponse,
  PipelineSimulationResponse,
  ValidationReportResponse,
} from '../types';

const API_BASE = '/api';

export const api = {
  async listContracts(): Promise<ContractListItem[]> {
    const res = await fetch(`${API_BASE}/contracts`);
    if (!res.ok) throw new Error('Failed to fetch contracts');
    return res.json();
  },

  async getContract(contractId: number): Promise<ContractDetail> {
    const res = await fetch(`${API_BASE}/contracts/${contractId}`);
    if (!res.ok) throw new Error(`Failed to fetch contract ${contractId}`);
    return res.json();
  },

  async createContract(data: {
    title: string;
    vendor_name: string;
    business_number: string;
    contract_amount: number;
  }): Promise<ContractDetail> {
    const res = await fetch(`${API_BASE}/contracts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to create contract');
    return res.json();
  },

  async seedDemoContract(): Promise<ContractDetail> {
    const res = await fetch(`${API_BASE}/contracts/seed-demo`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('Failed to seed demo contract');
    return res.json();
  },

  async uploadDocuments(contractId: number, files: File[], targetDocumentType?: string): Promise<DocumentResponse[]> {
    const formData = new FormData();
    for (const file of files) {
      formData.append('files', file);
    }
    if (targetDocumentType) {
      formData.append('target_document_type', targetDocumentType);
    }
    const res = await fetch(`${API_BASE}/contracts/${contractId}/documents`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) throw new Error('Failed to upload documents');
    return res.json();
  },

  async getDocument(documentId: number): Promise<DocumentResponse> {
    const res = await fetch(`${API_BASE}/documents/${documentId}`);
    if (!res.ok) throw new Error(`Failed to fetch document ${documentId}`);
    return res.json();
  },

  async deleteDocument(documentId: number): Promise<void> {
    const res = await fetch(`${API_BASE}/documents/${documentId}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error('Failed to delete document');
  },

  async triggerValidation(contractId: number): Promise<ValidationReportResponse> {
    const res = await fetch(`${API_BASE}/contracts/${contractId}/validate`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('Failed to run validation');
    return res.json();
  },

  async simulatePipeline(contractId: number): Promise<PipelineSimulationResponse> {
    const res = await fetch(`${API_BASE}/pipeline/${contractId}/simulate`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('Failed to run pipeline simulation');
    return res.json();
  },
};
