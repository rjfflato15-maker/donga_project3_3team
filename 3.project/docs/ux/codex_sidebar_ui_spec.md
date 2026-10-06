# Codex 사이드바 UI 구현 명세서

2026-10-06 · 작성 Claude · 구현·검증 Codex

## 0. 범위와 기준

- **디자인 기준(승인안):** `docs/ux/codex_sidebar_example/`의 Codex 사이드바 새안이다.
  - `ui_compare.html`의 오른쪽 화면
  - `codex-workflow.html`(같은 계약 14단계 + 예외 4개)
  - 세부 구현은 `src/App.jsx`, `src/StoryPreview.jsx`, `src/prototype.css`, `src/story.css`를 따른다.
  - Claude ERP 시안(`erp_redesign/`)은 섞지 않는다.
- **동작 기준:** `docs/ux/codex_sidebar_implementation_handoff_20261006.md`, `docs/api/frontend_handoff.md`, `work_system.md`, `bundled_requests.md`, `payment_record.md`, 현재 `frontend/src`(main `d4195d5` = feat/ui-polish frontend 동일).
- **원칙:** 겉모양은 시안을 따르고, 데이터·상태·권한·입력 조건·오류 처리는 현재 앱을 따른다. 둘이 다르면 **현재 앱의 조건이 이긴다**. 이 경우 문구만 시안 톤으로 줄인다.
- **시안에서 옮기지 않는 것:**
  - 가상 계약(`seed`)과 고정 날짜(`2026년 10월 6일 화요일`, `10.06 10:12`)
  - `시안 초기화`, `대표 결재 예시` 메뉴, 역할 선택 `<select>`
  - 단계 이동 막대(`story-controls`)
  - 로컬 `setRows`/`patch`로 승인·지급·요청을 성공 처리하는 것
  - 업무함 아래 `demo-hint` 문구
- 표기 규칙: **[시안]** = 시안 CSS·JSX에서 그대로 뽑은 값, **[추정]** = 시안에 없어 같은 규칙으로 정한 값, **[현행]** = 지금 앱 코드에서 유지할 값.

---

## 1. 화면 지도

### 1-1. 전체 구조

```
App (로그인 보호: LoginPage / PilotPasswordChange)
└─ 공통 셸 = Sidebar(222px, 접기) + Topbar(56px) + content(max 1500)
   ├─ 업무함 ─────────── 행 클릭 ─┐
   ├─ 계약 찾기 ──────── 행 클릭 ─┤
   ├─ 설정                         │
   └─ [계약 등록] 모달 ── 완료 ────┤
                                   ▼
      계약 상세 (머리 + 진행 막대 + 탭)
        ├─ 서류 탭 ── 원문 대조 모달 ─┬─ 읽은 값 수정(모달 안 폼)
        │     │                       └─ 고친 본 올리기(모달)
        │     ├─ 서류 추가(모달)
        │     └─ N종 요청 작성 → 묶음 요청 모달 → 기록 → 요청 내역 탭
        ├─ 요청 내역 탭 ── 받은 N종 기록 / 항목 취소 / 고친 본 올리기
        ├─ 결재 탭 ── 결재 패널(승인·반려) → 지급 기록 패널 → 완료
        └─ 처리 기록 탭
      ··· 더 보기: 서류 추가, 다른 담당자에게 맡기기, 자료 묶음(ZIP), 계약 정보 수정
```

### 1-2. 화면별 연결표

| 화면 | 시안 위치 | 재사용할 현재 구현 | 데이터·API |
|---|---|---|---|
| 공통 셸 | `App.jsx` `aside.sidebar`, `header.topbar` | `Sidebar.tsx`, `ContractDashboard.tsx`(레이아웃, `currentIdRef`, 1280 미만 접기 로직은 교체) | `api.me`, `api.pilotInfo`(회사명·`nts_mode`·필수 서류), 가림 토글 상태(현행 `isMaskingEnabled`) |
| 업무함 | `page!=='contract'` 블록(`heading`, `stats`, `filters`, `contracts` 표, `mobile-list`) | `StageDashboard.tsx`(`mineOf`, `nextAction`, `matchesQuery`, 정렬), `MyAssignmentsStrip.tsx`, `utils/stage.ts` | `GET /api/contracts`(`stage`, `work_state`, `open_issue_count`, `waiting_request_count`, `earliest_due_on`, `approval_next_step`) |
| 계약 찾기 | 같은 목록 틀, `filter='all'` | `ContractSearch.tsx` | `GET /api/contracts/search`(`q`, `completion`, `stage`, 기간, `limit/offset`) |
| 계약 상세 머리·탭 | `contract-heading`, `progress`, `content-tabs` | `ContractStageView.tsx` 머리, `stepStates`, `maskForDisplay` | `GET /api/contracts/{id}`, `review-context`(`revision`, `fingerprint`, `work_state`) |
| 서류 탭 | `docs-grid`(서류 표 + `next-panel`) | `ContractStageView.tsx`의 서류 목록·`IssueBlock`·`splitInternalIssues`, `BundleRequest.tsx`의 `RequestChecklist` | `contract.documents`, `checks`, `resubmission-bundle-context` |
| 원문 대조 | `modal source-modal`(`source-toolbar`, `paper-area`, `source-fields`, `source-actions`, 모바일 `source-mobile-tabs`) | `DocumentReviewDialog.tsx` 전체(근거 상자, compare, versions, 수정 폼, 재발행 폼, Esc 규칙) | `GET /api/documents/{id}/provenance`(값·출처·근거·`human_confirmation`), `/versions`, `/compare`, `api.correctFields`, `api.reissueDocument` |
| 묶음 요청 | `modal request-modal` | `BundleRequestDialog`(basis 잠금, idempotency key, `buildText`) | `GET .../resubmission-bundle-context`, `POST .../resubmission-bundles` |
| 요청 내역(부분 회신) | `tab==='requests'`(`request-record`, `panel-footer`) | `BundleReplyPanel`(`itemArrived`, `currentDocumentFor`, `locked`), 기존 단일 요청 목록(`followUp.list/resolve`) | `GET .../resubmission-requests`, `PATCH .../resubmission-bundles/{id}/items` |
| 결재 | `approval-grid`(요약, 바뀐 내용, 담당 검토 의견, `decision`, `opinions`) | `ApprovalPanel.tsx`(제출 조건·`ackText`), `utils/reviewSummary.ts`, `ActivityTimeline`의 `fieldChanges` | `GET/POST /api/pilot/contracts/{id}/approvals`, `GET /api/contracts/{id}/activity` |
| 지급·재확인·완료 | `StoryPreview.jsx` `payment`, `reconfirm`, `done` 화면 | `ContractStageView.tsx` 지급 블록(`paidBefore`, `BLOCKED_KO`, `paymentBasis` 동의 초기화) | `GET/POST .../payment`, `POST .../payment/{pid}/reconfirm` |
| 처리 기록 | `tab==='history'`(`history` article) | `ActivityTimeline.tsx`(페이지, `summarize`, `kst`) | `GET /api/contracts/{id}/activity?masked=` |
| 계약 등록 | `modal` `new`, `StoryPreview` `register`·`basis` | `UploadModal.tsx`(session ref, 초기화), `NewContractModal.tsx`, `AutoBatchContractModal.tsx` | `api.uploadDocuments`, `api.autoParseBatchDocuments`, `api.autoCreateBatchContract`, `api.createContract` |
| 서류 추가 | `modal` `upload`(`file-picker`) | `UploadModal.tsx` "새 서류 추가" 모드 | `api.uploadDocuments` |
| 맡기기 | (시안 없음) | `AssignmentPanel.tsx`(`prefill`, 끝냄 조건) | assignments API |
| 설정 | (시안 없음) | `PilotOperations.tsx`, `CompanyPolicySection.tsx`, `WorkStatsStrip.tsx`, 사용자 관리 | `company-policy`, `presets`, `users`, `llm-status`, `performance` |
| 로그인·비밀번호 | (시안 없음) | `LoginPage.tsx`, `PilotPasswordChange.tsx`, `auth/` | 현행 인증 API |

