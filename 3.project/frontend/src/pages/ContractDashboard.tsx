import React, { useState, useEffect } from 'react';
import {
  ContractDetail,
  ContractListItem,
  DocumentResponse,
} from '../types';
import { api } from '../api/client';
import { Sidebar, NavigationTab } from '../components/Sidebar';
import { TopHeader } from '../components/TopHeader';
import { OverallDashboardView } from '../components/OverallDashboardView';
import { DocumentsView } from '../components/DocumentsView';
import { ValidationReportView } from '../components/ValidationReportView';
import { MetricsSummary } from '../components/MetricsSummary';
import { Checklist } from '../components/Checklist';
import { RuleValidationCard } from '../components/RuleValidationCard';
import { DocumentViewerModal } from '../components/DocumentViewerModal';
import { UploadModal } from '../components/UploadModal';
import { PipelineSimulator } from '../components/PipelineSimulator';
import { NewContractModal } from '../components/NewContractModal';
import { Loader2, RefreshCw, AlertCircle } from 'lucide-react';

export const ContractDashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState<NavigationTab>('dashboard');
  const [contracts, setContracts] = useState<ContractListItem[]>([]);
  const [currentContract, setCurrentContract] = useState<ContractDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedDoc, setSelectedDoc] = useState<DocumentResponse | null>(null);
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [uploadTargetType, setUploadTargetType] = useState<string | null>(null);
  const [isSimulatorOpen, setIsSimulatorOpen] = useState(false);
  const [isNewContractOpen, setIsNewContractOpen] = useState(false);

  const fetchContracts = async () => {
    try {
      setLoading(true);
      setError(null);
      let list = await api.listContracts();
      if (list.length === 0) {
        // Automatically seed demo contract
        const demo = await api.seedDemoContract();
        list = await api.listContracts();
        setCurrentContract(demo);
      } else {
        const detail = await api.getContract(list[0].contract_id);
        setCurrentContract(detail);
      }
      setContracts(list);
    } catch (err: any) {
      console.error(err);
      setError('서버 연결 중 오류가 발생했습니다. 백엔드 서버 상태를 확인하세요.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchContracts();
  }, []);

  const handleSelectContract = async (contractId: number, targetTab?: NavigationTab) => {
    try {
      setActionLoading(true);
      const detail = await api.getContract(contractId);
      setCurrentContract(detail);
      if (targetTab) {
        setActiveTab(targetTab);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleSeedDemo = async () => {
    try {
      setActionLoading(true);
      const demo = await api.seedDemoContract();
      const list = await api.listContracts();
      setContracts(list);
      setCurrentContract(demo);
    } catch (err) {
      console.error(err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleUploadFiles = async (files: File[], targetDocumentType?: string) => {
    if (!currentContract) return;
    try {
      setActionLoading(true);
      await api.uploadDocuments(currentContract.contract_id, files, targetDocumentType);
      // Reload current contract detail
      const updated = await api.getContract(currentContract.contract_id);
      setCurrentContract(updated);
      const list = await api.listContracts();
      setContracts(list);
    } catch (err) {
      console.error(err);
      alert('문서 업로드 실패');
    } finally {
      setActionLoading(false);
    }
  };

  const handleOpenUploadModal = (targetType?: string | null) => {
    setUploadTargetType(targetType || null);
    setIsUploadOpen(true);
  };

  const handleCreateContract = async (data: {
    title: string;
    vendor_name: string;
    business_number: string;
    contract_amount: number;
  }) => {
    try {
      setActionLoading(true);
      const created = await api.createContract(data);
      const list = await api.listContracts();
      setContracts(list);
      setCurrentContract(created);
      setActiveTab('contracts');
    } catch (err) {
      console.error(err);
      alert('계약 등록 실패');
    } finally {
      setActionLoading(false);
    }
  };

  const handleRevalidate = async () => {
    if (!currentContract) return;
    try {
      setActionLoading(true);
      await api.triggerValidation(currentContract.contract_id);
      const updated = await api.getContract(currentContract.contract_id);
      setCurrentContract(updated);
    } catch (err) {
      console.error(err);
    } finally {
      setActionLoading(false);
    }
  };

  const renderActiveContent = () => {
    if (loading) {
      return (
        <div className="py-24 flex flex-col items-center justify-center text-slate-400 space-y-3">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
          <p className="text-sm font-semibold">데이터를 불러오는 중입니다...</p>
        </div>
      );
    }

    if (error) {
      return (
        <div className="bg-rose-50 border border-rose-200 rounded-2xl p-6 text-rose-800 flex items-start space-x-3">
          <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
          <div>
            <h3 className="text-sm font-bold">오류 안내</h3>
            <p className="text-xs mt-1">{error}</p>
            <button
              onClick={fetchContracts}
              className="mt-3 px-3 py-1.5 bg-rose-600 text-white rounded-lg text-xs font-semibold hover:bg-rose-700 transition-colors"
            >
              다시 시도
            </button>
          </div>
        </div>
      );
    }

    switch (activeTab) {
      case 'dashboard':
        return (
          <OverallDashboardView
            contracts={contracts}
            onSelectContract={(id) => handleSelectContract(id, 'contracts')}
            onViewAllContracts={() => setActiveTab('contracts')}
          />
        );

      case 'contracts':
        return (
          <div className="space-y-6">
            {/* Contract Selector Header Bar */}
            {contracts.length > 0 && (
              <div className="flex items-center justify-between bg-white p-3 px-4 rounded-xl border border-slate-200/80 text-xs shadow-2xs">
                <div className="flex items-center space-x-2">
                  <span className="font-extrabold text-slate-700">관리 대상 계약 선택:</span>
                  <select
                    value={currentContract?.contract_id || ''}
                    onChange={(e) => handleSelectContract(Number(e.target.value))}
                    className="bg-slate-50 border border-slate-300 rounded-lg px-3 py-1 font-bold text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  >
                    {contracts.map((c) => (
                      <option key={c.contract_id} value={c.contract_id}>
                        #{c.contract_id} {c.title} ({c.vendor_name}) — 충족률 {c.completeness_rate}%
                      </option>
                    ))}
                  </select>
                </div>

                <button
                  onClick={handleRevalidate}
                  disabled={actionLoading}
                  className="flex items-center space-x-1 text-indigo-600 hover:text-indigo-800 font-extrabold"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${actionLoading ? 'animate-spin' : ''}`} />
                  <span>검수 룰 재실행</span>
                </button>
              </div>
            )}

            {currentContract && (
              <>
                <MetricsSummary contract={currentContract} />
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <Checklist
                    documents={currentContract.documents}
                    onSelectDocument={(doc) => setSelectedDoc(doc)}
                    onUploadSpecific={(type) => handleOpenUploadModal(type)}
                  />
                  <RuleValidationCard checks={currentContract.checks} />
                </div>
              </>
            )}
          </div>
        );

      case 'documents':
        return (
          <DocumentsView
            currentContract={currentContract}
            onSelectDocument={(doc) => setSelectedDoc(doc)}
            onOpenUpload={() => handleOpenUploadModal()}
          />
        );

      case 'reports':
        return (
          <ValidationReportView
            currentContract={currentContract}
            onOpenSimulator={() => setIsSimulatorOpen(true)}
            onRevalidate={handleRevalidate}
            loading={actionLoading}
          />
        );

      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-[#f8fafc] flex">
      {/* Left Navigation Sidebar */}
      <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />

      {/* Main Container */}
      <div className="flex-1 flex flex-col min-w-0">
        <TopHeader
          activeTab={activeTab}
          onOpenNewContract={() => setIsNewContractOpen(true)}
          onSeedDemo={handleSeedDemo}
          onOpenUpload={() => handleOpenUploadModal()}
          onOpenSimulator={() => setIsSimulatorOpen(true)}
          loading={actionLoading}
        />

        <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-8">
          {renderActiveContent()}
        </main>

        <footer className="bg-white border-t border-slate-200/80 py-4 text-center text-xs text-slate-400">
          Smart Contract Evidence Hub • 3조 계약 증빙서류 누락·불일치 자동 검수 시스템 • FastAPI + React + Document AI
        </footer>
      </div>

      {/* Modals */}
      <DocumentViewerModal
        document={selectedDoc}
        onClose={() => setSelectedDoc(null)}
      />

      {currentContract && (
        <>
          <UploadModal
            contractId={currentContract.contract_id}
            isOpen={isUploadOpen}
            onClose={() => setIsUploadOpen(false)}
            onUpload={handleUploadFiles}
            loading={actionLoading}
            initialTargetType={uploadTargetType}
          />

          <PipelineSimulator
            contractId={currentContract.contract_id}
            isOpen={isSimulatorOpen}
            onClose={() => setIsSimulatorOpen(false)}
            onCompleted={() => handleSelectContract(currentContract.contract_id)}
          />
        </>
      )}

      <NewContractModal
        isOpen={isNewContractOpen}
        onClose={() => setIsNewContractOpen(false)}
        onCreate={handleCreateContract}
        loading={actionLoading}
      />
    </div>
  );
};

export default ContractDashboard;
