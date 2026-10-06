import React, { useState, useEffect, useRef } from 'react';
import {
  ContractDetail,
  ContractListItem,
  DocumentResponse,
  PilotInfo,
} from '../types';
import { api, downloadProtected } from '../api/client';
import { NavigationTab } from '../components/Sidebar';
import { AppShell } from '../components/AppShell';
import { OverallDashboardView } from '../components/OverallDashboardView';
import { ValidationReportView } from '../components/ValidationReportView';
import { ContractReviewOverview } from '../components/review/ContractReviewOverview';
import { CompareRegistration } from '../components/CompareRegistration';
import { StageDashboard, DashboardItem } from '../components/review/StageDashboard';
import { ContractStageView } from '../components/review/ContractStageView';
import { ContractSearch } from '../components/review/ContractSearch';
import { ApprovalPanel } from '../components/review/ApprovalPanel';
import { AssignmentPanel } from '../components/review/AssignmentPanel';
import { MyAssignmentsStrip } from '../components/review/MyAssignmentsStrip';
import { DocumentViewerModal } from '../components/DocumentViewerModal';
import { UploadModal } from '../components/UploadModal';
import { NewContractModal } from '../components/NewContractModal';
import { EditContractModal } from '../components/EditContractModal';
import { AutoBatchContractModal } from '../components/AutoBatchContractModal';
import { ContractsListView } from '../components/ContractsListView';
import { AccountPasswordResetView } from '../components/auth/AccountPasswordResetView';
import { ConfirmModal } from '../components/ConfirmModal';
import { ToastContainer, ToastItem } from '../components/Toast';
import { useAuth } from '../context/AuthContext';
import { PilotReviewPanel } from '../components/PilotReviewPanel';
import { PilotOperations } from '../components/PilotOperations';
import { PilotDocumentDialog } from '../components/PilotDocumentDialog';
import { maskVendorName } from '../utils/masking';
// import { DocumentsView } from '../components/DocumentsView'; // [임시 주석 처리] 증빙서류 관리
import {
  Loader2,
  RefreshCw,
  AlertCircle,
  Edit3,
  Trash2,
  ArrowLeft,
  MoreHorizontal,
  Upload,
  FileArchive,
} from 'lucide-react';

