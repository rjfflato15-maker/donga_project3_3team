/** 서버와 같은 한국 날짜(Asia/Seoul, YYYY-MM-DD). toISOString()은 UTC라 한국 00:00~08:59에 전날이 된다 */
export function seoulToday(now: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(now);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? '';
  return `${get('year')}-${get('month')}-${get('day')}`;
}
