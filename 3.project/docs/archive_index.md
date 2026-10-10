# 연구·기록·고정 평가 찾아보기

> 상태: 현재 기준
> 확인일: 2026-10-09
> 기준: HEAD `54a8841` + 미커밋 작업 트리. 작업 트리 기준. 설치 검증 범위는 고객 패키지 안내 참조.

이 자료는 당시 판단과 재현 근거를 보존한다. 최신 기능·설정·완료 여부는 [현재 상태](progress/current_status.md)를 우선 읽는다.

| 자료 | 취급 |
| --- | --- |
| [이전 개발 보고](progress/development_report.md) · [개발 일지](progress/history/) | 당시 완료·미완료·검증 기록. 과거 테스트 숫자·담당 분리를 현재 사실로 일괄 치환하지 않음 |
| [평가 안내](eval/local_llm_runbook.md) · [평가 도구](../eval/README.md) | 고정 구현·자료·정답·예측·receipt·캐시 보존 |
| [시장·기술 조사](research/) | 조사 시점과 출처를 확인. 현재 구현의 완료 증거와 구분 |
| [UX 설계](ux/) | 승인 시안·참고 구현. 실제 연결 상태는 코드와 현재 상태에서 확인 |
| [초기 ERD](architecture/erd_v0.1.md) · [초기 전처리](ai/privacy_preprocessing_v0.1.md) · [초기 규칙](validation/validation_rules_v0.1.md) | 초기 설계. 현재 구조로 잘못 읽지 않음 |
| [2026-10-06 공유 화면](progress/team_share_20261006/index.html) | 당시 공유본. 이후 XLSX·폴링·VLM·설치 초안 상태와 차이가 있음 |

문서 정리로 기록 이름·숫자·원문을 일괄 바꾸지 않는다. 공개·배포용 사본에 민감정보가 있는지는 별도로 확인하고, 보호된 원본의 출처·해시를 임의로 다시 고정하지 않는다. 보존 문서의 오래된 링크는 lint의 별도 참고 결과로 기록한다.

2026-10-07 docs 아래 Markdown과 현재 관리 문서의 참조 검사에서 과거 고객 점검 README의 `DocumentReviewDialog.tsx` 링크 2곳이 현재 소스에 없는 것으로 확인했다. 원본 기록은 보존했고 현재 원문 화면은 [DocumentWorkspace.tsx](../frontend/src/components/review/DocumentWorkspace.tsx)와 [현재 연결 규칙](api/frontend_integration.md)에서 확인한다. 현재 문서 검사 성공을 이 두 과거 링크까지 정상이라는 의미로 쓰지 않는다.


[전체 문서](README.md) · [현재 구현 상태](progress/current_status.md)
