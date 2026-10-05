/**
 * 가장 최근에 보낸 조회만 반영하기 위한 세대 번호.
 * 같은 계약에서도 먼저 보낸 느린 응답(성공·실패 모두)이 나중 응답을 덮어쓰지 않게 한다.
 */
export function createLatestGuard() {
  let gen = 0;
  return {
    next: () => ++gen,
    isLatest: (token: number) => token === gen,
    invalidate: () => { gen += 1; },
  };
}

/** 회신 저장 뒤 화면에 남길 안내: 저장 결과와 목록 재조회 결과를 따로 말한다 */
export function replyNotice(saved: boolean, refreshed: boolean, error?: string): { tone: 'ok' | 'warn' | 'error'; text: string } | null {
  if (saved && refreshed) return null;
  if (saved) return { tone: 'warn', text: '저장했어요. 다만 최신 목록을 불러오지 못했어요. 화면을 새로고침한 뒤 이어서 하세요.' };
  const why = error ? `저장하지 못했어요: ${error}` : '저장하지 못했어요.';
  return refreshed
    ? { tone: 'error', text: `${why} 최신 상태를 다시 불러왔어요. 다시 골라 주세요.` }
    : { tone: 'error', text: `${why} 최신 상태도 불러오지 못했어요. 화면을 새로고침해 주세요.` };
}
