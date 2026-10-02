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
      amount_basis?: string;
      tax_amount?: number | null;
      payment_mode?: string;
      revision?: number;
      change_note?: string;
    }
  ) => Promise<void>;
  loading: boolean;
  pilot?: boolean;
}

export const EditContractModal: React.FC<EditContractModalProps> = ({
  isOpen,
  onClose,
  contract,
  onUpdate,
  loading,
  pilot = false,
}) => {
  const [title, setTitle] = useState('');
  const [vendorName, setVendorName] = useState('');
  const [businessNumber, setBusinessNumber] = useState('');
  const [contractAmount, setContractAmount] = useState('');
  const [basis, setBasis] = useState('UNKNOWN');
  const [tax, setTax] = useState('');
  const [payment, setPayment] = useState('FULL');
  const [note, setNote] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (contract) {
      setTitle(contract.title || '');
      setVendorName(contract.vendor_name || '');
      setBusinessNumber(contract.business_number || '');
      setContractAmount(contract.contract_amount ? String(contract.contract_amount) : '');
      const workflow = 'workflow' in contract ? contract.workflow : undefined;
      setBasis(workflow?.amount_basis || 'UNKNOWN');
      setTax(workflow?.tax_amount == null ? '' : String(workflow.tax_amount));
      setPayment(workflow?.payment_mode || 'FULL'); setNote(''); setError('');
    }
  }, [contract]);

  if (!isOpen || !contract) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title || !vendorName || !businessNumber || !contractAmount) return;

    try {
      await onUpdate(contract.contract_id, {
      title,
      vendor_name: vendorName,
      business_number: businessNumber,
      contract_amount: parseFloat(contractAmount),
      ...(pilot ? { amount_basis: basis, tax_amount: tax === '' ? null : Number(tax), payment_mode: payment, revision: 'workflow' in contract ? contract.workflow?.revision : ('revision' in contract ? contract.revision : undefined), change_note: note } : {}),
    });

      onClose();
    } catch (reason) { setError(reason instanceof Error ? reason.message : '저장하지 못했습니다.'); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-lg max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="p-5 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold">
              <Edit3 className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">계약 정보 수정</h3>
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
              계약 기준 금액 (원) <span className="text-rose-500">*</span>
            </label>
            <input
              type="number"
              min={0}
              step={1}
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

          {pilot && <div className="space-y-3 rounded-xl border border-indigo-100 bg-indigo-50/40 p-4">
            <label className="block text-xs font-bold text-slate-700">금액 기준<select className="mt-1 w-full rounded-xl border border-slate-300 bg-white p-2 text-xs" value={basis} onChange={e => setBasis(e.target.value)}><option value="UNKNOWN">미확인</option><option value="TOTAL">부가세 포함 합계</option><option value="SUPPLY">공급가액 · 부가세 제외</option></select></label>
            <div className="grid grid-cols-2 gap-3"><label className="block text-xs font-bold text-slate-700">명시된 세액 · 원<input className="mt-1 w-full rounded-xl border border-slate-300 p-2 text-xs" type="number" min={0} step={1} value={tax} onChange={e => setTax(e.target.value)} placeholder="모르면 비워 두기" /></label><label className="block text-xs font-bold text-slate-700">지급 방식<select className="mt-1 w-full rounded-xl border border-slate-300 bg-white p-2 text-xs" value={payment} onChange={e => setPayment(e.target.value)}><option value="FULL">전액 지급</option><option value="INSTALLMENT">분할 지급</option></select></label></div>
            <p className="text-[11px] leading-5 text-slate-500">공급가액과 명시된 세액을 더해 합계로 비교합니다. 세율을 임의로 적용하지 않습니다. 기준 수정으로 문서 추출값을 덮어쓰지 않으며, 대표 재확인이 필요합니다.</p>
            <label className="block text-xs font-bold text-slate-700">변경 근거<textarea required minLength={3} maxLength={2000} value={note} onChange={e => setNote(e.target.value)} className="mt-1 w-full rounded-xl border border-slate-300 p-2 text-xs" placeholder="원본을 확인한 내용과 수정 사유" /></label>
          </div>}
          {error && <p role="alert" className="text-xs text-rose-700">{error}</p>}
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