---

## 2. 디자인 토큰

시안 CSS는 기본값 뒤에 "Readability pass"와 "Contrast" 덮어쓰기가 두 번 있다. 아래는 **덮어쓴 뒤 실제로 적용되는 최종값**이다.

**구현 방법:** `index.css`의 `:root`에 CSS 변수로 정의하고, `tailwind.config.js` `theme.extend`에서 그 변수를 참조한다. 현재 `brand` 팔레트(`#2563eb` 등)와 인디고 계열 클래스는 이 토큰으로 바꾼다.

### 2-1. 색

| 토큰 | 값 | 쓰는 곳 | 출처 |
|---|---|---|---|
| `--bg` | `#f7f9fc` | body 배경 | [시안] |
| `--sidebar-bg` | `#fcfdff` | 사이드바, `panel-footer`, 모달 footer | [시안] |
| `--surface` | `#ffffff` | 카드(`surface`), 상단 바, 모달 | [시안] |
| `--text` | `#243349` | 본문 기본, h1 | [시안] |
| `--text-2` | `#63758a` | 보조 글자(meta, sub, help, small 전반) | [시안] 대비 4.73:1 |
| `--text-3` | `#697b92` | `small`, `.muted`, `.eyebrow` | [시안] |
| `--th` | `#6c7f99` | 표 머리 글자 | [시안] |
| `--tab` | `#6d7f97` / 선택 `#3b67a4`, 밑줄 `#4e78b5` | 탭 | [시안] |
| `--primary` | `#315eaa`, hover `#284f90` | 주 버튼, 강조 | [시안] |
| `--link` | `#355f9d` | `text-button`, 근거 링크 | [시안] |
| `--contract-link` | `#476182`, hover `#315eaa` + 밑줄 | 목록 계약명 | [시안] |
| `--focus` | `#99baf0` | 포커스 3px, offset 2px | [시안] |
| `--line` | `#e2e8f0` | 카드·사이드바·상단 바 경계 | [시안] |
| `--line-soft` | `#eef2f7` | 표 행 경계 | [시안] |
| `--line-th` | `#e6edf6` | 표 머리 아래 | [시안] |
| `--line-section` | `#edf1f6` | `section-title` 아래, `panel-footer` 위 | [시안] |
| `--line-tabs` | `#dfe7f1` | 탭 줄 아래 | [시안] |
| `--input-line` | `#d7e0ec` | 입력칸 | [시안] |
| `--button-line` | `#d8e1ee`, hover `#b4c6df` / 배경 `#f6f9fd` | 보조 버튼 | [시안] |
| `--th-bg` | `#fafbfd` | 표 머리 배경 | [시안] |
| `--nav-active` | 글자 `#315f9f` / 배경 `#edf3fd` / hover `#f0f4fa` | 사이드바 메뉴 | [시안] |
| `--nav-text` | `#63758e` | 사이드바 메뉴 기본 | [시안] |
| `--decision` | 테두리 `#c7d7ee` / 머리 `#f4f8ff` | 결재 패널 | [시안] |
| `--field-selected` | `#f0f6ff`, hover `#f5f9ff` | 원문 대조 선택한 값 | [시안] |
| `--paper-area` | `#edf2f8` | 원문 뒤 배경 | [시안] |
| `--highlight` | 배경 `#fff4d6` / 테두리 2px `#e8c767` | 원문 근거 위치 | [시안] |
| `--shade` | `#20344c66`(모달) / `#243b5666`(모바일 메뉴) | 덮개 | [시안] |
| `--alert` | 배경 `#fff6e7` / 테두리 `#efdbb5` / 글자 `#825f22` | 상단 경고 띠(충돌·재확인) | [시안 story.css] |
| `--danger-band` | 배경 `#fbeded` / 테두리 `#efc9c9` / 글자 `#8f3a3a` | 재지급 금지·반려 띠 | [추정] red 배지 계열 |
| `--confirmed` | `#46775a` | "원문과 같음 · 이름 · 시각" | [시안] |

배지는 아래 다섯 가지만 쓴다. 공통: 11px, 굵기 600, 안쪽 여백 4px 8px, 모서리 4px, 줄바꿈 없음. [시안]

| tone | 배경 / 글자 | 의미 |
|---|---|---|
| gray | `#f0f3f7` / `#7a8799` | 중립(미조회, 기준 없음) |
| blue | `#edf3ff` / `#315e9e` | 내 차례, 결재 대기, 현재 본 |
| green | `#eaf5ee` / `#38765d` | 일치, 받음, 완료, 지급 대기 |
| amber | `#fff5df` / `#956d1a` | 확인 필요, 미제출, 회신 대기, 부분 회신 |
| red | `#fbeded` / `#a55757` | 반려, 불일치(금액), 막힘 |

### 2-2. 글자

글꼴: `'Malgun Gothic','Apple SD Gothic Neo',sans-serif`. 기본 14px, 줄높이 1.55. 금액은 `tabular-nums` + 굵기 600. [시안]

