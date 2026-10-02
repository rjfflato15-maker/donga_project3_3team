# dev 가드 v2 → v3 감사

가드 v3는 dev 감사 결과로 조정함
DOCX는 페이지 배치는 미확인, 글자 근거는 확인

PAGE_UNVERIFIED 15건은 실제 DOCX 4건과 PDF·PNG 범위 근거 누락 11건이다. 위치와 값이 모두 확인된 경우만 완화한다.

| 기존 정답 일치 거부 원인 | 건수 | 조치 |
|---|---:|---|
| 금액 범위의 위치·문구 누락 | 11 | 좁은 근거 검사로 채택 |
| 공급자 라벨 OCR 손상·당사자 확인 불가 | 6 | 계속 사람 추가 확인 |
| DOCX의 물리 페이지 요구 | 4 | 좁은 근거 검사로 채택 |
| 천 단위 숫자 안의 OCR 공백 | 4 | 좁은 근거 검사로 채택 |
| 라벨 뒤 OCR 구분 기호 | 2 | 좁은 근거 검사로 채택 |

| 지표 | 가드 v2 | 가드 v3 |
|---|---:|---:|
| 채택 VALUE 중 정답 일치 | 97.92% | 98.55% |
| 요청 80필드 중 추가 사람 확인 비율 | 36.25% | 13.75% |
| 요청 필드 기계 근거 검증 완료율 | 63.75% | 86.25% |
| 전체 59문서 중 추가 사람 확인 비율 | 33.90% | 8.47% |

거부는 운영 시 사람 추가 확인으로 넘기는 조치다. 값·상태가 틀린지는 확정 dev 정답으로 사후 분석한다.
기존 정답 일치 거부 27건 중 21건을 채택하고 6건은 유지했다. 기존 오답 2건은 모두 거부되며, 참고값 A/B를 ABSENT로 답한 3건도 새로 거부한다.
채택 VALUE 중 OCR 회사명 오독 1건은 이전과 동일하게 남는다. 새로 풀린 21건은 정답과 일치했으나 dev 조정 결과이며 안전성을 보증하지 않는다.
자동 검증 완료율은 기계 근거 검사 기준이다. 채택 AI 값은 여전히 최종 담당자 확인 전(human_confirmed=false)이다.
이전 전체 필드 정확도는 311/337(92.28%)이며 v3와 같은 정답·응답을 사용했다. 전체 필드 분모에서 거부·REVIEW를 제외하지 않는다.

| 문서 | 필드 | 원인 | 정답 일치 | 이전 | v3 | v3 사유 |
|---|---|---|---|---|---|---|
| 10102 | amount_scope | 금액 범위의 위치·문구 누락 | 일치 | 추가 확인 | 채택 |  |
| 10201 | company_name | 공급자 라벨 OCR 손상·당사자 확인 불가 | 일치 | 추가 확인 | 추가 확인 | FIELD_LABEL_OR_VALUE_MISMATCH |
| 10201 | business_registration_no | 공급자 라벨 OCR 손상·당사자 확인 불가 | 일치 | 추가 확인 | 추가 확인 | WRONG_PARTY |
| 10201 | amount_scope | 금액 범위의 위치·문구 누락 | 일치 | 추가 확인 | 채택 |  |
| 10301 | company_name | DOCX의 물리 페이지 요구 | 일치 | 추가 확인 | 채택 |  |
| 10306 | total_amount | 천 단위 숫자 안의 OCR 공백 | 일치 | 추가 확인 | 채택 |  |
| 10306 | amount_scope | 금액 범위의 위치·문구 누락 | 일치 | 추가 확인 | 채택 |  |
| 10402 | amount_scope | 금액 범위의 위치·문구 누락 | 일치 | 추가 확인 | 채택 |  |
| 10405 | supply_amount | 천 단위 숫자 안의 OCR 공백 | 일치 | 추가 확인 | 채택 |  |
| 10501 | company_name | 공급자 라벨 OCR 손상·당사자 확인 불가 | 일치 | 추가 확인 | 추가 확인 | FIELD_LABEL_OR_VALUE_MISMATCH |
| 10501 | business_registration_no | 공급자 라벨 OCR 손상·당사자 확인 불가 | 일치 | 추가 확인 | 추가 확인 | WRONG_PARTY |
| 10501 | amount_scope | 금액 범위의 위치·문구 누락 | 일치 | 추가 확인 | 채택 |  |
| 10504 | company_name | 라벨 뒤 OCR 구분 기호 | 일치 | 추가 확인 | 채택 |  |
| 10601 | company_name | DOCX의 물리 페이지 요구 | 일치 | 추가 확인 | 채택 |  |
| 10606 | amount_scope | 금액 범위의 위치·문구 누락 | 일치 | 추가 확인 | 채택 |  |
| 10607 | amount_scope | DOCX의 물리 페이지 요구 | 일치 | 추가 확인 | 채택 |  |
| 10701 | company_name | 기존 채택 불일치 | 불일치 | 채택 | 채택 |  |
| 10701 | supply_amount | 천 단위 숫자 안의 OCR 공백 | 일치 | 추가 확인 | 채택 |  |
| 10701 | amount_scope | 금액 범위의 위치·문구 누락 | 일치 | 추가 확인 | 채택 |  |
| 10702 | amount_scope | 금액 범위의 위치·문구 누락 | 일치 | 추가 확인 | 채택 |  |
| 10706 | supply_amount | 천 단위 숫자 안의 OCR 공백 | 일치 | 추가 확인 | 채택 |  |
| 10706 | amount_scope | 값 또는 보류 상태가 정답과 불일치 | 불일치 | 추가 확인 | 추가 확인 | UNSUPPORTED_ABSTENTION |
| 10801 | company_name | 공급자 라벨 OCR 손상·당사자 확인 불가 | 일치 | 추가 확인 | 추가 확인 | FIELD_LABEL_OR_VALUE_MISMATCH |
| 10801 | business_registration_no | 공급자 라벨 OCR 손상·당사자 확인 불가 | 일치 | 추가 확인 | 추가 확인 | WRONG_PARTY |
| 10801 | amount_scope | 금액 범위의 위치·문구 누락 | 일치 | 추가 확인 | 채택 |  |
| 10804 | company_name | 라벨 뒤 OCR 구분 기호 | 일치 | 추가 확인 | 채택 |  |
| 10901 | company_name | DOCX의 물리 페이지 요구 | 일치 | 추가 확인 | 채택 |  |
| 10902 | supply_amount | 기존 채택 불일치 | 불일치 | 채택 | 추가 확인 | AMBIGUOUS_UNLABELED_AMOUNT |
| 10902 | tax_amount | 기존 채택 불일치 | 불일치 | 채택 | 추가 확인 | AMBIGUOUS_UNLABELED_AMOUNT |
| 10902 | total_amount | 기존 채택 불일치 | 불일치 | 채택 | 추가 확인 | AMBIGUOUS_UNLABELED_AMOUNT |
| 10902 | amount_scope | 값 또는 보류 상태가 정답과 불일치 | 불일치 | 추가 확인 | 추가 확인 | FIELD_LABEL_OR_VALUE_MISMATCH |
| 10906 | amount_scope | 금액 범위의 위치·문구 누락 | 일치 | 추가 확인 | 채택 |  |
| 11002 | amount_scope | 금액 범위의 위치·문구 누락 | 일치 | 추가 확인 | 채택 |  |
