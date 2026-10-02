# 로컬 LLM·평가 문서 목록

LLM은 규칙 추출이 실패하거나 모순인 필드를 보완하고, 최종 PASS/FAIL은 규칙이 판단한다. 앱은 LLM 기본 비활성 상태이며 근거 화면은 시안 승인 후 구현한다.

| 역할 | 문서 |
| --- | --- |
| 실행 환경 담당 | [모델·타임아웃·클라우드 비활성 설정](llm_settings.md) |
| 문서 AI 담당 | [근거 검증 정책](../ai/grounding_policy.md) |
| 검증 담당 | [dev 비교와 캐시 재생](dev_workflow.md) |
| test 정답 담당 | [독립 판독 자료·사람 확인 준비](test_review_preparation.md) |
| 최종 평가 담당 | [test 실행 조건](final_workflow.md) |
| 배포 담당 | [모델 라이선스 기록](model_licenses.md) |

현재 확정 dev 수치와 조정 사실은 [가드 v3 기록](../progress/history/09_guard_v3.md)에 있다. 원본 결과 JSON·CSV·응답 캐시·고정 기록은 이동하거나 수정하지 않는다. test는 정답 확정 후 고정 버전으로 한 번만 평가한다.

[전체 문서 목록](../README.md)
