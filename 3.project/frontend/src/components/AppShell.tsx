import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { ChevronRight, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { Sidebar, SidebarProps } from './Sidebar';
import { useDialogA11y } from '../hooks/useDialogA11y';
const STORAGE_KEY = 'cp.sidebar.v1';
export const AppShell: React.FC<SidebarProps & { children: React.ReactNode; title: string }> = ({ children, title, ...sidebar }) => {
  const [mobile, setMobile] = useState(() => window.matchMedia('(max-width: 900px)').matches);
  const [open, setOpen] = useState(() => {
    if (window.matchMedia('(max-width: 900px)').matches) return false;
    try { return localStorage.getItem(STORAGE_KEY) !== 'closed'; } catch { return true; }
  });
  const navRef = useRef<HTMLDivElement>(null), mainRef = useRef<HTMLDivElement>(null), toggleRef = useRef<HTMLButtonElement>(null);
  const wasMobileOpen = useRef(false);
  // 포커스 이동 effect보다 먼저 메뉴를 활성화한다. 닫힌 메뉴는 키보드로 들어갈 수 없다.
  useLayoutEffect(() => { if (navRef.current) navRef.current.inert = !open; }, [open]);
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
      if (wasMobileOpen.current && !(mobile && open)) toggleRef.current?.focus();
    }
    wasMobileOpen.current = mobile && open;
  }, [mobile, open]);
  const closeMobile = () => { if (mobile) setOpen(false); };
  return <div className={`cf-app app story-app ${open ? 'nav-open' : 'nav-closed'}`}>
    {mobile && open && <button className="mobile-shade" aria-label="메뉴 닫기" tabIndex={-1} onClick={() => setOpen(false)} />}
    <div id="app-navigation" className="sidebar" ref={navRef} role={mobile && open ? 'dialog' : undefined} aria-modal={mobile && open ? true : undefined} aria-label={mobile && open ? '앱 메뉴' : undefined}>
      <Sidebar {...sidebar} onCloseNavigation={() => setOpen(false)} onTabChange={(tab) => { sidebar.onTabChange(tab); closeMobile(); }} onOpenAutoBatchContract={sidebar.onOpenAutoBatchContract ? () => { sidebar.onOpenAutoBatchContract?.(); closeMobile(); } : undefined} />
    </div>
    <div className="main" ref={mainRef}>
      <header className="topbar"><div><button ref={toggleRef} className="icon" aria-label={open ? '메뉴 접기' : '메뉴 펼치기'} aria-expanded={open} aria-controls="app-navigation" onClick={() => setOpen((v) => !v)}>{open ? <PanelLeftClose size={19} /> : <PanelLeftOpen size={19} />}</button><span>계약 증빙 관리</span><ChevronRight size={13}/><strong>{title}</strong></div><small>{new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',year:'numeric',month:'long',day:'numeric',weekday:'long'}).format(new Date())}</small></header>
      <main className="content">{children}</main>
    </div>
  </div>;
};
