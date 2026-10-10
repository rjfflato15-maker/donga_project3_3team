# 개발자 변경·확인 절차

> 상태: 현재 기준
> 확인일: 2026-10-09
> 기준: 2026-10-09 구조 정리 소스 사본. 현재 소스와 과거 설치·평가 기록의 검증 범위를 구분한다.

관련 소스: [workflow_service.py](../../backend/app/services/workflow_service.py) · [useAutoRefresh.ts](../../frontend/src/hooks/useAutoRefresh.ts)

## 공통 작업 순서

1. [현재 상태](../progress/current_status.md)와 [모듈 지도](../architecture/module_map.md)에서 수정 범위를 찾는다.
2. Git 상태와 작업 중인 변경을 확인한다. 다른 사람의 수정·고객 자료·미커밋 작업을 보존한다.
3. [작업 예시](maintenance_cheat_sheet.md)의 연결 범위와 권한·자료 버전 조건을 확인한다.
4. 임시 자료로 필요한 회귀 검증과 화면 확인을 한다. 테스트를 기존 결과에 맞춰 느슨하게 바꾸지 않는다.
5. 담당 기준 문서와 [검증 기록](verification_latest.md)을 갱신한다. 같은 설정·수치는 여러 문서에 복사하지 않는다.
6. 배포 전 자료를 백업하고 대상 서버를 종료·재시작하여 새 코드로 확인한다.

명령의 실행 위치·기대 결과·오류 대응은 [검증 안내](test_and_verification.md)가 기준이다. 코드와 DB 복구는 [복구 작업 예시](recipes/recovery.md)를 따른다.

## 유지해야 할 조건

- 입력 중인 상세 화면을 목록 폴링으로 덮어쓰지 않는다.
- 오래된 revision/fingerprint의 수정·동의·결재를 사용하지 않는다.
- 자동 검사, 필드별 사람 확인, 회신 수령, 결재, 실제 지급 기록을 구분한다.
- AI 실패 시 저장값을 임의로 채우거나 계산·추측하지 않는다.
- 개인정보 가림과 실제값 다운로드의 차이를 유지한다.
- 고객 DB·원본·계정·백업은 코드 업데이트로 덮어쓰지 않는다.

## 평가 기록과 현재 앱

`docs/eval/`, `eval/`, `sample-data/`와 `docs/progress/history/`의 고정 원본·정답·예측·receipt·release lock은 보존한다. 현재 앱에서 별도 VLM을 추가했다고 기존 평가에 해당 모델의 성능을 합쳐 쓰지 않는다. AI·가드·판정 변경은 새로운 개발 자료·버전·평가 계획으로 진행하고 기존 test 정답을 튜닝에 사용하지 않는다.

frontend와 backend는 현재 같은 작업 트리에서 연결되어 있다. 과거의 “다른 담당자가 앞으로 연결한다”는 문구는 당시 이력으로 읽는다. 새로운 API의 연결 완료는 타입 검사뿐 아니라 실제 사용자 동작으로 확인한다. 화면 디자인을 바꾸는 작업은 기존 합의된 시안을 기준으로 범위를 정한다.

실행 설정과 설치형 배포의 범위는 [실행 설정](../ai/runtime_settings.md), [배포 경계](distribution_boundary.md)에서 확인한다.


[전체 문서](../README.md) · [현재 구현 상태](../progress/current_status.md)
