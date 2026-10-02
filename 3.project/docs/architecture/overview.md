# 서비스 개요와 기술 구성

## 핵심 가치

- **모든 문서를 읽는 대신, 검토가 필요한 예외(불일치·누락·저신뢰)만 확인합니다.**
- **핵심 문서 6종 고정**:
  1. `contract` (계약서)
  2. `estimate` (견적서)
  3. `business_registration` (사업자등록증)
  4. `bank_account` (통장사본)
  5. `tax_invoice` (세금계산서)
  6. `inspection_confirmation` (납품·검수확인서)
- **개인정보 보호 전처리**: 원본 문서를 외부 LLM에 그대로 노출하지 않고, 로컬 전처리를 통해 주민번호(`[RRN_001]`), 연락처(`[PHONE_001]`), 계좌번호(`[ACCOUNT_001]`) 등을 사전 마스킹
- **결정론적 Rule Engine**: 사업자번호 일치 대조, 국세청 계속사업자 확인, 계약금액 ↔ 세금계산서 금액 차액 대조
- **5단계 파이프라인 시뮬레이터**: 업로드 → 마스킹/국세청 → AI 추출 → 정규화 → 교차검수 단계별 시각화

---

## 기술 구성

- **Backend**: Python 3.12, FastAPI, SQLAlchemy ORM, SQLite / PostgreSQL 호환
- **Document AI & Preprocessing**: `pypdf`, 정규식 기반 개인정보 탐지/마스킹, 시그니처 가중치 분류기
- **External Integration**: 국세청(NTS) 사업자등록 상태조회 API (`RealNtsClient` + `MockNtsClient`)
- **Frontend**: React 18, TypeScript, Tailwind CSS, Vite, Lucide Icons
- **Testing**: `pytest` 백엔드 회귀 검증과 TypeScript·Vite 프런트 빌드

---

현재 파일별 책임은 [소스 역할 표](module_map.md)를 확인한다.

[전체 문서 목록](../README.md)
