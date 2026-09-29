/**
 * Privacy & Document Format Masking Utilities for Contract Evidence System
 *
 * Rules:
 * 1. 개인정보 비식별화 마스킹:
 *    - 주민등록번호 (RRN): 뒷자리 성별 구분(1자리) 제외 * 표시 (예: 800101-1******)
 *    - 사업자등록번호: 앞 3자리 표시, 가운데 * 표시, 끝에 번호 * 표시 (예: 123-**-*****)
 *    - 계좌번호: 앞에 3자리 가운데 *표시 (끝자리 유지, 예: 110-***-456789)
 *    - 주소지: 지역만 표시하고 나머지 * 표시 (예: 서울특별시 ** **** ***)
 *    - 전화번호/휴대폰: 가운데 자리 * 표시 (예: 010-****-5678, 02-***-5678)
 *    - 이메일: 앞 2자리 유지 후 도메인까지 마스킹 (예: us***@domain.com)
 *    - 상호명/거래처명: 앞 글자 유지 후 마스킹 (예: (주)테스트소프트 -> (주)테****)
 *
 * 2. 문서형식 마스킹:
 *    - 문서 유형 (계약서, 견적서, 사업자등록증 등): 증빙서식 (***) / [보안서식]
 *    - 문서 포맷/확장자 (PDF, DOCX, HWP, XLSX 등): *** / [보안포맷]
 *    - 파일명: 개인정보 및 문서형식 비식별화
 *
 * 3. Masking OFF: 원본 전체 표시
 */

const KOREAN_REGIONS_REGEX =
  /^(서울특별시|서울시|서울|부산광역시|부산시|부산|대구광역시|대구시|대구|인천광역시|인천시|인천|광주광역시|광주시|광주|대전광역시|대전시|대전|울산광역시|울산시|울산|세종특별자치시|세종시|세종|경기도|경기|강원특별자치도|강원도|강원|충청북도|충북|충청남도|충남|전북특별자치도|전라북도|전북|전라남도|전남|경상북도|경북|경상남도|경남|제주특별자치도|제주도|제주)/;

/**
 * 주민번호 마스킹: 뒷자리 성별 구분 숫자(첫째 자리) 제외하고 모두 * 표시
 * 예: 800101-1234567 -> 800101-1******
 */
export function maskResidentNumber(val?: string | null): string {
  if (!val) return '';
  return val.replace(/\b(\d{6})\s*[-–]?\s*([1-8])\d{6}\b/g, '$1-$2******');
}

/**
 * 사업자등록번호 마스킹: 앞 3자리 표시, 가운데 * 표시, 끝에 번호 * 표시
 * 예: 123-45-67890 -> 123-**-*****
 */
export function maskBusinessNumber(val?: string | null): string {
  if (!val) return '';
  return val.replace(/\b(\d{3})\s*[-–]?\s*(\d{2})\s*[-–]?\s*(\d{5})\b/g, '$1-**-*****');
}

/**
 * 계좌번호 마스킹: 앞에 3자리 가운데 *표시 해서 나오고 (끝자리 번호 유지)
 * 예: 110-123-456789 -> 110-***-456789
 * 예: 352-0123-4567-89 -> 352-****-****-89
 */
export function maskAccountNumber(val?: string | null): string {
  if (!val) return '';
  return val.replace(/\b(\d{3,4})\s*[-–]\s*(\d{2,6})\s*[-–]\s*(\d{3,6})\b/g, (match, g1, g2, g3) => {
    if (g1.length === 3 && g2.length === 2 && g3.length === 5) {
      return `${g1}-**-*****`;
    }
    if (['010', '011', '016', '017', '018', '019', '02'].includes(g1)) {
      return match;
    }
    return `${g1}-${'*'.repeat(g2.length)}-${g3}`;
  });
}

/**
 * 전화번호/휴대폰 번호 마스킹: 가운데 번호 * 표시
 * 예: 010-1234-5678 -> 010-****-5678
 * 예: 02-123-4567 -> 02-***-4567
 */
export function maskPhone(val?: string | null): string {
  if (!val) return '';
  return val
    .replace(/\b(01[016789])\s*[-–.]?\s*(\d{3,4})\s*[-–.]?\s*(\d{4})\b/g, '$1-****-$3')
    .replace(/\b(02|0[3-6][1-5]|070|080)\s*[-–.]?\s*(\d{3,4})\s*[-–.]?\s*(\d{4})\b/g, '$1-***-$3');
}