export const ContractDashboard: React.FC = () => {
  const { user } = useAuth();
  const isPilot = user?.deployment_mode === 'pilot';
  const canEdit = !isPilot || user?.role === 'operator' || user?.role === 'admin';
  const [pilotInfo, setPilotInfo] = useState<PilotInfo | null>(null);
  const [advancedDocOpen, setAdvancedDocOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [assignPrefill, setAssignPrefill] = useState<{ title: string; memo: string; document_id: number | null; key: number } | null>(null);
  const [exporting, setExporting] = useState(false);
  const exportBundle = async () => {
    if (!currentContract) return;
    // 가림이 꺼져 있을 때만 원본 묶음. 원본은 한 번 더 묻는다
    const masked = isMaskingEnabled;
    if (!masked && !window.confirm('개인정보 가림이 꺼져 있어 원본 그대로 묶습니다. 사업자번호·계좌 등이 포함됩니다. 계속할까요?')) return;
    setExporting(true);
    try {
      const rev = currentContract.workflow?.revision;
      await downloadProtected(`/api/contracts/${currentContract.contract_id}/export?masked=${masked}${rev ? `&revision=${rev}` : ''}`,
        `계약_${currentContract.contract_id}_자료묶음.zip`);
      showToast('success', masked ? '가린 자료 묶음(ZIP)을 받았습니다. 원본 서류·검수 결과·처리 이력이 들어 있습니다.' : '원본 자료 묶음(ZIP)을 받았습니다. 전달 대상에 주의하세요.');
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : '자료 묶음을 만들지 못했습니다.');
    } finally {
      setExporting(false);
    }
  };
  const [recentUpload, setRecentUpload] = useState<{ contractId: number; names: string[] } | null>(null);
  const [activeTab, setActiveTab] = useState<NavigationTab>('dashboard');
  const [contractViewMode, setContractViewMode] = useState<'list' | 'detail'>('list');
  const [isMaskingEnabled, setIsMaskingEnabled] = useState<boolean>(true);
  const [contracts, setContracts] = useState<ContractListItem[]>([]);
  const [currentContract, setCurrentContract] = useState<ContractDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedDoc, setSelectedDoc] = useState<DocumentResponse | null>(null);
  const selectedDocRef=useRef(selectedDoc);selectedDocRef.current=selectedDoc;
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [uploadTargetType, setUploadTargetType] = useState<string | null>(null);
  const [isNewContractOpen, setIsNewContractOpen] = useState(false);
  const [isAutoBatchOpen, setIsAutoBatchOpen] = useState(false);
  const registrationEpoch=useRef(0), documentEpoch=useRef(0);
  const openRegistration=()=>{registrationEpoch.current++;setSelectedDoc(null);setIsAutoBatchOpen(true);};
  const closeRegistration=()=>{registrationEpoch.current++;setIsAutoBatchOpen(false);};
  const closeSource=()=>{documentEpoch.current++;setSelectedDoc(null);};
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
    }, 6000);
  };

  const handleDismissToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const fetchContracts = async () => {
    try {
      setLoading(true);
      setError(null);
      if (isPilot) await api.llmStatus().catch(() => null);
      const [list, environment] = await Promise.all([api.listContracts(), isPilot ? api.pilotInfo() : Promise.resolve(null)]);
      setPilotInfo(environment);
      if (list.length > 0) {
        const detail = await api.getContract(list[0].contract_id);
        setCurrentContract(detail);
      } else {
        setCurrentContract(null);
      }
      setContracts(list);
    } catch (err: any) {
      console.error(err);
      setError(err.message || '앱 서버에 연결하지 못했습니다.');
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
    closeSource();
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
      showToast('error', err instanceof Error ? err.message : '계약을 불러오지 못했습니다.');
    } finally {
      setActionLoading(false);
    }
  };

  const refreshCurrentContract = async (contractId?: number) => {
    const target = contractId ?? currentContract?.contract_id;
    const [list, environment, detail] = await Promise.all([
      api.listContracts(), isPilot ? api.pilotInfo() : Promise.resolve(null), target ? api.getContract(target) : Promise.resolve(null),
    ]);
    setContracts(list);setPilotInfo(environment);
    if(target!==currentIdRef.current)return;
    setCurrentContract(detail);
    const selected=selectedDocRef.current;
    if(selected&&detail)setSelectedDoc(detail.documents.find(doc=>doc.document_id===selected.document_id)||null);
  };

  const handleTabChange = (tab: NavigationTab) => {
    closeRegistration();closeSource();setIsUploadOpen(false);
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
    if (!currentContract || !canEdit) return;
    const targetId = currentContract.contract_id;
    try {
      setActionLoading(true);
      await api.uploadDocuments(currentContract.contract_id, files, targetDocumentType);

      // 화면 노출 없이 백그라운드에서 5단계 파이프라인(마스킹, OCR, 정규화, 최종 대조검수) 자동 수행
      try {
        if (!isPilot) await api.simulatePipeline(currentContract.contract_id);
      } catch (pipelineErr) {
        console.warn('Background pipeline execution error:', pipelineErr);
      }

      // Reload current contract detail
      // 업로드 중에 다른 계약으로 옮겼다면 그 화면을 이전 계약으로 덮어쓰지 않는다
      const updated = await api.getContract(targetId);
      if (currentIdRef.current === targetId) setCurrentContract(updated);
      const list = await api.listContracts();
      setContracts(list);
      if (isPilot) setRecentUpload({ contractId: targetId, names: files.map((f) => f.name) });
      showToast('success', `${files.length}건의 원본을 등록했습니다. 자동 검수 결과를 확인하세요.`);
    } catch (err: any) {
      console.error(err);
      showToast('error', '문서 업로드 실패: ' + (err.message || '오류'));
      throw err;
    } finally {
      setActionLoading(false);
    }
  };

  const currentIdRef = useRef<number | undefined>(undefined);
  currentIdRef.current = currentContract?.contract_id;

  const handleOpenUploadModal = (targetType?: string | null) => {
    if (!canEdit) return;
    closeSource();
    setUploadTargetType(targetType || null);
    setIsUploadOpen(true);
  };

  const handleCreateContract = async (data: {
    title: string;
    vendor_name: string;
    business_number: string;
    contract_amount: number;
  }, attachedFile?: File | null) => {
    if (!canEdit) throw new Error('담당자 권한이 필요합니다.');
    try {
      setActionLoading(true);
      const created = await api.createContract(data);
      if (attachedFile) {
        try {
          await api.uploadDocuments(created.contract_id, [attachedFile], 'contract');
        } catch (reason) {
          showToast('error', '계약은 등록했지만 원본 등록에 실패했습니다. 상세 화면에서 다시 첨부하세요. ' + (reason instanceof Error ? reason.message : ''));
        }
      }
      const list = await api.listContracts();
      setContracts(list);
      setCurrentContract(await api.getContract(created.contract_id));
      setActiveTab('contracts');
      setContractViewMode('detail');
    } catch (err) {
      console.error(err);
      showToast('error', err instanceof Error ? err.message : '계약 등록 실패');
      throw err;
    } finally {
      setActionLoading(false);
    }
  };

  const handleOpenEditModal = async (target?: ContractDetail | ContractListItem | null) => {
    if (!canEdit) return;
    const itemToEdit = target || currentContract;
    if (!itemToEdit) return;
    try {
      setEditingContractTarget(isPilot ? await api.getContract(itemToEdit.contract_id) : itemToEdit);
      setIsEditContractOpen(true);
    } catch (reason) { showToast('error', reason instanceof Error ? reason.message : '계약을 불러오지 못했습니다.'); }
  };

  const handleUpdateContract = async (
    contractId: number,
    data: {
      title?: string;
      vendor_name?: string;
      business_number?: string;
      contract_amount?: number;
      amount_basis?: string;
      tax_amount?: number | null;
      payment_mode?: string;
      revision?: number;
      change_note?: string;
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
      showToast('error', err instanceof Error ? err.message : '계약 정보 수정 실패');
      throw err;
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeleteContract = (contractId: number, title?: string) => {
    if (!canEdit) return;
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

  const [docMode, setDocMode] = useState<'view' | 'reissue'>('view');
  const handleOpenDocumentModal = async (doc: DocumentResponse, mode: 'view' | 'reissue' = 'view') => {
    if(currentIdRef.current!==doc.contract_id)return;
    const generation=++documentEpoch.current;
    setDocMode(mode);
    setSelectedDoc(doc);
    try {
      const freshDoc = await api.getDocument(doc.document_id);
      if(generation!==documentEpoch.current||currentIdRef.current!==doc.contract_id)return;
      setSelectedDoc(freshDoc);
      setCurrentContract((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          documents: prev.documents.map((d) => (d.document_id === freshDoc.document_id ? freshDoc : d)),
        };
      });
    } catch (err) {
      console.error('Failed to fetch fresh document detail:', err);
    }
  };

  const handleDeleteDocument = (documentId: number, fileName: string) => {
    if (!canEdit) return;
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
    if (isPilot) {
      try {
        setActionLoading(true);
        await api.triggerValidation(targetId);
        await refreshCurrentContract(targetId);
        showToast('success', '저장된 추출값으로 규칙 검수 결과를 갱신했습니다.');
      } catch (reason) { showToast('error', reason instanceof Error ? reason.message : '재검수 실패'); }
      finally { setActionLoading(false); }
      return;
    }


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
      await refreshCurrentContract();
      showToast('success', '룰 엔진 재검수가 완료되었습니다.');
    } catch (err: any) {
      console.error(err);
      showToast('error', '재검수 실패: ' + (err.message || '서버 오류'));
    } finally {
      setActionLoading(false);
    }
  };

  const renderActiveContent = () => {
    const sourceGeneration=documentEpoch.current;
    if(isPilot && isAutoBatchOpen){const session=registrationEpoch.current;return <CompareRegistration key={session} onClose={closeRegistration} onSuccess={async(id)=>{const [list,detail]=await Promise.all([api.listContracts(),api.getContract(id)]);setContracts(list);if(session!==registrationEpoch.current)return;setCurrentContract(detail);setActiveTab('contracts');setContractViewMode('detail');closeRegistration();}}/>;}
    if (loading) {
      return (
        <div className="py-24 flex flex-col items-center justify-center text-slate-400 space-y-3">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
          <p className="text-sm font-semibold">불러오는 중…</p>
        </div>
      );
    }

    if (error) {
      return (
        <div className="bg-rose-50 border border-rose-200 rounded-2xl p-6 text-rose-800 flex items-start space-x-3">
          <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
          <div>
            <h3 className="text-sm font-bold">자료를 불러오지 못했습니다</h3>
            <p className="text-xs mt-1">{error}</p>
            {isPilot && <p className="text-xs mt-1">서버 PC에서 C-Pilot이 켜져 있는지, 같은 네트워크에 연결되어 있는지 확인하세요.</p>}
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
        if (isPilot) {
          return (
            <div className="work-inbox">
              <StageDashboard
                contracts={contracts as DashboardItem[]}
                isMaskingEnabled={isMaskingEnabled}
                canEdit={canEdit}
                representative={user?.role === 'representative'}
                onOpen={(id) => handleSelectContract(id, 'contracts', 'detail')}
                onNew={canEdit ? openRegistration : undefined}
              />
              <MyAssignmentsStrip refreshKey={contracts} contracts={contracts} onOpen={(id) => handleSelectContract(id, 'contracts', 'detail')} />
            </div>
          );
        }
        return (
          <OverallDashboardView
            contracts={contracts}
            isMaskingEnabled={isMaskingEnabled}
            onSelectContract={(id) => handleSelectContract(id, 'contracts', 'detail')}
            onViewAllContracts={() => {
              setActiveTab('contracts');
              setContractViewMode('list');
            }}
            onEditContract={canEdit ? (item) => { void handleOpenEditModal(item); } : undefined}
            onDeleteContract={canEdit ? (id, title) => handleDeleteContract(id, title) : undefined}
            onOpenAutoBatchContract={canEdit ? openRegistration : undefined}
          />
        );

      case 'contracts':
        if (isPilot && (contractViewMode === 'list' || !currentContract)) {
          return <ContractSearch isMaskingEnabled={isMaskingEnabled} onOpen={(id) => handleSelectContract(id, undefined, 'detail')} />;
        }
        if (contractViewMode === 'list' || !currentContract) {
          return (
            <ContractsListView
              contracts={contracts}
              currentContractId={currentContract?.contract_id}
              onSelectContract={async (id) => {
                await handleSelectContract(id, undefined, 'detail');
              }}
              onOpenAutoBatchContract={canEdit ? openRegistration : undefined}
              onOpenNewContract={isPilot && canEdit ? () => setIsNewContractOpen(true) : undefined}
              pilot={isPilot}
              requiredDocumentTypes={pilotInfo?.required_document_types}
              onEditContract={canEdit ? (item) => { void handleOpenEditModal(item); } : undefined}
              onDeleteContract={canEdit ? (id, title) => handleDeleteContract(id, title) : undefined}
              onSeedDemo={!isPilot && canEdit ? handleSeedDemo : undefined}
              actionLoading={actionLoading}
              isMaskingEnabled={isMaskingEnabled}
            />
          );
        }

        if (isPilot) {
          return (
            <ContractStageView
              contract={currentContract}
              isMaskingEnabled={isMaskingEnabled}
              canEdit={canEdit}
              representative={user?.role === 'representative'}
              ntsMode={pilotInfo?.nts_mode}
              onReissuedDocument={doc=>{if(documentEpoch.current===sourceGeneration)void handleOpenDocumentModal(doc,'view');}}
              sourceDocument={selectedDoc} sourceMode={docMode} onCloseSource={closeSource}
              uploadOpen={isUploadOpen} uploadLoading={actionLoading} uploadTarget={uploadTargetType} onCloseUpload={()=>setIsUploadOpen(false)} onUploadFiles={handleUploadFiles}
              onBack={() => { setSelectedDoc(null);setActiveTab('dashboard'); setContractViewMode('list'); }}
              onOpenDocument={handleOpenDocumentModal}
              onUploadType={(type) => handleOpenUploadModal(type)}
              onChanged={() => refreshCurrentContract()}
              recentUploadNames={recentUpload?.contractId === currentContract.contract_id ? recentUpload.names : undefined}
              menu={[
                { label: '서류 추가로 올리기', onClick: () => handleOpenUploadModal(), hidden: !canEdit },
                { label: actionLoading ? '검사 중…' : '다시 검사', onClick: () => handleRunPipelineSimulation() },
                { label: `자료 묶음 받기 (ZIP${isMaskingEnabled ? '' : ', 원본'})`, onClick: () => void exportBundle() },
                { label: '계약 정보 수정', onClick: () => void handleOpenEditModal(currentContract), hidden: !canEdit },
                { label: '계약 제외', onClick: () => handleDeleteContract(currentContract.contract_id, currentContract.title), danger: true, hidden: !canEdit },
              ].filter((m) => !m.hidden)}
            />
          );
        }
        return (
          <div className="space-y-5">
            {/* 상단 이동·작업 바 */}
            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => setContractViewMode('list')}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 hover:border-indigo-300"
              >
                <ArrowLeft className="w-4 h-4" /> 계약 목록
              </button>
              <select
                value={currentContract?.contract_id || ''}
                onChange={(e) => handleSelectContract(Number(e.target.value), undefined, 'detail')}
                className="min-w-0 max-w-xs truncate rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                aria-label="다른 계약 선택"
              >
                {contracts.map((c) => (
                  <option key={c.contract_id} value={c.contract_id}>
                    {c.title} · {maskVendorName(c.vendor_name, isMaskingEnabled)}
                  </option>
                ))}
              </select>
              <div className="ml-auto flex items-center gap-2">
                {canEdit && (
                  <button
                    onClick={() => handleOpenUploadModal()}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 hover:border-indigo-300"
                  >
                    <Upload className="w-4 h-4" /> 서류 추가
                  </button>
                )}
                {isPilot && (
                  <button
                    onClick={() => void exportBundle()}
                    disabled={exporting}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 hover:border-indigo-300 disabled:opacity-50"
                    title="이 계약의 서류(현재본·이전본), 검수 결과, 요청·수정·결재 이력을 ZIP 하나로 받습니다. 대표나 회계 담당자에게 전달할 때 쓰세요."
                  >
                    <FileArchive className="w-4 h-4" /> {exporting ? '묶는 중…' : `자료 묶음 받기${isMaskingEnabled ? '' : ' (원본)'}`}
                  </button>
                )}
                <button
                  onClick={() => handleRunPipelineSimulation()}
                  disabled={actionLoading}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 hover:border-indigo-300 disabled:opacity-50"
                  title="저장된 값으로 검사를 다시 실행합니다."
                >
                  <RefreshCw className={`w-4 h-4 ${actionLoading ? 'animate-spin' : ''}`} /> {actionLoading ? '검사 중…' : '다시 검사'}
                </button>
                {canEdit && (
                  <div className="relative">
                    <button
                      onClick={() => setMoreOpen((v) => !v)}
                      className="rounded-lg border border-slate-200 bg-white p-1.5 text-slate-600 hover:border-indigo-300"
                      aria-label="계약 수정·제외 메뉴"
                      aria-expanded={moreOpen}
                    >
                      <MoreHorizontal className="w-5 h-5" />
                    </button>
                    {moreOpen && (
                      <div className="absolute right-0 z-30 mt-1 w-40 rounded-xl border border-slate-200 bg-white py-1 text-sm shadow-lg">
                        <button onClick={() => { setMoreOpen(false); void handleOpenEditModal(currentContract); }} className="flex w-full items-center gap-2 px-3 py-2 hover:bg-slate-50">
                          <Edit3 className="w-4 h-4" /> 계약 정보 수정
                        </button>
                        <button onClick={() => { setMoreOpen(false); handleDeleteContract(currentContract.contract_id, currentContract.title); }} className="flex w-full items-center gap-2 px-3 py-2 text-rose-600 hover:bg-rose-50">
                          <Trash2 className="w-4 h-4" /> 계약 제외
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            <ContractReviewOverview
              contract={currentContract}
              isMaskingEnabled={isMaskingEnabled}
              canEdit={canEdit}
              ntsMode={pilotInfo?.nts_mode}
              onOpenDocument={handleOpenDocumentModal}
              onUploadType={(type) => handleOpenUploadModal(type)}
              pilot={isPilot}
              onChanged={() => refreshCurrentContract()}
              recentUploadNames={recentUpload?.contractId === currentContract.contract_id ? recentUpload.names : undefined}
              onAssign={(d) => setAssignPrefill({ ...d, key: Date.now() })}
            />
            {isPilot && <ApprovalPanel contract={currentContract} onChanged={() => refreshCurrentContract()} />}
            {isPilot && <AssignmentPanel contract={currentContract} prefill={assignPrefill} />}
            {isPilot && <PilotReviewPanel contract={currentContract} onChanged={refreshCurrentContract} historyOnly />}
          </div>
        );

      // [임시 주석 처리] 증빙서류 관리 페이지
      // case 'documents':
      //   return (
      //     <DocumentsView
      //       currentContract={currentContract}
      //       onSelectDocument={(doc) => setSelectedDoc(doc)}
      //       onOpenUpload={canEdit ? () => handleOpenUploadModal() : undefined}
      //       onDeleteDocument={canEdit ? handleDeleteDocument : undefined}
      //     />
      //   );

      case 'reports':
        return (
          <ValidationReportView
            currentContract={currentContract}
            onRunPipeline={() => handleRunPipelineSimulation()}
            onRevalidate={handleRevalidate}
            loading={actionLoading}
            pilot={isPilot}
          />
        );

      case 'account-settings':
        if (isPilot && pilotInfo) return <PilotOperations info={pilotInfo} onChanged={refreshCurrentContract} />;
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
    <AppShell
      title={isAutoBatchOpen ? '새 계약 등록' : activeTab === 'dashboard' ? '업무함' : activeTab === 'contracts' ? (contractViewMode === 'detail' ? `계약 #${currentContract?.contract_id ?? ''}` : '계약 찾기') : activeTab === 'account-settings' ? '설정' : '검수 리포트'}
      activeTab={activeTab} onTabChange={handleTabChange}
      companyName={pilotInfo?.company_name}
      onOpenAutoBatchContract={canEdit ? openRegistration : undefined}
      onOpenUpload={canEdit ? () => handleOpenUploadModal() : undefined}
      onOpenNewContract={canEdit ? () => setIsNewContractOpen(true) : undefined}
      isMaskingEnabled={isMaskingEnabled} onToggleMasking={() => setIsMaskingEnabled((v) => !v)}
      onSeedDemo={!isPilot && canEdit ? handleSeedDemo : undefined} loading={actionLoading}
    >
      {renderActiveContent()}
      {/* Modals */}
      {advancedDocOpen && selectedDoc && currentContract?.workflow && <PilotDocumentDialog doc={selectedDoc} revision={currentContract.workflow.revision} canEdit={canEdit} onClose={() => setAdvancedDocOpen(false)} onChanged={refreshCurrentContract} />}
      <DocumentViewerModal
        document={advancedDocOpen || isPilot ? null : selectedDoc}
        onManage={isPilot && canEdit ? () => setAdvancedDocOpen(true) : undefined}
        onClose={() => setSelectedDoc(null)}
        onDelete={canEdit ? handleDeleteDocument : undefined}
        isMaskingEnabled={isMaskingEnabled}
      />

      {currentContract && (
        <>
          <UploadModal
            contractId={currentContract.contract_id}
            isOpen={!isPilot && isUploadOpen}
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
            pilot={isPilot}
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
        isOpen={!isPilot && isAutoBatchOpen}
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
        title="증빙서류 제외"
        itemName={documentToDelete?.fileName}
        itemBadge="증빙서류"
        message={`선택한 증빙서류를 이 계약에서 제외하시겠습니까?\n삭제 즉시 AI 검수 룰이 자동으로 재실행되어 계약 충족률과 검수 결과가 갱신됩니다.`}
        subMessage="원본 파일과 확인 이력은 회사 보관 정책에 따라 서버에 남습니다."
        confirmText="증빙 제외"
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
        message={`선택한 계약과 증빙 정보를 업무함에서 제외하시겠습니까?\n보관 파일과 대표 확인 이력은 서버에 남습니다.`}
        confirmText="계약 제외"
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
    </AppShell>
  );
};

export default ContractDashboard;
