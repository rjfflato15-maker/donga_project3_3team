import React, { useState, useEffect } from 'react';
import { DocumentResponse } from '../types';
import {
  X,
  FileText,
  CheckCircle2,
  Building,
  Calendar,
  DollarSign,
  CreditCard,
  Image as ImageIcon,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  Maximize2,
  Minimize2,
  Trash2,
} from 'lucide-react';

interface DocumentViewerModalProps {
  document: DocumentResponse | null;
  onClose: () => void;
  onDelete?: (documentId: number, fileName: string) => void;
}

export const DocumentViewerModal: React.FC<DocumentViewerModalProps> = ({
  document,
  onClose,
  onDelete,
}) => {
  const [activeTab, setActiveTab] = useState<'fields' | 'preview'>('fields');
  const [currentPage, setCurrentPage] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [pdfViewMode, setPdfViewMode] = useState<'image' | 'embedded'>('image');
  const [isZoomed, setIsZoomed] = useState<boolean>(false);
  const [imageLoaded, setImageLoaded] = useState<boolean>(false);

  const isImage = document ? /\.(png|jpe?g|webp|bmp|gif|tiff?)$/i.test(document.original_file_name) : false;
  const isPdf = document ? /\.pdf$/i.test(document.original_file_name) : false;
  const canPreview = isImage || isPdf;

  useEffect(() => {
    if (!document) return;
    setCurrentPage(0);
    setImageLoaded(false);
    setIsZoomed(false);

    if (isPdf) {
      fetch(`/api/documents/${document.document_id}/pages-info`)
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (data && data.total_pages) {
            setTotalPages(data.total_pages);
          } else {
            setTotalPages(1);
          }
        })
        .catch(() => setTotalPages(1));
    } else {
      setTotalPages(1);
    }
  }, [document?.document_id, isPdf]);

  if (!document) return null;

  const fields = document.analysis?.fields || {};
  const fileUrl = `/api/documents/${document.document_id}/file`;
  const previewImageUrl = `/api/documents/${document.document_id}/preview-image?page=${currentPage}&v=${document.document_id}`;

  const handleOpenInNewBrowserWindow = (e?: React.MouseEvent) => {
    if (e) e.preventDefault();
    window.open(fileUrl, '_blank', 'noopener,noreferrer');
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header - ONLY ONE "브라우저 새 창 열기" button here at the top */}
        <div className="p-5 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-blue-100 text-blue-700 flex items-center justify-center shrink-0">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2 flex-wrap gap-y-1">
                <h3 className="text-lg font-bold text-slate-900">{document.original_file_name}</h3>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-blue-100 text-blue-800">
                  {document.document_type}
                </span>
                {isImage && (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-100 text-purple-800">
                    이미지 OCR인식
                  </span>
                )}
                {isPdf && (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-100 text-indigo-800">
                    PDF 고해상도 렌더링
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                AI 분류 신뢰도: <strong className="text-slate-800">{Math.round(document.confidence * 100)}%</strong>
              </p>
            </div>
          </div>

          {/* Top Header Actions: Exactly ONE Browser New Window button */}
          <div className="flex items-center space-x-2">
            <button
              onClick={handleOpenInNewBrowserWindow}
              className="inline-flex items-center space-x-1.5 px-3.5 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl shadow-xs transition-colors cursor-pointer"
              title="브라우저 새 창(새 탭)에서 원본 파일 열기"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span>브라우저 새 창 열기</span>
            </button>
            <button
              onClick={onClose}
              className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-200/60 rounded-xl transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Tab switcher: Only 2 tabs (AI 구조화 추출 필드, 원본 PDF/이미지 미리보기) */}
        <div className="flex border-b border-slate-200 px-6 bg-white space-x-2">
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

          {canPreview && (
            <button
              onClick={() => setActiveTab('preview')}
              className={`py-3 px-4 text-xs font-bold border-b-2 transition-colors flex items-center space-x-2 ${
                activeTab === 'preview'
                  ? 'border-purple-600 text-purple-600'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
            >
              {isPdf ? <FileText className="w-4 h-4" /> : <ImageIcon className="w-4 h-4" />}
              <span>{isPdf ? '원본 PDF/이미지 미리보기' : '원본 이미지 미리보기'}</span>
              <span
                className={`text-[10px] px-1.5 py-0.2 rounded font-black ${
                  isPdf ? 'bg-indigo-100 text-indigo-700' : 'bg-purple-100 text-purple-700'
                }`}
              >
                {isPdf ? 'PDF' : 'IMG'}
              </span>
            </button>
          )}
        </div>

        {/* Modal Body: Only fields and preview */}
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

              {/* NTS Status with Hometax External Link */}
              {document.business_status && (
                <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 flex items-center justify-between">
                  <div>
                    <span className="text-xs font-bold text-emerald-800 uppercase tracking-wide">
                      국세청 홈택스 진위확인
                    </span>
                    <p className="text-sm font-semibold text-emerald-900 mt-0.5">
                      사업자 상태: <strong>{document.business_status}</strong>
                    </p>
                  </div>
                  <div className="flex items-center space-x-2">
                    <a
                      href="https://www.hometax.go.kr"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center space-x-1 px-3 py-1.5 bg-white hover:bg-emerald-100 text-emerald-800 text-xs font-bold rounded-lg border border-emerald-300 shadow-2xs transition-colors"
                      title="국세청 홈택스 공식 포털 새 창 열기"
                    >
                      <span>홈택스 새 창 열기</span>
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                    <span className="px-3 py-1.5 bg-emerald-600 text-white font-bold text-xs rounded-lg shadow-sm">
                      확인 완료
                    </span>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              {/* Preview Toolbar (no duplicate new window button) */}
              <div className="flex flex-wrap items-center justify-between gap-2 bg-white px-4 py-3 rounded-xl border border-slate-200 shadow-sm">
                <div className="flex items-center space-x-2 text-xs text-slate-700 font-semibold">
                  {isPdf ? (
                    <FileText className="w-4 h-4 text-indigo-600 shrink-0" />
                  ) : (
                    <ImageIcon className="w-4 h-4 text-purple-600 shrink-0" />
                  )}
                  <span>
                    {isPdf
                      ? '업로드된 원본 PDF 증빙문서 (pypdfium2 고해상도 이미지 렌더링)'
                      : '업로드된 원본 증빙 이미지 (Windows Native & RapidOCR 엔진 자동 인식 완료)'}
                  </span>
                </div>

                {/* For PDF: Toggle between Image View and Embedded PDF viewer */}
                {isPdf && (
                  <div className="flex items-center bg-slate-100 p-0.5 rounded-lg border border-slate-200 text-xs">
                    <button
                      onClick={() => setPdfViewMode('image')}
                      className={`px-2.5 py-1 rounded-md font-bold transition-all ${
                        pdfViewMode === 'image'
                          ? 'bg-white text-indigo-700 shadow-xs'
                          : 'text-slate-600 hover:text-slate-900'
                      }`}
                    >
                      🖼️ 이미지 뷰
                    </button>
                    <button
                      onClick={() => setPdfViewMode('embedded')}
                      className={`px-2.5 py-1 rounded-md font-bold transition-all ${
                        pdfViewMode === 'embedded'
                          ? 'bg-white text-indigo-700 shadow-xs'
                          : 'text-slate-600 hover:text-slate-900'
                      }`}
                    >
                      📄 내장 PDF 뷰어
                    </button>
                  </div>
                )}
              </div>

              {/* Main Content Area */}
              {isPdf && pdfViewMode === 'embedded' ? (
                <div className="bg-slate-900/5 rounded-xl border border-slate-200 p-2 min-h-[520px]">
                  <iframe
                    src={`${fileUrl}#view=FitH`}
                    title={document.original_file_name}
                    className="w-full h-[540px] rounded-lg border border-slate-200 bg-white"
                  />
                </div>
              ) : (
                <div className="bg-slate-900/5 rounded-xl border border-slate-200 p-4 flex flex-col items-center justify-center min-h-[380px] overflow-auto">
                  {/* Multi-page controls for PDF */}
                  {isPdf && totalPages > 1 && (
                    <div className="flex items-center justify-between w-full max-w-sm mb-3 bg-white px-3 py-1.5 rounded-lg border border-slate-200 shadow-xs text-xs">
                      <button
                        onClick={() => setCurrentPage((p) => Math.max(0, p - 1))}
                        disabled={currentPage === 0}
                        className="flex items-center space-x-1 px-2.5 py-1 rounded font-bold bg-slate-100 hover:bg-slate-200 disabled:opacity-40 disabled:cursor-not-allowed text-slate-700 transition-colors"
                      >
                        <ChevronLeft className="w-3.5 h-3.5" />
                        <span>이전 페이지</span>
                      </button>
                      <span className="font-extrabold text-slate-800">
                        {currentPage + 1} / {totalPages} 페이지
                      </span>
                      <button
                        onClick={() => setCurrentPage((p) => Math.min(totalPages - 1, p + 1))}
                        disabled={currentPage >= totalPages - 1}
                        className="flex items-center space-x-1 px-2.5 py-1 rounded font-bold bg-slate-100 hover:bg-slate-200 disabled:opacity-40 disabled:cursor-not-allowed text-slate-700 transition-colors"
                      >
                        <span>다음 페이지</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  )}

                  {/* Zoom controller */}
                  <div className="flex items-center space-x-2 self-end mb-2">
                    <button
                      onClick={() => setIsZoomed(!isZoomed)}
                      className="px-2.5 py-1 bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 rounded-lg text-xs font-semibold flex items-center space-x-1 shadow-2xs"
                    >
                      {isZoomed ? <Minimize2 className="w-3 h-3" /> : <Maximize2 className="w-3 h-3" />}
                      <span>{isZoomed ? '기본 크기' : '확대 보기'}</span>
                    </button>
                  </div>

                  {/* Rendered Image */}
                  <div className="relative flex justify-center w-full">
                    {!imageLoaded && (
                      <div className="absolute inset-0 flex items-center justify-center min-h-[300px]">
                        <div className="flex items-center space-x-2 text-xs text-slate-500 font-semibold bg-white/90 px-4 py-2 rounded-xl shadow-xs border border-slate-200">
                          <span className="w-2 h-2 rounded-full bg-blue-600 animate-ping"></span>
                          <span>고화질 원본 파일 렌더링 중...</span>
                        </div>
                      </div>
                    )}
                    <img
                      key={`${document.document_id}-${currentPage}`}
                      src={previewImageUrl}
                      alt={document.original_file_name}
                      onLoad={() => setImageLoaded(true)}
                      className={`w-auto object-contain rounded-lg shadow-md border border-slate-200 bg-white transition-all duration-200 ${
                        isZoomed ? 'max-h-[900px] max-w-full' : 'max-h-[500px] max-w-full'
                      } ${imageLoaded ? 'opacity-100' : 'opacity-0'}`}
                    />
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer: Clean with optional delete and close button */}
        <div className="p-4 bg-white border-t border-slate-200 flex items-center justify-between">
          {onDelete ? (
            <button
              onClick={() => {
                onDelete(document.document_id, document.original_file_name);
              }}
              className="inline-flex items-center space-x-1 px-3 py-1.5 text-rose-600 hover:text-rose-700 hover:bg-rose-50 rounded-xl text-xs font-bold transition-colors"
              title="증빙서류 삭제"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>증빙서류 삭제</span>
            </button>
          ) : (
            <div />
          )}

          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs rounded-xl transition-colors cursor-pointer"
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  );
};
