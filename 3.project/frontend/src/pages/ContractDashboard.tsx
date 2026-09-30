import React, { useState, useEffect } from 'react';
import {
  ContractDetail,
  ContractListItem,
  DocumentResponse,
} from '../types';
import { api } from '../api/client';
import { Sidebar, NavigationTab } from '../components/Sidebar';
import { OverallDashboardView } from '../components/OverallDashboardView';
import { ValidationReportView } from '../components/ValidationReportView';
import { MetricsSummary } from '../components/MetricsSummary';
import { Checklist } from '../components/Checklist';
import { RuleValidationCard } from '../components/RuleValidationCard';
import { DocumentViewerModal } from '../components/DocumentViewerModal';
import { UploadModal } from '../components/UploadModal';
import { NewContractModal } from '../components/NewContractModal';
import { EditContractModal } from '../components/EditContractModal';
import { AutoBatchContractModal } from '../components/AutoBatchContractModal';
import { ContractsListView } from '../components/ContractsListView';
import { AccountPasswordResetView } from '../components/auth/AccountPasswordResetView';
import { ConfirmModal } from '../components/ConfirmModal';
import { ToastContainer, ToastItem } from '../components/Toast';
// import { DocumentsView } from '../components/DocumentsView'; // [임시 주석 처리] 증빙서류 관리
import {
  Loader2,
  RefreshCw,
  AlertCircle,
  Edit3,
  Trash2,
  ArrowLeft,
  List,
  FileSearch,
  Sparkles,
} from 'lucide-react';

