import React from 'react';
import { LayoutDashboard, FolderOpen, Settings, ShieldCheck, LogOut, Plus, FileCheck, Upload, RefreshCw } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export type NavigationTab = 'dashboard' | 'contracts' | 'documents' | 'reports' | 'account-settings';
export interface SidebarProps {
  activeTab: NavigationTab;
  onTabChange: (tab: NavigationTab) => void;
  onOpenAutoBatchContract?: () => void;
  onOpenUpload?: () => void;
  onOpenNewContract?: () => void;
  isMaskingEnabled?: boolean;
  onToggleMasking?: () => void;
  onSeedDemo?: () => void;
  loading?: boolean;
  companyName?: string;
}
export const Sidebar: React.FC<SidebarProps> = ({ activeTab, onTabChange, onOpenAutoBatchContract, onOpenNewContract, onOpenUpload, isMaskingEnabled = true, onToggleMasking, onSeedDemo, loading, companyName }) => {
  const { user, logout } = useAuth();
  const pilot = user?.deployment_mode === 'pilot';
  const menus = [
    { id: 'dashboard' as NavigationTab, label: '업무함', icon: LayoutDashboard },
    { id: 'contracts' as NavigationTab, label: '계약 찾기', icon: FolderOpen },
    ...(!pilot ? [{ id: 'reports' as NavigationTab, label: '검수 리포트', icon: FileCheck }] : []),
    { id: 'account-settings' as NavigationTab, label: '설정', icon: Settings },
  ];
  return <aside className="cp-sidebar">
    <div className="cp-brand"><ShieldCheck size={21} /><strong>증빙검수</strong></div>
    <div className="cp-workspace"><span>{companyName || '계약 증빙 관리'}</span><small>계약 증빙 관리</small></div>
    <small className="cp-nav-label">업무</small>
    <nav aria-label="앱 메뉴">{menus.map(({ id, label, icon: Icon }) => <button key={id} aria-current={activeTab === id ? 'page' : undefined} onClick={() => onTabChange(id)}><Icon size={18} />{label}</button>)}</nav>
    {(onOpenAutoBatchContract || onOpenNewContract) && <button className="cp-sidebar-create" onClick={onOpenAutoBatchContract || onOpenNewContract}><Plus size={15} />계약 등록</button>}
    {!pilot && onOpenUpload && <button className="cp-sidebar-create" onClick={onOpenUpload}><Upload size={15} />서류 추가</button>}
    <div className="cp-sidebar-footer">
      {onSeedDemo && <button className="cp-text-button" onClick={onSeedDemo} disabled={loading}><RefreshCw size={14} />데모 초기화</button>}
      <button role="switch" aria-checked={isMaskingEnabled} aria-label="개인정보 가림" className="cp-privacy" onClick={onToggleMasking} title="화면 표시값 가림. 원문 자동 가림은 누락될 수 있으며 값 수정칸·거래처 요청 문구에는 실제 값이 표시됩니다.">
        <span>개인정보 가림<small>{isMaskingEnabled ? 'ON · 화면 표시값 가림' : 'OFF · 원본 표시'}</small></span><span className={`cp-switch ${isMaskingEnabled ? 'on' : ''}`} />
      </button>
      <div className="cp-profile"><span className="cp-avatar">{(user?.display_name || user?.email || '사').charAt(0)}</span><button onClick={() => onTabChange('account-settings')}><strong>{user?.display_name || user?.email}</strong><small>{user?.role === 'representative' ? '대표' : user?.role === 'admin' ? '관리자' : '담당자'}</small></button><button className="cp-icon" aria-label="로그아웃" onClick={logout}><LogOut size={17} /></button></div>
    </div>
  </aside>;
};
