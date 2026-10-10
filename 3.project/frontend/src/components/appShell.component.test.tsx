// @vitest-environment jsdom
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { AppShell } from './AppShell';
vi.mock('../context/AuthContext', () => ({ useAuth: () => ({ user: { display_name: '가상 담당자', role: 'operator', deployment_mode: 'pilot' }, logout: vi.fn() }) }));
let mobile = false;
beforeEach(() => {
  localStorage.clear(); mobile = false;
  vi.spyOn(HTMLElement.prototype,'offsetParent','get').mockImplementation(function(this:HTMLElement){return this.parentElement;});
  window.matchMedia = vi.fn(() => ({ matches: mobile, addEventListener: vi.fn(), removeEventListener: vi.fn() } as unknown as MediaQueryList));
});
afterEach(() => {cleanup();vi.restoreAllMocks();});
function Screen() {
  const [note,setNote] = useState('');
  return <AppShell title="결재" activeTab="dashboard" onTabChange={() => {}} isMaskingEnabled><label>결재 의견<input value={note} onChange={(e) => setNote(e.target.value)} /></label></AppShell>;
}
describe('앱 셸: 메뉴는 업무 입력과 독립', () => {
  it('접고 펼쳐도 입력값과 본문 컴포넌트를 유지한다', () => {
    render(<Screen />);
    fireEvent.change(screen.getByLabelText('결재 의견'), { target: { value: '원문 확인 후 승인' } });
    fireEvent.click(screen.getByRole('button', { name: '메뉴 접기' }));
    expect((screen.getByLabelText('결재 의견') as HTMLInputElement).value).toBe('원문 확인 후 승인');
    expect(localStorage.getItem('cp.sidebar.v1')).toBe('closed');
    fireEvent.click(screen.getByRole('button', { name: '메뉴 펼치기' }));
    expect((screen.getByLabelText('결재 의견') as HTMLInputElement).value).toBe('원문 확인 후 승인');
  });
  it('모바일 메뉴는 본문을 잠그고 Esc로 닫는다', () => {
    mobile = true; render(<Screen />);
    expect(screen.queryByRole('dialog')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '메뉴 펼치기' }));
    expect(screen.getByRole('dialog', { name: '앱 메뉴' })).toBeTruthy();
    expect((document.querySelector('.main') as HTMLElement).inert).toBe(true);
    expect(document.activeElement).toBe(screen.getByRole('button',{name:'메뉴 접기'}));
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
    expect((document.querySelector('.main') as HTMLElement).inert).toBe(false);
    expect(document.activeElement).toBe(screen.getByRole('button',{name:'메뉴 펼치기'}));
    expect((document.querySelector('.sidebar') as HTMLElement).inert).not.toBe(true);
    expect(screen.getByRole('button',{name:'업무함'})).toBeTruthy();
  });
});
