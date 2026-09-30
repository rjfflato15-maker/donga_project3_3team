import React from 'react';
import {
  LayoutDashboard,
  FileText,
  FileCheck,
  ShieldCheck,
  Shield,
  LogOut,
  Sparkles,
  UploadCloud,
  RefreshCw,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export type NavigationTab = 'dashboard' | 'contracts' | 'documents' | 'reports' | 'account-settings';

export interface SidebarProps {
  isOpen?: boolean;
  onToggleCollapse?: () => void;
  activeTab: NavigationTab;
  onTabChange: (tab: NavigationTab) => void;
  onOpenAutoBatchContract?: () => void;
  onOpenUpload?: () => void;
  onOpenNewContract?: () => void;
  isMaskingEnabled?: boolean;
  onToggleMasking?: () => void;
  onSeedDemo?: () => void;
  loading?: boolean;
}

// -------------------------------------------------------------
// Capsule Toggle Switch Icon (Exact match to user requested image)
// -------------------------------------------------------------
export const CapsuleToggleIcon: React.FC<{ className?: string }> = ({ className = 'w-5 h-5' }) => (
  <svg
    viewBox="0 0 24 24"
    className={className}
    fill="none"
    stroke="currentColor"
    strokeWidth="2.3"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <rect x="2.5" y="6" width="19" height="12" rx="6" />
    <circle cx="8" cy="12" r="2.2" />
  </svg>
);

// -------------------------------------------------------------
// Floating Tooltip for Collapsed Sidebar Items (Gemini Style)
// -------------------------------------------------------------
const SidebarTooltip: React.FC<{ text: string; badge?: string }> = ({ text, badge }) => (
  <div className="absolute left-full ml-3 px-3 py-1.5 bg-slate-900 text-white text-xs font-bold rounded-lg shadow-xl whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-all duration-200 transform translate-x-1 group-hover:translate-x-0 z-50 flex items-center space-x-1.5 border border-slate-700/80">
    <span>{text}</span>
    {badge && (
      <span className="text-[9px] font-black bg-gradient-to-r from-indigo-500 to-purple-500 text-white px-1.5 py-0.5 rounded-full shadow-2xs">
        {badge}
      </span>
    )}
    <div className="absolute -left-1 top-1/2 -translate-y-1/2 w-2 h-2 bg-slate-900 rotate-45 border-l border-b border-slate-700/80"></div>
  </div>
);

export const Sidebar: React.FC<SidebarProps> = ({
  isOpen = true,
  onToggleCollapse,
  activeTab,
  onTabChange,
  onOpenAutoBatchContract,
  onOpenUpload,
  onOpenNewContract,
  isMaskingEnabled = true,
  onToggleMasking,
  onSeedDemo,
  loading = false,
}) => {
  const { user, logout } = useAuth();

  // Full Menu Items for Expanded Mode (Original Icons)
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
    {
      id: 'reports',
      label: 'AI 교차검수 리포트',
      icon: <FileCheck className="w-4 h-4" />,
      badge: 'AI Powered',
    },
  ];

  return (
    <aside
      className={`bg-white/95 backdrop-blur-md border-r border-slate-200/80 flex flex-col justify-between h-screen sticky top-0 shrink-0 select-none shadow-sm z-30 transition-all duration-300 ease-in-out ${
        isOpen ? 'w-64 min-w-[16rem]' : 'w-[68px] min-w-[68px]'
      }`}
    >
      {/* ============================================================== */}
      {/* 1. COLLAPSED MODE: Gemini-style slim icon bar (Original Icons) */}
      {/* ============================================================== */}
      {!isOpen ? (
        <div className="flex flex-col justify-between items-center h-full py-4 px-2 w-full overflow-x-visible">
          {/* Top to Middle Icons Stack */}
          {/* Top to Middle Icons Stack */}
          <div className="flex flex-col items-center space-y-3 w-full">
            {/* 1. Sidebar Toggle Button */}
            <div className="relative group flex items-center justify-center">
              <button
                onClick={onToggleCollapse}
                className="p-2 rounded-xl text-slate-700 hover:text-indigo-600 hover:bg-slate-100 transition-all active:scale-95"
                title="메뉴 펼치기"
                aria-label="메뉴 펼치기"
              >
                <CapsuleToggleIcon className="w-6 h-6 text-slate-700 hover:text-indigo-600 transition-colors" />
              </button>
              <SidebarTooltip text="메뉴 펼치기" />
            </div>

            {/* 2. Main Menu: Dashboard (대시보드) - 위로 이동 */}
            <div className="relative group flex items-center justify-center">
              <button
                onClick={() => onTabChange('dashboard')}
                className={`p-2.5 rounded-xl transition-all active:scale-95 ${
                  activeTab === 'dashboard'
                    ? 'bg-indigo-50 text-indigo-600 ring-1 ring-indigo-200 shadow-2xs'
                    : 'text-slate-700 hover:text-indigo-600 hover:bg-slate-100'
                }`}
                title="대시보드"
                aria-label="대시보드"
              >
                <LayoutDashboard className="w-5 h-5" />
              </button>
              <SidebarTooltip text="대시보드" />
            </div>

            {/* 3. Main Menu: Contracts (외주/용역 계약) */}
            <div className="relative group flex items-center justify-center">
              <button
                onClick={() => onTabChange('contracts')}
                className={`p-2.5 rounded-xl transition-all active:scale-95 ${
                  activeTab === 'contracts'
                    ? 'bg-indigo-50 text-indigo-600 ring-1 ring-indigo-200 shadow-2xs'
                    : 'text-slate-700 hover:text-indigo-600 hover:bg-slate-100'
                }`}
                title="외주/용역 계약"
                aria-label="외주/용역 계약"
              >
                <FileText className="w-5 h-5" />
              </button>
              <SidebarTooltip text="외주/용역 계약 목록" />
            </div>

            {/* 4. Main Menu: AI Reports (AI 교차검수 리포트) */}
            <div className="relative group flex items-center justify-center">
              <button
                onClick={() => onTabChange('reports')}
                className={`p-2.5 rounded-xl transition-all active:scale-95 ${
                  activeTab === 'reports'
                    ? 'bg-purple-50 text-purple-600 ring-1 ring-purple-200 shadow-2xs'
                    : 'text-slate-700 hover:text-purple-600 hover:bg-slate-100'
                }`}
                title="AI 교차검수 리포트"
                aria-label="AI 교차검수 리포트"
              >
                <FileCheck className="w-5 h-5" />
              </button>
              <SidebarTooltip text="AI 교차검수 리포트" badge="AI" />
            </div>

            {/* Thin Divider between Main Menu and Quick Tools */}
            <div className="w-8 h-px bg-slate-200/80 my-0.5"></div>

            {/* 5. 6종 서류로 계약 자동 생성 (증빙서류 업로드 위로 위치 변경) */}
            <div className="relative group flex items-center justify-center">
              <button
                onClick={() => {
                  if (onOpenAutoBatchContract) onOpenAutoBatchContract();
                  else if (onOpenNewContract) onOpenNewContract();
                }}
                className="w-10 h-10 rounded-full bg-slate-100 hover:bg-indigo-50 text-slate-800 hover:text-indigo-600 transition-all flex items-center justify-center active:scale-95 shadow-2xs border border-slate-200/80 hover:border-indigo-200"
                title="6종 서류로 계약 자동 생성"
                aria-label="6종 서류로 계약 자동 생성"
              >
                <Sparkles className="w-5 h-5 text-amber-500 fill-amber-400 group-hover:rotate-12 transition-transform" />
              </button>
              <SidebarTooltip text="6종 서류로 계약 자동 생성" badge="AUTO" />
            </div>

            {/* 6. 증빙서류 업로드 */}
            {onOpenUpload && (
              <div className="relative group flex items-center justify-center">
                <button
                  onClick={onOpenUpload}
                  className="p-2.5 rounded-xl text-slate-700 hover:text-indigo-600 hover:bg-slate-100 transition-all active:scale-95"
                  title="증빙서류 업로드"
                  aria-label="증빙서류 업로드"
                >
                  <UploadCloud className="w-5 h-5 text-indigo-600" />
                </button>
                <SidebarTooltip text="증빙서류 업로드" />
              </div>
            )}

            {/* Thin Divider */}
            <div className="w-8 h-px bg-slate-200/80 my-0.5"></div>

            {/* 9. Privacy Masking Shield Toggle Icon */}
            {onToggleMasking && (
              <div className="relative group flex items-center justify-center">
                <button
                  onClick={onToggleMasking}
                  className="p-2.5 rounded-xl text-slate-700 hover:text-indigo-600 hover:bg-slate-100 transition-all active:scale-95 relative"
                  title={`개인정보 비식별화 (${isMaskingEnabled ? 'ON' : 'OFF'})`}
                  aria-label="개인정보 비식별화 On/Off"
                >
                  <Shield className="w-5 h-5 text-slate-700" />
                  <span
                    className={`w-2 h-2 rounded-full absolute top-1.5 right-1.5 ring-2 ring-white ${
                      isMaskingEnabled ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'
                    }`}
                  />
                </button>
                <SidebarTooltip
                  text={`개인정보 보호: ${isMaskingEnabled ? 'ON (비식별화 보호)' : 'OFF (원본 노출)'}`}
                />
              </div>
            )}
          </div>

          {/* Collapsed Bottom Section */}
          <div className="flex flex-col items-center space-y-3 w-full pt-3 border-t border-slate-100">
            {/* Demo Reset */}
            {onSeedDemo && (
              <div className="relative group flex items-center justify-center">
                <button
                  onClick={onSeedDemo}
                  disabled={loading}
                  className="p-2 rounded-xl text-slate-500 hover:text-indigo-600 hover:bg-slate-100 transition-all active:scale-95"
                  title="데모 데이터 초기화"
                  aria-label="데모 데이터 초기화"
                >
                  <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-indigo-600' : ''}`} />
                </button>
                <SidebarTooltip text="데모 시나리오 초기화" />
              </div>
            )}

            {/* User Profile Avatar */}
            <div className="relative group flex items-center justify-center">
              <button
                onClick={() => onTabChange('account-settings')}
                className={`w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-600 to-violet-600 text-white font-extrabold text-xs flex items-center justify-center shadow-xs active:scale-95 relative transition-all ${
                  activeTab === 'account-settings' ? 'ring-2 ring-indigo-500 ring-offset-2' : ''
                }`}
                title="계정 보안 및 비밀번호 변경"
                aria-label="계정 보안 및 비밀번호 변경"
              >
                {user?.email ? user.email.charAt(0).toUpperCase() : 'S'}
                <span className="w-2 h-2 rounded-full bg-emerald-500 border border-white absolute bottom-0 right-0"></span>
              </button>
              <SidebarTooltip text="계정 보안 및 비밀번호 변경" />
            </div>

            {/* Logout */}
            <div className="relative group flex items-center justify-center">
              <button
                onClick={logout}
                className="p-2 rounded-xl text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-all active:scale-95"
                title="로그아웃"
                aria-label="로그아웃"
              >
                <LogOut className="w-4 h-4" />
              </button>
              <SidebarTooltip text="로그아웃" />
            </div>
          </div>
        </div>
      ) : (
        /* ============================================================== */
        /* 2. EXPANDED MODE: Full Sidebar Menu (Original Icons)           */
        /* ============================================================== */
        <div className="w-64 flex flex-col justify-between h-full overflow-y-auto">
          <div>
            {/* Header: Logo & Toggle Button */}
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
                  title="메뉴 접기"
                  aria-label="메뉴 접기"
                >
                  <CapsuleToggleIcon className="w-5 h-5" />
                </button>
              )}
            </div>

            {/* Main Navigation Menu (MAIN MENU 위로 이동) */}
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
                        <span
                          className={`transition-colors ${
                            isActive ? 'text-indigo-600 scale-110' : 'text-slate-400'
                          }`}
                        >
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

              {/* QUICK TOOLS (5단계 시뮬레이터 삭제 & 6종 서류 자동 생성은 증빙서류 업로드 위로 배치) */}
              <div className="mt-4 pt-3 border-t border-slate-100 space-y-2">
                <p className="px-3 text-[10px] font-extrabold text-slate-400 uppercase tracking-wider mb-2">
                  QUICK TOOLS
                </p>

                {/* 6종 서류로 계약 자동 생성 (증빙서류 업로드 위로 변경) */}
                {onOpenAutoBatchContract && (
                  <button
                    onClick={onOpenAutoBatchContract}
                    className="w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-bold bg-indigo-50/80 hover:bg-indigo-100/90 text-indigo-700 border border-indigo-200/80 transition-all hover:scale-[1.01] active:scale-95 group shadow-2xs"
                    title="6종 서류로 계약 내용, 금액, 사업자번호, 날짜 자동 생성"
                  >
                    <div className="flex items-center space-x-2.5">
                      <Sparkles className="w-4 h-4 text-amber-500 fill-amber-400 group-hover:rotate-12 transition-transform shrink-0" />
                      <span className="font-extrabold text-indigo-900 leading-tight">6종 서류로 계약 자동 생성</span>
                    </div>
                    <span className="text-[10px] bg-indigo-200/60 text-indigo-800 px-1.5 py-0.5 rounded font-black">
                      ⚡ 자동
                    </span>
                  </button>
                )}

                {/* 증빙서류 업로드 */}
                {onOpenUpload && (
                  <button
                    onClick={onOpenUpload}
                    className="w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-bold bg-indigo-50/80 hover:bg-indigo-100/90 text-indigo-700 border border-indigo-200/80 transition-all hover:scale-[1.01] active:scale-95 group text-left"
                    title="계약 증빙서류 업로드"
                  >
                    <div className="flex items-center space-x-2.5">
                      <UploadCloud className="w-4 h-4 text-indigo-600 group-hover:-translate-y-0.5 transition-transform shrink-0" />
                      <span>증빙서류 업로드</span>
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
                        title={
                          isMaskingEnabled
                            ? '개인정보 마스킹 해제 (원본 보기)'
                            : '개인정보 마스킹 켜기 (비식별화 보호)'
                        }
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
          </div>
        </div>
      )}
    </aside>
  );
};

export default Sidebar;