| 요소 | 크기 / 굵기 | 비고 |
|---|---|---|
| 페이지 제목 h1(업무함) | 25 / 기본, 자간 -0.8 | ≤700: 23 |
| 계약 제목 | 24 | ≤1200: 22, ≤700: 22 |
| 계약 금액 | 25, 자간 -0.6, `#334e75` | 단위 "원" 12 `#91a4bc` |
| 통계 숫자(stats) | 27, `#455d7e` | ≤700: 24 |
| 영역 제목 h2 | 15 / 650 | |
| 모달 제목 | 17, `#395d8c` | ≤700: 16 |
| 표 본문 | 13 | 목록 계약명 14 / 600 |
| 표 머리 | 12 / 500 | |
| 탭 | 13 | 선택 650 |
| 사이드바 메뉴 | 14 | 활성 650 |
| 보조(small, meta, help) | 11–12 | 색은 `--text-2` |
| eyebrow | 11 / 600, 자간 0.6 | `계약 {id}` 등 |
| 버튼 | 12 / 600 | 영역 제목 안 버튼 11 |

### 2-3. 간격·크기

| 항목 | 값 | 출처 |
|---|---|---|
| 사이드바 폭 | 222px(`--sidebar`), 브랜드 줄 높이 65 | [시안] |
| 상단 바 높이 | 56, 좌우 27(≤900: 17) | [시안] |
| 본문 | `max-width:1500; padding:24px 30px 48px`<br>≥1500: 좌우 42<br>≤1200: `24 22 40`<br>≤900: `23 20 40`<br>≤700: `21 16 40` | [시안] |
| 제목 줄 아래 | 25 | [시안] |
| 카드 사이 | 18–20(결재 그리드 gap 20, 열 사이 18) | [시안] |
| `section-title` | 최소 높이 55, 안쪽 14 19 | [시안] |
| 표 칸 | 안쪽 13 16. 업무함·서류 표는 세로 19 | [시안] |
| 입력칸 | 안쪽 9 11, 모서리 5 | [시안] |
| 버튼 | 최소 높이 36, 안쪽 9 13, 모서리 5<br>영역 제목 안: 30 / 6 10<br>모바일 결재 버튼: 42 | [시안] |
| 모서리 | 카드 8, 모달 10, 메뉴 항목 6, 업무 공간 상자 7, 배지 4 | [시안] |
| 그림자 | 모달 `0 18px 80px #172e4a22`, 토스트 `0 5px 24px #233a5315`, 모바일 사이드바 `10px 0 35px #20354b18`. 카드에는 그림자 없음 | [시안] |
| 모달 폭 | 기본 520 / 요청 680 / 원문 대조 1220<br>최대 높이 `100dvh - 48`(≤700: `-20`) | [시안] |
| 결재 그리드 | `1fr 320px`(≥1500: 345, ≤1200: 300, ≤900: 310, ≤700: 세로) | [시안] |
| 서류 그리드 | `1fr 280px`(≤1200: 240, ≤900: 세로) | [시안] |
| 아이콘 | Lucide. 메뉴 19, 버튼 14–16, 표 안 17 | [시안] |
| 비활성 | `opacity:.45; cursor:not-allowed` | [시안] |
| 애니메이션 | 사이드바 `transform/margin .2s ease`. `prefers-reduced-motion`이면 끔 | [시안] |

**[추정] 값:** 설정·사용자·로그인 화면은 시안이 없다. 이 화면들은 같은 `surface`/`section-title`/표/폼 토큰으로 만든다. 로그인 카드 폭 400, 설정 폼 라벨 폭 160은 추정값이다.

---

## 3. 컴포넌트 규격

반복되는 요소는 아래 컴포넌트로 하나씩 만들어 모든 화면에서 같이 쓴다. 이름은 제안이고, 위치는 `components/ui/`를 제안한다.

