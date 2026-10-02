import React, { useState, useEffect } from 'react';
import {
  X,
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
  // 등록할 때 계약 기준을 같이 받아서, 등록 직후 '계약 기준 확인'이 뜨지 않게 한다
  const [amountBasis, setAmountBasis] = useState<'TOTAL' | 'SUPPLY'>('TOTAL');
  const [taxAmount, setTaxAmount] = useState('');
  const [paymentMode, setPaymentMode] = useState<'FULL' | 'INSTALLMENT'>('FULL');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const resetForm = () => {
    setSelectedFiles([]);
    setParsing(false);
    setSubmitting(false);
    setSynthesis(null);
    setTitle('');
    setVendorName('');
    setBusinessNumber('');
    setContractAmount('');
    setIssueDate('');
    setAmountBasis('TOTAL');
    setTaxAmount('');
    setPaymentMode('FULL');
    setErrorMsg(null);
  };

  useEffect(() => {
    if (!isOpen) {
      resetForm();
    }
  }, [isOpen]);

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

    if (amountBasis === 'SUPPLY' && !(Number(taxAmount) >= 0 && taxAmount !== '')) {
      setErrorMsg('공급가액 기준이면 계약서에 적힌 세액도 입력해 주세요. (임의로 10%를 더하지 않습니다)');
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

      try {
        await api.updateContract(createdContract.contract_id, {
          amount_basis: amountBasis,
          tax_amount: amountBasis === 'SUPPLY' ? Number(taxAmount) : null,
          payment_mode: paymentMode,
          revision: createdContract.workflow?.revision,
          change_note: '등록할 때 계약 기준 입력',
        });
      } catch (policyErr) {
        // 계약은 만들어졌으니 화면으로 이동하고, 기준은 계약 화면에서 다시 입력하게 둔다
        console.warn('계약 기준 저장 실패:', policyErr);
      }
      onSuccess(createdContract.contract_id);
      onClose();
    } catch (err: any) {
      console.error(err);
      setErrorMsg(err instanceof Error && err.message ? `등록하지 못했습니다: ${err.message}` : '등록하지 못했습니다. 잠시 뒤 다시 시도해 주세요.');
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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50" role="dialog" aria-modal="true">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-3xl overflow-hidden flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="flex items-start gap-3 border-b border-slate-100 px-6 py-4 shrink-0">
          <div className="min-w-0">
            <h3 className="text-lg font-bold text-slate-900">서류 6종으로 계약 등록</h3>
            <p className="mt-0.5 text-sm text-slate-500">서류를 올리면 종류를 나누고 계약명·거래처·금액을 읽어 미리 채웁니다. 내용을 확인하고 계약 기준을 고르면 등록됩니다.</p>
          </div>
          <button onClick={onClose} aria-label="닫기" className="ml-auto rounded-lg p-1.5 text-slate-400 hover:bg-slate-100">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="p-6 overflow-y-auto space-y-6">
          {/* File Upload Slot Cards */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <div>
                <h4 className="text-xs font-black text-slate-800 flex items-center space-x-2">
                  <Upload className="w-4 h-4 text-indigo-600" />
                  <span>올린 서류 {selectedFiles.length}개</span>
                </h4>
                <p className="text-[11px] text-slate-400 mt-0.5 font-medium">
                  PDF·이미지·워드·한글·엑셀 파일을 올릴 수 있어요. 한 번에 여러 개 골라도 됩니다.
                </p>
              </div>
              <label className="cursor-pointer inline-flex items-center space-x-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-extrabold rounded-xl shadow-sm transition-all hover:scale-[1.02]">
                <Upload className="w-3.5 h-3.5" />
                <span>파일 고르기</span>
                <input
                  type="file"
                  multiple
                  accept=".pdf,.png,.jpg,.jpeg,.webp,.bmp,.tiff,.tif,.gif,.txt,.docx,.doc,.hwp,.hwpx,.xlsx,.xls,.csv"
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
                        <span className="text-[10px] text-slate-400 font-medium">아직 없음</span>
                      )}
                    </div>
                    {isAttached ? (
                      <p className="text-[10px] text-emerald-700 font-semibold truncate">
                        {uploadedMatches.map((m) => m.name).join(', ')}
                      </p>
                    ) : (
                      <p className="text-[10px] text-slate-400">이 종류의 파일이 아직 없어요</p>
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
                <p className="text-xs font-extrabold">서류를 읽고 있습니다…</p>
                <p className="text-[11px] text-indigo-700 mt-0.5">
                  계약명·거래처·사업자번호·금액·날짜를 찾아 아래 칸에 미리 채웁니다.
                </p>
              </div>
            </div>
          )}

          {/* Synthesis AI Results Card */}
          {synthesis && !parsing && (
            <div className="p-4 bg-emerald-50/60 border border-emerald-200 rounded-2xl space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-black text-emerald-950 flex items-center space-x-1.5">
                  <ShieldCheck className="w-4 h-4 text-emerald-600" />
                  <span>서류를 다 읽었어요 · 아래 내용이 맞는지 확인하세요</span>
                </span>
                <span className="text-[11px] font-bold text-emerald-700 bg-emerald-100/80 px-2 py-0.5 rounded-lg">
                  서류 {synthesis.documents.length}개
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                {synthesis.documents.map((doc, idx) => (
                  <div key={idx} className="bg-white/90 p-2.5 rounded-xl border border-slate-200/80 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-800 truncate max-w-[180px]">{doc.file_name}</span>
                      <span className="text-[10px] font-extrabold text-indigo-700 bg-indigo-50 px-1.5 py-0.5 rounded">
                        {getTypeNameInKorean(doc.document_type)} (분류 참고점수 {Math.round(doc.confidence * 100)}%)
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
              읽어 온 내용 확인 (틀린 곳은 고쳐 주세요)
            </h4>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                계약명 <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                required
                placeholder="예: 업무지원 시스템 구축 용역"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full px-3.5 py-2.5 text-xs font-bold border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-900 bg-white"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  거래처 <span className="text-rose-500">*</span>
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
                  계약 금액 (원) <span className="text-rose-500">*</span>
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
                  계약일
                </label>
                <input
                  type="date"
                  value={issueDate}
                  onChange={(e) => setIssueDate(e.target.value)}
                  className="w-full px-3.5 py-2.5 text-xs font-semibold border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-800 bg-white"
                />
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 space-y-3">
              <div className="text-xs font-bold text-slate-700">계약 기준 <span className="font-normal text-slate-500">계약서에 적힌 대로 고르세요. 금액 대조에 그대로 씁니다.</span></div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <label className="text-xs font-semibold text-slate-700">금액 기준
                  <select value={amountBasis} onChange={(e) => setAmountBasis(e.target.value as 'TOTAL' | 'SUPPLY')}
                    className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs text-slate-800">
                    <option value="TOTAL">부가세 포함 합계</option>
                    <option value="SUPPLY">공급가액 (부가세 별도)</option>
                  </select>
                </label>
                {amountBasis === 'SUPPLY' && (
                  <label className="text-xs font-semibold text-slate-700">계약서의 세액 (원)
                    <input type="number" min={0} value={taxAmount} onChange={(e) => setTaxAmount(e.target.value)} placeholder="예: 150000"
                      className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs text-slate-800" />
                  </label>
                )}
                <label className="text-xs font-semibold text-slate-700">지급 방식
                  <select value={paymentMode} onChange={(e) => setPaymentMode(e.target.value as 'FULL' | 'INSTALLMENT')}
                    className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs text-slate-800">
                    <option value="FULL">일시(전액) 지급</option>
                    <option value="INSTALLMENT">분할 지급 (선금·잔금)</option>
                  </select>
                </label>
              </div>
            </div>
          </form>
        </div>

        {/* Footer */}
        <div className="p-5 border-t border-slate-200 bg-slate-50 flex items-center justify-between shrink-0">
          <div className="text-[11px] text-slate-500 font-medium hidden sm:block">
            등록하면 개인정보를 가리고, 서류를 나누고, 자동 검사까지 한 번에 진행합니다.
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
              className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold rounded-lg transition-colors flex items-center space-x-2 disabled:opacity-50"
            >
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>계약 & 6종 서류 등록 중...</span>
                </>
              ) : (
                <>
                  <span>계약 등록하기</span>
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
