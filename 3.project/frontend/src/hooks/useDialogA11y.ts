import { RefObject, useEffect } from 'react';

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * 팝업 창 키보드 처리: 열리면 창 안으로 포커스, Tab은 창 안에서만 돌고, Esc로 닫고, 닫히면 원래 버튼으로 포커스를 돌려준다.
 */
export function useDialogA11y(ref: RefObject<HTMLElement>, onClose: () => void) {
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    const root = ref.current;
    const items = () => (root ? [...root.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((el) => el.offsetParent !== null) : []);
    // 닫기 버튼보다 본문 첫 칸에 먼저 가도록, 닫기(X)가 첫 번째면 그다음 요소로
    const list = items();
    const first = list.find((el) => el.getAttribute('aria-label') !== '닫기') ?? list[0];
    first?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.stopPropagation(); onClose(); return; }
      if (e.key !== 'Tab') return;
      const els = items();
      if (!els.length) return;
      const i = els.indexOf(document.activeElement as HTMLElement);
      if (e.shiftKey && (i <= 0)) { e.preventDefault(); els[els.length - 1].focus(); }
      else if (!e.shiftKey && (i === -1 || i === els.length - 1)) { e.preventDefault(); els[0].focus(); }
    };
    document.addEventListener('keydown', onKey, true);
    return () => {
      document.removeEventListener('keydown', onKey, true);
      if (opener && document.contains(opener)) opener.focus();
    };
    // 열릴 때 한 번만 설정한다
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
