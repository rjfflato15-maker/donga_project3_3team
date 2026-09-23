import React from 'react';
import { RefreshCw, FileText, Plus, Sparkles } from 'lucide-react';
import { NavigationTab } from './Sidebar';

interface TopHeaderProps {
  activeTab: NavigationTab;
  onOpenNewContract: () => void;
  onOpenAutoBatchContract?: () => void;
  onSeedDemo: () => void;
  onOpenUpload: () => void;
  onOpenSimulator: () => void;
  loading: boolean;
}

export const TopHeader: React.FC<TopHeaderProps> = ({
  activeTab,
  onOpenNewContract,
  onOpenAutoBatchContract,
  onSeedDemo,
  onOpenUpload,
  onOpenSimulator,
  loading,
}) => {
  const getTabTitle = () => {
    switch (activeTab) {
      case 'dashboard':
        return '종합 검수 대시보드';
      case 'contracts':
        return '외주/용역 계약 관리';
      case 'documents':
        return '증빙서류 관리';
      case 'reports':
        return 'AI 교차검수 리포트';
      default:
        return '종합 검수 대시보드';
    }
  };

  return (
    <header className="bg-white/85 backdrop-blur-md border-b border-slate-200/80 sticky top-0 z-10 shadow-2xs transition-all">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        {/* Page Header Title */}
        <div className="flex items-center space-x-3">
          <h1 className="text-base font-black text-slate-900 tracking-tight">
            {getTabTitle()}
          </h1>
        </div>

        {/* Right Section: System Status & Action Buttons */}
        <div className="flex items-center space-x-3 sm:space-x-4">
          {/* Status Indicator */}
          <div className="hidden lg:flex items-center space-x-2 text-xs font-semibold bg-slate-50 border border-slate-200/80 px-3 py-1 rounded-full shadow-2xs">
            <span className="text-slate-400">시스템 상태:</span>
            <span className="inline-flex items-center space-x-1.5 text-emerald-700 font-extrabold">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              <span>AI Rule Engine 정상 가동 중</span>
            </span>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={onSeedDemo}
              disabled={loading}
              className="flex items-center space-x-1.5 px-3 py-1.5 text-xs font-bold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-xl transition-all duration-200 hover:-translate-y-0.5 active:translate-y-0"
              title="기획서 데모 시나리오 불러오기"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-indigo-600' : 'text-slate-500'}`} />
              <span className="hidden sm:inline">데모 초기화</span>
            </button>

            <button
              onClick={onOpenSimulator}
              className="flex items-center space-x-1.5 px-3 py-1.5 text-xs font-bold text-indigo-700 bg-indigo-50/80 hover:bg-indigo-100 border border-indigo-200/80 rounded-xl transition-all duration-200 hover:-translate-y-0.5 shadow-2xs"
            >
              <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
              <span>5단계 시뮬레이터</span>
            </button>

            <button
              onClick={onOpenUpload}
              className="flex items-center space-x-1.5 px-3 py-1.5 text-xs font-bold text-blue-700 bg-blue-50/80 hover:bg-blue-100 border border-blue-200/80 rounded-xl transition-all duration-200 hover:-translate-y-0.5 shadow-2xs"
            >
              <FileText className="w-3.5 h-3.5 text-blue-600" />
              <span>증빙 업로드</span>
            </button>

            {onOpenAutoBatchContract && (
              <button
                onClick={onOpenAutoBatchContract}
                className="flex items-center space-x-1.5 px-3 py-1.5 text-xs font-black text-amber-900 bg-gradient-to-r from-amber-300 via-amber-400 to-amber-300 hover:from-amber-400 hover:to-amber-500 shadow-md shadow-amber-400/20 border border-amber-300 rounded-xl transition-all duration-200 hover:-translate-y-0.5 active:translate-y-0 animate-pulse"
                title="6종 서류를 업로드하여 계약 내용, 금액, 사업자번호, 날짜 자동 생성"
              >
                <Sparkles className="w-4 h-4 text-amber-950" />
                <span>⚡ 6종 서류로 계약 자동 생성</span>
              </button>
            )}

            <button
              onClick={onOpenNewContract}
              className="flex items-center space-x-1.5 px-3.5 py-1.5 text-xs font-extrabold text-white bg-gradient-to-r from-indigo-600 via-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700 shadow-md shadow-indigo-500/20 hover:shadow-indigo-500/35 rounded-xl transition-all duration-200 hover:-translate-y-0.5 active:translate-y-0"
            >
              <Plus className="w-4 h-4" />
              <span className="hidden sm:inline">새 계약 등록</span>
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};
