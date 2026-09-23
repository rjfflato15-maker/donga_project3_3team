import React, { useState } from 'react';
import {
  X,
  Sparkles,
  Upload,
  Loader2,
  CheckCircle2,
  FileCheck,
  Building2,
  CreditCard,
  Receipt,
  FileSpreadsheet,
  AlertCircle,
  ArrowRight,
  ShieldCheck,
} from 'lucide-react';
import { api } from '../api/client';
import { AutoContractSynthesisResponse, DocumentType } from '../types';

interface AutoBatchContractModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (contractId: number) => void;
}

const DOCUMENT_SLOTS: { type: DocumentType; label: string; icon: React.FC<{ className?: string }> }[] = [
  { type: 'contract', label: '1. 외주계약서', icon: FileCheck },
  { type: 'estimate', label: '2. 견적서', icon: FileSpreadsheet },
  { type: 'business_registration', label: '3. 사업자등록증', icon: Building2 },
  { type: 'bank_account', label: '4. 통장사본', icon: CreditCard },
  { type: 'tax_invoice', label: '5. 전자세금계산서', icon: Receipt },
  { type: 'inspection_confirmation', label: '6. 검수확인서', icon: CheckCircle2 },
];

export const AutoBatchContractModal: React.FC<AutoBatchContractModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [parsing, setParsing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [synthesis, setSynthesis] = useState<AutoContractSynthesisResponse | null>(null);

  // Form states initialized after AI parsing
  const [title, setTitle] = useState('');
  const [vendorName, setVendorName] = useState('');
  const [businessNumber, setBusinessNumber] = useState('');
  const [contractAmount, setContractAmount] = useState('');
  const [issueDate, setIssueDate] = useState('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleFilesSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const fileArray = Array.from(files);
    setSelectedFiles((prev) => [...prev, ...fileArray]);
    setErrorMsg(null);
    setParsing(true);

    try {
      const allFiles = [...selectedFiles, ...fileArray];
      const res = await api.autoParseBatchDocuments(allFiles);
      setSynthesis(res);

      if (res.title) setTitle(res.title);
      if (res.vendor_name) setVendorName(res.vendor_name);
      if (res.business_number) setBusinessNumber(res.business_number);
      if (res.contract_amount) setContractAmount(res.contract_amount.toString());
      if (res.issue_date) setIssueDate(res.issue_date);
    } catch (err: any) {
      console.error(err);
      setErrorMsg('서류 자동 분석 중 오류가 발생했습니다. 직접 필드를 입력하여 계약을 생성할 수 있습니다.');
    } finally {
      setParsing(false);
    }
  };

  const handleRemoveFile = async (indexToRemove: number) => {
    const updated = selectedFiles.filter((_, idx) => idx !== indexToRemove);
    setSelectedFiles(updated);
    if (updated.length > 0) {
      setParsing(true);
      try {
        const res = await api.autoParseBatchDocuments(updated);
        setSynthesis(res);
        if (res.title) setTitle(res.title);
        if (res.vendor_name) setVendorName(res.vendor_name);
        if (res.business_number) setBusinessNumber(res.business_number);
        if (res.contract_amount) setContractAmount(res.contract_amount.toString());
        if (res.issue_date) setIssueDate(res.issue_date);
      } catch (err) {
        console.error(err);
      } finally {
        setParsing(false);
      }
    } else {
      setSynthesis(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title || !vendorName || !businessNumber || !contractAmount) {
      setErrorMsg('모든 필수 항목(계약명, 거래처, 사업자번호, 계약금액)을 입력해주세요.');
      return;
    }

    if (selectedFiles.length === 0) {
      setErrorMsg('최소 1개 이상의 증빙 서류를 첨부해 주세요.');
      return;
    }

    setSubmitting(true);
    setErrorMsg(null);

    try {
      const createdContract = await api.autoCreateBatchContract(
        {
          title,
          vendor_name: vendorName,
          business_number: businessNumber,
          contract_amount: parseFloat(contractAmount),
        },
        selectedFiles
      );

      onSuccess(createdContract.contract_id);
      onClose();
    } catch (err: any) {
      console.error(err);
      setErrorMsg('계약 및 6종 서류 자동 생성 중 오류가 발생했습니다.');
    } finally {
      setSubmitting(false);
    }
  };

  const getTypeNameInKorean = (typeStr: string) => {
    const mapping: Record<string, string> = {
      contract: '계약서',
      estimate: '견적서',
      business_registration: '사업자등록증',
      bank_account: '통장사본',
      tax_invoice: '전자세금계산서',
      inspection_confirmation: '검수확인서',
      unknown: '기타서류',
    };
    return mapping[typeStr] || typeStr;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-md animate-in fade-in duration-200">
      <div className="bg-white rounded-3xl shadow-2xl border border-indigo-100 w-full max-w-3xl overflow-hidden flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="p-6 bg-gradient-to-r from-indigo-900 via-indigo-800 to-slate-900 text-white flex items-center justify-between shrink-0">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-2xl bg-indigo-500/30 border border-indigo-400/40 flex items-center justify-center text-amber-300 shadow-inner">
              <Sparkles className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-lg font-black tracking-tight">6종 증빙 서류 기반 계약 자동 생성</h3>
                <span className="text-[10px] font-bold bg-amber-400 text-indigo-950 px-2 py-0.5 rounded-full uppercase">
                  AI Auto Generator
                </span>
              </div>
              <p className="text-xs text-indigo-200 mt-0.5">
                6종 서류(계약서, 견적서, 사업자증, 통장, 계산서, 검수서)를 등록하면 계약 내용, 금액, 사업자번호, 날짜를 자동 추출하여 계약을 완성합니다.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-indigo-200 hover:text-white hover:bg-white/10 rounded-2xl transition-all"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="p-6 overflow-y-auto space-y-6">
          {/* File Upload Slot Cards */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-xs font-black text-slate-800 flex items-center space-x-2">
                <Upload className="w-4 h-4 text-indigo-600" />
                <span>6종 증빙 서류 업로드 ({selectedFiles.length}/6개 등록됨)</span>
              </h4>
              <label className="cursor-pointer inline-flex items-center space-x-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-extrabold rounded-xl shadow-sm transition-all hover:scale-[1.02]">
                <Upload className="w-3.5 h-3.5" />
                <span>서류 추가 / 일괄 선택</span>
                <input
                  type="file"
                  multiple
                  accept=".pdf,.png,.jpg,.jpeg,.txt"
                  onChange={handleFilesSelect}
                  className="hidden"
                />
              </label>
            </div>

            {/* Slots Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
              {DOCUMENT_SLOTS.map((slot) => {
                const IconComp = slot.icon;
                const uploadedMatches = selectedFiles.filter((f) => {
                  if (!synthesis) return false;
                  const found = synthesis.documents.find((d) => d.file_name === f.name);
                  return found?.document_type === slot.type;
                });
                const isAttached = uploadedMatches.length > 0;

                return (
                  <div
                    key={slot.type}
                    className={`p-3 rounded-2xl border transition-all ${
                      isAttached
                        ? 'bg-emerald-50/80 border-emerald-300 text-emerald-900 shadow-2xs'
                        : 'bg-slate-50 border-slate-200 text-slate-500 hover:border-indigo-300'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[11px] font-bold flex items-center space-x-1.5">
                        <IconComp className={`w-3.5 h-3.5 ${isAttached ? 'text-emerald-600' : 'text-slate-400'}`} />
                        <span>{slot.label}</span>
                      </span>
                      {isAttached ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                      ) : (
                        <span className="text-[10px] text-slate-400 font-medium">대기중</span>
                      )}
                    </div>
                    {isAttached ? (
                      <p className="text-[10px] text-emerald-700 font-semibold truncate">
                        {uploadedMatches.map((m) => m.name).join(', ')}
                      </p>
                    ) : (
                      <p className="text-[10px] text-slate-400">파일을 첨부하세요</p>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Selected File Chips */}
            {selectedFiles.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5 p-3 bg-slate-50 border border-slate-200 rounded-2xl">
                <span className="text-[11px] font-bold text-slate-600 mr-1 self-center">첨부된 파일:</span>
                {selectedFiles.map((file, idx) => {
                  const docInfo = synthesis?.documents.find((d) => d.file_name === file.name);
                  return (
                    <span
                      key={idx}
                      className="inline-flex items-center space-x-1.5 bg-white border border-slate-300 px-2.5 py-1 rounded-xl text-xs font-semibold text-slate-700 shadow-2xs"
                    >
                      <span className="truncate max-w-[150px]">{file.name}</span>
                      {docInfo && (
                        <span className="text-[10px] font-extrabold text-indigo-600 bg-indigo-50 px-1.5 py-0.5 rounded-md">
                          {getTypeNameInKorean(docInfo.document_type)}
                        </span>
                      )}
                      <button
                        type="button"
                        onClick={() => handleRemoveFile(idx)}
                        className="text-slate-400 hover:text-rose-600 ml-1"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </span>
                  );
                })}
              </div>
            )}
          </div>

          {/* AI Parsing Banner */}
          {parsing && (
            <div className="p-4 bg-indigo-50 border border-indigo-200 rounded-2xl flex items-center space-x-3 text-indigo-900 animate-pulse">
              <Loader2 className="w-5 h-5 text-indigo-600 animate-spin shrink-0" />
              <div>
                <p className="text-xs font-extrabold">AI가 6종 서류를 교차 분석 및 정보 자동 합성 중입니다...</p>
                <p className="text-[11px] text-indigo-700 mt-0.5">
                  계약서, 사업자증, 통장, 세금계산서 등에서 계약명, 금액, 사업자번호, 날짜를 통합 추출합니다.
                </p>
              </div>
            </div>
          )}

          {/* Synthesis AI Results Card */}
          {synthesis && !parsing && (
            <div className="p-4 bg-gradient-to-r from-emerald-50/90 via-teal-50/60 to-indigo-50/80 border border-emerald-200 rounded-2xl shadow-2xs space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-black text-emerald-950 flex items-center space-x-1.5">
                  <ShieldCheck className="w-4 h-4 text-emerald-600" />
                  <span>AI 서류 교차 대조 추출 완료</span>
                </span>
                <span className="text-[11px] font-bold text-emerald-700 bg-emerald-100/80 px-2 py-0.5 rounded-lg">
                  {synthesis.documents.length}개 서류 합성 완료
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                {synthesis.documents.map((doc, idx) => (
                  <div key={idx} className="bg-white/90 p-2.5 rounded-xl border border-slate-200/80 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-800 truncate max-w-[180px]">{doc.file_name}</span>
                      <span className="text-[10px] font-extrabold text-indigo-700 bg-indigo-50 px-1.5 py-0.5 rounded">
                        {getTypeNameInKorean(doc.document_type)} ({Math.round(doc.confidence * 100)}%)
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-600 font-medium space-y-0.5">
                      {doc.company_name && <div>거래처: <span className="font-bold text-slate-900">{doc.company_name}</span></div>}
                      {doc.business_registration_no && <div>사업자번호: <span className="font-mono font-bold text-slate-900">{doc.business_registration_no}</span></div>}
                      {doc.amount && <div>금액: <span className="font-bold text-indigo-700">{doc.amount.toLocaleString()}원</span></div>}
                      {doc.issue_date && <div>날짜: <span className="font-bold text-slate-900">{doc.issue_date}</span></div>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Error Message */}
          {errorMsg && (
            <div className="p-3 bg-rose-50 border border-rose-200 text-rose-700 rounded-2xl text-xs font-semibold flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-600" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Final Form Inputs */}
          <form id="auto-contract-form" onSubmit={handleSubmit} className="space-y-4 pt-2">
            <h4 className="text-xs font-black text-slate-800 border-b border-slate-200 pb-2">
              계약 정보 확인 및 최종 검토 (AI 자동 완성)
            </h4>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                계약 내용 (계약명) <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                required
                placeholder="예: AI 서비스 개발 및 라이선스 외주 계약"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full px-3.5 py-2.5 text-xs font-bold border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-900 bg-white"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  수주 거래처명 <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="예: 주식회사 앤티그래비티"
                  value={vendorName}
                  onChange={(e) => setVendorName(e.target.value)}
                  className="w-full px-3.5 py-2.5 text-xs font-semibold border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-900 bg-white"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  사업자등록번호 <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="예: 123-45-67890"
                  value={businessNumber}
                  onChange={(e) => setBusinessNumber(e.target.value)}
                  className="w-full px-3.5 py-2.5 text-xs font-mono font-bold border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 text-indigo-900 bg-white"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  총 계약금액 (원) <span className="text-rose-500">*</span>
                </label>
                <input
                  type="number"
                  required
                  placeholder="예: 15000000"
                  value={contractAmount}
                  onChange={(e) => setContractAmount(e.target.value)}
                  className="w-full px-3.5 py-2.5 text-xs font-black border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 text-indigo-700 bg-white"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  계약 / 발행 날짜
                </label>
                <input
                  type="date"
                  value={issueDate}
                  onChange={(e) => setIssueDate(e.target.value)}
                  className="w-full px-3.5 py-2.5 text-xs font-semibold border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-800 bg-white"
                />
              </div>
            </div>
          </form>
        </div>

        {/* Footer */}
        <div className="p-5 border-t border-slate-200 bg-slate-50 flex items-center justify-between shrink-0">
          <div className="text-[11px] text-slate-500 font-medium hidden sm:block">
            완료 클릭 시 6종 서류 마스킹, 분류, 검증 및 계약 등록이 원스톱으로 처리됩니다.
          </div>
          <div className="flex items-center space-x-2 ml-auto">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 text-xs font-extrabold rounded-xl transition-all"
            >
              취소
            </button>
            <button
              type="submit"
              form="auto-contract-form"
              disabled={submitting || parsing}
              className="px-5 py-2.5 bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-700 hover:to-indigo-800 text-white text-xs font-black rounded-xl shadow-lg shadow-indigo-600/30 transition-all flex items-center space-x-2 disabled:opacity-50"
            >
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>계약 & 6종 서류 등록 중...</span>
                </>
              ) : (
                <>
                  <span>⚡ 6종 서류로 계약 자동 생성 완료</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
