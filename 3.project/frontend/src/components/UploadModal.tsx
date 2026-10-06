import React, { useState, useRef, useEffect } from 'react';
import { useDialogA11y } from '../hooks/useDialogA11y';
import { X, UploadCloud, File, Trash2, Tag, Shield } from 'lucide-react';
import { DocumentType } from '../types';

interface UploadModalProps {
  contractId: number;
  isOpen: boolean;
  onClose: () => void;
  onUpload: (files: File[], targetDocumentType?: string) => Promise<void>;
  loading: boolean;
  initialTargetType?: DocumentType | string | null;
}

export const UploadModal: React.FC<UploadModalProps> = ({
  contractId,
  isOpen,
  onClose,
  onUpload,
  loading,
  initialTargetType,
}) => {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [targetType, setTargetType] = useState<string>('');
  const [error, setError] = useState('');
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // 열기·닫기(취소·Esc 포함)·대상 계약이 바뀔 때마다 선택·오류·종류·파일 입력을 새로 시작한다.
  // 같은 창에서 실패 후 다시 시도할 때는 이 effect가 돌지 않으므로 파일이 남는다.
  // session은 늦게 끝난 업로드가 이미 닫혔거나 다른 계약으로 바뀐 창을 건드리지 않게 한다.
  const session = useRef(0);
  useEffect(() => {
    session.current += 1;
    setSelectedFiles([]);
    setError('');
    setDragActive(false);
    setTargetType(initialTargetType || '');
    if (inputRef.current) inputRef.current.value = '';
  }, [isOpen, contractId, initialTargetType]);

  const dialogRef = useRef<HTMLDivElement>(null);
  useDialogA11y(dialogRef, onClose, isOpen);

  if (!isOpen) return null;

  const handleFiles = (fileList: FileList | null) => {
    if (!fileList) return;
    const newFiles = Array.from(fileList);
    if (selectedFiles.length + newFiles.length > 20 || newFiles.some(file => file.size > 20 * 1024 * 1024)) {
      setError('한 번에 최대 20개, 파일당 20MB까지 등록할 수 있습니다.');
      return;
    }
    setError('');
    setSelectedFiles((prev) => [...prev, ...newFiles]);
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files);
    }
  };

  const removeFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = async () => {
    if (selectedFiles.length === 0) return;
    const mine = session.current;
    try {
      setError('');
      await onUpload(selectedFiles, targetType || undefined);
      if (session.current !== mine) return;
      onClose();
    } catch (reason) {
      if (session.current !== mine) return;
      setError(reason instanceof Error ? reason.message : '업로드하지 못했습니다.');
    }
  };

  return (
    <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="upload-title" className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
      <div className="flex max-h-[calc(100vh-2rem)] w-full max-w-xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
        {/* Header */}
        <div className="p-5 border-b border-slate-200 flex shrink-0 items-center justify-between bg-slate-50">
          <div>
            <h3 id="upload-title" className="text-base font-bold text-slate-900">새 서류 추가</h3>
            <p className="text-xs text-slate-500 mt-0.5">계약 #{contractId}</p>
          </div>
          <button
            onClick={onClose}
            aria-label="닫기"
            className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-200/60 rounded-xl transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-6">
          <p className="rounded-xl bg-sky-50 p-3 text-xs text-sky-900">같은 서류의 수정본은 원문 대조창의 <b>‘고친 본 올리기’</b>에서 등록합니다. 이전 본은 자동 보관됩니다.</p>
          {error && (
            <div role="alert" className="rounded-xl bg-rose-50 p-3 text-xs font-semibold text-rose-800">
              {error}
              <div className="mt-1 font-normal">올리지 못한 파일은 아래 목록에 그대로 있어요. 다시 시도하거나, 문제 파일을 빼고 올리세요.
                {selectedFiles.length > 0 && <button onClick={() => { setSelectedFiles([]); setError(''); }} className="ml-2 font-semibold underline">선택 모두 빼기</button>}
              </div>
            </div>
          )}
          {/* Document Type Category Selector */}
          <div>
            <label className="text-xs font-bold text-slate-700 flex items-center space-x-1.5 mb-1.5">
              <Tag className="w-3.5 h-3.5 text-indigo-600" />
              <span>업로드 서류 종류 지정 (선택)</span>
            </label>
            <select
              value={targetType}
              onChange={(e) => setTargetType(e.target.value)}
              className="w-full bg-slate-50 border border-slate-300 rounded-xl px-3 py-2 text-xs font-bold text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="">종류 자동으로 나누기 (추천)</option>
              <option value="contract">계약서</option>
              <option value="estimate">견적서</option>
              <option value="business_registration">사업자등록증</option>
              <option value="bank_account">통장사본</option>
              <option value="tax_invoice">세금계산서</option>
              <option value="inspection_confirmation">검수확인서</option>
            </select>
          </div>

          {/* Dropzone */}
          <div
            role="button"
            tabIndex={0}
            aria-label="파일 선택"
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); inputRef.current?.click(); } }}
            className={`border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center cursor-pointer transition-all ${
              dragActive
                ? 'border-indigo-500 bg-indigo-50/50'
                : 'border-slate-300 hover:border-indigo-400 bg-slate-50/50'
            }`}
          >
            <input
              ref={inputRef}
              type="file"
              multiple
              accept=".pdf,.png,.jpg,.jpeg,.webp,.bmp,.tiff,.tif,.gif,.txt,.docx,.doc,.hwp,.hwpx,.xlsx,.xls,.csv"
              className="hidden"
              onChange={(e) => { handleFiles(e.target.files); e.target.value = ''; }}
              aria-label="올릴 파일 고르기"
            />
            <div className="w-12 h-12 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center mb-3 shadow-xs">
              <UploadCloud className="w-6 h-6" />
            </div>
            <p className="text-sm font-bold text-slate-800">
              클릭하여 파일을 선택하거나 여기로 드래그하세요
            </p>
            <p className="text-xs text-slate-500 mt-1 text-center">
              PDF, 이미지, 워드, 한글, 엑셀 문서를 자동으로 인식하고 텍스트 및 정보를 추출합니다
            </p>

            {/* Supported Format Badges */}
            <div className="mt-3.5 flex flex-wrap items-center justify-center gap-1.5 max-w-md">
              <span className="px-2 py-0.5 rounded-md text-[10px] font-extrabold bg-rose-50 text-rose-700 border border-rose-200">
                PDF
              </span>
              <span className="px-2 py-0.5 rounded-md text-[10px] font-extrabold bg-purple-50 text-purple-700 border border-purple-200">
                이미지 (PNG/JPG)
              </span>
              <span className="px-2 py-0.5 rounded-md text-[10px] font-extrabold bg-blue-50 text-blue-700 border border-blue-200">
                워드 (DOCX/DOC)
              </span>
              <span className="px-2 py-0.5 rounded-md text-[10px] font-extrabold bg-cyan-50 text-cyan-700 border border-cyan-200">
                한글 (HWP/HWPX)
              </span>
              <span className="px-2 py-0.5 rounded-md text-[10px] font-extrabold bg-emerald-50 text-emerald-700 border border-emerald-200">
                엑셀 (XLSX/XLS/CSV)
              </span>
              <span className="px-2 py-0.5 rounded-md text-[10px] font-extrabold bg-slate-100 text-slate-600 border border-slate-200">
                TXT
              </span>
            </div>
          </div>

          {/* File list */}
          {selectedFiles.length > 0 && (
            <div className="space-y-2 max-h-48 overflow-y-auto">
              <div className="text-xs font-bold text-slate-600 px-1">
                선택된 파일 ({selectedFiles.length}개)
              </div>
              {selectedFiles.map((file, idx) => {
                const ext = file.name.split('.').pop()?.toLowerCase();
                let badgeClass = 'bg-slate-100 text-slate-700 border-slate-200';
                let badgeLabel = ext?.toUpperCase() || 'FILE';
                if (ext === 'pdf') {
                  badgeClass = 'bg-rose-100 text-rose-700 border-rose-200';
                  badgeLabel = 'PDF';
                } else if (['png', 'jpg', 'jpeg', 'webp', 'bmp', 'gif'].includes(ext || '')) {
                  badgeClass = 'bg-purple-100 text-purple-700 border-purple-200';
                  badgeLabel = '이미지';
                } else if (['docx', 'doc'].includes(ext || '')) {
                  badgeClass = 'bg-blue-100 text-blue-700 border-blue-200';
                  badgeLabel = '워드';
                } else if (['hwp', 'hwpx'].includes(ext || '')) {
                  badgeClass = 'bg-cyan-100 text-cyan-800 border-cyan-200';
                  badgeLabel = '한글';
                } else if (['xlsx', 'xls', 'csv'].includes(ext || '')) {
                  badgeClass = 'bg-emerald-100 text-emerald-800 border-emerald-200';
                  badgeLabel = '엑셀';
                }

                return (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-2.5 bg-slate-50 rounded-lg border border-slate-200 text-xs"
                  >
                    <div className="flex items-center space-x-2 truncate">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-extrabold border shrink-0 ${badgeClass}`}>
                        {badgeLabel}
                      </span>
                      <File className="w-4 h-4 text-indigo-600 shrink-0" />
                      <span className="font-semibold text-slate-800 truncate">{file.name}</span>
                      <span className="text-slate-400 shrink-0">
                        ({(file.size / 1024).toFixed(1)} KB)
                      </span>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        removeFile(idx);
                      }}
                      aria-label={`${file.name} 빼기`}
                      className="p-1 text-slate-400 hover:text-rose-600 rounded transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                );
              })}
            </div>
          )}

          {/* Masking Option */}
          <div className="bg-slate-50 border border-slate-200/80 rounded-xl p-3 flex items-center justify-between text-xs">
            <div className="flex items-center space-x-2">
              <Shield className="w-4 h-4 text-indigo-600" />
              <div>
                <span className="font-bold text-slate-800">가린 문서 미리보기</span>
                <p className="text-[10px] text-slate-400">원본은 서버에 보관됩니다. 마스킹 결과는 원문과 함께 확인하세요.</p>
              </div>
            </div>
            <span className="px-3 py-1 rounded-lg text-xs font-black bg-emerald-100 text-emerald-800 border border-emerald-300">기본 ON</span>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 bg-slate-50 border-t border-slate-200 flex shrink-0 justify-end space-x-2">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-white border border-slate-300 text-slate-700 font-semibold text-xs rounded-xl hover:bg-slate-50 transition-colors"
          >
            취소
          </button>
          <button
            onClick={handleSubmit}
            disabled={selectedFiles.length === 0 || loading}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 text-white font-semibold text-xs rounded-xl shadow-sm transition-colors flex items-center space-x-1.5"
          >
            <span>{loading ? '처리 중...' : '업로드 및 자동 검수 실행'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
