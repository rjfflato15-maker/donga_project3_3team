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
  ChevronLeft,
  ChevronRight,
  Maximize2,
  Minimize2,
  Trash2,
  FileSpreadsheet,
  FileCode,
  Download,
  Copy,
  Check,
  Shield,
} from 'lucide-react';
import {
  formatSensitiveField,
  maskVendorName,
  maskFileName,
  maskAllSensitiveInfo,
} from '../utils/masking';

interface DocumentViewerModalProps {
  document: DocumentResponse | null;
  onClose: () => void;
  onDelete?: (documentId: number, fileName: string) => void;
  isMaskingEnabled?: boolean;
}

export const DocumentViewerModal: React.FC<DocumentViewerModalProps> = ({
  document,
  onClose,
  onDelete,
  isMaskingEnabled = true,
}) => {
  const [activeTab, setActiveTab] = useState<'fields' | 'preview'>('fields');
  const [isMasked, setIsMasked] = useState<boolean>(isMaskingEnabled);
  const [currentPage, setCurrentPage] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [pdfViewMode, setPdfViewMode] = useState<'image' | 'embedded'>('image');
  const [isZoomed, setIsZoomed] = useState<boolean>(false);
  const [imageLoaded, setImageLoaded] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);

  const isImage = document ? /\.(png|jpe?g|webp|bmp|gif|tiff?)$/i.test(document.original_file_name) : false;
  const isPdf = document ? /\.pdf$/i.test(document.original_file_name) : false;
  const isWord = document ? /\.(docx?)$/i.test(document.original_file_name) : false;
  const isHwp = document ? /\.(hwp|hwpx)$/i.test(document.original_file_name) : false;
  const isExcel = document ? /\.(xlsx?|csv)$/i.test(document.original_file_name) : false;
  const isText = document ? /\.(txt|md|json)$/i.test(document.original_file_name) : false;
  const canPreview = true;

  useEffect(() => {
    setIsMasked(isMaskingEnabled);
  }, [isMaskingEnabled, document?.document_id]);

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
  const fileUrl = `/api/documents/${document.document_id}/file?masked=${isMasked}`;
  const previewImageUrl = `/api/documents/${document.document_id}/preview-image?page=${currentPage}&masked=${isMasked}&v=${document.document_id}_${isMasked}`;

  const getDisplayContent = () => {
    if (!document) return '';
    if (isMasked) {
      const baseText = document.masked_text || document.raw_text || '';
      return maskAllSensitiveInfo(baseText);
    }
    // When masking is OFF, show full raw unmasked original text
    return document.raw_text || document.masked_text || '';
  };

  const handleCopyText = (text: string) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const renderExcelPreview = () => {
    const rawContent = getDisplayContent();
    if (!rawContent) {
      return (
        <div className="bg-white rounded-xl p-8 border border-slate-200 text-center text-slate-400 font-medium">
          스프레드시트에서 추출된 데이터가 없습니다.
        </div>
      );
    }

    const lines = rawContent.split('\n').filter((l) => l.trim().length > 0);
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between bg-emerald-50 border border-emerald-200 p-3.5 rounded-xl">
          <div className="flex items-center space-x-2 text-xs font-bold text-emerald-900">
            <FileSpreadsheet className="w-4 h-4 text-emerald-600" />
            <span>
              엑셀 스프레드시트 구조화 파싱 뷰 ({lines.length}행 데이터)
            </span>
            <span
              className={`text-[10px] font-extrabold px-2 py-0.5 rounded-full ml-1 ${
                isMasked ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-900'
              }`}
            >
              {isMasked ? '개인정보 마스킹 ON' : '마스킹 OFF (원본)'}
            </span>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => handleCopyText(rawContent)}
              className="inline-flex items-center space-x-1 px-2.5 py-1 bg-white hover:bg-emerald-100 text-emerald-800 border border-emerald-300 rounded-lg text-xs font-bold transition-colors cursor-pointer"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? '복사 완료' : '전체 복사'}</span>
            </button>
            <a
              href={fileUrl}
              download={document.original_file_name}
              className="inline-flex items-center space-x-1 px-3 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold shadow-xs transition-colors cursor-pointer"
            >
              <Download className="w-3.5 h-3.5" />
              <span>원본 다운로드</span>
            </a>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto shadow-xs max-h-[500px]">
          <table className="w-full text-xs text-left border-collapse">
            <tbody>
              {lines.map((line, rIdx) => {
                const isSheetHeader = line.startsWith('[시트:');
                if (isSheetHeader) {
                  return (
                    <tr key={rIdx} className="bg-emerald-100/70 font-bold text-emerald-900 border-y border-emerald-200">
                      <td colSpan={20} className="px-4 py-2 text-xs font-extrabold">
                        📊 {line.replace(/\[|\]/g, '')}
                      </td>
                    </tr>
                  );
                }
                const cells = line.split('\t');
                const isHeaderRow = rIdx === 0 || (rIdx > 0 && lines[rIdx - 1]?.startsWith('[시트:'));
                return (
                  <tr
                    key={rIdx}
                    className={`border-b border-slate-100 transition-colors ${
                      isHeaderRow ? 'bg-slate-100/80 font-bold text-slate-800' : 'hover:bg-slate-50/80 text-slate-700'
                    }`}
                  >
                    <td className="px-3 py-1.5 text-[10px] text-slate-400 font-mono w-10 text-center select-none bg-slate-50 border-r border-slate-200">
                      {rIdx + 1}
                    </td>
                    {cells.map((cell, cIdx) => (
                      <td key={cIdx} className="px-3 py-1.5 border-r border-slate-100 whitespace-nowrap">
                        {isMasked ? maskAllSensitiveInfo(cell) : cell}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  const renderDocumentPaperPreview = () => {
    const rawContent = getDisplayContent();
    const paragraphs = rawContent.split('\n').filter((p) => p.trim());
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between bg-blue-50 border border-blue-200 p-3.5 rounded-xl">
          <div className="flex items-center space-x-2 text-xs font-bold text-blue-900">
            <FileText className="w-4 h-4 text-blue-600" />
            <span>
              {isWord
                ? '워드(Word .docx/.doc) 문서 파싱 뷰'
                : '한글(HWP/HWPX) 문서 파싱 뷰'}
            </span>
            <span
              className={`text-[10px] font-extrabold px-2 py-0.5 rounded-full ml-1 ${
                isMasked ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-900'
              }`}
            >
              {isMasked ? '개인정보 마스킹 ON' : '마스킹 OFF (원본)'}
            </span>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => handleCopyText(rawContent)}
              className="inline-flex items-center space-x-1 px-2.5 py-1 bg-white hover:bg-blue-100 text-blue-800 border border-blue-300 rounded-lg text-xs font-bold transition-colors cursor-pointer"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-blue-600" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? '복사 완료' : '본문 복사'}</span>
            </button>
            <a
              href={fileUrl}
              download={document.original_file_name}
              className="inline-flex items-center space-x-1 px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold shadow-xs transition-colors cursor-pointer"
            >
              <Download className="w-3.5 h-3.5" />
              <span>원본 다운로드</span>
            </a>
          </div>
        </div>

        {/* Paper style card */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-md p-8 max-w-3xl mx-auto space-y-4 min-h-[450px] max-h-[550px] overflow-y-auto">
          <div className="border-b border-slate-200 pb-3 mb-3 flex items-center justify-between">
            <div>
              <span
                className={`text-[10px] font-extrabold px-2 py-0.5 rounded-full ${
                  isWord
                    ? 'bg-blue-100 text-blue-800'
                    : 'bg-cyan-100 text-cyan-800'
                }`}
              >
                {isWord
                  ? 'MS Word Document'
                  : 'Hangul Office Document'}
              </span>
              <h2 className="text-base font-extrabold text-slate-900 mt-1">
                {maskFileName(document.original_file_name, isMasked)}
              </h2>
            </div>
            <span className="text-xs text-slate-400 font-semibold">{paragraphs.length}개 단락</span>
          </div>

          <div className="space-y-2.5 text-xs text-slate-800 leading-relaxed font-normal">
            {paragraphs.length > 0 ? (
              paragraphs.map((p, idx) => (
                <p key={idx} className="whitespace-pre-wrap">
                  {p}
                </p>
              ))
            ) : (
              <p className="text-slate-400 italic">추출된 본문 텍스트가 없습니다.</p>
            )}
          </div>
        </div>
      </div>
    );
  };

  const renderTextPreview = () => {
    const rawContent = getDisplayContent();
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between bg-slate-100 border border-slate-200 p-3.5 rounded-xl">
          <div className="flex items-center space-x-2 text-xs font-bold text-slate-800">
            <FileCode className="w-4 h-4 text-slate-600" />
            <span>텍스트 문서 뷰</span>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => handleCopyText(rawContent)}
              className="inline-flex items-center space-x-1 px-2.5 py-1 bg-white hover:bg-slate-200 text-slate-700 border border-slate-300 rounded-lg text-xs font-bold transition-colors cursor-pointer"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-slate-600" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? '복사 완료' : '전체 복사'}</span>
            </button>
            <a
              href={fileUrl}
              download={document.original_file_name}
              className="inline-flex items-center space-x-1 px-3 py-1 bg-slate-700 hover:bg-slate-800 text-white rounded-lg text-xs font-bold shadow-xs transition-colors cursor-pointer"
            >
              <Download className="w-3.5 h-3.5" />
              <span>원본 다운로드</span>
            </a>
          </div>
        </div>

        <pre className="bg-slate-900 text-slate-100 p-5 rounded-xl text-xs font-mono overflow-auto max-h-[500px] leading-relaxed whitespace-pre-wrap">
          {rawContent || '내용 없음'}
        </pre>
      </div>
    );
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
                <h3 className="text-lg font-bold text-slate-900">
                  {maskFileName(document.original_file_name, isMasked)}
                </h3>
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
                {isWord && (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-100 text-blue-800">
                    Word 문서인식
                  </span>
                )}
                {isHwp && (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-cyan-100 text-cyan-800">
                    한글(HWP) 문서인식
                  </span>
                )}
                {isExcel && (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800">
                    엑셀 스프레드시트
                  </span>
                )}
                {isText && (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-800">
                    텍스트 문서
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                AI 분류 신뢰도: <strong className="text-slate-800">{Math.round(document.confidence * 100)}%</strong>
              </p>
            </div>
          </div>

          {/* Top Header Actions: Dual Masking Toggles + Browser New Window button + Close */}
          <div className="flex items-center space-x-2 flex-wrap gap-y-1">
            <button
              onClick={() => {
                setImageLoaded(false);
                setIsMasked(!isMasked);
              }}
              className={`inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-xl text-xs font-black border transition-all cursor-pointer shadow-2xs ${
                isMasked
                  ? 'bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border-emerald-300'
                  : 'bg-amber-50 hover:bg-amber-100 text-amber-900 border-amber-300'
              }`}
              title="클릭 시 주민등록번호, 계좌번호, 전화번호, 상호명 마스킹 처리 ON/OFF 전환"
            >
              <Shield className={`w-3.5 h-3.5 ${isMasked ? 'text-emerald-600' : 'text-amber-600'}`} />
              <span>개인정보·사업자 마스킹: {isMasked ? 'ON' : 'OFF'}</span>
            </button>


            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-200/60 rounded-xl transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Tab switcher: AI 구조화 추출 필드 + 원본 파일 미리보기 */}
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
              {isPdf ? (
                <FileText className="w-4 h-4" />
              ) : isImage ? (
                <ImageIcon className="w-4 h-4" />
              ) : isExcel ? (
                <FileSpreadsheet className="w-4 h-4" />
              ) : (
                <FileText className="w-4 h-4" />
              )}
              <span>
                {isPdf
                  ? '원본 PDF 미리보기'
                  : isImage
                  ? '원본 이미지 미리보기'
                  : isWord
                  ? '워드(Word) 미리보기'
                  : isHwp
                  ? '한글(HWP) 미리보기'
                  : isExcel
                  ? '엑셀 데이터 미리보기'
                  : '문서 텍스트 미리보기'}
              </span>
              <span
                className={`text-[10px] px-1.5 py-0.2 rounded font-black ${
                  isPdf
                    ? 'bg-indigo-100 text-indigo-700'
                    : isImage
                    ? 'bg-purple-100 text-purple-700'
                    : isWord
                    ? 'bg-blue-100 text-blue-700'
                    : isHwp
                    ? 'bg-cyan-100 text-cyan-800'
                    : isExcel
                    ? 'bg-emerald-100 text-emerald-800'
                    : 'bg-slate-100 text-slate-700'
                }`}
              >
                {isPdf
                  ? 'PDF'
                  : isImage
                  ? 'IMG'
                  : isWord
                  ? 'DOCX'
                  : isHwp
                  ? 'HWP'
                  : isExcel
                  ? 'XLSX'
                  : 'TXT'}
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
                    {/*{isMasked && (
                      <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">
                        {비식별화 적용}
                      </span>
                    )}*/}
                  </div>
                  <div className="text-base font-bold text-slate-900">
                    {fields.company_name ? (
                      isMasked ? maskVendorName(fields.company_name, true) : fields.company_name
                    ) : (
                      <span className="text-slate-400">미추출</span>
                    )}
                  </div>
                </div>

                {/* Business Reg No */}
                <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
                  <div className="flex items-center space-x-2 text-xs font-semibold text-slate-500 mb-1">
                    <CreditCard className="w-3.5 h-3.5 text-indigo-600" />
                    <span>사업자등록번호</span>
                    {/*
                    <span
                      className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${
                        isMasked ? 'bg-indigo-50 text-indigo-700 border border-indigo-200' : 'bg-amber-50 text-amber-800 border border-amber-200'
                      }`}
                    >
                      {isMasked ? '마스킹 적용 (123-**-*****)' : '원본 노출'}
                    </span>*/}
                  </div>
                  <div className="text-base font-bold text-slate-900 font-mono">
                    {fields.business_registration_no ? (
                      formatSensitiveField(fields.business_registration_no, 'business_number', isMasked)
                    ) : (
                      <span className="text-slate-400 font-sans">미추출</span>
                    )}
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
                    <span className="text-xs font-bold text-emerald-800 uppercase tracking-wide">
                      국세청 홈택스 진위확인
                    </span>
                    <p className="text-sm font-semibold text-emerald-900 mt-0.5">
                      사업자 상태: <strong>{document.business_status}</strong>
                    </p>
                  </div>
                  <span className="px-3 py-1.5 bg-emerald-600 text-white font-bold text-xs rounded-lg shadow-sm">
                    확인 완료
                  </span>
                </div>
              )}

              {/* Privacy Masking Info Card */}
              <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm space-y-3">
                {/* 1. 개인정보 비식별화 마스킹 */}
                <div className="flex flex-wrap items-center justify-between gap-2 pb-2.5 border-b border-slate-100">
                  <div className="flex items-center space-x-2">
                    <Shield className={`w-4 h-4 ${isMasked ? 'text-emerald-600' : 'text-amber-600'}`} />
                    <span className="text-xs font-bold text-slate-800">개인정보(PII) 비식별화 마스킹</span>
                    <span
                      className={`text-[10px] font-black px-2 py-0.5 rounded-full ${
                        isMasked
                          ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                          : 'bg-amber-100 text-amber-900 border border-amber-200'
                      }`}
                    >
                      {isMasked ? 'ON (비식별화 적용)' : 'OFF (원본 노출)'}
                    </span>
                  </div>

                  <button
                    onClick={() => setIsMasked(!isMasked)}
                    className={`text-xs font-bold px-3 py-1 rounded-lg border transition-colors ${
                      isMasked
                        ? 'border-slate-300 hover:bg-slate-100 text-slate-700'
                        : 'border-emerald-300 bg-emerald-50 hover:bg-emerald-100 text-emerald-800'
                    }`}
                  >
                    {isMasked ? '개인정보 마스킹 해제 (원본 보기)' : '개인정보 비식별화 켜기 (ON)'}
                  </button>
                </div>



                <p className="text-xs text-slate-500">
                  {isMasked
                    ? '주민번호(뒷자리 제외 *), 계좌번호(가운데 *), 사업자번호(123-**-*****), 주소지(지역 제외 *), 상호명 비식별화가 적용되었습니다.'
                    : '개인정보 마스킹이 해제되어 주민등록번호, 계좌번호, 사업자등록번호, 상세 주소, 상호명이 원본 그대로 전체 노출됩니다.'}
                </p>

                {(document.masked_text || document.raw_text) && (
                  <div className="mt-2 bg-slate-900 text-slate-100 p-3 rounded-lg text-[11px] font-mono max-h-36 overflow-y-auto whitespace-pre-wrap leading-relaxed">
                    {getDisplayContent() || '추출 텍스트 없음'}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {isPdf || isImage ? (
                <>
                  {/* Masking Status Notice Banner */}
                  <div
                    className={`px-4 py-2.5 rounded-xl text-xs flex items-center justify-between border transition-all ${
                      isMasked
                        ? 'bg-emerald-50/90 text-emerald-900 border-emerald-200'
                        : 'bg-amber-50/90 text-amber-900 border-amber-200'
                    }`}
                  >
                    <div className="flex items-center space-x-2">
                      <Shield className={`w-4 h-4 shrink-0 ${isMasked ? 'text-emerald-600' : 'text-amber-600'}`} />
                      <span>
                        {isMasked ? (
                          <>
                            <strong className="font-extrabold text-emerald-950">개인정보·사업자 비식별화 마스킹 보호 중:</strong>{' '}
                            사업자등록번호, 법인등록번호, 대표자명, 연락처, 입금계좌, 상세주소가 안전하게 마스킹 처리되어 표시됩니다.
                          </>
                        ) : (
                          <>
                            <strong className="font-extrabold text-amber-950">원본 노출 모드 (마스킹 해제):</strong>{' '}
                            모든 사업자 및 개인정보가 원본 그대로 표시됩니다.
                          </>
                        )}
                      </span>
                    </div>
                    <button
                      onClick={() => {
                        setImageLoaded(false);
                        setIsMasked(!isMasked);
                      }}
                      className={`font-extrabold underline cursor-pointer text-xs ml-3 shrink-0 ${
                        isMasked ? 'text-emerald-800 hover:text-emerald-950' : 'text-amber-800 hover:text-amber-950'
                      }`}
                    >
                      {isMasked ? '원본(마스킹 해제) 보기' : '개인정보 마스킹 켜기'}
                    </button>
                  </div>

                  {/* Preview Toolbar */}
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

                    <div className="flex items-center space-x-2 flex-wrap gap-y-1">
                      {/* Masking Toggle inside Preview Toolbar */}
                      <button
                        onClick={() => {
                          setImageLoaded(false);
                          setIsMasked(!isMasked);
                        }}
                        className={`inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-black border transition-all cursor-pointer shadow-xs ${
                          isMasked
                            ? 'bg-emerald-600 hover:bg-emerald-700 text-white border-emerald-600'
                            : 'bg-amber-50 hover:bg-amber-100 text-amber-900 border-amber-300'
                        }`}
                        title="사업자등록번호, 법인등록번호, 계좌번호, 연락처, 대표자명, 상세주소 마스킹 토글"
                      >
                        <Shield className={`w-3.5 h-3.5 ${isMasked ? 'text-white' : 'text-amber-600'}`} />
                        <span>마스킹: {isMasked ? 'ON (보호 중)' : 'OFF (원본 노출)'}</span>
                      </button>

                      {/* For PDF: Toggle between Image View and Embedded PDF viewer */}
                      {isPdf && (
                        <div className="flex items-center bg-slate-100 p-0.5 rounded-lg border border-slate-200 text-xs">
                          <button
                            onClick={() => setPdfViewMode('image')}
                            className={`px-2.5 py-1 rounded-md font-bold transition-all cursor-pointer ${
                              pdfViewMode === 'image'
                                ? 'bg-white text-indigo-700 shadow-xs'
                                : 'text-slate-600 hover:text-slate-900'
                            }`}
                          >
                            🖼️ 이미지 뷰
                          </button>
                          <button
                            onClick={() => setPdfViewMode('embedded')}
                            className={`px-2.5 py-1 rounded-md font-bold transition-all cursor-pointer ${
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
                            onClick={() => {
                              setImageLoaded(false);
                              setCurrentPage((p) => Math.max(0, p - 1));
                            }}
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
                            onClick={() => {
                              setImageLoaded(false);
                              setCurrentPage((p) => Math.min(totalPages - 1, p + 1));
                            }}
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
                          className="px-2.5 py-1 bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 rounded-lg text-xs font-semibold flex items-center space-x-1 shadow-2xs cursor-pointer"
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
                              <span>
                                {isMasked ? '비식별화 마스킹 처리 렌더링 중...' : '고화질 원본 파일 렌더링 중...'}
                              </span>
                            </div>
                          </div>
                        )}
                        <img
                          key={`${document.document_id}-${currentPage}-${isMasked}`}
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
                </>
              ) : isExcel ? (
                renderExcelPreview()
              ) : isWord || isHwp ? (
                renderDocumentPaperPreview()
              ) : (
                renderTextPreview()
              )}
            </div>
          )}
        </div>

        {/* Footer: Clean with optional delete and close button */}
        <div className="p-4 bg-white border-t border-slate-200 flex items-center justify-between">
          {onDelete ? (
            <button
              type="button"
              onClick={() => {
                onDelete(document.document_id, document.original_file_name);
              }}
              className="inline-flex items-center space-x-1.5 px-3.5 py-2 text-rose-600 hover:text-rose-700 hover:bg-rose-50 active:bg-rose-100 rounded-xl text-xs font-bold transition-all cursor-pointer border border-rose-200/80 shadow-2xs hover:shadow-xs active:scale-95"
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
