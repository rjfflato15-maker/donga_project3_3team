import {
  ContractDetail,
  ContractListItem,
  DocumentResponse,
  PipelineSimulationResponse,
  ValidationReportResponse,
  AutoContractSynthesisResponse,
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

  async parseContractFile(file: File): Promise<{
    title?: string;
    vendor_name?: string;
    business_number?: string;
    contract_amount?: number;
    issue_date?: string;
    document_type?: string;
    raw_text_snippet?: string;
  }> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE}/contracts/parse-file`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) throw new Error('Failed to parse contract file');
    return res.json();
  },

  async updateContract(
    contractId: number,
    data: {
      title?: string;
      vendor_name?: string;
      business_number?: string;
      contract_amount?: number;
    }
  ): Promise<ContractDetail> {
    const res = await fetch(`${API_BASE}/contracts/${contractId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(`Failed to update contract ${contractId}`);
    return res.json();
  },

  async deleteContract(contractId: number): Promise<void> {
    const res = await fetch(`${API_BASE}/contracts/${contractId}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error(`Failed to delete contract ${contractId}`);
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

  async autoParseBatchDocuments(files: File[]): Promise<AutoContractSynthesisResponse> {
    const formData = new FormData();
    for (const file of files) {
      formData.append('files', file);
    }
    const res = await fetch(`${API_BASE}/contracts/auto-parse-batch`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) throw new Error('Failed to parse batch documents');
    return res.json();
  },

  async autoCreateBatchContract(
    data: {
      title: string;
      vendor_name: string;
      business_number: string;
      contract_amount: number;
    },
    files: File[]
  ): Promise<ContractDetail> {
    const formData = new FormData();
    formData.append('title', data.title);
    formData.append('vendor_name', data.vendor_name);
    formData.append('business_number', data.business_number);
    formData.append('contract_amount', data.contract_amount.toString());
    for (const file of files) {
      formData.append('files', file);
    }
    const res = await fetch(`${API_BASE}/contracts/auto-create-batch`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) throw new Error('Failed to auto create batch contract');
    return res.json();
  },
};

