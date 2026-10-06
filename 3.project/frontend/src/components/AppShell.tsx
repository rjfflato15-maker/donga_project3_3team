import React, { useEffect, useRef, useState } from 'react';
import { PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { Sidebar, SidebarProps } from './Sidebar';
import { useDialogA11y } from '../hooks/useDialogA11y';
import { seoulToday } from '../utils/date';
const STORAGE_KEY = 'cp.sidebar.v1';
export const AppShell: React.FC<SidebarProps & { children: React.ReactNode; title: string }> = ({ children, title, ...sidebar }) => {
  const [mobile, setMobile] = useState(() => window.matchMedia('(max-width: 900px)').matches);
  const [open, setOpen] = useState(() => {
    if (window.matchMedia('(max-width: 900px)').matches) return false;
    try { return localStorage.getItem(STORAGE_KEY) !== 'closed'; } catch { return true; }
  });
  const navRef = useRef<HTMLDivElement>(null), mainRef = useRef<HTMLDivElement>(null), toggleRef = useRef<HTMLButtonElement>(null);
  useDialogA11y(navRef, () => setOpen(false), mobile && open);
  useEffect(() => {
    const media = window.matchMedia('(max-width: 900px)');
    const resize = () => { setMobile(media.matches); if (media.matches) setOpen(false); else { try { setOpen(localStorage.getItem(STORAGE_KEY) !== 'closed'); } catch { setOpen(true); } } };
    media.addEventListener('change', resize); return () => media.removeEventListener('change', resize);
  }, []);
  useEffect(() => { if (!mobile) { try { localStorage.setItem(STORAGE_KEY, open ? 'open' : 'closed'); } catch { /* private storage unavailable */ } } }, [mobile, open]);
  useEffect(() => {
    if (mainRef.current) {
      mainRef.current.inert = mobile && open;
      if (mobile && !open && navRef.current?.contains(document.activeElement)) toggleRef.current?.focus();
    }
  }, [mobile, open]);
  const closeMobile = () => { if (mobile) { setOpen(false); toggleRef.current?.focus(); } };
  return <div className={`cp-app ${open ? 'cp-nav-open' : 'cp-nav-closed'}`}>
    {mobile && open && <button className="cp-nav-shade" aria-label="메뉴 닫기" tabIndex={-1} onClick={() => setOpen(false)} />}
    <div id="app-navigation" className="cp-nav" ref={navRef} role={mobile && open ? 'dialog' : undefined} aria-modal={mobile && open ? true : undefined} aria-label={mobile && open ? '앱 메뉴' : undefined}>
      {mobile && <button className="cp-nav-close cp-icon" aria-label="메뉴 닫기" onClick={() => setOpen(false)}><PanelLeftClose size={19} /></button>}
      <Sidebar {...sidebar} onTabChange={(tab) => { sidebar.onTabChange(tab); closeMobile(); }} onOpenAutoBatchContract={sidebar.onOpenAutoBatchContract ? () => { sidebar.onOpenAutoBatchContract?.(); closeMobile(); } : undefined} />
    </div>
    <div className="cp-main" ref={mainRef}>
      <header className="cp-topbar"><div><button ref={toggleRef} className="cp-icon" aria-label={open ? '메뉴 접기' : '메뉴 펼치기'} aria-expanded={open} aria-controls="app-navigation" onClick={() => setOpen((v) => !v)}>{open ? <PanelLeftClose size={19} /> : <PanelLeftOpen size={19} />}</button><span>계약 증빙 관리 <span className="cp-crumb">/ {title}</span></span></div><small>{seoulToday()} · {sidebar.isMaskingEnabled ? '개인정보 가림 ON' : '개인정보 가림 OFF'}</small></header>
      <main className="cp-content">{children}</main>
      <footer className="cp-app-footer">계약 증빙 검수 · 회사 서버에 보관</footer>
    </div>
  </div>;
};
