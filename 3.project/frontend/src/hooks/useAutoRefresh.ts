import { useCallback, useEffect, useRef, useState } from 'react';

export const AUTO_REFRESH_INTERVAL_MS = 10_000;

/** Refresh read-only lists without remounting forms, overlapping requests or hidden-tab polling. */
export function useAutoRefresh<T>(load: (signal: AbortSignal) => Promise<T>, onData: (data: T) => void,
  enabled: boolean, intervalMs = AUTO_REFRESH_INTERVAL_MS) {
  const latest = useRef({ load, onData });
  latest.current = { load, onData };
  const generation = useRef(0);
  const request = useRef<AbortController | null>(null);
  const runRef = useRef<() => void>(() => {});
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [error, setError] = useState('');
  const invalidate = useCallback(() => { generation.current++; request.current?.abort(); }, []);
  const refresh = useCallback(() => runRef.current(), []);

  useEffect(() => {
    if (!enabled) return;
    let active = true;
    let busy = false;
    let timer: ReturnType<typeof setTimeout>;
    const run = async () => {
      if (!active || busy || document.visibilityState === 'hidden') return;
      busy = true;
      clearTimeout(timer);
      const token = ++generation.current;
      const controller = new AbortController();
      request.current = controller;
      let timedOut = false;
      const timeout = setTimeout(() => { timedOut = true; controller.abort(); }, 12_000);
      try {
        const data = await latest.current.load(controller.signal);
        if (!active || controller.signal.aborted || token !== generation.current) return;
        latest.current.onData(data);
        setLastUpdated(new Date());
        setError('');
      } catch (reason) {
        if (active && token === generation.current && (!controller.signal.aborted || timedOut))
          setError(timedOut ? '서버 응답이 늦습니다. 다음 갱신에서 다시 확인합니다.' : reason instanceof Error ? reason.message : '자동 갱신을 완료하지 못했습니다.');
      } finally {
        clearTimeout(timeout);
        busy = false;
        if (request.current === controller) request.current = null;
        if (active) timer = setTimeout(() => void run(), intervalMs);
      }
    };
    const wake = () => { if (document.visibilityState !== 'hidden') void run(); };
    runRef.current = () => void run();
    timer = setTimeout(() => void run(), intervalMs);
    document.addEventListener('visibilitychange', wake);
    window.addEventListener('focus', wake);
    return () => {
      active = false;
      clearTimeout(timer);
      invalidate();
      runRef.current = () => {};
      document.removeEventListener('visibilitychange', wake);
      window.removeEventListener('focus', wake);
    };
  }, [enabled, intervalMs, invalidate]);

  return { lastUpdated, error, refresh, invalidate };
}
