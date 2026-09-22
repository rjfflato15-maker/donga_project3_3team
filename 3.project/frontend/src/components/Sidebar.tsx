import React from 'react';
import {
  LayoutDashboard,
  FileText,
  FolderKanban,
  FileCheck,
  ShieldCheck,
  LogOut,
  Sparkles,
} from 'lucide-react';

export type NavigationTab = 'dashboard' | 'contracts' | 'documents' | 'reports';

interface SidebarProps {
  activeTab: NavigationTab;
  onTabChange: (tab: NavigationTab) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ activeTab, onTabChange }) => {
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
      id: 'documents',
      label: '증빙서류 관리',
      icon: <FolderKanban className="w-4 h-4" />,
    },
    {
      id: 'reports',
      label: 'AI 교차검수 리포트',
      icon: <FileCheck className="w-4 h-4" />,
      badge: 'AI Powered',
    },
  ];

  return (
    <aside className="w-64 bg-white/90 backdrop-blur-md border-r border-slate-200/80 flex flex-col justify-between h-screen sticky top-0 shrink-0 select-none shadow-sm z-20">
      <div>
        {/* Logo Section */}
        <div className="p-5 flex items-center space-x-3.5 border-b border-slate-100/80">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-violet-600 via-indigo-600 to-blue-500 flex items-center justify-center text-white shadow-lg shadow-indigo-500/25 shrink-0 transition-transform duration-300 hover:scale-105">
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

        {/* Navigation Menu */}
        <div className="px-3 pt-4 pb-2">
          <p className="px-3 text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">
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
        </div>
      </div>

      {/* User Profile Footer */}
      <div className="p-4 border-t border-slate-100/80 bg-slate-50/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="relative">
              <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-600 to-violet-600 text-white font-extrabold text-xs flex items-center justify-center shadow-xs">
                S
              </div>
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 border-2 border-white absolute -bottom-0.5 -right-0.5"></span>
            </div>
            <div className="text-left">
              <p className="text-xs font-extrabold text-slate-800 leading-tight">System Admin</p>
              <p className="text-[10px] text-slate-400 font-semibold">IT Compliance</p>
            </div>
          </div>
          <button className="text-slate-400 hover:text-slate-700 hover:bg-slate-100 p-1.5 rounded-lg transition-colors" title="로그아웃">
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );
};