| 컴포넌트 | 구조 | 상태 |
|---|---|---|
| `AppShell` | `aside.sidebar`(fixed) + `.main`(margin-left 222) + `Topbar` + `main.content`. 닫히면 사이드바 `translateX(-100%)` + `visibility:hidden`, 본문 margin 0 | 열림 여부는 `localStorage`에 저장(try/catch). ≤900은 기본 닫힘이고, 열면 덮개 + 본문 `inert` |
| `Sidebar` | 순서: 브랜드(아이콘·"증빙검수"·접기 버튼) → 업무 공간 상자(회사명·"계약 증빙 관리") → 메뉴 라벨 "업무" → **업무함**(진행 건수 배지) / **계약 찾기** / **설정** → 아래쪽: **계약 등록** 버튼 [추정 위치: 메뉴 아래 주 버튼], 개인정보 가림 토글 [현행 기능, 시안 없음 → 푸터 위], 프로필(이름·역할·로그아웃) | 활성: `--nav-active`. hover 배경 `#f0f4fa`. 포커스는 공통 링. 메뉴를 고르면 ≤900에서 닫힘 |
| `Topbar` | 메뉴 토글 아이콘 + 경로(`계약 증빙 관리 › 현재 위치`) + 오른쪽 오늘 날짜(`seoulToday`, 형식 `2026년 10월 6일 화요일`) | 토글 버튼에 `aria-expanded`. 날짜는 ≤900에서 숨김 |
| `PageHeading` | eyebrow + h1 + (선택) 한 줄 설명 + 오른쪽 주 버튼 | 설명은 한 줄만 쓰고 생략할 수 있다 |
| `StatStrip` | 4칸 그리드. 칸마다 라벨 + 숫자 + "건" | 칸을 누르면 그 필터 탭이 선택된다 [추정] |
| `Surface` + `SectionTitle` + `PanelFooter` | 흰 카드, 테두리 `--line`, 모서리 8. 제목 줄에는 오른쪽 action 자리 | — |
| `Tabs` | `role="tablist"`. 버튼 `role="tab"` + `aria-selected`, 개수는 `small` | 선택: 글자·밑줄 색, 굵기 650. 가로 넘치면 가로 스크롤 |
| `DataTable` | `table-wrap`(가로 스크롤) 안 표. 금액 열 `.right .number` | hover 행 `#fcfdff`. 넓은 표는 ≤700에서 `min-width`를 주고 표 안에서 스크롤 |
| `Badge` | 2-1의 tone 5개 | 상태 판정 함수는 하나로 묶는다. 시안의 `tone(status)` 자리에 현재 `stage`+`work_state` 기반 함수를 둔다 |
| `ContractHeader` | 왼쪽: `back`("업무함") → eyebrow `계약 #{contract_id}` → 제목 + 상태 배지 → meta(거래처 · 담당 · 등록일)<br>오른쪽: `contract-amount`(라벨 "계약 금액 · {금액 기준}", 금액, 지급 방식)<br>오른쪽 위 `···` 메뉴 [현행 기능, 시안 없음] | 모든 탭에서 같은 자리에 있다 |
| `ProgressStrip` | `서류 등록 › 담당 검토 › 대표 결재 › 지급 기록`(정책이 1단계면 `담당 검토` 대신 `검수`) [시안 문구]. 완료 칸은 ✓, 현재 칸은 굵게 | **결재 탭에서는 숨김**(시안 `progress-hidden`, 720px에서 승인 버튼이 보이게) |
| `ApprovalLine` | 사람 칸(원 31px + 이름 + 상태) 사이에 선. 완료 칸 green, 대기 칸 blue 테두리 | 칸 수 = `approvals.steps.length`(1 또는 2). 3칸 이상은 그리지 않는다 |
| `DecisionPanel` | `surface.decision`: 제목 "대표 결재"(1단계 검토 차례면 "담당 검토") + 차례 배지 → `ApprovalLine` → 의견 칸(라벨 + "필수") → help → 확인 체크 → 버튼 2칸(`1fr 1.6fr`: 반려 \| 승인) | 내 차례가 아니면 `decision-state`(아이콘 + 한 줄 + 다음 할 일) |
| `OpinionList` | 배지(담당 검토 완료=green, 대표 반려=red, 대표 승인=green) + 시각 / 의견 / 이름 | 최근 3개만 보이고, 나머지는 "처리 기록" 탭 링크 [추정] |
| `RequestRecord` | 머리(`R-번호` + 회신 배지 + 방법·기한) → 표(선택 \| 항목 \| 회신 \| 검사) | 받은 항목의 체크박스는 비활성 |
| `Modal` | `modal-shade`(바깥 mousedown이면 닫힘) + `section[role=dialog][aria-modal]` → `modal-heading`(eyebrow + 제목 + X) → `modal-body`(스크롤) → `modal-footer`(왼쪽 취소, 오른쪽 보조 + 주 버튼) | **현재 `useDialogA11y`를 그대로 쓴다**(초기 포커스는 `data-autofocus` 우선, Tab 순환, Esc, 연 버튼으로 복귀, body 스크롤 잠금). 원문 대조에서 폼이 열려 있으면 Esc가 폼을 먼저 닫는다 [현행] |
| `Toast` | 하단 중앙, 흰 바탕, ✓ 아이콘, 닫기 X, 6초 뒤 사라짐, `role="status"` | 실패는 토스트가 아니라 해당 영역의 붉은 줄로 보여 준다 [현행 규칙] |
| `AlertBand` | 아이콘 + 문장 + 오른쪽 버튼(예: "최신 자료 불러오기") | 충돌·막힘·재지급 금지에 쓴다. 계약 머리 바로 아래, 단계가 바뀌어도 남는다 [현행 `replyMsg` 규칙] |
| `EmptyState` | 아이콘 25 + 굵은 한 줄 + 보조 한 줄 + (선택) 버튼 | — |
| `FilePicker` | 점선 테두리 상자(`#becfe7`, 배경 `#f8fbff`, 모서리 7) | 파일 입력 초기화 규칙은 [현행] `fileInputKey` |

공통 상호작용 상태:
- hover: 버튼은 배경 `#f6f9fd`와 테두리 `#b4c6df`, 주 버튼은 `#284f90`
- focus-visible: 3px `#99baf0`, offset 2
- disabled: `.45`
- 선택: 탭 밑줄, 메뉴 배경, 원문 값 `#f0f6ff`

---

## 4. 동작 표

상태 판단은 모두 서버의 `stage` / `work_state.next_actions` / `approvals`(`steps`, `next_step`, `completed_steps`)로 한다. 시안의 `status` 문자열 비교는 옮기지 않는다.

### 4-1. 셸·업무함

| 행동 | 호출할 현재 기능 | 활성 조건 | 성공 후 | 실패 시 |
|---|---|---|---|---|
| 사이드바 접기/펼치기 | 상태만 바꿈 | 항상 | 계약·탭·입력·모달은 그대로 유지(UI-01) | — |
| 메뉴 이동 | `ContractDashboard` 뷰 전환 | 항상 | 업무함·찾기는 검색어 초기화, 계약 선택 해제(`currentIdRef` 갱신) | — |
| 상태 필터 탭 | 프론트 필터. "완료"·"전체"는 `/contracts/search` | 항상 | 목록과 건수 갱신 | 검색 실패는 표 자리에 오류 + 다시 시도 |
| 검색 입력 | `matchesQuery`(금액 쉼표·"원" 정규화) | 항상 | 즉시 필터, X로 지움 | 빈 결과는 `EmptyState`("해당하는 계약이 없습니다." / "검색어나 상태 필터를 바꿔 보세요.") |
| 계약 행 클릭 | `api.getContract` + review-context | 항상 | 계약 상세. 기본 탭: `WAITING`→요청 내역, `APPROVAL`/`PAYMENT`/`DONE`→결재, 그 밖→서류 | 404: 목록으로, 토스트 없이 상단 오류 |
| 계약 등록 | `UploadModal`(현행 등록 흐름 전체) | 항상(권한은 서버) | 새 계약 상세 | 실패 파일만 표시하고 재시도. 다른 계약으로 섞이지 않게(`session ref`) |

**업무함 표 열:**
- 계약: 이름 + `#id · 담당`
- 거래처: 가림 적용
- 계약 금액
- 상태: 배지
- 다음 할 일: `nextAction` 문구, ≤1200에서 숨김
- 화살표

**상태 배지와 정렬:**
- 배지는 `mineOf` 기준이다. 내 차례면 blue "결재 차례", 그 밖은 `stage` 라벨 + tone이다.
- 정렬은 현행 `StageDashboard` 순서(내 차례 우선)를 유지한다.

**통계 4칸:** 진행 중 / 결재 대기 / 회신 대기 / 완료

| 칸 | 서버 기준 |
|---|---|
| 진행 중 | `stage!=DONE` |
| 결재 대기 | `stage=APPROVAL` |
| 회신 대기 | `stage=WAITING` |
| 완료 | `stage=DONE`. 검색 API에서 `completion=DONE`으로 센 값 |

**[확인 필요]** RECEIVING·CHECK·PAYMENT는 칸이 없다. 이 단계는 "진행 중"에만 포함한다.

### 4-2. 계약 상세

