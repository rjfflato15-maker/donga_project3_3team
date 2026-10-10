# 유지보수 작업표

> 상태: 현재 기준
> 확인일: 2026-10-09
> 기준: HEAD `54a8841` + 미커밋 작업 트리. 작업 트리 기준. 설치 검증 범위는 고객 패키지 안내 참조.

작업을 고른 뒤 상세 예시의 수정 위치·검증·복구를 순서대로 따른다. 파일 이름만 바꾸고 연결된 타입·권한·자료 기준을 생략하지 않는다.

| 작업 | 난이도·영향 | 작업 예시 |
| --- | --- | --- |
| 버튼·문구·배치 수정 | 작은 UI 변경. 기존 권한·확인 동작 유지 | [화면 수정](recipes/change_ui.md) |
| API 응답·화면 연결 변경 | 타입·오류·취소·동시 변경 확인 | [API 변경](recipes/change_api.md) |
| 추출·표시 필드 추가 | 판독·스키마·근거·가림·내보내기에 영향 | [필드 추가](recipes/add_field.md) |
| 자동 검사 정책 변경 | 결과·후속 결재·평가에 영향. 검토 필요 | [검수 규칙 변경](recipes/change_rule.md) |
| 새로운 서류 종류 추가 | 여러 계층 변경. 독립 작업·회귀 검증 필요 | [서류 종류 추가](recipes/add_document_type.md) |
| 이전 정상 상태로 복구 | 코드와 DB를 별도로 확인 | [복구](recipes/recovery.md) |

수정 위치를 찾으면 [모듈 책임](../architecture/module_map.md)과 관련 API를 함께 확인한다. AI 설정만 바꾸는 작업은 [설정 기준](../ai/runtime_settings.md)을 읽는다. 설치 패키지의 빌드·격리 설치 시험과 새 PC·AI 준비 검증 범위는 [고객 설치 안내](../operations/customer_package.md)에서 확인한다.


[전체 문서](../README.md) · [현재 구현 상태](../progress/current_status.md)
