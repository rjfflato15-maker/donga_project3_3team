# 새로운 서류 종류 추가

> 상태: 현재 기준
> 확인일: 2026-10-09
> 기준: 2026-10-09 구조 정리 소스 사본. 현재 소스와 과거 설치·평가 기록의 검증 범위를 구분한다.

관련 소스: [common.py](../../../backend/app/schemas/common.py) · [classifier.py](../../../backend/app/ai/classifier.py) · [extractor.py](../../../backend/app/ai/extractor.py) · [company_policy_service.py](../../../backend/app/services/company_policy_service.py) · [engine.py](../../../backend/app/validation/engine.py) · [index.ts](../../../frontend/src/types/index.ts) · [documentLabels.ts](../../../frontend/src/utils/documentLabels.ts)

## 목표와 위치

예를 들어 입금표를 추가하려면 enum 이름·화면 이름·적용 회사·필수 여부·추출 필드·검수 정책부터 정한다. 현재 DocumentType은 schemas/common.py에 있고 DB의 document_type은 문자열이다. enum만 추가하면 전체 기능이 지원되는 것은 아니다.

## 수정 범위

공통 enum·분류 시그니처·추출/근거·회사 필수서류 정책·현재본/재발행 규칙·화면 타입/라벨/필드·업로드와 내보내기를 확인한다. 모든 회사의 CORE_6_DOCUMENT_TYPES에 자동으로 추가하는지 판단해야 한다. 자동 분류가 다른 서류를 새 종류로 잘못 읽는 경우도 고려한다. 기존 6종 평가 데이터에 새 종류를 삽입하지 않는다.

## 검증과 복구

```powershell
& .\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_api.py backend/tests/test_rules.py backend/tests/test_document_versions.py backend/tests/test_contract_export.py -q
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
```

프로젝트 루트에서 실행한다. 새 종류의 업로드·수동 지정·재발행·필수 누락·표시·ZIP을 별도 합성 자료로 확인한다. 기존 타입 회귀도 확인한다. 적용 후 enum을 단순히 삭제하면 이미 저장한 문서가 읽히지 않을 수 있으므로 저장 타입의 호환/복구 정책을 정한다. 저장 형식과 처리 단계에 영향을 주므로 관련 계층의 회귀 검증을 함께 수행한다.

[전체 문서](../../README.md) · [현재 구현 상태](../../progress/current_status.md)
