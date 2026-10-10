# 현재 API와 화면 연결 입구

> 상태: 현재 기준
> 확인일: 2026-10-09
> 기준: 2026-10-09 구조 정리 소스 사본. 현재 소스와 과거 설치·평가 기록의 검증 범위를 구분한다.

관련 소스: [__init__.py](../../backend/app/api/__init__.py) · [client.ts](../../frontend/src/api/client.ts)

API 등록은 api/__init__.py, 실제 타입·권한·응답은 연결된 소스가 기준이다. 화면별 요청·공통 로직·테스트의 연결은 [소스 책임 지도](../architecture/module_map.md)를 따른다. 개발 서버의 /docs 또는 /openapi.json에서 생성 규격을 확인할 수 있다. 예제는 실제 고객 자료를 넣지 않는다.

| 작업 | 규격 | 화면 시작 |
| --- | --- | --- |
| 목록·상세·자동 갱신 | [공통 상태·검색·이력](work_system.md) | ContractDashboard · ContractSearch |
| 원문·정정·근거·버전 | [현재 화면 연결](frontend_integration.md) · [이전 세부 규격 기록](frontend_handoff.md) | DocumentWorkspace |
| 묶음 요청·부분 회신 | [요청 규격](bundled_requests.md) | BundleRequestPage · BundleReplyPanel |
| 결재·지급 재확인 | [지급 기록 규격](payment_record.md) | ContractStageView · ApprovalPanel |
| 정산 XLSX | [추가 API](work_system.md) | 계약 더 보기 메뉴 |
| VLM 후보·선택 저장 | [현재 화면 연결](frontend_integration.md) · [추가 API](work_system.md) | DocumentWorkspace → useVlmReread · ReviewFieldTable |
| 실제 모델·사람 확인 의미 | [분석 흐름](../ai/pipeline.md) | 후보·출처·사람 확인 |

JSON에서 0/null, 문서 종류 수/파일 수, 검사 항목 수/문제 카드 수, 회신 수령/검수 통과, 승인/지급 사실을 구분한다. 오래된 자료의 요청은 최신 상태를 불러와 다시 확인한다. 응답에 실제 원문 근거가 없으면 근거 없음으로 표시하며 모델 문구·가상 bbox를 만들어 붙이지 않는다.

기존 frontend_handoff.md는 날짜별 설계·인계·통합 기록을 함께 보존한 문서다. 그 안의 당시 “연결 예정”을 현재 미연동 상태로 해석하지 않는다. 현재 연결 규칙은 아래 integration 문서와 현재 코드가 우선이다.


[전체 문서](../README.md) · [현재 구현 상태](../progress/current_status.md)