| 행동 | 호출할 현재 기능 | 활성 조건 | 성공 후 | 실패 시 |
|---|---|---|---|---|
| 탭 전환 | 상태만 바꿈 | 항상 | 입력·선택 유지. 탭 사이에 계약이 바뀌지 않음(UI-01) | — |
| 업무함(back) | 뷰 전환 | 항상 | 목록 다시 조회 | — |
| ··· → 서류 추가 | `UploadModal` 새 서류 추가 모드 | 권한 | 계약 재조회, 서류 탭 | 같은 창에서 재시도용 파일 유지 |
| ··· → 맡기기 | `AssignmentPanel`을 모달로 | 권한 | 맡은 일 갱신 | 해당 폼 안 오류 |
| ··· → 자료 묶음(ZIP) | 현행 `downloadProtected(.../export?masked=)`. OFF면 `confirm` 유지 | 항상 | 토스트(현행 문구 축약) | 오류 줄 |
| 서류 → 원문 대조 | `DocumentReviewDialog` | 원본 있음(`file_available`) | 모달 | 원본 없음: 비활성 + `title` 이유 |
| N종 요청 작성 | `RequestChecklist` → `BundleRequestDialog` | 선택 ≥1. 불일치 항목은 "원문도 틀림" 확인 체크 필요 [현행] | 모달 | — |

**서류 표 열:**
- 서류: 아이콘 + 종류명
- 현재 본: `N번째 본` 또는 `—`
- 검사: 배지
- 원문 확인: 확인자 이름 또는 `확인 필요` 또는 `—`. 집계 규칙은 아래 **[확인 필요]** 참고
- 원문 대조 링크

**오른쪽 `next-panel`("지금 확인할 것") 구성:**
- 외부 누락이 있을 때: amber 배지 `빠진 서류 N종` → 제목 "거래처에 한 번에 요청" → 체크 목록(`RequestChecklist`) → 주 버튼 `N종 요청 작성`
- 사내 확인이 있을 때(`splitInternalIssues`): 같은 패널 아래 "회사 안 확인" 목록. 각 줄의 동작은 `원문 대조` 또는 `작성한 파일 올리기`
- 남은 것이 없을 때: green 배지 `필수 서류 등록 완료` → 다음 행동 버튼(결재 탭으로)

### 4-3. 원문 대조 모달

**배치:**
- 툴바: 현재 본 배지(`현재 본 · N번째`) → 파일명·쪽 → (이전 본이 있으면) 버전 선택 [현행 versions] → 오른쪽 `고친 본 올리기`
- 본문: 원문(좌) | 읽은 값(우)

**읽은 값 한 줄(`field` 버튼):**
- 1행: 항목명 + 출처(`규칙` / `AI 보완` / `사람 수정`)
- 2행: 값(15px) + 검사 배지
- 3행: `기준 {expected}` + 근거 링크 `p.N ↗`
- `human_confirmation`이 있으면 4행: `✓ 원문과 같음 · {actor_name} · {at}`

**하단 `source-actions`:** 선택한 항목명 → 보조 한 줄 → `원문과 같음` | `읽은 값 수정`

| 행동 | 호출할 현재 기능 | 활성 조건 | 성공 후 | 실패 시 |
|---|---|---|---|---|
| 값 선택 | 근거 상자 강조(bbox/bboxes) | 근거가 있을 때만 강조. 없으면 강조하지 않음(**좌표를 만들지 않음**). AMBIGUOUS면 "같은 값 근거 여러 곳" 표시 | 원문 해당 위치로 스크롤. ≤700이면 원문 쪽으로 전환 | — |
| 원문과 같음 | `api.correctFields`(`confirmed_fields`) | 원문 미리보기가 정상일 때 | 그 줄에 확인 표시, 계약 재조회 | 409: `AlertBand`, 최신 provenance 다시 조회 |
| 읽은 값 수정 | 수정 폼(현행 E2) | 항상 | 저장하면 출처가 사람 수정으로 바뀜, 검사 다시 실행, 이전 결재 동의 초기화 | 409: 입력 유지 + 충돌 띠 + "최신 자료 불러오기" |
| 고친 본 올리기 | `api.reissueDocument`(`upload_mode=REISSUE`) | 파일 + 사유 | 새 본으로 compare 다시 조회, 이전 본은 읽기 전용 | 실패: 현재 본은 그대로라고 표시. 파일은 같은 창에서만 유지 |
| 닫기 / Esc | `useDialogA11y` | 항상 | 연 버튼으로 포커스 복귀 | — |

**원문 위 표시:**
- 가림 ON이면 자동 가림 원문을 보여 준다.
- 하단 `paper-area > small`에 "자동 가림은 일부 누락될 수 있음"을 유지한다 [현행 문구 축약].

### 4-4. 묶음 요청 모달

**배치:**
- 상단 3칸: 거래처(읽기) / 연락 방법 / 회신 기한(`data-autofocus`)
- `request-items`: 요청할 서류 N종. 줄마다 사유(`미제출` / `금액 정정 3,520,000 → 3,410,000`)
- 보낼 문구 textarea(readOnly). `짧게` / `자세히` 전환은 [현행] `buildText` 그대로
- help 한 줄
- footer: `취소` | `문구 복사` + 주 버튼 `보낸 뒤 기록`

| 행동 | 호출할 현재 기능 | 활성 조건 | 성공 후 | 실패 시 |
|---|---|---|---|---|
| 문구 복사 | `navigator.clipboard` | 항상 | 토스트 "요청 문구를 복사했습니다." | "문구를 직접 선택해 복사해 주세요." |
| 보낸 뒤 기록 | `POST resubmission-bundles`(idempotency key, basis = 선택 당시 계약 ID·revision·fingerprint) | 선택 ≥1, 기한 형식, 메모 ≤2,000자, `sameBasis` | 모달을 닫고 요청 내역 탭으로 이동. 토스트 "요청 1건 기록 · N항목. 메시지는 발송되지 않았습니다." | 409/400: 창 안 오류. 선택을 다시 쓰지 않고 "최신 목록에서 다시 선택" + 잠금 [현행]. 422: 해당 칸 |
| 연속 클릭 | busy 잠금 + 같은 키 | — | 요청은 1건만 생김(UI-06) | — |

**가림 안내:** ON이어도 문구에는 실제 거래처명이 들어간다. 이 안내는 help 한 줄로 유지한다 [현행 예외].

### 4-5. 요청 내역(부분 회신)

**배치:**
- 요청마다 `RequestRecord`를 둔다.
- 요청 번호: 시안은 `R-01`이다. 실제로는 계약 안 순번(`R-` + 생성 순서 2자리)을 표시용으로 쓰고, 서버 ID는 `title`에 넣는다 **[확인 필요]**.
- 회신 배지:
  - `수령 완료`(모두 받음)
  - `부분 회신 a/b`
  - `회신 대기`
  - 취소가 있으면 `취소 n` 배지를 추가로 붙인다
