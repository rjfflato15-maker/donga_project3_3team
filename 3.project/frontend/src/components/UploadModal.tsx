import React, { useState, useRef, useEffect } from 'react';
import { X, UploadCloud, File, Trash2, Tag } from 'lucide-react';
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
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (initialTargetType) {
      setTargetType(initialTargetType);
    } else {
      setTargetType('');
    }
  }, [initialTargetType, isOpen]);

  if (!isOpen) return null;

  const handleFiles = (fileList: FileList | null) => {
    if (!fileList) return;
    const newFiles = Array.from(fileList);
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
    await onUpload(selectedFiles, targetType || undefined);
    setSelectedFiles([]);
    setTargetType('');
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-xl overflow-hidden">
        {/* Header */}
        <div className="p-5 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div>
            <h3 className="text-base font-bold text-slate-900">증빙문서 업로드 및 검수</h3>
            <p className="text-xs text-slate-500 mt-0.5">계약 ID #{contractId} 건에 증빙서류를 첨부합니다</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-200/60 rounded-xl transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-4">
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
              <option value="">✨ AI 자동 분류 (추천)</option>
              <option value="contract">📄 계약서 (contract)</option>
              <option value="estimate">📊 견적서 (estimate)</option>
              <option value="business_registration">🏢 사업자등록증 (business_registration)</option>
              <option value="bank_account">💳 통장사본 (bank_account)</option>
              <option value="tax_invoice">🧾 세금계산서 (tax_invoice)</option>
              <option value="inspection_confirmation">✅ 검수확인서 (inspection_confirmation)</option>
            </select>
          </div>

          {/* Dropzone */}
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
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
              accept=".pdf,.png,.jpg,.jpeg,.webp,.bmp,.txt"
              className="hidden"
              onChange={(e) => handleFiles(e.target.files)}
            />
            <div className="w-12 h-12 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center mb-3 shadow-xs">
              <UploadCloud className="w-6 h-6" />
            </div>
            <p className="text-sm font-bold text-slate-800">
              클릭하여 파일을 선택하거나 여기로 드래그하세요
            </p>
            <p className="text-xs text-slate-400 mt-1">
              지원 형식: PDF, PNG, JPG, JPEG, WEBP, TXT (외주용역계약서, 견적서, 세금계산서, 사업자등록증, 통장사본, 검수확인서 등)
            </p>
          </div>

          {/* File list */}
          {selectedFiles.length > 0 && (
            <div className="space-y-2 max-h-48 overflow-y-auto">
              <div className="text-xs font-bold text-slate-600 px-1">
                선택된 파일 ({selectedFiles.length}개)
              </div>
              {selectedFiles.map((file, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-2.5 bg-slate-50 rounded-lg border border-slate-200 text-xs"
                >
                  <div className="flex items-center space-x-2 truncate">
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
                    className="p-1 text-slate-400 hover:text-rose-600 rounded transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 bg-slate-50 border-t border-slate-200 flex justify-end space-x-2">
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
