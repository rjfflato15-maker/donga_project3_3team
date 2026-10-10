import React, { useId, useState } from 'react';
import { Grid2X2,FolderOpen,Settings,FileText,PanelLeftClose,PanelLeftOpen,LogOut,Plus,Upload,RefreshCw,ShieldCheck,LucideIcon } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
export type NavigationTab='dashboard'|'contracts'|'documents'|'reports'|'account-settings';
export interface SidebarProps {activeTab:NavigationTab;onTabChange:(tab:NavigationTab)=>void;onCloseNavigation?:()=>void;collapsed?:boolean;onOpenAutoBatchContract?:()=>void;onOpenUpload?:()=>void;onOpenNewContract?:()=>void;isMaskingEnabled?:boolean;onToggleMasking?:()=>void;onSeedDemo?:()=>void;loading?:boolean;companyName?:string;}
interface ActionProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {label:string;tip?:string;Icon?:LucideIcon;compact?:boolean}
function SidebarAction({label,tip,Icon,compact,className='',children,...props}:ActionProps){
 const [visible,setVisible]=useState(false),id=useId();
 return <button type="button" {...props} className={`sidebar-action ${className}`} aria-label={label} aria-describedby={compact&&visible?id:undefined}
   onMouseEnter={()=>setVisible(true)} onMouseLeave={()=>setVisible(false)} onFocus={()=>setVisible(true)} onBlur={()=>setVisible(false)} onKeyDown={event=>{if(event.key==='Escape')setVisible(false);props.onKeyDown?.(event);}}>
   {Icon&&<Icon size={19}/>} {children||<span className="nav-text">{label}</span>}{compact&&visible&&<span className="sidebar-tooltip" role="tooltip" id={id}>{tip||label}</span>}
 </button>;
}
export const Sidebar:React.FC<SidebarProps>=({activeTab,onTabChange,onCloseNavigation,collapsed=false,onOpenAutoBatchContract,onOpenNewContract,onOpenUpload,isMaskingEnabled=true,onToggleMasking,onSeedDemo,loading,companyName})=>{
 const {user,logout}=useAuth(),pilot=user?.deployment_mode==='pilot';
 const role=user?.role==='representative'?'대표':user?.role==='admin'?'관리자':'담당자',name=user?.display_name||user?.email||'현재 계정';
 return <>
 <div className="brand"><FileText size={24} className="brand-icon"/><strong>증빙검수</strong><SidebarAction label={collapsed?'메뉴 펼치기':'메뉴 접기'} compact={collapsed} Icon={collapsed?PanelLeftOpen:PanelLeftClose} className="collapse-control" aria-expanded={!collapsed} aria-controls="app-navigation" onClick={onCloseNavigation}/></div>
 <div className="workspace"><small>업무 공간</small><strong>{companyName||'회사 업무함'}</strong><span>계약 증빙 관리</span></div>
 <div className="nav-label">업무</div><nav aria-label="주 메뉴">
   <SidebarAction label="업무함" Icon={Grid2X2} compact={collapsed} className={`nav-item ${activeTab==='dashboard'?'active':''}`} aria-current={activeTab==='dashboard'?'page':undefined} onClick={()=>onTabChange('dashboard')}/>
   <SidebarAction label="계약 찾기" Icon={FolderOpen} compact={collapsed} className={`nav-item ${activeTab==='contracts'?'active':''}`} aria-current={activeTab==='contracts'?'page':undefined} onClick={()=>onTabChange('contracts')}/>
   {!pilot&&<SidebarAction label="검수 리포트" Icon={FileText} compact={collapsed} className={`nav-item ${activeTab==='reports'?'active':''}`} onClick={()=>onTabChange('reports')}/>}
 </nav>
 <div className="sidebar-bottom"><div className="sidebar-links">
   {(onOpenAutoBatchContract||onOpenNewContract)&&<SidebarAction label="계약 등록" Icon={Plus} compact={collapsed} onClick={onOpenAutoBatchContract||onOpenNewContract}/>}
   {!pilot&&onOpenUpload&&<SidebarAction label="서류 추가" Icon={Upload} compact={collapsed} onClick={onOpenUpload}/>}<SidebarAction label="설정" Icon={Settings} compact={collapsed} onClick={()=>onTabChange('account-settings')}/>
   {onSeedDemo&&<SidebarAction label="데모 초기화" Icon={RefreshCw} compact={collapsed} disabled={loading} onClick={onSeedDemo}/>}
 </div>
 <SidebarAction label={`개인정보 가림 ${isMaskingEnabled?'ON':'OFF'}`} tip={`개인정보 가림 · ${isMaskingEnabled?'켜짐':'꺼짐'}`} Icon={ShieldCheck} compact={collapsed} className="privacy-switch" aria-pressed={isMaskingEnabled} onClick={onToggleMasking}>
   <span className="nav-text">개인정보 가림</span><b>{isMaskingEnabled?'ON':'OFF'}</b>
 </SidebarAction>
 <div className="user"><SidebarAction label="현재 계정" tip={`${name} · ${role}`} compact={collapsed} className="profile-control" onClick={()=>onTabChange('account-settings')}><span className="avatar">{name.charAt(0)}</span><span className="profile-details"><strong>{name}</strong><small>{role}</small></span></SidebarAction>
 <SidebarAction label="로그아웃" Icon={LogOut} compact={collapsed} className="logout-control" onClick={logout}/></div></div>
 </>;
};
