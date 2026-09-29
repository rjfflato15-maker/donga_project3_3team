import React from 'react';
import {
  LayoutDashboard,
  FileText,
  // FolderKanban, // [임시 주석 처리] 증빙서류 관리
  FileCheck,
  ShieldCheck,
  Shield,
  LogOut,
  Sparkles,
  UploadCloud,
  RefreshCw,
  PanelLeftClose,
} from 'lucide-react';

import { useAuth } from '../context/AuthContext';

export type NavigationTab = 'dashboard' | 'contracts' | 'documents' | 'reports' | 'account-settings';

interface SidebarProps {
  isOpen?: boolean;
  onToggleCollapse?: () => void;
  activeTab: NavigationTab;
  onTabChange: (tab: NavigationTab) => void;
  onOpenAutoBatchContract?: () => void;
  onOpenUpload?: () => void;
  isMaskingEnabled?: boolean;
  onToggleMasking?: () => void;
  onSeedDemo?: () => void;
  loading?: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isOpen = true,
  onToggleCollapse,
  activeTab,
  onTabChange,
  onOpenAutoBatchContract,
  onOpenUpload,
  isMaskingEnabled = true,
  onToggleMasking,
  onSeedDemo,
  loading = false,
}) => {
  const { user, logout } = useAuth();
  const menuItems: { id: NavigationTab; label: string; icon: React.ReactNode; badge?: string }[] = [
    {
      id: 'dashboard',
      label: '대시보드',
      icon: <LayoutDashboard className="w-4 h-4" />,
    },
    {
      id: 'contracts',
      label: '외주/용역 계약',
      icon: <FileText className="w-4 h-4" />,
    },
    // [임시 주석 처리] 증빙서류 관리 페이지
    // {
    //   id: 'documents',
    //   label: '증빙서류 관리',
    //   icon: <FolderKanban className="w-4 h-4" />,
    // },
    {
      id: 'reports',
      label: 'AI 교차검수 리포트',
      icon: <FileCheck className="w-4 h-4" />,
      badge: 'AI Powered',
    },
  ];

  return (
    <aside
      className={`bg-white/95 backdrop-blur-md border-r border-slate-200/80 flex flex-col justify-between h-screen sticky top-0 shrink-0 select-none shadow-sm z-20 transition-all duration-300 ease-in-out overflow-hidden ${
        isOpen ? 'w-64 min-w-[16rem] opacity-100' : 'w-0 min-w-0 opacity-0 border-r-0 pointer-events-none'
      }`}
    >
      <div className="w-64 flex flex-col justify-between h-full overflow-y-auto">
        <div>
          {/* Logo Section & Collapse Button */}
          <div className="p-4 sm:p-5 flex items-center justify-between border-b border-slate-100/80">
            <div className="flex items-center space-x-3">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-violet-600 via-indigo-600 to-blue-500 flex items-center justify-center text-white shadow-lg shadow-indigo-500/25 shrink-0 transition-transform duration-300 hover:scale-105">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <div className="overflow-hidden">
                <h1 className="font-extrabold text-sm text-slate-900 tracking-tight leading-tight flex items-center space-x-1">
                  <span>Smart Contract</span>
                </h1>
                <div className="flex items-center space-x-1 mt-0.5">
                  <span className="text-[10px] font-black text-indigo-600 tracking-widest uppercase">
                    EVIDENCE HUB
                  </span>
                  <span className="text-[9px] bg-indigo-100 text-indigo-700 font-extrabold px-1.5 py-0.2 rounded-full">
                    PRO
                  </span>
                </div>
              </div>
            </div>

            {onToggleCollapse && (
              <button
                onClick={onToggleCollapse}
                className="p-1.5 rounded-xl text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 transition-colors border border-transparent hover:border-indigo-100 active:scale-95"
                title="메뉴 영역 감추기"
                aria-label="메뉴 영역 감추기"
              >
                <PanelLeftClose className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Navigation Menu */}
          <div className="px-3 pt-4 pb-2">
            <p className="px-3 text-[10px] font-extrabold text-slate-400 uppercase tracking-wider mb-2">
              MAIN MENU
            </p>
            <nav className="space-y-1">
            {menuItems.map((item) => {
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => onTabChange(item.id)}
                  className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-bold transition-all duration-200 relative ${
                    isActive
                      ? 'bg-gradient-to-r from-indigo-50 to-blue-50/60 text-indigo-700 shadow-xs border border-indigo-100'
                      : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                  }`}
                >
                  <div className="flex items-center space-x-3">
                    <span className={`transition-colors ${isActive ? 'text-indigo-600 scale-110' : 'text-slate-400'}`}>
                      {item.icon}
                    </span>
                    <span>{item.label}</span>
                  </div>

                  {item.badge ? (
                    <span className="text-[9px] font-black bg-gradient-to-r from-indigo-500 to-purple-500 text-white px-1.5 py-0.5 rounded-full flex items-center space-x-0.5 shadow-2xs">
                      <Sparkles className="w-2.5 h-2.5 inline" />
                      <span>AI</span>
                    </span>
                  ) : isActive ? (
                    <span className="w-1.5 h-1.5 rounded-full bg-indigo-600"></span>
                  ) : null}
                </button>
              );
            })}
          </nav>

          {/* Quick Actions in Main Menu */}
          <div className="mt-4 pt-3 border-t border-slate-100 space-y-2">
            <p className="px-3 text-[10px] font-extrabold text-slate-400 uppercase tracking-wider">
              QUICK ACTIONS
            </p>

            {/* 6종 서류로 계약 자동 생성 */}
            {onOpenAutoBatchContract && (
              <button
                onClick={onOpenAutoBatchContract}
                className="w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-bold bg-indigo-50/80 hover:bg-indigo-100/90 text-indigo-700 border border-indigo-200/80 transition-all hover:scale-[1.02] active:scale-95 group text-left"
                title="6종 서류를 업로드하여 계약 내용, 금액, 사업자번호, 날짜 자동 생성"
              >
                <div className="flex items-center space-x-2.5">
                  <Sparkles className="w-4 h-4 text-amber-500 fill-amber-400 group-hover:rotate-12 transition-transform shrink-0" />
                  <span className="leading-tight">6종 서류로 계약 자동 생성</span>
                </div>
                <span className="text-[10px] bg-indigo-200/60 text-indigo-800 px-1.5 py-0.5 rounded font-extrabold shrink-0">
                  ⚡ 자동
                </span>
              </button>
            )}

            {/* 증빙 업로드 */}
            {onOpenUpload && (
              <button
                onClick={onOpenUpload}
                className="w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-bold bg-indigo-50/80 hover:bg-indigo-100/90 text-indigo-700 border border-indigo-200/80 transition-all hover:scale-[1.02] active:scale-95 group text-left"
                title="계약 증빙서류 업로드"
              >
                <div className="flex items-center space-x-2.5">
                  <UploadCloud className="w-4 h-4 text-indigo-600 group-hover:-translate-y-0.5 transition-transform shrink-0" />
                  <span>증빙 업로드</span>
                </div>
                <span className="text-[10px] bg-indigo-200/60 text-indigo-800 px-1.5 py-0.5 rounded font-extrabold shrink-0">
                  + 파일
                </span>
              </button>
            )}
          </div>

          {/* Privacy & Masking Setting Control */}
          <div className="mt-4 pt-3 border-t border-slate-100 space-y-2">
            <p className="px-3 text-[10px] font-extrabold text-slate-400 uppercase tracking-wider mb-2">
              보안 및 개인정보 설정
            </p>

            <div className="bg-slate-50/90 rounded-2xl p-3 border border-slate-200/80 shadow-2xs">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Shield className={`w-4 h-4 ${isMaskingEnabled ? 'text-indigo-600' : 'text-slate-400'}`} />
                  <span className="text-xs font-bold text-slate-800">개인정보 비식별화</span>
                </div>

                {onToggleMasking && (
                  <button
                    type="button"
                    onClick={onToggleMasking}
                    className={`relative inline-flex h-5 w-10 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                      isMaskingEnabled ? 'bg-indigo-600' : 'bg-slate-300'
                    }`}
                    title={isMaskingEnabled ? '개인정보 마스킹 해제 (원본 보기)' : '개인정보 마스킹 켜기 (비식별화 보호)'}
                  >
                    <span
                      className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-md ring-0 transition duration-200 ease-in-out ${
                        isMaskingEnabled ? 'translate-x-5' : 'translate-x-0'
                      }`}
                    />
                  </button>
                )}
              </div>

              <div className="mt-1.5 text-[10px] leading-tight font-semibold">
                {isMaskingEnabled ? (
                  <span className="text-emerald-700 flex items-center space-x-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block animate-pulse"></span>
                    <span>ON (주민·계좌·사업자·상호 보호)</span>
                  </span>
                ) : (
                  <span className="text-amber-700 flex items-center space-x-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-500 inline-block"></span>
                    <span>OFF (전체 원본 노출)</span>
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* User Profile & Demo Reset Footer */}
      <div className="p-4 border-t border-slate-100/80 bg-slate-50/50 space-y-2">
        {onSeedDemo && (
          <button
            onClick={onSeedDemo}
            disabled={loading}
            className="w-full flex items-center justify-center space-x-1.5 px-3 py-1.5 text-[11px] font-bold text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors border border-slate-200/60"
            title="기획서 데모 시나리오 불러오기"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin text-indigo-600' : ''}`} />
            <span>기본 데모 데이터 초기화</span>
          </button>
        )}

        <div
          onClick={() => onTabChange('account-settings')}
          className={`flex items-center justify-between p-2 rounded-xl cursor-pointer transition-all duration-200 ${
            activeTab === 'account-settings'
              ? 'bg-indigo-50/90 border border-indigo-200/90 shadow-2xs'
              : 'hover:bg-slate-100/80 border border-transparent'
          }`}
          title="계정 보안 및 비밀번호 변경"
        >
          <div className="relative shrink-0">
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-600 to-violet-600 text-white font-extrabold text-xs flex items-center justify-center shadow-xs">
              {user?.email ? user.email.charAt(0).toUpperCase() : 'S'}
            </div>
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 border-2 border-white absolute -bottom-0.5 -right-0.5"></span>
          </div>
          <div className="flex-1 text-center min-w-0 px-2">
            <p className="text-xs font-extrabold text-slate-800 leading-tight truncate">
              {user?.email || 'System Admin'}
            </p>
          </div>
          <button
            onClick={(e) => {
              e.stopPropagation();
              logout();
            }}
            className="text-slate-400 hover:text-rose-600 hover:bg-rose-50 p-1.5 rounded-lg transition-colors shrink-0"
            title="로그아웃"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>

        {onToggleCollapse && (
          <button
            onClick={onToggleCollapse}
            className="w-full flex items-center justify-center space-x-1.5 px-3 py-1.5 text-[11px] font-bold text-slate-500 hover:text-indigo-600 hover:bg-indigo-50/70 rounded-lg transition-colors border border-dashed border-slate-200/90 active:scale-95"
            title="메뉴 영역 감추기"
          >
            <PanelLeftClose className="w-3.5 h-3.5" />
            <span>메뉴 영역 감추기</span>
          </button>
        )}
      </div>
    </div>
  </aside>
  );
};

export default Sidebar;