- 표의 검사 열: 현재 그 문서의 검사 결과(`일치` / `불일치` / `원문 확인 필요` / `—`). **받음과 검사는 다른 열**이다.
- 대기 항목 줄에서 도착 파일 상태: [현행] `itemArrived`면 "새 본 도착" 표시 + `원문 대조`. 아니면 `고친 본 올리기`
- 기존 단일 요청(bundle=null)은 아래에 "이전 방식 요청"으로 표시하고, 항목은 추측하지 않는다.

| 행동 | 호출할 현재 기능 | 활성 조건 | 성공 후 | 실패 시 |
|---|---|---|---|---|
| 항목 체크 | 상태만 바꿈 | 대기 항목만 | — | — |
| 받은 N종 기록 | `PATCH .../items`(RECEIVED, `revision`, `fingerprint`, `request_revision`) | 선택 ≥1, 잠금 아님 | 토스트 "선택한 항목의 수령을 기록했습니다. 검사 결과는 따로 확인합니다." 나머지는 대기 유지 | 409: 상단 `AlertBand` + 재조회. 선택을 다시 쓰지 않음(UI-11) |
| 항목 취소 | 같은 API(CANCELLED, 사유 1~2,000자) | 대기 항목 | 취소 수 표시 | 같음 |
| 이전 방식 요청 받음/취소 | `followUp.resolve` | 대기 | — | 새 묶음에는 쓰지 않음 |

### 4-6. 결재 탭

**왼쪽 열(`approval-main`):**
1. **결재 요약**
   - 필수 서류 `n/필요` + 배지
   - 자동 검사: `checks` 기준. NTS 미연동 REVIEW는 따로 분리
   - 담당 검토: `approvals.history` 1단계의 이름·시각. 1단계 정책이면 행 없음
   - 국세청 진위 조회 `미조회` 배지(`nts_mode=disabled`)
   - 오른쪽 배지: STALE 뒤면 `재결재`
2. **반려(또는 지난 결재) 이후 바뀐 내용**
   - 표: 서류·항목 | 이전 | 현재 | 원문 링크
   - 출처: `reviewSummary.ts` + activity `fieldChanges`
   - 기록이 없으면 표를 그리지 않고 "기록된 변경 없음"을 쓴다(추정 금지)
3. **담당 검토 의견**: 1단계 검토 note + 이름·시각. 1단계 정책이면 카드 없음

**오른쪽 열(`approval-side`):** `DecisionPanel` → `OpinionList`(activity의 결재·반려 이벤트)

| 행동 | 호출할 현재 기능 | 활성 조건 [현행 `ApprovalPanel`] | 성공 후 | 실패 시 |
|---|---|---|---|---|
| 승인(최종) / 담당 검토 완료(1단계) | `POST /approvals`(`step`, `CONFIRMED`, `note`, `revision`, `fingerprint`, `acknowledge_unverified`) | 내 차례(`role===nextStep.role` 또는 admin) **AND** `!blocked`(누락·원본 없음 없음) **AND** note ≥1자 **AND**(미확인 검사가 없거나, `ack` + note ≥10자) | approvals·계약 재조회. 다음 단계 또는 PAYMENT | 409: 동의·메모 초기화 + 충돌 띠 + 재조회 |
| 반려 | 같은 API(`RETURNED`) | **마지막 단계만** 노출, note ≥1자 | 담당자 쪽에 반려 띠 표시 | 같음 |
| 대표 전달 문장 복사(담당자) | 현행 복사 문구 | 담당자이고, 대표 차례이거나 결재 대기 | 토스트 "복사했습니다" | 직접 복사 안내 |

**시안 조건과 다른 점:**
- 시안은 "의견 항상 10자 이상"이다. 실제는 위 조건이고, help 문구를 조건에 맞게 바꾼다.
  - 미확인 검사가 있으면 "남은 확인이 있어 의견 10자 이상"
  - 없으면 "의견 필수"
- 확인 체크 문구는 [현행] `ackText`를 그대로 쓴다.

**결재 상태 문장(`decision-state`):**

| 상황 | 문장 |
|---|---|
| 확정 | 결재 완료 · 자료가 바뀌면 다시 결재 |
| 내 차례 아님 | {역할}의 {단계명} 대기 |
| 반려 | 담당자 재확인 필요 |

**대표 전달 의미:** 시안의 "대표 전달"은 **문장 복사**다. 버튼 이름에 `상신`·`요청 보내기`를 쓰지 않는다. 1단계 정책에서는 담당자의 결재 저장 단계가 없다.

### 4-7. 지급·재확인·완료

**배치:** `stage=PAYMENT`이면 결재 탭 오른쪽 `DecisionPanel` 자리가 **지급 기록 패널**로 바뀐다. 왼쪽 요약은 그대로다. **[추정 위치]** 시안의 `StoryPreview` `payment` 화면은 별도 단계 화면이다.

| 행동 | 호출할 현재 기능 | 활성 조건 | 성공 후 | 실패 시 |
|---|---|---|---|---|
| 계약 전체 지급 완료 기록 | `POST .../payment`(`paid_on`, `method` TRANSFER/OTHER, `note`, `revision`) | 현재 결재 CONFIRMED, `paid_on ≤ seoulToday`, 실존 날짜 | DONE. 완료 화면(`story-complete`): "계약 전체 지급 기록 완료" + 지급일·방법 | 409 문구는 서버 detail 그대로 |
| 기존 지급 재확인 | `POST .../payment/{pid}/reconfirm`(`acknowledge_same_payment:true`, note 10~2,000, `revision`) | `RECONFIRMATION_REQUIRED` **AND** `reconfirmation_allowed` | 재확인 이력 추가. 새 지급은 생기지 않음 | `blocked_reason`이면 버튼 비활성 + `BLOCKED_KO` 문구 |

**지급 패널 라벨:** 버튼과 제목은 **"계약 전체 지급 완료 기록"**. 분할 계약이면 "모든 회차 지급 뒤 기록" 한 줄을 붙인다 [현행].

**재확인 상태(`RECONFIRMATION_REQUIRED`):**
- 머리 아래에 `AlertBand`(danger 톤): `지급 기록 있음 {recorded_paid_on} — 재지급 금지` [현행 "다시 지급하지 마세요" 의미 유지]
- 새 지급 입력칸은 보이지 않는다.
- 동의 체크는 `paymentBasis`가 바뀌면 초기화한다 [현행].

### 4-8. 처리 기록 탭

`ActivityTimeline`(페이지 넘김 유지)을 `history` article 모양으로 보여 준다.
- 한 줄: 아이콘 + 제목(`summarize`) + `시각 · 처리자` + 본문
- 사람 처리와 자동 검사 기록은 아이콘과 배지로 구분한다 [현행 구분 유지]

