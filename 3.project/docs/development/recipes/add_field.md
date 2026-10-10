# 새 추출·표시 필드 추가

> 상태: 현재 기준
> 확인일: 2026-10-09
> 기준: HEAD `54a8841` + 미커밋 작업 트리. 작업 트리 기준. 설치 검증 범위는 고객 패키지 안내 참조.

관련 소스: [document.py](../../../backend/app/schemas/document.py) · [extractor.py](../../../backend/app/ai/extractor.py) · [review_context_service.py](../../../backend/app/services/review_context_service.py) · [documentFields.ts](../../../frontend/src/utils/documentFields.ts) · [settlement_export_service.py](../../../backend/app/services/settlement_export_service.py)

## 목표와 위치

새로운 문서 필드를 저장·표시하는 작업은 여러 계층에 영향을 준다. 먼저 값 타입, 미추출/null, 명시 0, 적용 서류 종류와 근거 정책을 정한다. 현재 AnalysisFields, 추출 JSON, 별도 DB 컬럼을 구분한다. JSON 필드 추가만 필요한지 DB 변경도 필요한지 확인한다.

## 수정 범위

규칙 추출→스키마→정정 API→provenance→프론트 타입·필드 목록→가림·내보내기의 연결을 확인한다. AI 대상으로 추가한다면 local_llm 스키마·보완 대상·grounding을 함께 검토한다. VLM의 허용 FIELDS와 응답 스키마는 별도이며 임의로 기존 평가에 합치지 않는다.

## 검증과 복구

```powershell
& .\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_financial_extraction.py backend/tests/test_field_confirmation_scope.py backend/tests/test_settlement_export.py backend/tests/test_preview_masking.py -q
npm.cmd --prefix frontend test -- src/components/review/documentReview.component.test.tsx
npm.cmd --prefix frontend run build
```

프로젝트 루트에서 실행한다. 새 필드 자체에 대해 의미 있는 정상/누락/모호/정정 사례를 추가하고, 기존 필드가 그대로인지 확인한다. 숫자만 찾았다고 올바른 필드 근거로 채택하지 않는다. 반영을 보류할 때는 이번 필드의 연결된 변경을 함께 보관·복구한다. 이미 저장한 JSON/DB의 호환 정책도 남긴다.

[전체 문서](../../README.md) · [현재 구현 상태](../../progress/current_status.md)
