import React from 'react';
import {
  DocumentType,
  DocumentResponse,
} from '../types';
import {
  FileText,
  Calculator,
  Building2,
  CreditCard,
  Receipt,
  FileCheck2,
  Eye,
  Upload,
} from 'lucide-react';

interface ChecklistProps {
  documents: DocumentResponse[];
  onSelectDocument: (doc: DocumentResponse) => void;
  onUploadSpecific: (docType: DocumentType) => void;
}

const CHECKLIST_ITEMS: {
  type: DocumentType;
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  description: string;
}[] = [
  {
    type: 'contract',
    title: '계약서',
    icon: FileText,
    description: '외주 용역 표준 계약서 (업체명, 계약금액, 계약기간 확인)',
  },
  {
    type: 'estimate',
    title: '견적서',
    icon: Calculator,
    description: '공급가액 및 세액 명세 (계약금액 대조)',
  },
  {
    type: 'business_registration',
    title: '사업자등록증',
    icon: Building2,
    description: '사업자등록번호 및 개업연월일 (국세청 진위확인 연동)',
  },
  {
    type: 'bank_account',
    title: '통장사본',
    icon: CreditCard,
    description: '대금 지급용 계좌개설확인서 (예금주명 일치 확인)',
  },
  {
    type: 'tax_invoice',
    title: '세금계산서',
    icon: Receipt,
    description: '전자세금계산서 (공급가액 및 세액 청구액 확인)',
  },
  {
    type: 'inspection_confirmation',
    title: '검수확인서',
    icon: FileCheck2,
    description: '과업 완료에 따른 납품 및 검수확인서',
  },
];

export const Checklist: React.FC<ChecklistProps> = ({
  documents,
  onSelectDocument,
  onUploadSpecific,
}) => {
  return (
    <div className="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-sm">
      <div className="flex items-center justify-between pb-4 mb-4 border-b border-slate-100">
        <div className="flex items-center space-x-2">
          <FileCheck2 className="w-5 h-5 text-blue-600" />
          <h2 className="text-lg font-bold text-slate-900">증빙 Checklist</h2>
        </div>
        <span className="text-xs text-slate-400 font-medium">핵심 6종 문서</span>
      </div>

      <div className="space-y-3">
        {CHECKLIST_ITEMS.map((item) => {
          const doc = documents.find((d) => d.document_type === item.type);
          const Icon = item.icon;

          // Determine status pill
          let statusLabel = '누락';
          let statusStyle = 'bg-rose-50 text-rose-700 border-rose-200';

          if (doc) {
            // Check if there is an issue (e.g., tax invoice amount mismatch)
            if (item.type === 'tax_invoice' && doc.analysis.fields.amount) {
              statusLabel = '검토';
              statusStyle = 'bg-amber-50 text-amber-800 border-amber-200';
            } else {
              statusLabel = '제출';
              statusStyle = 'bg-emerald-50 text-emerald-700 border-emerald-200';
            }
          }

          return (
            <div
              key={item.type}
              onClick={() => doc && onSelectDocument(doc)}
              className={`flex items-center justify-between p-3.5 rounded-xl border transition-all ${
                doc
                  ? 'bg-slate-50/50 border-slate-200/80 hover:bg-blue-50/40 hover:border-blue-200 cursor-pointer'
                  : 'bg-rose-50/30 border-rose-100/70 border-dashed'
              }`}
            >
              {/* Left: Icon & Name */}
              <div className="flex items-center space-x-3.5">
                <div
                  className={`w-9 h-9 rounded-lg flex items-center justify-center ${
                    doc ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 text-slate-400'
                  }`}
                >
                  <Icon className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="text-sm font-bold text-slate-900">{item.title}</span>
                    {doc && doc.analysis.fields.amount && (
                      <span className="text-xs font-semibold text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
                        {doc.analysis.fields.amount.toLocaleString()}원
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 mt-0.5 hidden sm:block">
                    {doc ? (
                      <span>{doc.original_file_name} • 신뢰도 {Math.round(doc.confidence * 100)}%</span>
                    ) : (
                      item.description
                    )}
                  </p>
                </div>
              </div>

              {/* Right: Status Pill & Action */}
              <div className="flex items-center space-x-2">
                <span
                  className={`px-3 py-1 rounded-full text-xs font-bold border ${statusStyle}`}
                >
                  {statusLabel}
                </span>

                {doc ? (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectDocument(doc);
                    }}
                    className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                    title="문서 상세 대조 확인"
                  >
                    <Eye className="w-4 h-4" />
                  </button>
                ) : (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onUploadSpecific(item.type);
                    }}
                    className="flex items-center space-x-1 px-2.5 py-1 text-xs font-semibold text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-lg transition-colors"
                    title="서류 업로드"
                  >
                    <Upload className="w-3 h-3" />
                    <span>업로드</span>
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
