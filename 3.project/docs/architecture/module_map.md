# 소스 역할과 수정 위치

앱 소스는 이미 기능별로 나뉘어 있다. 필요한 영역부터 읽고, 변경 사항은 해당 담당 문서에 기록한다. 사람 이름 대신 역할로 책임을 정하며 한 사람이 여러 역할을 맡을 수 있다.

| 담당 영역 | 시작 소스 | 책임 |
| --- | --- | --- |
| 실행·설치 | [launcher/](../../backend/launcher/README.md), [EXE 진입점](../../tools/launcher/Program.cs) | 실행 환경·설정·서버·관리 메뉴 |
| 계정·권한 | [security.py](../../backend/app/security.py), [api/auth.py](../../backend/app/api/auth.py), [api/pilot.py](../../backend/app/api/pilot.py) | 로그인·세션·역할·퇴사 처리 |
| 문서 읽기·가리기 | [preprocessor.py](../../backend/app/ai/preprocessor.py), [masking.py](../../backend/app/ai/masking.py), [api/documents.py](../../backend/app/api/documents.py) | 파일 판독·OCR·미리보기·개인정보 처리 |
| AI 추출·근거 | [extractor.py](../../backend/app/ai/extractor.py), [local_llm.py](../../backend/app/ai/local_llm.py), [grounding.py](../../backend/app/ai/grounding.py) | 규칙값·로컬 LLM·근거 검증 |
| 최종 검수 | [validation/engine.py](../../backend/app/validation/engine.py), [financial.py](../../backend/app/validation/financial.py) | 누락·불일치·금액 정책과 PASS/FAIL |
| 처리·업무 흐름 | [pipeline_service.py](../../backend/app/services/pipeline_service.py), [workflow_service.py](../../backend/app/services/workflow_service.py) | 분석·저장 연결·보완 요청·재확인 |
| 화면용 근거·회신 기록 | [api/workflow.py](../../backend/app/api/workflow.py), [review_context_service.py](../../backend/app/services/review_context_service.py) | 근거·출처·한 줄 요약·재제출 요청 이력 |
| 회사 설정·결재 순서 | [company_policy_service.py](../../backend/app/services/company_policy_service.py) | 회사 유형·역할 표시 이름·최대 2단계 결재 |
| DB·자료·복원 | [db/models.py](../../backend/app/db/models.py), [storage_service.py](../../backend/app/services/storage_service.py), [manage_pilot.py](../../backend/manage_pilot.py) | DB 구조·파일 저장·이주·백업·복원 |
| 화면 | [frontend/src/](../../frontend/src/) | 화면·사용 흐름·API 연결. 디자인 변경은 시안 승인 후 |
| 평가·통합 검증 | [backend/tests/](../../backend/tests/), [평가 안내](../eval/local_llm_runbook.md) | 회귀·성능 평가·정답 출처·버전 고정 |

`api/`는 요청·권한·응답, `services/`는 업무 순서, `ai/`는 문서 분석, `validation/`은 최종 판정, `db/`는 저장 구조, `schemas/`는 데이터 계약을 담당한다. 화면에서 최종 판정 규칙을 중복 구현하지 않는다.

AI·검수·평가 코드는 가드 v3 최종 평가용으로 고정되어 있다. 이번 정리에서 이동하지 않았다. 변경 제한과 확인 방법은 [개발자 작업 안내](../development/maintenance.md)를 따른다.

test의 정답 확인은 [준비 안내](../eval/test_review_preparation.md)를 따른다. 평가 정답 검증기의 dev 전용 표본 확인 제한만 test로 확장했고, AI·검수 코드 변경 없이 별도 파생 고정 기록을 남겼다. Claude 화면 담당자는 [API 변경 안내](../api/frontend_handoff.md)를 참고한다.
