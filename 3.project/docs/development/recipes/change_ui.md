# 화면 문구·버튼·배치 수정

> 상태: 현재 기준
> 확인일: 2026-10-09
> 기준: 2026-10-09 구조 정리 소스 사본. 현재 소스와 과거 설치·평가 기록의 검증 범위를 구분한다.

관련 소스: [ContractDashboard.tsx](../../../frontend/src/pages/ContractDashboard.tsx) · [ContractStageView.tsx](../../../frontend/src/components/review/ContractStageView.tsx) · [DocumentWorkspace.tsx](../../../frontend/src/components/review/DocumentWorkspace.tsx) · [compare-ui.css](../../../frontend/src/compare-ui.css) · [index.css](../../../frontend/src/index.css)

## 목표와 위치

문서 상세의 버튼·필드 배치를 바꾸는 예시다. 계약 목록은 ContractDashboard, 상세 업무는 ContractStageView, 원문 작업은 DocumentWorkspace에서 시작한다. 승인된 원문 대조와 사이드바 스타일은 [review-workspace.css](../../../frontend/src/components/review-workspace.css), 항목·검사 매핑은 [reviewFields.ts](../../../frontend/src/components/review/reviewFields.ts), 메뉴는 [ContractActions.tsx](../../../frontend/src/components/review/ContractActions.tsx), VLM 요청 취소는 [useVlmReread.ts](../../../frontend/src/hooks/useVlmReread.ts)를 확인한다. 기존 업무·결재 화면 스타일은 compare-ui.css에 있다. 익숙한 클래스가 있다는 이유로 전역 선택자를 바꿔 다른 화면까지 수정하지 않는다.

## 전역 CSS 계층

[main.tsx](../../../frontend/src/main.tsx)의 import 순서가 아래 적용 순서다. 독립적인 CSS 모듈 다섯 개가 아니라 전역 선택자가 겹치는 누적 계층이다.

| 순서 | 파일 | 현재 역할·수정 범위 |
| --- | --- | --- |
| 1 | [index.css](../../../frontend/src/index.css) | Tailwind 기반·공통 유틸리티·기존 화면 스타일 |
| 2 | [sidebar-ui.css](../../../frontend/src/sidebar-ui.css) | `cp-*` 셸·탐색·공통 컨트롤·기존 상세 화면 |
| 3 | [compare-ui.css](../../../frontend/src/compare-ui.css) | `.cf-app` 범위의 업무함·등록·결재 화면 기본 스타일. 과거 시안에서 파생된 현재 앱 입력 파일 |
| 4 | [compare-runtime.css](../../../frontend/src/compare-runtime.css) | 실제 데이터·폼·원문·키보드 상태·반응형 보정 |
| 5 | [review-workspace.css](../../../frontend/src/components/review-workspace.css) | `.cf-app.story-app`의 원문 대조와 최종 셸·사이드바·콘텐츠 배치 보정 |

`review-workspace.css`는 원문 대조 외에도 전체 셸을 덮어쓴다. 중복 import와 전역 선택자 변경은 다른 화면의 우선순위를 바꿀 수 있으므로 현재 순서를 유지한다. 이번 구조 정리는 CSS 병합·재생성·디자인 변경을 포함하지 않는다.

과거 `build-compare-css.cjs`는 제출본에 없는 `docs/ux/codex_sidebar_example/src/prototype.css`·`story.css`를 읽던 시안 생성 도구여서 제거했다. 현재 [npm build](../../../frontend/package.json)는 저장된 CSS를 입력으로 `tsc && vite build`를 실행하며 해당 생성기를 호출하지 않는다.

[현재 원문 대조 흐름](../../ux/current_review_flow.md)을 기준으로 같은 화면 크기·선택 항목·가림 상태를 비교한다. 과거 시안의 탭과 문구를 현재 화면에 다시 넣지 않는다.

## 연결 조건

권한에 따라 숨김/비활성화되는 버튼, saving/busy, 원문 동의, 선택 항목, revision 변경 시 초기화·늦은 응답 취소를 유지한다. 원문 확인을 자동 PASS로 표시하지 않는다. 필드 표시 목록은 documentFields.ts, 문서 이름은 documentLabels.ts에서 관리한다.

## 검증과 복구

프로젝트 루트에서 아래 명령을 실행한다.

```powershell
npm.cmd --prefix frontend test -- src/components/review/documentReview.component.test.tsx src/components/review/contractStage.component.test.tsx
npm.cmd --prefix frontend run build
```

실제 화면에서 버튼 활성 조건·좁은 화면·키보드 이름·콘솔을 확인한다. 스타일 변경은 관련 화면을 함께 확인한다. 동작이 바뀌지 않는 작은 문구 수정에 구현을 그대로 따라 하는 테스트를 추가하지 않는다. 실패하면 이번 UI 변경 범위를 보존하고 정상 코드와 비교하여 복구한다. DB를 수정하는 작업이 아니다.

[전체 문서](../../README.md) · [현재 구현 상태](../../progress/current_status.md)
