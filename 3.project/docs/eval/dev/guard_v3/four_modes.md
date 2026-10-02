# 확정 정답 기준 dev 네 조건 비교

dev 개발용 평가이며 별도 test 최종 성능이 아니다.
분류는 네 조건 모두 같은 규칙 분류기를 사용한다. LLM만은 필드 추출만 LLM이라는 뜻이다.

정답 검수 출처: {"reviewer": "이창헌", "human_full_review": false, "human_direct_count": 113, "ai_agreement_count": 781, "confirmed_at": "2026-10-02T10:32:24.742579+09:00"}
사람 표본 확인과 AI 일치 확인을 구분하며 사람 전수 검수로 해석하지 않는다.

| 조건 | 필드 정확도 | 검수 상태 정확도 | 검수 Macro F1 | 잘못된 PASS | 가드 거부 | 문서 평균 시간 |
|---|---:|---:|---:|---:|---:|---:|
| rule | 78.34% | 75.00% | 0.7530 | 0 | 0 | 0.051초 |
| llm | 94.66% | 100.00% | 1.0000 | 0 | 0 | 10.020초 |
| hybrid_unguarded | 99.11% | 100.00% | 1.0000 | 0 | 0 | 2.164초 |
| hybrid_guarded | 98.52% | 100.00% | 1.0000 | 0 | 11 | 2.164초 |

③과 ④는 문서별 response_id가 같은 LLM 응답을 재사용한다. 시간은 최초 실제 호출시간과 공통 분류·OCR 시간, 가드 시간을 합친 값이며 캐시 실행시간은 별도로 기록한다. 조건별 규칙 검수 시간과 사람 확인 시간은 포함하지 않는다.

검수 상태 정확도의 분모는 정답 또는 출력에 적용되는 항목의 합집합이다. 양쪽 모두 N/A인 항목은 분모에서 제외하며 누락·추가 출력은 오답에 포함한다. 핵심 필드 정확도는 VALUE+REVIEW 정답을 분모로 유지하고 ABSENT 거짓 추출률은 별도 집계한다.

DOCX는 페이지 배치는 미확인, 글자 근거는 확인: 실제 문단·표 셀 위치로 원문을 대조한다. 물리 페이지를 확인한 것으로 표시하지 않는다. 원문 자체의 산술 불일치는 SOURCE_ARITHMETIC_MISMATCH로 기록하고 표시값을 계산값으로 고치지 않는다.

모델: qwen3:latest. 정답 SHA256: 6361b13bd820f40cea38edf5df66da1714d1b0b1fb045763c3795d28d1d84f5b

가드 거부 이유(한 제안에 여러 이유가 있을 수 있음):
{"FIELD_LABEL_OR_VALUE_MISMATCH": 4, "WRONG_PARTY": 3, "UNSUPPORTED_ABSTENTION": 1, "AMBIGUOUS_UNLABELED_AMOUNT": 3}

근거 검증은 특정 형식·라벨·당사자 오류 위험을 줄이는 장치이며 원문 OCR 오류와 모든 의미 오류를 해결하지 않는다. 개선 여부는 조건별 실제 수치로 판단한다.

채택 VALUE 중 맞은 비율: 68/69 (98.55%)
요청 필드 중 사람 추가 확인으로 넘김: 11/80 (13.75%); 기계 근거 검증 완료율 86.25%.
전체 문서 중 추가 확인으로 넘김: 5/59 (8.47%).
가드의 추가 확인과 최종 담당자 승인은 다른 단계다. 채택한 AI 값도 human_confirmed=false를 유지한다. 거부값을 모두 오답으로 세지 않으며, 거부 중 정답 일치·불일치는 별도 사후 감사 결과다.

{"accepted_gold_matching": 68, "accepted_value_count": 69, "accepted_value_correct": 68, "requested_field_count": 80, "human_referral_field_count": 11, "rejected_gold_matching": 6, "rejected_human_referral_count": 11, "accepted_gold_mismatching": 1, "rejected_gold_mismatching": 5, "accepted_value_precision": 0.9855072463768116, "human_referral_field_rate": 0.1375, "guard_auto_validated_field_rate": 0.8625, "document_count": 59, "called_document_count": 28, "human_referral_document_count": 5, "human_referral_document_rate": 0.0847457627118644, "no_additional_review_document_rate": 0.9152542372881356, "guard_auto_validated_called_document_count": 23, "guard_auto_validated_called_document_rate": 0.8214285714285714, "human_referral_document_ids": ["10201", "10501", "10706", "10801", "10902"], "definition": "Referral means unresolved requested field (rejected, REVIEW or failed/missing response). Auto validation is machine grounding, not final human confirmation; all AI proposals remain human_confirmed=false. Rejected correctness is an offline gold audit."}

가드 v3는 dev 감사 결과로 조정함.
기존 dev 호출 대상·원문·모델 응답을 고정해 가드 효과를 비교했다. 현재 실행기의 대상 선정은 별도로 기록한다. 이 실행에서 test는 열지 않았다.