export const ContractDashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState<NavigationTab>('dashboard');
  const [contractViewMode, setContractViewMode] = useState<'list' | 'detail'>('list');
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem('sidebar_visible');
      return saved !== null ? saved === 'true' : true;
    } catch {
      return true;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem('sidebar_visible', String(isSidebarOpen));
    } catch {
      // ignore
    }
  }, [isSidebarOpen]);

  const [isMaskingEnabled, setIsMaskingEnabled] = useState<boolean>(true);
  const [contracts, setContracts] = useState<ContractListItem[]>([]);
  const [currentContract, setCurrentContract] = useState<ContractDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedDoc, setSelectedDoc] = useState<DocumentResponse | null>(null);
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [uploadTargetType, setUploadTargetType] = useState<string | null>(null);
  const [isNewContractOpen, setIsNewContractOpen] = useState(false);
  const [isAutoBatchOpen, setIsAutoBatchOpen] = useState(false);
  const [isEditContractOpen, setIsEditContractOpen] = useState(false);
  const [editingContractTarget, setEditingContractTarget] = useState<ContractDetail | ContractListItem | null>(null);

  // Modals & Confirmation States
  const [documentToDelete, setDocumentToDelete] = useState<{ documentId: number; fileName: string } | null>(null);
  const [contractToDelete, setContractToDelete] = useState<{ contractId: number; title?: string } | null>(null);
  const [isSeedConfirmOpen, setIsSeedConfirmOpen] = useState<boolean>(false);
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const showToast = (type: 'success' | 'error' | 'info', message: string) => {
    const id = `${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3500);
  };

  const handleDismissToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const fetchContracts = async () => {
    try {
      setLoading(true);
      setError(null);
      const list = await api.listContracts();
      if (list.length > 0) {
        const detail = await api.getContract(list[0].contract_id);
        setCurrentContract(detail);
      } else {
        setCurrentContract(null);
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

  const handleSelectContract = async (
    contractId: number,
    targetTab?: NavigationTab,
    viewMode: 'list' | 'detail' = 'detail'
  ) => {
    try {
      setActionLoading(true);
      const detail = await api.getContract(contractId);
      setCurrentContract(detail);
      if (targetTab) {
        setActiveTab(targetTab);
      }
      setContractViewMode(viewMode);
    } catch (err) {
      console.error(err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleTabChange = (tab: NavigationTab) => {
    setActiveTab(tab);
    if (tab === 'contracts') {
      setContractViewMode('list');
    }
  };

  const handleSeedDemo = () => {
    setIsSeedConfirmOpen(true);
  };

  const handleConfirmSeedDemo = async () => {
    try {
      setActionLoading(true);
      const demo = await api.seedDemoContract();
      const list = await api.listContracts();
      setContracts(list);
      setCurrentContract(demo);
      showToast('success', '기본 데모 시나리오(ABC 홈페이지 구축 외주 계약)가 성공적으로 초기화되었습니다.');
    } catch (err: any) {
      console.error(err);
      showToast('error', '데모 초기화 중 오류: ' + (err.message || '서버 오류'));
    } finally {
      setActionLoading(false);
      setIsSeedConfirmOpen(false);
    }
  };

  const handleUploadFiles = async (files: File[], targetDocumentType?: string) => {
    if (!currentContract) return;
    try {
      setActionLoading(true);
      await api.uploadDocuments(currentContract.contract_id, files, targetDocumentType);

      // 화면 노출 없이 백그라운드에서 5단계 파이프라인(마스킹, OCR, 정규화, 최종 대조검수) 자동 수행
      try {
        await api.simulatePipeline(currentContract.contract_id);
      } catch (pipelineErr) {
        console.warn('Background pipeline execution error:', pipelineErr);
      }

      // Reload current contract detail
      const updated = await api.getContract(currentContract.contract_id);
      setCurrentContract(updated);
      const list = await api.listContracts();
      setContracts(list);
      showToast('success', `${files.length}건의 증빙서류 업로드 및 5단계 파이프라인 자동 검수가 완료되었습니다.`);
    } catch (err: any) {
      console.error(err);
      showToast('error', '문서 업로드 실패: ' + (err.message || '오류'));
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

  const handleOpenEditModal = (target?: ContractDetail | ContractListItem | null) => {
    const itemToEdit = target || currentContract;
    if (!itemToEdit) return;
    setEditingContractTarget(itemToEdit);
    setIsEditContractOpen(true);
  };

  const handleUpdateContract = async (
    contractId: number,
    data: {
      title?: string;
      vendor_name?: string;
      business_number?: string;
      contract_amount?: number;
    }
  ) => {
    try {
      setActionLoading(true);
      const updated = await api.updateContract(contractId, data);
      const list = await api.listContracts();
      setContracts(list);
      setCurrentContract(updated);
    } catch (err) {
      console.error(err);
      alert('계약 정보 수정 실패');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeleteContract = (contractId: number, title?: string) => {
    setContractToDelete({ contractId, title });
  };

  const handleConfirmDeleteContract = async () => {
    if (!contractToDelete) return;
    const { contractId, title } = contractToDelete;
    try {
      setActionLoading(true);
      await api.deleteContract(contractId);
      const list = await api.listContracts();
      setContracts(list);
      if (list.length > 0) {
        const nextDetail = await api.getContract(list[0].contract_id);
        setCurrentContract(nextDetail);
      } else {
        setCurrentContract(null);
      }
      setContractViewMode('list');
      showToast('success', `'${title || '계약'}' 계약이 삭제되었습니다.`);
    } catch (err: any) {
      console.error(err);
      showToast('error', '계약 삭제 중 오류가 발생했습니다: ' + (err.message || '서버 오류'));
    } finally {
      setActionLoading(false);
      setContractToDelete(null);
    }
  };

  const handleDeleteDocument = (documentId: number, fileName: string) => {
    setDocumentToDelete({ documentId, fileName });
  };

  const handleConfirmDeleteDocument = async () => {
    if (!documentToDelete) return;
    const { documentId, fileName } = documentToDelete;
    try {
      setActionLoading(true);
      await api.deleteDocument(documentId);

      // Close modal if deleting open document
      if (selectedDoc && selectedDoc.document_id === documentId) {
        setSelectedDoc(null);
      }

      // Refresh contract & list
      if (currentContract) {
        const updated = await api.getContract(currentContract.contract_id);
        setCurrentContract(updated);
      }

      const list = await api.listContracts();
      setContracts(list);

      showToast('success', `'${fileName}' 증빙서류가 삭제되었습니다. AI 검수 결과가 갱신되었습니다.`);
    } catch (err: any) {
      console.error(err);
      showToast('error', '증빙서류 삭제에 실패했습니다: ' + (err.message || '서버 오류'));
    } finally {
      setActionLoading(false);
      setDocumentToDelete(null);
    }
  };

  const handleRunPipelineSimulation = async (contractId?: number) => {
    const targetId = contractId || currentContract?.contract_id;
    if (!targetId) return;

    try {
      setActionLoading(true);
      showToast('info', '5단계 AI 파이프라인(업로드·마스킹·OCR·정규화·대조검수)을 백그라운드에서 실행 중입니다...');
      const res = await api.simulatePipeline(targetId);

      const updated = await api.getContract(targetId);
      setCurrentContract(updated);
      const list = await api.listContracts();
      setContracts(list);

      showToast(
        'success',
        `5단계 AI 파이프라인 검수가 성공적으로 완료되었습니다! (총 ${res.steps?.length || 5}개 검수 파이프라인 단계 완료 및 결과 갱신)`
      );
    } catch (err: any) {
      console.error(err);
      showToast('error', '5단계 파이프라인 실행 중 오류: ' + (err.message || '서버 오류'));
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
      showToast('success', '룰 엔진 재검수가 완료되었습니다.');
    } catch (err: any) {
      console.error(err);
      showToast('error', '재검수 실패: ' + (err.message || '서버 오류'));
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
            onSelectContract={(id) => handleSelectContract(id, 'contracts', 'detail')}
            onViewAllContracts={() => {
              setActiveTab('contracts');
              setContractViewMode('list');
            }}
            onEditContract={(item) => handleOpenEditModal(item)}
            onDeleteContract={(id, title) => handleDeleteContract(id, title)}
            onOpenAutoBatchContract={() => setIsAutoBatchOpen(true)}
          />
        );

      case 'contracts':
        if (contractViewMode === 'list' || !currentContract) {
          return (
            <ContractsListView
              contracts={contracts}
              currentContractId={currentContract?.contract_id}
              onSelectContract={async (id) => {
                await handleSelectContract(id, undefined, 'detail');
              }}
              onOpenAutoBatchContract={() => setIsAutoBatchOpen(true)}
              onEditContract={(item) => handleOpenEditModal(item)}
              onDeleteContract={(id, title) => handleDeleteContract(id, title)}
              onSeedDemo={handleSeedDemo}
              actionLoading={actionLoading}
              isMaskingEnabled={isMaskingEnabled}
            />
          );
        }

        return (
          <div className="space-y-6">
            {/* Top Navigation & Breadcrumb Bar for Detail View */}
            <div className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-xs flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center space-x-3">
                <button
                  onClick={() => setContractViewMode('list')}
                  className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-slate-100 hover:bg-indigo-50 text-slate-700 hover:text-indigo-700 rounded-xl font-extrabold text-xs transition-all border border-slate-200 active:scale-95 shadow-2xs"
                >
                  <ArrowLeft className="w-4 h-4" />
                  <span>← 계약 목록으로 돌아가기</span>
                </button>

                <div className="h-4 w-px bg-slate-200 hidden sm:block"></div>

                {/* View Mode Toggle */}
                <div className="flex items-center p-1 bg-slate-100 rounded-xl text-xs font-bold">
                  <button
                    onClick={() => setContractViewMode('list')}
                    className="flex items-center space-x-1 px-2.5 py-1 rounded-lg text-slate-600 hover:text-slate-900 transition-colors"
                  >
                    <List className="w-3.5 h-3.5" />
                    <span>목록 보기</span>
                  </button>
                  <button
                    onClick={() => setContractViewMode('detail')}
                    className="flex items-center space-x-1 px-2.5 py-1 rounded-lg bg-white text-indigo-700 font-extrabold shadow-2xs transition-colors"
                  >
                    <FileSearch className="w-3.5 h-3.5" />
                    <span>상세 검수</span>
                  </button>
                </div>
              </div>

              {/* Right Side: Contract Selector & Actions */}
              <div className="flex items-center space-x-2">
                <select
                  value={currentContract?.contract_id || ''}
                  onChange={(e) => handleSelectContract(Number(e.target.value), undefined, 'detail')}
                  className="bg-slate-50 border border-slate-300 rounded-xl px-3 py-1.5 font-bold text-slate-800 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500 max-w-xs truncate"
                >
                  {contracts.map((c) => (
                    <option key={c.contract_id} value={c.contract_id}>
                      #{c.contract_id} {c.title} ({c.vendor_name}) — 충족률 {c.completeness_rate}%
                    </option>
                  ))}
                </select>

                <button
                  onClick={() => handleOpenEditModal(currentContract)}
                  className="inline-flex items-center space-x-1 px-3 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 rounded-xl font-bold text-xs transition-colors"
                  title="선택된 계약 정보 수정"
                >
                  <Edit3 className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">수정</span>
                </button>

                <button
                  onClick={() => handleDeleteContract(currentContract.contract_id, currentContract.title)}
                  className="inline-flex items-center space-x-1 px-3 py-1.5 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded-xl font-bold text-xs transition-colors"
                  title="선택된 계약 삭제"
                >
                  <Trash2 className="w-3.5 h-3.5 text-rose-600" />
                  <span className="hidden sm:inline">삭제</span>
                </button>

                <button
                  onClick={() => handleRunPipelineSimulation()}
                  disabled={actionLoading}
                  className="inline-flex items-center space-x-1 px-3 py-1.5 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700 text-white rounded-xl font-bold text-xs shadow-xs transition-all active:scale-95 disabled:bg-slate-300"
                  title="화면 노출 없이 백그라운드로 5단계 파이프라인(업로드·마스킹·OCR·정규화·대조검수) 실행"
                >
                  <Sparkles className={`w-3.5 h-3.5 ${actionLoading ? 'animate-spin text-amber-300' : 'text-amber-300'}`} />
                  <span className="hidden sm:inline">{actionLoading ? '파이프라인 실행 중...' : '5단계 파이프라인 실행'}</span>
                </button>

                <button
                  onClick={handleRevalidate}
                  disabled={actionLoading}
                  className="inline-flex items-center space-x-1 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl font-bold text-xs transition-colors active:scale-95"
                  title="검수 룰 재실행"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${actionLoading ? 'animate-spin' : ''}`} />
                  <span className="hidden sm:inline">룰 재검수</span>
                </button>
              </div>
            </div>

            {/* Contract Detail Content */}
            <MetricsSummary
              contract={currentContract}
              onEditContract={() => handleOpenEditModal(currentContract)}
              onDeleteContract={() => handleDeleteContract(currentContract.contract_id, currentContract.title)}
              isMaskingEnabled={isMaskingEnabled}
            />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Checklist
                documents={currentContract.documents}
                onSelectDocument={(doc) => setSelectedDoc(doc)}
                onUploadSpecific={(type) => handleOpenUploadModal(type)}
                onOpenUploadAll={() => handleOpenUploadModal()}
                onDeleteDocument={handleDeleteDocument}
                isMaskingEnabled={isMaskingEnabled}
              />
              <RuleValidationCard checks={currentContract.checks} isMaskingEnabled={isMaskingEnabled} />
            </div>
          </div>
        );

      // [임시 주석 처리] 증빙서류 관리 페이지
      // case 'documents':
      //   return (
      //     <DocumentsView
      //       currentContract={currentContract}
      //       onSelectDocument={(doc) => setSelectedDoc(doc)}
      //       onOpenUpload={() => handleOpenUploadModal()}
      //       onDeleteDocument={handleDeleteDocument}
      //     />
      //   );

      case 'reports':
        return (
          <ValidationReportView
            currentContract={currentContract}
            onRunPipeline={() => handleRunPipelineSimulation()}
            onRevalidate={handleRevalidate}
            loading={actionLoading}
          />
        );

      case 'account-settings':
        return (
          <AccountPasswordResetView
            onSuccessReturn={() => setActiveTab('dashboard')}
          />
        );

      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-[#f8fafc] flex">
      {/* Left Navigation Sidebar */}
      <Sidebar
        isOpen={isSidebarOpen}
        onToggleCollapse={() => setIsSidebarOpen((prev) => !prev)}
        activeTab={activeTab}
        onTabChange={handleTabChange}
        onOpenAutoBatchContract={() => setIsAutoBatchOpen(true)}
        onOpenUpload={() => handleOpenUploadModal()}
        onOpenNewContract={() => setIsNewContractOpen(true)}
        isMaskingEnabled={isMaskingEnabled}
        onToggleMasking={() => setIsMaskingEnabled((prev) => !prev)}
        onSeedDemo={handleSeedDemo}
        loading={actionLoading}
      />

      {/* Main Container */}
      <div className="flex-1 flex flex-col min-w-0 transition-all duration-300">
        {/* Top Header Bar */}
        <header className="bg-white/95 backdrop-blur-md border-b border-slate-200/80 px-4 sm:px-6 py-2.5 flex items-center justify-between sticky top-0 z-20 shadow-2xs transition-all">
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2 text-xs font-bold text-slate-700">
              <span className="text-indigo-600 font-extrabold">
                {activeTab === 'dashboard' && '대시보드'}
                {activeTab === 'contracts' && (contractViewMode === 'list' ? '외주/용역 계약 목록' : `계약 상세 검수 (#${currentContract?.contract_id ?? ''})`)}
                {/* {activeTab === 'documents' && '증빙서류 관리'} */}
                {activeTab === 'reports' && 'AI 교차검수 리포트'}
                {activeTab === 'account-settings' && '계정 정보 및 비밀번호 변경'}
              </span>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={() => setIsMaskingEnabled((prev) => !prev)}
              className={`inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-lg text-xs font-bold border transition-colors shadow-2xs ${
                isMaskingEnabled
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100'
                  : 'bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100'
              }`}
              title="개인정보(주민·계좌·사업자·상호) 비식별화 On/Off 전환"
            >
              <span className={`w-1.5 h-1.5 rounded-full ${isMaskingEnabled ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'}`}></span>
              <span>개인정보 {isMaskingEnabled ? 'ON' : 'OFF'}</span>
            </button>
          </div>
        </header>

        <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-8">
          {renderActiveContent()}
        </main>

        <footer className="bg-white/95 backdrop-blur-xs border-t border-slate-200/80 py-3.5 px-4 text-xs text-slate-700 select-none">
          <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1.5 font-medium">
            <span className="font-extrabold text-slate-900 tracking-tight">Smart Contract Evidence Hub</span>
            <span className="text-slate-300 hidden sm:inline">|</span>

            {/* 3조 스마트 계약 증빙 누락·불일치 자동 검증 시스템 */}
            <div className="inline-flex items-center space-x-1.5">
              <svg viewBox="0 0 24 24" className="w-4 h-4 text-slate-700 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                <path d="m9 12 2 2 4-4" />
              </svg>
              <span className="font-bold text-slate-800">3조 스마트 계약 증빙 누락·불일치 자동 검증 시스템</span>
            </div>

            <span className="text-slate-300 hidden sm:inline">|</span>

            {/* 시스템 기술 스택 */}
            <div className="inline-flex items-center space-x-1.5 text-slate-600">
              <svg className="w-4 h-4 text-slate-700 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="6" cy="12" r="3" />
                <path d="M9 12h5" />
                <circle cx="18" cy="6" r="2.5" />
                <circle cx="18" cy="18" r="2.5" />
                <path d="M14 12l2-4" />
                <path d="M14 12l2 4" />
              </svg>
              <span className="font-bold text-slate-800">시스템 기술 스택</span>
            </div>

            <span className="text-slate-300 hidden sm:inline">|</span>

            {/* FastAPI */}
            <div className="inline-flex items-center space-x-1.5">
              <span className="w-4 h-4 rounded-full bg-slate-800 text-white flex items-center justify-center shrink-0">
                <svg className="w-2.5 h-2.5 fill-current" viewBox="0 0 24 24">
                  <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
                </svg>
              </span>
              <span className="font-semibold text-slate-700">FastAPI</span>
            </div>

            <span className="text-slate-400 font-bold">•</span>

            {/* React */}
            <div className="inline-flex items-center space-x-1.5">
              <svg viewBox="-11.5 -10.23 23 20.46" className="w-4 h-4 text-slate-800 shrink-0" fill="none" stroke="currentColor">
                <circle cx="0" cy="0" r="2.05" fill="currentColor" />
                <g strokeWidth="1.2">
                  <ellipse rx="11" ry="4.2" />
                  <ellipse rx="11" ry="4.2" transform="rotate(60)" />
                  <ellipse rx="11" ry="4.2" transform="rotate(120)" />
                </g>
              </svg>
              <span className="font-semibold text-slate-700">React</span>
            </div>

            <span className="text-slate-400 font-bold">•</span>

            {/* Document AI */}
            <div className="inline-flex items-center space-x-1.5">
              <svg viewBox="0 0 24 24" className="w-4 h-4 text-slate-800 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <text x="6.5" y="17.5" fill="currentColor" stroke="none" fontSize="7" fontWeight="900" fontFamily="sans-serif">AI</text>
              </svg>
              <span className="font-semibold text-slate-700">Document AI</span>
            </div>
          </div>
        </footer>
      </div>

      {/* Modals */}
      <DocumentViewerModal
        document={selectedDoc}
        onClose={() => setSelectedDoc(null)}
        onDelete={handleDeleteDocument}
        isMaskingEnabled={isMaskingEnabled}
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

          <EditContractModal
            contract={editingContractTarget || currentContract}
            isOpen={isEditContractOpen}
            onClose={() => {
              setIsEditContractOpen(false);
              setEditingContractTarget(null);
            }}
            onUpdate={handleUpdateContract}
            loading={actionLoading}
          />
        </>
      )}

      <NewContractModal
        isOpen={isNewContractOpen}
        onClose={() => setIsNewContractOpen(false)}
        onCreate={handleCreateContract}
        loading={actionLoading}
      />

      <AutoBatchContractModal
        isOpen={isAutoBatchOpen}
        onClose={() => setIsAutoBatchOpen(false)}
        onSuccess={async (newContractId) => {
          const list = await api.listContracts();
          setContracts(list);
          await handleSelectContract(newContractId, 'contracts', 'detail');
        }}
      />

      {/* 증빙서류 삭제 확인 모달 */}
      <ConfirmModal
        isOpen={!!documentToDelete}
        title="증빙서류 삭제"
        itemName={documentToDelete?.fileName}
        itemBadge="증빙서류"
        message={`선택한 증빙서류를 영구 삭제하시겠습니까?\n삭제 즉시 AI 검수 룰이 자동으로 재실행되어 계약 충족률과 검수 결과가 갱신됩니다.`}
        subMessage="서류 삭제 후에도 언제든지 해당 서류를 다시 업로드할 수 있습니다."
        confirmText="증빙서류 삭제"
        cancelText="취소"
        isDanger={true}
        loading={actionLoading}
        onConfirm={handleConfirmDeleteDocument}
        onCancel={() => !actionLoading && setDocumentToDelete(null)}
      />

      {/* 외주/용역 계약 삭제 확인 모달 */}
      <ConfirmModal
        isOpen={!!contractToDelete}
        title="외주/용역 계약 삭제"
        itemName={contractToDelete?.title || `계약 #${contractToDelete?.contractId}`}
        itemBadge="계약 정보"
        message={`선택한 외주/용역 계약 및 첨부된 모든 증빙서류를 영구 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.`}
        confirmText="계약 영구 삭제"
        cancelText="취소"
        isDanger={true}
        loading={actionLoading}
        onConfirm={handleConfirmDeleteContract}
        onCancel={() => !actionLoading && setContractToDelete(null)}
      />

      {/* 시연 데모 시나리오 초기화 모달 */}
      <ConfirmModal
        isOpen={isSeedConfirmOpen}
        title="시연 데모 시나리오 초기화"
        itemName="ABC 홈페이지 구축 외주 계약"
        itemBadge="데모 시나리오"
        message={`기본 시연용 데모 시나리오를 초기 상태로 재설정하시겠습니까?\n\n• 5종 서류 등록 및 1종 누락 (검수확인서)\n• 세금계산서 55만원 차액 불일치 AI 검수 시나리오가 새로 로드됩니다.`}
        confirmText="데모 데이터 생성"
        cancelText="취소"
        isDanger={false}
        loading={actionLoading}
        onConfirm={handleConfirmSeedDemo}
        onCancel={() => !actionLoading && setIsSeedConfirmOpen(false)}
      />

      {/* 플로팅 알림 토스트 컨테이너 */}
      <ToastContainer toasts={toasts} onDismiss={handleDismissToast} />
    </div>
  );
};

export default ContractDashboard;
