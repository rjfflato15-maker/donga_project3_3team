import React, { useState } from 'react';
import { X, Plus, FileText } from 'lucide-react';

interface NewContractModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreate: (data: {
    title: string;
    vendor_name: string;
    business_number: string;
    contract_amount: number;
  }) => Promise<void>;
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

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title || !vendorName || !businessNumber || !contractAmount) return;

    await onCreate({
      title,
      vendor_name: vendorName,
      business_number: businessNumber,
      contract_amount: parseFloat(contractAmount),
    });

    setTitle('');
    setVendorName('');
    setBusinessNumber('');
    setContractAmount('');
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-lg overflow-hidden">
        {/* Header */}
        <div className="p-5 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center space-x-2">
            <FileText className="w-5 h-5 text-blue-600" />
            <h3 className="text-base font-bold text-slate-900">새 계약 등록</h3>
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
          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1">
              계약명 <span className="text-rose-500">*</span>
            </label>
            <input
              type="text"
              required
              placeholder="예: 2026년 모바일 앱 UI/UX 개편 외주 계약"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
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
                placeholder="예: (주)디지털솔루션"
                value={vendorName}
                onChange={(e) => setVendorName(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
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
                className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
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
              placeholder="예: 15000000"
              value={contractAmount}
              onChange={(e) => setContractAmount(e.target.value)}
              className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
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
              disabled={loading}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs rounded-xl shadow-sm transition-colors flex items-center space-x-1.5"
            >
              <Plus className="w-4 h-4" />
              <span>{loading ? '등록 중...' : '계약 생성'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
