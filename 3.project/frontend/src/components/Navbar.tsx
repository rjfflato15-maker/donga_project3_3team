import React from 'react';
import { ShieldCheck, Plus, RefreshCw, FileText } from 'lucide-react';

interface NavbarProps {
  onOpenNewContract: () => void;
  onSeedDemo: () => void;
  onOpenUpload: () => void;
  onOpenSimulator: () => void;
  loading: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  onOpenNewContract,
  onSeedDemo,
  onOpenUpload,
  onOpenSimulator,
  loading,
}) => {
  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Left: Brand */}
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center text-white shadow-md shadow-blue-500/20">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-bold text-lg text-slate-900 tracking-tight">AI Contract Evidence Manager</span>
              <span className="text-xs bg-blue-100 text-blue-800 font-semibold px-2 py-0.5 rounded-full">v1.0 MVP</span>
            </div>
            <p className="text-xs text-slate-500 hidden sm:block">외주·용역 계약 증빙서류 누락·불일치 자동 검수 시스템</p>
          </div>
        </div>

        {/* Right: Actions */}
        <div className="flex items-center space-x-2 sm:space-x-3">
          <button
            onClick={onSeedDemo}
            disabled={loading}
            className="flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
            title="기획서 데모 시나리오 (ABC 홈페이지 구축 외주 계약) 불러오기"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>데모 초기화</span>
          </button>

          <button
            onClick={onOpenSimulator}
            className="flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 rounded-lg transition-colors"
          >
            <span>5단계 시뮬레이터</span>
          </button>

          <button
            onClick={onOpenUpload}
            className="flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium text-blue-600 bg-blue-50 hover:bg-blue-100 border border-blue-200 rounded-lg transition-colors"
          >
            <FileText className="w-3.5 h-3.5" />
            <span>증빙 업로드</span>
          </button>

          <button
            onClick={onOpenNewContract}
            className="flex items-center space-x-1.5 px-3.5 py-1.5 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 shadow-sm rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4" />
            <span>새 계약 등록</span>
          </button>
        </div>
      </div>
    </header>
  );
};
