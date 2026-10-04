/** 마지막 글자에 받침이 있는지. 숫자는 읽는 소리로 판단(0 영·1 일·3 삼·6 육·7 칠·8 팔은 받침 있음) */
export function hasBatchim(word: string): boolean | null {
  const ch = word.trim().slice(-1);
  if (!ch) return null;
  const code = ch.charCodeAt(0);
  if (code >= 0xac00 && code <= 0xd7a3) return (code - 0xac00) % 28 !== 0;
  if (/[0-9]/.test(ch)) return '013678'.includes(ch);
  return null;
}

const PAIRS: Record<string, [string, string]> = {
  '이/가': ['이', '가'], '을/를': ['을', '를'], '은/는': ['은', '는'], '과/와': ['과', '와'], '으로/로': ['으로', '로'],
};

/** josa('통장사본', '이/가') → '통장사본이' */
export function josa(word: string, pair: keyof typeof PAIRS): string {
  const [withB, withoutB] = PAIRS[pair];
  const b = hasBatchim(word);
  if (b === null) return `${word}${withB}(${withoutB})`;
  if (pair === '으로/로' && word.trim().slice(-1).match(/[가-힣]/)) {
    const code = word.trim().slice(-1).charCodeAt(0);
    if ((code - 0xac00) % 28 === 8) return `${word}로`; // ㄹ 받침은 '로'
  }
  return `${word}${b ? withB : withoutB}`;
}

/** '통장사본이(가)', '세금계산서을(를)'처럼 붙어 나온 조사 표기를 앞 글자에 맞게 고친다 */
export function fixParticles(text: string): string {
  return text.replace(/([가-힣0-9])(이\(가\)|가\(이\)|을\(를\)|를\(을\)|은\(는\)|는\(은\)|과\(와\)|와\(과\))/g, (_m, ch: string, p: string) => {
    const b = hasBatchim(ch);
    const [first] = p.split('(');
    const pair = ({ 이: '이/가', 가: '이/가', 을: '을/를', 를: '을/를', 은: '은/는', 는: '은/는', 과: '과/와', 와: '과/와' } as const)[first as '이'];
    const [withB, withoutB] = PAIRS[pair];
    return ch + (b === null ? p : b ? withB : withoutB);
  });
}
