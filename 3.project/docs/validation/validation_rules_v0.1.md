# 검수 룰 및 지표 계산 규격서 (v0.1)

AI Contract Evidence Manager의 결정론적 Rule Engine 및 검수율 산출 공식 명세서입니다.

---

## 1. 4대 결정론적 검수 룰

| 룰 ID | 대상 항목 | 판정 기준 | 결과 상태 |
|---|---|---|---|
| `REQUIRED_DOCUMENTS` | 핵심 6종 증빙 서류 | 필수 6종(`contract`, `estimate`, `business_registration`, `bank_account`, `tax_invoice`, `inspection_confirmation`) 중 미제출된 서류 탐지 | `MISSING` |
| `BUSINESS_NO_MATCH` | 사업자등록번호 교차 대조 | 계약서 기준 사업자번호와 사업자등록증/견적서/세금계산서의 번호 일치 여부 대조 | `PASS` / `FAIL` |
| `BUSINESS_STATUS` | 국세청 사업자 진위/상태 | 국세청 홈택스 사업자 상태가 정상(계속사업자)인지 조회 | `PASS` / `FAIL` |
| `AMOUNT_MATCH` | 계약금액 vs 견적/세금계산서 | 계약서 총금액과 견적서 및 세금계산서 청구 금액 대조 (불일치 시 원문 차액 계산) | `PASS` / `FAIL` |

---

## 2. 검수 지표 산출 공식 (강사 피드백 반영)

1. **증빙 충족률 (Completeness Rate)**:
   $$\text{증빙 충족률} = \frac{\text{제출된 필수 문서 수}}{\text{전체 필수 문서 수 (6)}} \times 100$$

2. **정보 일치율 (Match Rate)**:
   $$\text{정보 일치율} = \frac{\text{PASS 수}}{\text{PASS 수} + \text{FAIL 수}} \times 100$$

3. **정보 불일치율 (Mismatch Rate)**:
   $$\text{정보 불일치율} = \frac{\text{FAIL 수}}{\text{PASS 수} + \text{FAIL 수}} \times 100$$

- `REVIEW` 및 `MISSING`은 일치율/불일치율 분모에서 제외하고 독립적인 예외 항목으로 집계합니다.
- 비교 가능한 항목이 없을 경우(`PASS + FAIL == 0`) 일치율과 불일치율은 `null`로 처리합니다.