---

## 5. 예외 상태

문구는 현행 의미를 유지한다. 대화체 "~해요"는 "~합니다" 또는 명사형으로 줄인다. 조건과 다음 행동은 지우지 않는다.

| 상태 | 판단 기준 | 표시 | 다음 행동 |
|---|---|---|---|
| 로딩 | 조회 진행 중 | 표·패널 자리에 회색 줄 3개 [추정] 또는 현행 스피너. 이전 계약 자료를 보여 주지 않음 | — |
| 늦은 응답 | `createLatestGuard`, `currentIdRef` | 버림(표시 없음) | — |
| 빈 업무함 | 목록 0 | `EmptyState` "처리할 계약 없음" + `계약 등록` | 등록 |
| 빈 검색 | 결과 0 | "해당하는 계약이 없습니다." | 필터 바꾸기 |
| 요청 없음 | bundles 0 | "기록된 요청이 없습니다." / "서류 탭에서 빠진 항목을 골라 요청할 수 있습니다." | 서류 탭 |
| 판독 불가 | `isReadingCheck`, 값 비어 있음 | 원문 대조 줄: 값 `—` + amber `확인 필요`, 출처 그대로. 사내 확인 목록에 들어감(거래처 요청 제외) | 값 수정 |
| 근거 위치 없음 | bbox 없음 | 근거 링크 비활성. 강조 없음 | — |
| 원본 없음 | `file_available=false` | 원문 대조 비활성 + 결재 차단(`blocked`) | 원본 복구(`restoreOriginal`) |
| 부분 회신 | bundle counts | `부분 회신 a/b`, 남은 대기 유지, 단계 WAITING | 받은 것만 기록 |
| 항목 취소 | CANCELLED | 줄 회색 + `취소` 배지, 집계에 취소 수 | — |
| 반려 | `approval_status=RETURNED` | 머리 아래 `AlertBand`(danger): `반려 · {이름} {시각} — {사유}`. 배지 red `반려` | 서류 확인 → 다시 결재 |
| 자료 변경 후 재결재 | `STALE` | 결재 요약 배지 `재결재`. "이전 결재 이후 바뀐 내용" 표 | 결재 |
| 409 충돌 | 저장 응답 409 | `AlertBand`(alert 톤): 서버 detail + `최신 자료 불러오기`. 입력은 유지하되 저장은 잠금. **단계가 바뀌어도 띠 유지** | 재조회 후 다시 선택 |
| 세션 만료 | 401 → `session-expired` 이벤트 | 현행 로그인 화면 이동 + 안내 | 다시 로그인 |
| 권한 없음 | 403 | 버튼 비활성 + `title` 이유 / 서버 detail | — |
| 업로드 실패 | 업로드 응답 오류 | 실패 파일 줄에 red 문구, 성공 파일은 유지 | 같은 창에서 재시도. 닫거나 Esc면 파일 초기화 |
| 이미 지급(재확인) | `RECONFIRMATION_REQUIRED` | 4-7 참고 | 재확인 또는 막힌 이유 |
| 지급 막힘 | `blocked_reason` | `FINAL_REVIEW_REQUIRED`: 다시 결재 필요<br>`SOURCE_VERSION_UNVERIFIED`: 원본 확인 불가, 복구·재등록 뒤 재결재<br>`PAYEE_OR_AMOUNT_CHANGED`: 거래처·금액 조건 변경, 실제 지급 내역 따로 확인 | — |
| LLM 상태 | `/pilot/llm-status` | 설정 화면에만 둔다. 실제 상태를 그대로 보여 주고 바꾸지 않음 | — |

---

## 6. 가림·반응형·키보드

### 6-1. 가림(handoff 표 그대로 유지)

| 위치 | ON | OFF | 구현 |
|---|---|---|---|
| 업무함·검색·계약 머리 거래처 | 가림 | 실제 | `maskVendorName` |
| 원문 대조 읽은 값(상호·사업자번호·계좌), 버전 비교 | 가림 | 실제 | `DocumentReviewDialog` `display` |
| 검사 문장·기준값·비교값 | 사업자번호·주민번호만 가림 | 실제 | `maskForDisplay` |
| 원문 미리보기 | 자동 감지 가림 + "일부 누락 가능" 한 줄 | 원문 | 서버 `preview_masking_service` |
| 값 수정칸 | 실제 값 + "가림 ON에서도 실제 값 표시" 한 줄 | 실제 | 현행 |
| 거래처 요청 문구 | 실제 거래처명 + 안내 한 줄 | 실제 | 현행 |
| 처리 기록의 사내 처리자 이름 | 유지 | 유지 | 현행 |
| ZIP | 가림(서류·JSON) | 원본 + confirm | `export?masked=` |
| 가린 원본 받기 | 가린 파일 | **OFF여도 가린 파일** | 현행 |

- 시안의 `가상 새봄기획`, `123-**-*****`는 예시 문자열이다. **가림 로직으로 쓰지 않는다.**
- 토글은 표시만 바꾼다. 저장 원본과 DB는 삭제·암호화하지 않는다. 설정에 이 뜻을 한 줄로 유지한다.
- 토글 위치: 사이드바 아래쪽(프로필 위). 상태는 `ON · 화면 표시값 가림`으로 짧게 쓴다.

### 6-2. 반응형

| 폭 | 사이드바 | 업무함 | 상세 | 원문 대조 |
|---|---|---|---|---|
| 1440×900 | 기본 열림. 결재 탭 오른쪽 열 320 | 표 6열 | 서류 그리드 `1fr 280` | 1220 모달, 2단 |
| 1280×720 | 기본 열림(현행 1280 미만 자동 접기는 **900 기준으로 바꿈**) | ≤1200이면 "다음 할 일" 열 숨김 | 결재 300. **승인 버튼이 720 안에 보여야 함**(진행 막대 숨김) | 2단, 표 안 스크롤 |
| 390×844 | 덮개형. 메뉴 버튼으로 열고, 덮개를 누르거나 Esc로 닫음. 본문 `inert` | `mobile-list`(배지·번호 / 계약명 / 거래처 / 금액 / 다음 할 일) | 머리 세로 배치, 결재 그리드 세로, 넓은 표는 `min-width` + 표 안 스크롤 | `원문 \| 읽은 값·근거` 탭 전환. 값을 고르면 원문 탭으로 이동. `source-actions`는 아래 고정 |

- 화면 폭을 바꿔도 업무 상태는 바뀌지 않는다. 열려 있는 수정 폼의 입력은 전환해도 유지한다.
- 문서 전체에 가로 스크롤이 생기면 안 된다. `scrollWidth == clientWidth`(UI-15)