/**
 * 이메일 마스킹: 앞 2자리만 표시하고 나머지는 * 표시
 * 예: user@example.com -> us***@example.com
 */
export function maskEmail(val?: string | null): string {
  if (!val) return '';
  return val.replace(/\b([A-Za-z0-9._%+-]{2})[A-Za-z0-9._%+-]*(@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b/g, '$1***$2');
}

/**
 * 주소지 마스킹: 지역만 표시하고 나머지 *로 표시
 * 예: 서울특별시 중구 세종대로 100 -> 서울특별시 ** **** ***
 */
export function maskAddress(val?: string | null): string {
  if (!val) return '';
  const match = val.match(KOREAN_REGIONS_REGEX);
  if (match) {
    const region = match[1];
    const rest = val.slice(region.length);
    const maskedRest = rest.replace(/\S/g, '*');
    return `${region}${maskedRest}`;
  }
  return val;
}

/**
 * 상호명 / 거래처명 / 대표자명 비식별화 마스킹
 * 예: (주)테스트소프트 -> (주)테****
 * 예: ABC 주식회사 -> A** 주식회사
 * 예: 홍길동 -> 홍*동
 */
export function maskVendorName(val?: string | null, isMasked: boolean = true): string {
  if (!val) return '';
  if (!isMasked) return val;

  // (주) Prefix handling
  if (val.startsWith('(주)')) {
    const namePart = val.substring(3).trim();
    if (namePart.length <= 1) return val;
    return `(주)${namePart[0]}${'*'.repeat(Math.max(2, namePart.length - 1))}`;
  }
  if (val.endsWith('주식회사')) {
    const namePart = val.replace('주식회사', '').trim();
    if (namePart.length <= 1) return val;
    return `${namePart[0]}${'*'.repeat(Math.max(2, namePart.length - 1))} 주식회사`;
  }
  // 일반 3글자 한국인 이름 예: 홍길동 -> 홍*동
  if (val.length === 3 && /^[가-힣]+$/.test(val)) {
    return `${val[0]}*${val[2]}`;
  }
  if (val.length === 2 && /^[가-힣]+$/.test(val)) {
    return `${val[0]}*`;
  }
  // 기본 기업명 마스킹
  if (val.length > 2) {
    return `${val.substring(0, 2)}${'*'.repeat(Math.max(2, val.length - 2))}`;
  }
  return val;
}

/**
 * 파일명 비식별화 마스킹 (개인정보 비식별화)
 */
export function maskFileName(
  fileName?: string | null,
  isPiiMasked: boolean = true
): string {
  if (!fileName) return '';
  let result = fileName;

  // 개인정보 마스킹 (주민번호, 사업자번호, 계좌번호 등)
  if (isPiiMasked) {
    result = maskResidentNumber(result);
    result = maskBusinessNumber(result);
    result = maskAccountNumber(result);
    result = maskPhone(result);
  }

  return result;
}

/**
 * 본문 전체 텍스트에 대한 통합 개인정보 비식별화 마스킹
 */
export function maskAllSensitiveInfo(text?: string | null): string {
  if (!text) return '';
  let out = text;
  out = maskResidentNumber(out);
  out = maskBusinessNumber(out);
  out = maskAccountNumber(out);
  out = maskPhone(out);
  out = maskEmail(out);
  out = maskAddress(out);
  return out;
}

/**
 * 마스킹 ON/OFF에 따른 유동적 포맷 함수
 */
export function formatSensitiveField(
  val: string | null | undefined,
  type: 'business_number' | 'rrn' | 'account' | 'address' | 'phone' | 'email' | 'vendor',
  isMasked: boolean
): string {
  if (!val) return '';
  if (!isMasked) return val; // OFF일 때는 원본 전체 노출

  switch (type) {
    case 'business_number':
      return maskBusinessNumber(val);
    case 'rrn':
      return maskResidentNumber(val);
    case 'account':
      return maskAccountNumber(val);
    case 'address':
      return maskAddress(val);
    case 'phone':
      return maskPhone(val);
    case 'email':
      return maskEmail(val);
    case 'vendor':
      return maskVendorName(val, true);
    default:
      return val;
  }
}

