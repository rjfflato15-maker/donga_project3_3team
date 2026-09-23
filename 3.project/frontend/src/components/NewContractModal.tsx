import React, { useState } from 'react';
import { X, Plus, FileText, Upload, Loader2, Sparkles, CheckCircle2 } from 'lucide-react';
import { api } from '../api/client';

interface NewContractModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreate: (
    data: {
      title: string;
      vendor_name: string;
      business_number: string;
      contract_amount: number;
    },
    attachedFile?: File | null
  ) => Promise<void>;
  loading: boolean;
}

export const NewContractModal: React.FC<NewContractModalProps> = ({
  isOpen,
  onClose,
  onCreate,
  loading,
}) => {
  const [title, setTitle] = useState('');
  const [vendorName, setVendorName] = useState('');
  const [businessNumber, setBusinessNumber] = useState('');
  const [contractAmount, setContractAmount] = useState('');

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [parsingLoading, setParsingLoading] = useState(false);
  const [parseSuccessMessage, setParseSuccessMessage] = useState<string | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const file = files[0];
    setSelectedFile(file);
    setParsingLoading(true);
    setParseError(null);
    setParseSuccessMessage(null);

    try {
      const parsed = await api.parseContractFile(file);

      if (parsed.title) setTitle(parsed.title);
      if (parsed.vendor_name) setVendorName(parsed.vendor_name);
      if (parsed.business_number) setBusinessNumber(parsed.business_number);
      if (parsed.contract_amount) setContractAmount(parsed.contract_amount.toString());

      setParseSuccessMessage(`'${file.name}' 서류에서 계약명, 거래처, 사업자번호, 금액 정보를 성공적으로 추출했습니다!`);
    } catch (err: any) {
      console.error(err);
      setParseError('파일에서 정보를 자동으로 읽는 중 오류가 발생했습니다. 직접 입력해주세요.');
    } finally {
      setParsingLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title || !vendorName || !businessNumber || !contractAmount) return;

    await onCreate(
      {
        title,
        vendor_name: vendorName,
        business_number: businessNumber,
        contract_amount: parseFloat(contractAmount),
      },
      selectedFile
    );

    setTitle('');
    setVendorName('');
    setBusinessNumber('');
    setContractAmount('');
    setSelectedFile(null);
    setParseSuccessMessage(null);
    setParseError(null);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-lg overflow-hidden">
        {/* Header */}
        <div className="p-5 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 rounded-xl bg-indigo-600 text-white flex items-center justify-center font-bold">
              <FileText className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-base font-extrabold text-slate-900">새 계약 등록</h3>
              <p className="text-[11px] text-slate-500 font-semibold">PDF 계약서를 선택하면 정보가 자동으로 입력됩니다.</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-200/60 rounded-xl transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* PDF File Auto-parsing Section */}
          <div className="bg-gradient-to-r from-indigo-50/80 via-blue-50/60 to-slate-50 rounded-2xl p-4 border border-indigo-100 shadow-2xs space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-black text-indigo-900 flex items-center space-x-1.5">
                <Sparkles className="w-4 h-4 text-indigo-600" />
                <span>PDF / 계약서 파일로 자동 입력</span>
              </span>
              {parsingLoading && (
                <span className="inline-flex items-center space-x-1 text-xs font-bold text-indigo-600 animate-pulse">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>AI 파일 파싱 중...</span>
                </span>
              )}
            </div>

            <label className="block cursor-pointer">
              <div className="flex items-center justify-center space-x-2 border-2 border-dashed border-indigo-300 hover:border-indigo-500 bg-white/80 hover:bg-white rounded-xl py-3 px-4 transition-all">
                <Upload className="w-4 h-4 text-indigo-600" />
                <span className="text-xs font-bold text-slate-700">
                  {selectedFile ? `선택된 파일: ${selectedFile.name}` : 'PDF / 이미지 계약서 파일 선택'}
                </span>
              </div>
              <input
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.txt"
                onChange={handleFileSelect}
                className="hidden"
              />
            </label>

            {parseSuccessMessage && (
              <div className="flex items-start space-x-1.5 text-[11px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 p-2 rounded-xl">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <span>{parseSuccessMessage}</span>
              </div>
            )}

            {parseError && (
              <div className="text-[11px] font-semibold text-rose-600 bg-rose-50 border border-rose-200 p-2 rounded-xl">
                {parseError}
              </div>
            )}
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1">
              계약명 <span className="text-rose-500">*</span>
            </label>
            <input
              type="text"
              required
              placeholder="예: ABC 홈페이지 구축 외주 계약"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium text-slate-900"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                수주 거래처명 <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                required
                placeholder="예: ABC 주식회사"
                value={vendorName}
                onChange={(e) => setVendorName(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium text-slate-900"
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
                className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono text-slate-900 font-semibold"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1">
              총 계약금액 (원) <span className="text-rose-500">*</span>
            </label>
            <input
              type="number"
              required
              placeholder="예: 11000000"
              value={contractAmount}
              onChange={(e) => setContractAmount(e.target.value)}
              className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 font-bold text-indigo-700"
            />
          </div>

          {/* Footer */}
          <div className="pt-4 border-t border-slate-100 flex justify-end space-x-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-slate-100 text-slate-700 font-semibold text-xs rounded-xl hover:bg-slate-200 transition-colors"
            >
              취소
            </button>
            <button
              type="submit"
              disabled={loading || parsingLoading}
              className="px-4.5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-extrabold text-xs rounded-xl shadow-md transition-all flex items-center space-x-1.5"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
              <span>{loading ? '계약 및 서류 등록 중...' : '계약 등록 완료'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

