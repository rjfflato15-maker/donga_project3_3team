import React from 'react';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';

export interface ToastItem {
  id: string;
  type: 'success' | 'error' | 'info';
  message: string;
}

interface ToastProps {
  toasts: ToastItem[];
  onDismiss: (id: string) => void;
}

export const ToastContainer: React.FC<ToastProps> = ({ toasts, onDismiss }) => {
  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-6 right-6 z-[100] flex flex-col space-y-2 pointer-events-none max-w-sm w-full">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`pointer-events-auto p-3.5 rounded-2xl shadow-xl border flex items-start space-x-3 transition-all animate-in slide-in-from-bottom-5 duration-300 ${
            toast.type === 'success'
              ? 'bg-emerald-900/95 text-white border-emerald-700/80'
              : toast.type === 'error'
              ? 'bg-rose-900/95 text-white border-rose-700/80'
              : 'bg-slate-900/95 text-white border-slate-700/80'
          }`}
        >
          <div className="shrink-0 mt-0.5">
            {toast.type === 'success' && <CheckCircle2 className="w-4 h-4 text-emerald-300" />}
            {toast.type === 'error' && <AlertCircle className="w-4 h-4 text-rose-300" />}
            {toast.type === 'info' && <Info className="w-4 h-4 text-blue-300" />}
          </div>

          <p className="text-xs font-bold flex-1 leading-relaxed">{toast.message}</p>

          <button
            onClick={() => onDismiss(toast.id)}
            className="text-white/60 hover:text-white p-0.5 rounded-lg transition-colors shrink-0"
            aria-label="알림 닫기"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      ))}
    </div>
  );
};
