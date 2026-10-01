# 규칙 예비 성능 보고서

생성 정보와 파일을 대조해 만든 Codex 정답 초안을 사용했다. 사람 검수와 Claude 독립 검토는 아직 완료하지 않았다. 이 결과는 개발용 예비 측정이며 최종 발표의 검증된 성능 수치로 사용하지 않는다.

평가 구분은 dev이며 모델을 사용하지 않은 규칙 기준 성능이다.

실행 일시: 2026-10-02T00:08:34.512546+09:00
자료 버전: synthetic-v1
정답 SHA256: 87b636d1a8830ed194a65ac44099d45e13d992b407c6a8d3ffc7c71e9f0cb283
자료 목록 SHA256: ba103e8a64f08c41c6f511cdcf5c908b0ab7e57aa827f38d8137f795af53258f
계약 10건, 문서 59개

| 지표 | 측정값 | 목표 | 달성 여부 |
| --- | --- | --- | --- |
| 분류 Macro F1 | 100.0% | 90.0% | 예비 기준 충족 |
| 핵심 필드 정확도 | 78.3% | 90.0% | 예비 기준 미충족 |
| 누락 Recall | 100.0% | 95.0% | 예비 기준 충족 |
| 교차검증 Macro F1 | 75.3% | 90.0% | 예비 기준 미충족 |

문제가 있는 항목에서 잘못된 PASS 비율: 0.0%
PASS 결과 중 잘못된 PASS 비율: 0.0%
자동 추출값 제공 비율: 63.0%
확인 필요 검수 비율: 25.0%
존재하는 필드의 정확도: 78.1%
모호한 필드의 보류 정확도: 100.0%
없는 필드에 값을 만든 비율: 0.0%
문서당 평균 분류·추출 시간: 0.047초 (규칙 검수와 사람 확인 시간 제외)

## 측정 조건과 한계

핵심 필드 정확도의 분모는 VALUE와 REVIEW 정답이다. 값이 존재하는데 추출을 거절한 경우는 오답이며 분모에서 빼지 않는다. ABSENT는 정답이 쉽게 늘어나는 것을 막기 위해 별도 거짓 추출 비율로 보고한다. 처리율은 값 제공 여부이고 담당자 또는 대표의 승인율이 아니다.

모든 실행에서 국세청 외부 API를 호출하지 않는다. BUSINESS_STATUS는 미연동에 따른 확인 필요로 평가한다. 이 수치는 합성 자료에서의 결과이며 실제 회사 서류의 성능이나 검수 시간 절감을 보장하지 않는다.

분류는 사용자 유형 힌트 없이 수행한다. 파일명은 문서 유형을 담지 않은 이름을 사용한다. 분류 점수는 정확도 지표에 넣지 않는다. Macro F1은 분류 6종과 검수 상태 4종을 고정하여 평균하며, 정답과 예측이 모두 없는 클래스의 F1은 0으로 기록한다.

개발용 결과는 모델 선택과 개선에만 사용한다. 최종 발표 수치는 구현과 설정을 고정한 뒤 별도 test 자료로 평가해야 한다.

## 오류 사례

- {"kind": "field", "document_id": "10101", "field": "company_name", "expected_state": "VALUE"}
- {"kind": "field", "document_id": "10102", "field": "supply_amount", "expected_state": "VALUE"}
- {"kind": "field", "document_id": "10102", "field": "tax_amount", "expected_state": "VALUE"}
- {"kind": "field", "document_id": "10102", "field": "total_amount", "expected_state": "VALUE"}
- {"kind": "field", "document_id": "10102", "field": "amount_scope", "expected_state": "VALUE"}
- {"kind": "field", "document_id": "10105", "field": "supply_amount", "expected_state": "VALUE"}
- {"kind": "field", "document_id": "10105", "field": "tax_amount", "expected_state": "VALUE"}
- {"kind": "field", "document_id": "10105", "field": "total_amount", "expected_state": "VALUE"}
- {"kind": "check", "contract_id": "101", "rule_id": "AMOUNT_EXTRACTION", "field": "10102", "expected": "N/A", "actual": "REVIEW"}
- {"kind": "check", "contract_id": "101", "rule_id": "AMOUNT_EXTRACTION", "field": "10105", "expected": "N/A", "actual": "REVIEW"}
