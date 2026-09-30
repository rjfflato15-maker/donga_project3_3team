import React from 'react';
import { AlertTriangle, Trash2, X, Loader2 } from 'lucide-react';

interface ConfirmModalProps {
  isOpen: boolean;
  title: string;
  itemName?: string;
  itemBadge?: string;
  message: string;
  subMessage?: string;
  confirmText?: string;
  cancelText?: string;
  isDanger?: boolean;
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export const ConfirmModal: React.FC<ConfirmModalProps> = ({
  isOpen,
  title,
  itemName,
  itemBadge,
  message,
  subMessage,
  confirmText = '삭제 실행',
  cancelText = '취소',
  isDanger = true,
  loading = false,
  onConfirm,
  onCancel,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-in fade-in duration-200">
      <div
        className="bg-white rounded-2xl shadow-2xl max-w-md w-full border border-slate-200 overflow-hidden transform transition-all scale-100 animate-in zoom-in-95 duration-200"
        role="dialog"
        aria-modal="true"
      >
        {/* Header */}
        <div className="px-6 pt-6 pb-4 flex items-start justify-between">
          <div className="flex items-center space-x-3">
            <div
              className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
                isDanger ? 'bg-rose-100 text-rose-600' : 'bg-amber-100 text-amber-600'
              }`}
            >
              {isDanger ? <Trash2 className="w-5 h-5" /> : <AlertTriangle className="w-5 h-5" />}
            </div>
            <div>
              <h3 className="text-base font-extrabold text-slate-900">{title}</h3>
              <p className="text-xs text-slate-500 font-medium">안내 사항을 확인해 주세요</p>
            </div>
          </div>
          <button
            onClick={onCancel}
            disabled={loading}
            className="p-1 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors disabled:opacity-50"
            aria-label="닫기"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-2 space-y-3">
          {itemName && (
            <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between">
              <span className="text-xs font-bold text-slate-800 truncate flex-1 mr-2">
                {itemName}
              </span>
              {itemBadge && (
                <span className="text-[10px] font-black px-2 py-0.5 rounded-md bg-rose-100 text-rose-700 shrink-0">
                  {itemBadge}
                </span>
              )}
            </div>
          )}

          <p className="text-xs font-semibold text-slate-700 leading-relaxed whitespace-pre-line">
            {message}
          </p>

          {subMessage && (
            <p className="text-[11px] text-slate-500 font-medium bg-amber-50/70 border border-amber-200/60 p-2.5 rounded-lg text-amber-800 leading-relaxed">
              💡 {subMessage}
            </p>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-slate-50/80 border-t border-slate-100 flex items-center justify-end space-x-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={loading}
            className="px-4 py-2 bg-white hover:bg-slate-100 text-slate-700 font-bold text-xs rounded-xl border border-slate-200 transition-colors disabled:opacity-50 cursor-pointer"
          >
            {cancelText}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={loading}
            className={`px-4 py-2 text-white font-bold text-xs rounded-xl shadow-xs flex items-center space-x-1.5 transition-all cursor-pointer ${
              isDanger
                ? 'bg-rose-600 hover:bg-rose-700 active:scale-95 disabled:bg-rose-300'
                : 'bg-indigo-600 hover:bg-indigo-700 active:scale-95 disabled:bg-indigo-300'
            }`}
          >
            {loading ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>처리 중...</span>
              </>
            ) : (
              <>
                {isDanger && <Trash2 className="w-3.5 h-3.5" />}
                <span>{confirmText}</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
