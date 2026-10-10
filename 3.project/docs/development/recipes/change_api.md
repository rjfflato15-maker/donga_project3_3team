# API 변경과 화면 연결

> 상태: 현재 기준
> 확인일: 2026-10-09
> 기준: 2026-10-09 구조 정리 소스 사본. 현재 소스와 과거 설치·평가 기록의 검증 범위를 구분한다.

관련 소스: [__init__.py](../../../backend/app/api/__init__.py) · [documents.py](../../../backend/app/api/documents.py) · [document.py](../../../backend/app/schemas/document.py) · [client.ts](../../../frontend/src/api/client.ts) · [index.ts](../../../frontend/src/types/index.ts)

## 목표와 위치

기존 문서 응답의 변경은 api의 요청·권한과 schemas의 타입에서 시작하며 공통 업무 계산은 services에서 관리한다. 필드 정정은 [schemas/document.py](../../../backend/app/schemas/document.py)의 `Correction`과 [document_correction_service.py](../../../backend/app/services/document_correction_service.py), 최종 검토·반려는 [schemas/review.py](../../../backend/app/schemas/review.py)의 `ReviewRequest`와 [contract_review_service.py](../../../backend/app/services/contract_review_service.py)가 담당한다. 다른 API 라우터를 업무 구현으로 호출하지 않는다.

프론트 공통 HTTP 처리는 `api/client.ts`, 보완 요청·담당자 기능은 `features/requests`·`features/assignments`의 API와 모델 모듈이 담당한다. 화면 컴포넌트에 공유 DTO나 전송 함수를 다시 정의하지 않는다. 라우터 등록·회사 인증 의존성·양쪽 타입을 함께 확인한다. 분리 범위와 남은 직접 호출은 [소스 책임 지도](../../architecture/module_map.md)를 따른다.

## 연결 조건

기존 응답과 호환 가능한 기본값/null 의미를 정한다. 수정 API는 오래된 revision을 409로 막고 사유·확인 범위를 받는다. 실제 권한 검사를 서버에서 유지한다. 화면은 로딩·401/403·409·취소·계약 전환 뒤 늦은 응답을 처리한다. 변경 전후 API 규격을 해당 담당 문서에서 함께 갱신한다.

## 검증과 복구

```powershell
& .\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_api.py backend/tests/test_field_confirmation_scope.py backend/tests/test_service_boundaries.py -q
npm.cmd --prefix frontend test -- src/components/review/documentReview.component.test.tsx
npm.cmd --prefix frontend run build
```

명령은 프로젝트 루트에서 실행한다. 임시 업무함에서 실제 변경·동일값 확인·권한 없는 요청·자료 변경 충돌을 확인한다. 추가 필드의 0과 null도 확인한다. 문제가 있으면 이번 API·타입 변경을 함께 복구하고 고객 적용 전 버전 호환을 확인한다. 스키마 변경이 있으면 코드 복구만으로 DB를 되돌렸다고 판단하지 않는다.

[전체 문서](../../README.md) · [현재 구현 상태](../../progress/current_status.md)
