# 문서 찾아보기

문서는 **작업 하나에 책임 하나**를 기준으로 나눈다. 첫 페이지는 안내와 링크만, 실행 방법은 운영 문서에, 코드 변경 위치는 개발 문서에, 과거 수치는 작업 기록에 둔다.

| 맡은 역할 | 시작할 문서 | 이 문서에서 찾을 것 |
| --- | --- | --- |
| 앱 사용자·설치 담당 | [운영 문서 목록](operations/run_guide.md) | 설치·실행·계정·백업 |
| 서버·기능 개발 담당 | [소스 역할 표](architecture/module_map.md) | 수정할 파일과 영향 범위 |
| 화면 개발 담당 | [백엔드 API 인계](api/frontend_handoff.md) | 검사 근거·출처·연락 기록·회사 설정·결재 |
| 유지보수·통합 담당 | [개발자 작업 안내](development/maintenance.md) | 확인 명령·변경 기록·복구 |
| 문서 AI·검증 담당 | [LLM·평가 문서 목록](eval/local_llm_runbook.md) | 모델·근거 검증·dev/test 절차 |
| 프로젝트 담당 | [진행 요약](progress/development_report.md) | 완료 사항·합의 기준·다음 작업 |
| 시연 담당 | [C업체 프로필](architecture/c_company_profile.md) · [시연 업무함](operations/demo_inbox.md) · [팀원 접속 안내](operations/team_test_network.md) | 시범 가정·다섯 사례·분리 실행·국세청 미연동·사내망 테스트 |
| 제출 문서 담당 | [설명 문서 목차](submission/explanation_outline.md) | 문제·구조·평가·결과·한계와 작성 재료 |
| 배포 담당 | [배포 경계](development/distribution_boundary.md) | 앱·고객 자료·평가 도구 구분 |
| 폴더 정리 담당 | [보관·삭제 기준](development/folder_guide.md) | 필요한 자료·캐시·로컬 보관함 구분 |

참고 설계는 [서비스 개요](architecture/overview.md), [기존 ERD](architecture/erd_v0.1.md), [초기 검수 규칙](validation/validation_rules_v0.1.md), [개인정보 전처리](ai/privacy_preprocessing_v0.1.md)에 있다. 오래된 설계 문서보다 현재 소스와 진행 요약을 우선 확인한다.

문서를 추가할 때는 목적·관련 소스·작업 절차·확인 방법·관련 문서를 남긴다. 같은 수치나 설정을 여러 안내에 복사하기보다 담당 문서에 링크한다. 작업 역할은 팀 분담 기준이며 앱 사용자 권한과 별개다.