### 6-3. 키보드

- **모달:** 초기 포커스는 `data-autofocus` 우선 → 첫 입력 → 대화창. Tab/Shift+Tab 순환, Esc 닫기, 연 버튼으로 복귀 [현행 `useDialogA11y`].
- **원문 대조:** 수정 폼이나 재발행 폼이 열려 있으면 Esc가 폼부터 닫는다. 모드를 바꾸면 첫 입력에 포커스 [현행].
- **모바일 메뉴:** 열면 첫 메뉴에 포커스, Tab 순환, Esc로 닫고 메뉴 버튼으로 복귀.
- **데스크톱 사이드바:** 접혀 있을 때는 `visibility:hidden`이라 Tab에서 빠진다.
- **탭:** `role=tab` + `aria-selected`. 좌우 화살표 이동 [추정, 시안에 없음. 넣지 않아도 됨].
- **표 행:** 계약명은 `<button>`, 행 끝 화살표 버튼에는 `aria-label="{계약명} 열기"`.
- **결재 라벨:** 의견 칸 `label for`. 확인 체크는 라벨로 감싼다.

---

## 7. 구현 순서와 확인 목록

한 묶음마다: 구현 → `npm test` + `npm run build` → 브라우저 장면 확인 → 시안 캡처와 비교 → 로컬 커밋.

| 순서 | 묶음 | 시안과 비교할 것 | 실제 흐름 확인(handoff ID) |
|---|---|---|---|
| 1 | 토큰 + `AppShell`·`Sidebar`·`Topbar` + 업무함 + 계약 찾기 | 사이드바 폭·메뉴 활성색·상단 바 / 통계 4칸 / 필터 탭 / 표 열·행 높이 / 배지 색 / 빈 결과 | UI-01, 02, 03, 12(목록) |
| 2 | `ContractHeader`·`ProgressStrip`·`Tabs` + 서류 탭 + 처리 기록 탭 | 머리 좌우 배치·금액 크기 / 진행 막대 / 서류 표 / `next-panel` | UI-04, 01(탭 유지) |
| 3 | 원문 대조 모달(+ 수정 폼·재발행·비교) | 1220 2단 / 근거 강조 / 값 줄 4행 / 하단 행동 | UI-05, 08, 13, 12(원문·수정칸) |
| 4 | 묶음 요청 모달 + 요청 내역 탭 | 요청 모달 680 / 항목 상자 / 요청 기록 표 / 하단 받은 N종 | UI-06, 07, 11, 12(요청 문구) |
| 5 | 결재 탭(요약·변경·의견·결재 패널·이력) | 결재 그리드 / 결재 패널 색 / 결재선 / 1280×720에서 승인 버튼 보임 | UI-09, 02(1단계·2단계 정책) |
| 6 | 지급·재확인·완료 + ZIP | 지급 패널 / 재지급 금지 띠 / 완료 화면 | UI-10, 14 |
| 7 | 등록·서류 추가·맡기기·설정·로그인·비밀번호 변경 | 같은 토큰. 시안 없음(추정 값 기록) | UI-16, 13(업로드 취소), 15(세 폭 전체) |

**묶음마다 공통으로 확인할 것:**
- 가림 ON/OFF 두 번 본다.
- 담당자·대표 두 역할로 본다.
- 1440/1280/390 세 폭으로 본다.
- 콘솔 오류 0개.
- 기존 컴포넌트 테스트(`stageDashboard.component`, `uploadModal.component` 등)가 바뀐 DOM에서도 통과하게 테스트를 고친다. 테스트 의미는 유지한다.

**최종 통합:** 등록 → 근거 확인 → 사람 수정 → 재발행 → 묶음 요청 → 부분 회신 → 재결재 → 지급 → ZIP을 한 번에 이어서 확인한다. 백엔드 테스트와 프론트 빌드를 돌린다. 의도적으로 시안과 다르게 한 곳은 문서로 남긴다.

---

## 확인 필요

1. **계약 번호 표기.** 시안은 `2026-0142` 형식인데 서버에는 정수 `contract_id`뿐이다. 제안은 `계약 #{id}`다. 원문 번호로 오해할 형식은 쓰지 않는다.
2. **요청 번호 `R-01`.** 계약 안 생성 순서로 프론트에서 계산한다(표시용). 서버 ID는 `title`에 넣는다. 이 표기를 써도 되는지 확인이 필요하다.
3. **"담당" 표시.** 계약 담당자로 쓸 수 있는 건 `registered_by_user_id`와 맡기기(assignee)뿐이다. 이름으로 바꿀 출처가 일반 사용자에게 열려 있는지 확인이 필요하다. 안 되면 맡긴 사람만 표시하고 나머지는 생략한다.
4. **업무함 "완료"·"전체" 탭.** 현재 할 일 목록은 DONE을 빼고 보여 준다. 두 탭은 `/contracts/search`로 불러오는 것으로 했다. 통계의 완료 수도 같은 출처다.
5. **서류 표 "원문 확인" 열.** `human_confirmation`은 필드 단위다. 서류 단위 표시 규칙이 필요하다. 제안: 확인할 값이 있는 필드가 모두 확인되면 마지막 확인자 이름, 일부만 확인되면 `a/b 확인`, 확인 대상이 없으면 `—`.
6. **결재 버튼 이름.**
   - 최종 단계는 `승인`(시안), 1단계는 `담당 검토 완료`로 했다.
   - 현행 `{step.label} 완료`와 다르다.
   - 정책의 `step.label`을 그대로 쓸지 정해야 한다.
7. **진행 막대 칸 이름.**
   - 시안은 4칸(서류 등록·담당 검토·대표 결재·지급 기록)이다. 서버 단계는 RECEIVING/CHECK/WAITING/APPROVAL/PAYMENT 5개다.
   - 제안: WAITING은 "서류 등록" 칸에 `보완 중` 보조 표시로 넣는다. 1단계 정책은 "담당 검토"를 "검수"로 바꾼다.
8. **지급 패널 위치.** 시안은 별도 단계 화면이다. 이 명세는 결재 탭 오른쪽 패널을 바꾸는 방식으로 정했다(탭 4개 유지).
9. **사이드바의 계약 등록 버튼과 가림 토글 위치.** 시안에는 없다. 계약 등록은 업무함 머리의 주 버튼이 기본이다. 사이드바에도 둘지는 선택이다.
10. **로딩 표시.** 시안에 없다. 회색 줄 3개 방식이 좋은지, 현행 스피너를 유지할지 정해야 한다.
