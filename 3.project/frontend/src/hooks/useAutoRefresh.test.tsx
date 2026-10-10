// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { useAutoRefresh } from './useAutoRefresh';

beforeEach(() => { vi.useFakeTimers(); Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' }); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

function Fixture({ load, enabled = true }: { load: (signal: AbortSignal) => Promise<number>; enabled?: boolean }) {
  const [count, setCount] = useState(0), [draft, setDraft] = useState('');
  const refresh = useAutoRefresh(load, setCount, enabled);
  return <><span>대기 {count}건</span><input aria-label="작성 메모" value={draft} onChange={e => setDraft(e.target.value)}/>
    <span>{refresh.error}</span><button onClick={refresh.refresh}>지금 갱신</button><button onClick={refresh.invalidate}>저장 시작</button></>;
}

it('10초마다 대기 건수를 갱신하면서 작성 중인 입력을 유지한다', async () => {
  const load = vi.fn().mockResolvedValueOnce(2).mockResolvedValueOnce(3);
  render(<Fixture load={load}/>);
  fireEvent.change(screen.getByLabelText('작성 메모'), { target: { value: '작성 중인 결재 메모' } });
  await act(() => vi.advanceTimersByTimeAsync(9_999));
  expect(load).not.toHaveBeenCalled();
  await act(() => vi.advanceTimersByTimeAsync(1));
  expect(screen.getByText('대기 2건')).toBeTruthy();
  await act(() => vi.advanceTimersByTimeAsync(10_000));
  expect(screen.getByText('대기 3건')).toBeTruthy();
  expect((screen.getByLabelText('작성 메모') as HTMLInputElement).value).toBe('작성 중인 결재 메모');
});

it('숨긴 탭에서는 조회하지 않고 돌아오면 즉시 갱신한다', async () => {
  const load = vi.fn().mockResolvedValue(2);
  render(<Fixture load={load}/>);
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'hidden' });
  await act(() => vi.advanceTimersByTimeAsync(30_000));
  expect(load).not.toHaveBeenCalled();
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' });
  await act(async () => { document.dispatchEvent(new Event('visibilitychange')); });
  expect(load).toHaveBeenCalledOnce();
  expect(screen.getByText('대기 2건')).toBeTruthy();
});

it('느린 조회는 중복하지 않고 저장 시작 뒤 도착한 이전 응답을 버린다', async () => {
  let finish: (value: number) => void = () => {};
  const load = vi.fn((_signal: AbortSignal) => new Promise<number>(resolve => { finish = resolve; }));
  render(<Fixture load={load}/>);
  await act(() => vi.advanceTimersByTimeAsync(10_000));
  fireEvent.click(screen.getByText('지금 갱신'));
  await act(() => vi.advanceTimersByTimeAsync(30_000));
  expect(load).toHaveBeenCalledOnce();
  fireEvent.click(screen.getByText('저장 시작'));
  expect(load.mock.calls[0][0]?.aborted).toBe(true);
  await act(async () => { finish(99); });
  expect(screen.getByText('대기 0건')).toBeTruthy();
});

it('조회 실패 시 기존 목록과 입력을 유지하고 다음 조회로 복구한다', async () => {
  const load = vi.fn().mockResolvedValueOnce(2).mockRejectedValueOnce(new Error('서버 연결 실패')).mockResolvedValueOnce(4);
  const { unmount } = render(<Fixture load={load}/>);
  await act(() => vi.advanceTimersByTimeAsync(10_000));
  await act(() => vi.advanceTimersByTimeAsync(10_000));
  expect(screen.getByText('대기 2건')).toBeTruthy();
  expect(screen.getByText('서버 연결 실패')).toBeTruthy();
  await act(() => vi.advanceTimersByTimeAsync(10_000));
  expect(screen.getByText('대기 4건')).toBeTruthy();
  unmount();
  await act(() => vi.advanceTimersByTimeAsync(30_000));
  expect(load).toHaveBeenCalledTimes(3);
});
