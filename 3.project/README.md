# AI Contract Evidence Manager (계약 증빙서류 누락·불일치 자동 검수 시스템)

> **외주·용역 계약 체결 후 대금 지급 전, 여러 증빙서류를 자동 분류하고 필수 증빙의 누락 및 문서 간 불일치를 근거와 함께 자동 검수하는 B2B 업무지원 시스템**

---

## 1. 프로젝트 핵심 가치

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

## 2. 기술 스택 및 아키텍처

- **Backend**: Python 3.12, FastAPI, SQLAlchemy ORM, SQLite / PostgreSQL 호환
- **Document AI & Preprocessing**: `pypdf`, 정규식 기반 개인정보 탐지/마스킹, 시그니처 가중치 분류기
- **External Integration**: 국세청(NTS) 사업자등록 상태조회 API (`RealNtsClient` + `MockNtsClient`)
- **Frontend**: React 18, TypeScript, Tailwind CSS, Vite, Lucide Icons
- **Testing**: `pytest` 8개 단위/통합 테스트 완비

---

## 3. 실행 방법 (Quick Start)

### 3-1. 백엔드 서버 실행
```powershell
cd c:\project
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
- Swagger API 문서: `http://localhost:8000/docs`
- 통합 SPA 대시보드: `http://localhost:8000/`

### 3-2. 프론트엔드 개발 서버 실행 (선택 사항)
```powershell
cd c:\project\frontend
npm run dev
```
- 프론트엔드 Dev URL: `http://localhost:5173`

### 3-3. 단위 및 통합 테스트 실행
```powershell
cd c:\project
python -m pytest backend/tests -v
```

---

## 4. 기획서 데모 시나리오 안내 ("ABC 홈페이지 구축 외주 계약")

시스템 최초 실행 시 기획서 슬라이드 1 및 4페이지의 검수 시나리오가 자동 적재됩니다:
- **총 계약금액**: 11,000,000 원
- **제출된 증빙 (5종)**:
  - 계약서: 정상 제출 (`contract`)
  - 견적서: 정상 제출 (`estimate`)
  - 사업자등록증: 정상 제출 (`business_registration`)
  - 통장사본: 정상 제출 (`bank_account`)
  - 세금계산서: 10,450,000 원 청구 (`tax_invoice`)
- **검토 필요 2건 (Exception Review)**:
  1. **검수확인서 누락**: 6종 중 `inspection_confirmation` 미제출로 **증빙 충족률 83%** 표시
  2. **금액 550,000원 불일치**: 계약서(11,000,000원) ↔ 세금계산서(10,450,000원) 간 차액 탐지 및 불일치 근거 제시
- **문서 카드 클릭**: 원본 텍스트 vs 마스킹본(`[RRN_001]`, `[PHONE_001]`, `[ACCOUNT_001]`) 대조 확인
- **5단계 시뮬레이터**: "5단계 시뮬레이터" 버튼을 통해 ERD Slide 7의 데이터 처리 파이프라인 단계별 동작 확인
