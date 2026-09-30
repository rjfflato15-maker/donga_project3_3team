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
  Plus,
  Trash2,
  File,
} from 'lucide-react';
import { maskFileName } from '../utils/masking';

interface ChecklistProps {
  documents: DocumentResponse[];
  onSelectDocument: (doc: DocumentResponse) => void;
  onUploadSpecific: (docType: DocumentType) => void;
  onOpenUploadAll?: () => void;
  onDeleteDocument?: (documentId: number, fileName: string) => void;
  isMaskingEnabled?: boolean;
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
  onOpenUploadAll,
  onDeleteDocument,
  isMaskingEnabled = true,
}) => {
  // Collect IDs of primary matched documents to find extra/additional documents
  const primaryDocIds = new Set<number>();
  CHECKLIST_ITEMS.forEach((item) => {
    const matched = documents.find((d) => d.document_type === item.type);
    if (matched) primaryDocIds.add(matched.document_id);
  });
  const additionalDocs = documents.filter((d) => !primaryDocIds.has(d.document_id));

  return (
    <div className="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 mb-4 border-b border-slate-100">
        <div className="flex items-center space-x-2">
          <FileCheck2 className="w-5 h-5 text-blue-600" />
          <h2 className="text-lg font-bold text-slate-900">증빙 Checklist</h2>
        </div>
        <div className="flex items-center space-x-2">
          {onOpenUploadAll && (
            <button
              onClick={onOpenUploadAll}
              className="flex items-center space-x-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl shadow-xs transition-colors cursor-pointer"
              title="신규 증빙 서류 추가 업로드"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>증빙서류 추가</span>
            </button>
          )}
          <span className="text-xs text-slate-400 font-medium hidden sm:inline">핵심 6종 문서</span>
        </div>
      </div>

      {/* 6 Core Documents List */}
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
              <div className="flex items-center space-x-3.5 min-w-0 flex-1 mr-2">
                <div
                  className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${
                    doc ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 text-slate-400'
                  }`}
                >
                  <Icon className="w-5 h-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center space-x-2 flex-wrap">
                    <span className="text-sm font-bold text-slate-900">
                      {item.title}
                    </span>
                    {doc && doc.analysis.fields.amount && (
                      <span className="text-xs font-semibold text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
                        {doc.analysis.fields.amount.toLocaleString()}원
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 mt-0.5 truncate hidden sm:block">
                    {doc ? (
                      <span>
                        {maskFileName(doc.original_file_name, isMaskingEnabled)} • 신뢰도 {Math.round(doc.confidence * 100)}%
                      </span>
                    ) : (
                      item.description
                    )}
                  </p>
                </div>
              </div>

              {/* Right: Status Pill & Action Buttons */}
              <div className="flex items-center space-x-1.5 shrink-0">
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${statusStyle}`}>
                  {statusLabel}
                </span>

                {doc ? (
                  <div className="flex items-center space-x-1">

                    {/* 더보기 / 상세 대조 확인 */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectDocument(doc);
                      }}
                      className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                      title="더보기 (AI 구조화 필드 및 원본 미리보기)"
                    >
                      <Eye className="w-4 h-4" />
                    </button>

                    {/* 교체 / 추가 업로드 */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onUploadSpecific(item.type);
                      }}
                      className="p-1.5 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
                      title="해당 서류 다시 올리기 (교체/추가)"
                    >
                      <Upload className="w-4 h-4" />
                    </button>

                    {/* 서류 삭제 */}
                    {onDeleteDocument && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onDeleteDocument(doc.document_id, doc.original_file_name);
                        }}
                        className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors cursor-pointer"
                        title="증빙서류 삭제"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                ) : (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onUploadSpecific(item.type);
                    }}
                    className="flex items-center space-x-1 px-2.5 py-1 text-xs font-semibold text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-lg transition-colors cursor-pointer"
                    title="서류 추가 업로드"
                  >
                    <Plus className="w-3 h-3" />
                    <span>추가</span>
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Additional / Other submitted evidence documents */}
      {additionalDocs.length > 0 && (
        <div className="mt-4 pt-4 border-t border-slate-100 space-y-2">
          <div className="flex items-center justify-between text-xs font-bold text-slate-500 mb-1">
            <span>기타 / 추가 제출 증빙 ({additionalDocs.length}건)</span>
          </div>
          {additionalDocs.map((extraDoc) => (
            <div
              key={extraDoc.document_id}
              onClick={() => onSelectDocument(extraDoc)}
              className="flex items-center justify-between p-3 rounded-xl border border-slate-200/80 bg-slate-50/50 hover:bg-blue-50/40 hover:border-blue-200 cursor-pointer transition-all"
            >
              <div className="flex items-center space-x-3 min-w-0 flex-1 mr-2">
                <div className="w-8 h-8 rounded-lg bg-slate-100 text-slate-500 flex items-center justify-center shrink-0">
                  <File className="w-4 h-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center space-x-2">
                    <span className="text-xs font-bold text-slate-800 truncate">
                      {maskFileName(extraDoc.original_file_name, isMaskingEnabled)}
                    </span>
                    <span className="text-[10px] font-bold text-slate-500 bg-slate-200/70 px-1.5 py-0.2 rounded">
                      {extraDoc.document_type}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    신뢰도 {Math.round(extraDoc.confidence * 100)}%
                  </p>
                </div>
              </div>

              <div className="flex items-center space-x-1 shrink-0">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectDocument(extraDoc);
                  }}
                  className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                  title="더보기"
                >
                  <Eye className="w-4 h-4" />
                </button>
                {onDeleteDocument && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteDocument(extraDoc.document_id, extraDoc.original_file_name);
                    }}
                    className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors cursor-pointer"
                    title="증빙서류 삭제"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
