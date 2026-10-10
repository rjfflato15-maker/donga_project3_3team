# 목적별 문서 포털

> 상태: 현재 기준
> 확인일: 2026-10-09
> 기준: 2026-10-09 구조 정리 소스 사본. 현재 소스와 과거 설치·평가 기록의 검증 범위를 구분한다.

목적별 참조 문서와 현재 구현의 기준을 정리한다. 화면·기능별 수정 위치는 [소스 책임 지도](architecture/module_map.md), 실행 결과는 [검증 기록](development/verification_latest.md)에서 확인한다. 설정·규격·수치는 담당 문서 한 곳에서 관리한다.

| 영역 | 기준 문서 | 관련 문서 |
| --- | --- | --- |
| 사용·운영 | [운영 문서 목록](operations/run_guide.md) | 설치·계정·AI·내보내기·백업 |
| 개발·유지보수 | [개발 시작](development/getting_started.md) | [작업표](development/maintenance_cheat_sheet.md) → [검증](development/test_and_verification.md) |
| 제출·발표 | [설명 문서 구성](submission/explanation_outline.md) | [평가 요약](submission/evaluation_results.md) · [발표 구성](submission/presentation_outline.md) |
| 제출용 소스 | [ZIP 포함·제외·검증](submission/source_package.md) | 실제 설정·업무 자료 제외, 작업 트리 파일 목록과 SHA-256 |
| 앱 소개·경쟁 조사 | [앱 소개와 심층 리서치 요청서](submission/app_overview_research_brief.md) | 구현 범위·대체 수단·조사 결과의 발표 기준 |
| 연구·기록 | [보존 자료 찾아보기](archive_index.md) | 당시 기록·고정 평가·조사·시안 |

| 기준 내용 | 담당 문서 |
| --- | --- |
| 현재 구현·검증·미완료 | [현재 상태](progress/current_status.md) |
| 전체 구성·호출 흐름 | [아키텍처](architecture/overview.md) |
| 화면 → 소스 → 공통 로직/API → 회귀 테스트 | [소스 책임 지도](architecture/module_map.md) |
| 현재 DB 구조 | [ERD](architecture/erd.md) |
| 화면과 API의 연결 계약 | [API 입구](api/README.md) |
| 현재 원문 대조 사용자 흐름 | [문제 항목 처리 흐름](ux/current_review_flow.md) |
| 판독·LLM·VLM·사람 확인 | [문서 분석 흐름](ai/pipeline.md) |
| 실행 모드·AI 설정 | [설정 기준](ai/runtime_settings.md) |
| 자동 검사 정책 | [현재 검수 규칙](validation/current_rules.md) |
| 문서 작성·lint·보존 | [문서 유지보수](development/documentation.md) |
| 배포 범위 | [배포 경계](development/distribution_boundary.md) |
| 자료·캐시 보관 | [폴더 안내](development/folder_guide.md) |
| 작업 공간 바깥 자료 | [작업 공간·공유본·보관함](development/workspace_layout.md) |
| 개발·운영 도구 | [tools 안내](../tools/README.md) |

기존 폴더를 일괄 이동하지 않는다. `eval/`, `docs/eval/`, `docs/progress/history/`와 연구·시안 원본의 경로·해시는 보존한다. 날짜가 있는 과거 공유 HTML/ZIP은 당시 상태의 설명이며 최신 앱의 완료 근거로 사용하지 않는다.

[전체 문서](README.md) · [현재 구현 상태](progress/current_status.md)
