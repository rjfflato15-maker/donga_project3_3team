# 자동 검사 정책 변경

> 상태: 현재 기준
> 확인일: 2026-10-09
> 기준: HEAD `54a8841` + 미커밋 작업 트리. 작업 트리 기준. 설치 검증 범위는 고객 패키지 안내 참조.

관련 소스: [engine.py](../../../backend/app/validation/engine.py) · [financial.py](../../../backend/app/validation/financial.py) · [metrics.py](../../../backend/app/validation/metrics.py) · [workflow_service.py](../../../backend/app/services/workflow_service.py)

## 목표와 위치

허용 오차·금액 의미·누락 정책 변경처럼 업무 결과를 바꾸는 작업이다. 먼저 요구 조건과 현재 규칙 ID, 기대값·실제값·메시지를 정한다. 현재 구현은 임의 10% 세액 계산을 하지 않으며 계약 기준과 문서의 명시 금액을 비교한다. 오차를 완화하면 되는지 업무 기준을 먼저 검토한다.

## 연결 조건

표시 문제 수와 실제 판정은 다른 계층이다. 숫자 0/null, 공급가액/합계, 당사자, 부분 청구, 중복 문서, 이전 본 제외를 확인한다. 후속 결재·지급 연결에 미치는 영향을 확인한다. 과거 고정 평가의 소스·정답·점수는 그대로 두고 새 개발 자료로 변경 정책을 검증한다.

## 검증과 복구

```powershell
& .\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_rules.py backend/tests/test_financial_extraction.py backend/tests/test_review_workflow_api.py backend/tests/test_payment_records.py -q
```

프로젝트 루트에서 실행한다. 올바른 PASS뿐 아니라 FAIL/REVIEW/MISSING을 PASS로 잘못 바꾸는 사례를 포함한다. 테스트를 새 코드가 무조건 통과하도록 바꾸지 않는다. 반영 전후 정책과 회귀 결과를 기록하고 검토받는다. 적용 뒤 복구 시 이미 저장한 검사·결재 자료를 어떤 기준으로 다시 확인할지 별도 결정한다.

[전체 문서](../../README.md) · [현재 구현 상태](../../progress/current_status.md)
