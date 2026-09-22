import React, { useState } from 'react';
import { DocumentResponse } from '../types';
import { X, FileText, CheckCircle2, Lock, Building, Calendar, DollarSign, CreditCard } from 'lucide-react';

interface DocumentViewerModalProps {
  document: DocumentResponse | null;
  onClose: () => void;
}

export const DocumentViewerModal: React.FC<DocumentViewerModalProps> = ({ document, onClose }) => {
  const [activeTab, setActiveTab] = useState<'fields' | 'masking'>('fields');

  if (!document) return null;

  const fields = document.analysis.fields;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="p-5 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-blue-100 text-blue-700 flex items-center justify-center">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-lg font-bold text-slate-900">{document.original_file_name}</h3>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-blue-100 text-blue-800">
                  {document.document_type}
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                AI 분류 신뢰도: <strong className="text-slate-800">{Math.round(document.confidence * 100)}%</strong> • 마스킹 상태:{' '}
                <strong className={document.mask_status === 'MASKED' ? 'text-emerald-700' : 'text-slate-700'}>
                  {document.mask_status}
                </strong>
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

        {/* Tab switcher */}
        <div className="flex border-b border-slate-200 px-6 bg-white">
          <button
            onClick={() => setActiveTab('fields')}
            className={`py-3 px-4 text-xs font-bold border-b-2 transition-colors flex items-center space-x-2 ${
              activeTab === 'fields'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            <CheckCircle2 className="w-4 h-4" />
            <span>AI 구조화 추출 필드</span>
          </button>

          <button
            onClick={() => setActiveTab('masking')}
            className={`py-3 px-4 text-xs font-bold border-b-2 transition-colors flex items-center space-x-2 ${
              activeTab === 'masking'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            <Lock className="w-4 h-4" />
            <span>개인정보 마스킹 전/후 대조 (강사 피드백 구현)</span>
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto flex-1 bg-slate-50/50">
          {activeTab === 'fields' ? (
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Company Name */}
                <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
                  <div className="flex items-center space-x-2 text-xs font-semibold text-slate-500 mb-1">
                    <Building className="w-3.5 h-3.5 text-blue-600" />
                    <span>추출 상호 / 업체명</span>
                  </div>
                  <div className="text-base font-bold text-slate-900">
                    {fields.company_name || <span className="text-slate-400">미추출</span>}
                  </div>
                </div>

                {/* Business Reg No */}
                <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
                  <div className="flex items-center space-x-2 text-xs font-semibold text-slate-500 mb-1">
                    <CreditCard className="w-3.5 h-3.5 text-indigo-600" />
                    <span>사업자등록번호</span>
                  </div>
                  <div className="text-base font-bold text-slate-900">
                    {fields.business_registration_no || <span className="text-slate-400">미추출</span>}
                  </div>
                </div>

                {/* Amount */}
                <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
                  <div className="flex items-center space-x-2 text-xs font-semibold text-slate-500 mb-1">
                    <DollarSign className="w-3.5 h-3.5 text-emerald-600" />
                    <span>추출 금액 (VAT 포함 여부 확인)</span>
                  </div>
                  <div className="text-base font-bold text-slate-900">
                    {fields.amount !== null && fields.amount !== undefined ? (
                      <span className="text-blue-700">{fields.amount.toLocaleString()} 원</span>
                    ) : (
                      <span className="text-slate-400">금액 정보 없음</span>
                    )}
                  </div>
                </div>

                {/* Date */}
                <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
                  <div className="flex items-center space-x-2 text-xs font-semibold text-slate-500 mb-1">
                    <Calendar className="w-3.5 h-3.5 text-amber-600" />
                    <span>작성일 / 발급일자</span>
                  </div>
                  <div className="text-base font-bold text-slate-900">
                    {fields.issue_date || <span className="text-slate-400">일자 미기재</span>}
                  </div>
                </div>
              </div>

              {/* NTS Status */}
              {document.business_status && (
                <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 flex items-center justify-between">
                  <div>
                    <span className="text-xs font-bold text-emerald-800 uppercase tracking-wide">국세청 홈택스 진위확인</span>
                    <p className="text-sm font-semibold text-emerald-900 mt-0.5">
                      사업자 상태: <strong>{document.business_status}</strong>
                    </p>
                  </div>
                  <span className="px-3 py-1 bg-emerald-600 text-white font-bold text-xs rounded-lg shadow-sm">
                    확인 완료
                  </span>
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              <div className="bg-blue-50 border border-blue-200 rounded-xl p-3.5 text-xs text-blue-900">
                <strong>개인정보 보호 원칙 적용:</strong> 원본 문서는 외부 생성형 AI에 전달되지 않으며, 로컬 사전 전처리를 통해
                주민등록번호(<code className="bg-blue-100 px-1 py-0.5 rounded text-blue-800">[RRN_001]</code>), 연락처(<code className="bg-blue-100 px-1 py-0.5 rounded text-blue-800">[PHONE_001]</code>), 계좌번호(<code className="bg-blue-100 px-1 py-0.5 rounded text-blue-800">[ACCOUNT_001]</code>)가 안전하게 비식별화됩니다.
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Left: Original raw text */}
                <div className="flex flex-col bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
                  <div className="bg-slate-100 px-3.5 py-2 text-xs font-bold text-slate-700 border-b border-slate-200 flex items-center justify-between">
                    <span>원본 문서 텍스트 (로컬 전용)</span>
                    <span className="text-[10px] bg-slate-200 px-1.5 py-0.5 rounded">Raw</span>
                  </div>
                  <pre className="p-4 text-xs font-mono text-slate-800 whitespace-pre-wrap leading-relaxed max-h-[350px] overflow-y-auto">
                    {document.raw_text || '내용 없음'}
                  </pre>
                </div>

                {/* Right: Masked text */}
                <div className="flex flex-col bg-white rounded-xl border border-emerald-200 overflow-hidden shadow-sm">
                  <div className="bg-emerald-50 px-3.5 py-2 text-xs font-bold text-emerald-800 border-b border-emerald-200 flex items-center justify-between">
                    <span>마스킹 완료 텍스트 (외부 AI 전달 가능본)</span>
                    <span className="text-[10px] bg-emerald-200 text-emerald-800 px-1.5 py-0.5 rounded font-bold">Masked</span>
                  </div>
                  <pre className="p-4 text-xs font-mono text-slate-800 whitespace-pre-wrap leading-relaxed max-h-[350px] overflow-y-auto">
                    {document.masked_text || '마스킹된 내용 없음'}
                  </pre>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 bg-white border-t border-slate-200 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs rounded-xl transition-colors"
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  );
};
