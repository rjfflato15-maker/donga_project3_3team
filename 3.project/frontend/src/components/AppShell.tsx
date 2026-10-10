import React, { useEffect, useRef, useState } from 'react';
import { Sidebar, SidebarProps } from './Sidebar';
import { useDialogA11y } from '../hooks/useDialogA11y';
const STORAGE_KEY='cp.sidebar.v1';
export const AppShell:React.FC<SidebarProps&{children:React.ReactNode;title:string}>=({children,title,...sidebar})=>{
 const [mobile,setMobile]=useState(()=>window.matchMedia('(max-width:760px)').matches);
 const [open,setOpen]=useState(()=>{if(window.matchMedia('(max-width:760px)').matches)return false;try{const stored=localStorage.getItem(STORAGE_KEY);return stored?stored!=='closed':!window.matchMedia('(max-width:1100px)').matches;}catch{return true;}});
 const navRef=useRef<HTMLDivElement>(null),mainRef=useRef<HTMLDivElement>(null),wasMobileOpen=useRef(false);
 useDialogA11y(navRef,()=>setOpen(false),mobile&&open);
 useEffect(()=>{const media=window.matchMedia('(max-width:760px)');const resize=()=>{setMobile(media.matches);if(media.matches)setOpen(false);};media.addEventListener('change',resize);return()=>media.removeEventListener('change',resize);},[]);
 useEffect(()=>{if(!mobile)try{localStorage.setItem(STORAGE_KEY,open?'open':'closed');}catch{/* storage unavailable */}},[mobile,open]);
 useEffect(()=>{if(mainRef.current)mainRef.current.inert=mobile&&open;if(wasMobileOpen.current&&!(mobile&&open))navRef.current?.querySelector<HTMLButtonElement>('.collapse-control')?.focus();wasMobileOpen.current=mobile&&open;},[mobile,open]);
 const closeMobile=()=>{if(mobile)setOpen(false);};
 return <div className={`cf-app app story-app ${open?'nav-open':'nav-closed'}`}>
   {mobile&&open&&<button className="mobile-shade" aria-label="메뉴 닫기" tabIndex={-1} onClick={()=>setOpen(false)}/>}
   <div id="app-navigation" className="sidebar" ref={navRef} role={mobile&&open?'dialog':undefined} aria-modal={mobile&&open?true:undefined} aria-label={mobile&&open?'앱 메뉴':'업무 메뉴'}>
    <Sidebar {...sidebar} collapsed={!open} onCloseNavigation={()=>setOpen(value=>!value)} onTabChange={tab=>{sidebar.onTabChange(tab);closeMobile();}}
      onOpenAutoBatchContract={sidebar.onOpenAutoBatchContract?()=>{sidebar.onOpenAutoBatchContract?.();closeMobile();}:undefined}/>
   </div><div className="main" ref={mainRef}><main className="content" aria-label={title}>{children}</main></div>
 </div>;
};
