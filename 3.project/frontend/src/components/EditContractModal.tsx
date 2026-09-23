import React, { useState, useEffect } from 'react';
import { X, Save, Edit3 } from 'lucide-react';
import { ContractDetail, ContractListItem } from '../types';

interface EditContractModalProps {
  isOpen: boolean;
  onClose: () => void;
  contract: ContractDetail | ContractListItem | null;
  onUpdate: (
    contractId: number,
    data: {
      title?: string;
      vendor_name?: string;
      business_number?: string;
      contract_amount?: number;
    }
  ) => Promise<void>;
  loading: boolean;
}

export const EditContractModal: React.FC<EditContractModalProps> = ({
  isOpen,
  onClose,
  contract,
  onUpdate,
  loading,
}) => {
  const [title, setTitle] = useState('');
  const [vendorName, setVendorName] = useState('');
  const [businessNumber, setBusinessNumber] = useState('');
  const [contractAmount, setContractAmount] = useState('');

  useEffect(() => {
    if (contract) {
      setTitle(contract.title || '');
      setVendorName(contract.vendor_name || '');
      setBusinessNumber(contract.business_number || '');
      setContractAmount(contract.contract_amount ? String(contract.contract_amount) : '');
    }
  }, [contract]);

  if (!isOpen || !contract) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title || !vendorName || !businessNumber || !contractAmount) return;

    await onUpdate(contract.contract_id, {
      title,
      vendor_name: vendorName,
      business_number: businessNumber,
      contract_amount: parseFloat(contractAmount),
    });

    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-lg overflow-hidden">
        {/* Header */}
        <div className="p-5 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold">
              <Edit3 className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">용역 계약 정보 수정</h3>
              <p className="text-[11px] text-slate-400 font-semibold">
                계약 ID #{contract.contract_id}의 기본 정보 및 대조 기준을 변경합니다.
              </p>
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
          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1">
              계약 명칭 <span className="text-rose-500">*</span>
            </label>
            <input
              type="text"
              required
              placeholder="예: ABC 홈페이지 구축 외주 계약"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full px-3.5 py-2.5 text-xs border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 font-semibold"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                상대 업체명 (거래처) <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                required
                placeholder="예: ABC 주식회사"
                value={vendorName}
                onChange={(e) => setVendorName(e.target.value)}
                className="w-full px-3.5 py-2.5 text-xs border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 font-semibold"
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
                className="w-full px-3.5 py-2.5 text-xs border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 font-semibold"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1">
              총 계약 금액 (원) <span className="text-rose-500">*</span>
            </label>
            <input
              type="number"
              required
              placeholder="예: 11000000"
              value={contractAmount}
              onChange={(e) => setContractAmount(e.target.value)}
              className="w-full px-3.5 py-2.5 text-xs border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 font-bold text-indigo-700"
            />
            <p className="text-[11px] text-slate-400 mt-1 font-medium">
              💡 세금계산서 청구금액과 대조되는 기준 금액입니다. 금액 수정 시 룰 엔진이 자동 재실행됩니다.
            </p>
          </div>

          {/* Footer */}
          <div className="pt-4 border-t border-slate-100 flex justify-end space-x-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2.5 bg-slate-100 text-slate-700 font-bold text-xs rounded-xl hover:bg-slate-200 transition-colors"
            >
              취소
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-extrabold text-xs rounded-xl shadow-md transition-colors flex items-center space-x-1.5"
            >
              <Save className="w-4 h-4" />
              <span>{loading ? '저장 및 검수 룰 재계산 중...' : '변경사항 저장'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
