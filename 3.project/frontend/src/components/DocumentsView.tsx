import React, { useState } from 'react';
import { ContractDetail, DocumentResponse } from '../types';
import { Eye, FileText, Lock } from 'lucide-react';

interface DocumentsViewProps {
  currentContract: ContractDetail | null;
  onSelectDocument: (doc: DocumentResponse) => void;
  onOpenUpload: () => void;
}

export const DocumentsView: React.FC<DocumentsViewProps> = ({
  currentContract,
  onSelectDocument,
  onOpenUpload,
}) => {
  const [filterType, setFilterType] = useState<string>('all');

  if (!currentContract) {
    return (
      <div className="bg-white rounded-2xl p-12 border border-slate-200 text-center text-slate-400 font-semibold">
        선택된 계약 정보가 없습니다.
      </div>
    );
  }

  const filteredDocs = currentContract.documents.filter((doc) => {
    if (filterType === 'all') return true;
    return doc.document_type === filterType;
  });

  const getDocTypeKoreanName = (type: string) => {
    switch (type) {
      case 'contract':
        return '계약서 (contract)';
      case 'estimate':
        return '견적서 (estimate)';
      case 'business_registration':
        return '사업자등록증 (business_registration)';
      case 'bank_account':
        return '통장사본 (bank_account)';
      case 'tax_invoice':
        return '세금계산서 (tax_invoice)';
      case 'inspection_confirmation':
        return '검수확인서 (inspection_confirmation)';
      default:
        return '기타 서류 (unknown)';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">
            증빙서류 관리
          </h1>
          <p className="text-xs text-slate-500 font-medium mt-1">
            계약명: <strong className="text-slate-800">{currentContract.title}</strong> (총 {currentContract.documents.length}건 제출)
          </p>
        </div>

        <button
          onClick={onOpenUpload}
          className="flex items-center space-x-1.5 px-4 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 shadow-sm rounded-xl transition-colors self-start sm:self-auto"
        >
          <FileText className="w-4 h-4" />
          <span>신규 증빙서류 업로드</span>
        </button>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center space-x-2 border-b border-slate-200 pb-2 overflow-x-auto text-xs font-bold">
        {[
          { id: 'all', label: `전체 서류 (${currentContract.documents.length})` },
          { id: 'contract', label: '계약서' },
          { id: 'estimate', label: '견적서' },
          { id: 'business_registration', label: '사업자등록증' },
          { id: 'bank_account', label: '통장사본' },
          { id: 'tax_invoice', label: '세금계산서' },
          { id: 'inspection_confirmation', label: '검수확인서' },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setFilterType(tab.id)}
            className={`px-3 py-1.5 rounded-lg whitespace-nowrap transition-colors ${
              filterType === tab.id
                ? 'bg-indigo-600 text-white shadow-xs'
                : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200/80'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Document Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredDocs.length === 0 ? (
          <div className="col-span-full bg-white rounded-2xl p-12 border border-slate-200 text-center text-slate-400 font-semibold">
            해당 조건의 제출된 증빙서류가 없습니다.
          </div>
        ) : (
          filteredDocs.map((doc) => (
            <div
              key={doc.document_id}
              className="bg-white rounded-2xl p-5 border border-slate-200/80 shadow-xs hover:shadow-md transition-all flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-extrabold uppercase tracking-wider text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-md border border-indigo-100">
                    {doc.document_type}
                  </span>
                  <span className="text-xs font-bold text-slate-400">
                    ID #{doc.document_id}
                  </span>
                </div>

                <h3 className="font-extrabold text-sm text-slate-900 mt-2.5 truncate" title={doc.original_file_name}>
                  {doc.original_file_name}
                </h3>
                <p className="text-xs text-slate-500 font-semibold mt-0.5">
                  {getDocTypeKoreanName(doc.document_type)}
                </p>

                {/* Metadata Details */}
                <div className="mt-4 p-3 bg-slate-50 rounded-xl space-y-1.5 text-xs text-slate-600 border border-slate-100">
                  <div className="flex justify-between">
                    <span>AI 분류 신뢰도:</span>
                    <strong className="text-slate-900">{Math.round(doc.confidence * 100)}%</strong>
                  </div>
                  <div className="flex justify-between">
                    <span>개인정보 마스킹:</span>
                    <strong className={doc.mask_status === 'MASKED' ? 'text-emerald-600 flex items-center space-x-1' : 'text-slate-500'}>
                      <Lock className="w-3 h-3 inline mr-0.5" />
                      {doc.mask_status === 'MASKED' ? '완료 (RRN/PHONE)' : '미발견'}
                    </strong>
                  </div>
                  {doc.analysis?.fields?.company_name && (
                    <div className="flex justify-between">
                      <span>추출 상호명:</span>
                      <strong className="text-slate-900 truncate max-w-[140px]">{doc.analysis.fields.company_name}</strong>
                    </div>
                  )}
                  {doc.analysis?.fields?.amount && (
                    <div className="flex justify-between">
                      <span>추출 금액:</span>
                      <strong className="text-indigo-600">₩{doc.analysis.fields.amount.toLocaleString()}</strong>
                    </div>
                  )}
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
                <span className="text-[11px] text-slate-400 font-medium">상세 대조 지원</span>
                <button
                  onClick={() => onSelectDocument(doc)}
                  className="flex items-center space-x-1 px-3 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 rounded-lg text-xs font-bold transition-colors"
                >
                  <Eye className="w-3.5 h-3.5" />
                  <span>서류 보기 & 마스킹</span>
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
