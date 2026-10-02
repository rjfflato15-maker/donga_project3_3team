# 어려운 서류 v2와 독립 정답 확인

`eval/dataset-v2/`는 dev2/test2 각 6계약·36문서, 총 72개 PDF다. 내부 검증 도구의 split 값은 기존과 동일한 dev/test이고 폴더·문서 ID·자료 버전으로 v1과 구분한다. 다른 표현, 금액 표, 기울어진 스캔, 도장 가림, 여러 쪽, 두 단 서식의 여섯 조건을 미리 선언했다. dev2/test2의 서식 계열은 겹치지 않는다. 원래 test를 복사하거나 그 실패 사례로 생성하지 않았다.

`predeclared_design.json`을 원본 생성 전에 저장했고 앱 추출·LLM·RuleEngine 출력으로 정답을 만들지 않았다. PDF 글자 또는 래스터 설계로 원본을 대조했고 74페이지를 렌더링해 핵심 서식 14페이지를 시각 확인했다. 사람 확정과 독립 판독은 아직 없다. 도장으로 가린 합계는 생성기가 금액을 알아도 REVIEW다. 공급가액+세액이나 등록 계약금액으로 원문 합계를 복원하지 않는다.

## Claude 독립 판독

- dev2: `eval/claude_blind_review_dev2.zip`
- test2: `eval/claude_blind_review_test2.zip`
- 각 폴더의 CLAUDE_PROMPT.md를 새 판독 대화에서 사용한다. frontend 개발 대화·정답 초안·생성 코드·앱 예측을 제공하지 않는다.
- 실제 계약별 JSON을 각 묶음의 replies/에 저장한다. 독립 판독을 대신 생성하거나 완료했다고 기록하지 않는다.
- dev2 사람 확인 페이지: `eval/human_review_page_dev2/index.html`
- test2 사람 확인 페이지: `eval/human_review_page_test2/index.html`

페이지는 원문과 등록 기준을 준비한 판독 대기 상태다. 독립 판독 전에는 완료 파일 저장을 허용하지 않는다. 응답 수령 후 기존 `compare_reference_labels.py`를 dataset-v2와 해당 split에 적용해 불일치·모호함 전부와 일치 10% 표본을 선정한다. 참조 초안의 freeze 해시를 유지한다. 사람 확인 정답은 기존 `import_reconciled_labels.py`의 출처 검증으로 확정한다. 세부 해석 질문과 해당 양식·페이지는 응답 수령 후 실제 대조 결과로 생성한다.

## 측정과 고정

dev2에서는 규칙만·LLM 필드 추출만·혼합 가드 없음·혼합 가드 있음의 네 조건을 같은 입력과 동일 혼합 LLM 응답으로 비교한다. v4를 확정한 뒤에만 test2를 한 번 추론한다. 독립 정답·사람 확인을 기다리는 동안 다음 API 작업을 진행한다. v3 test 결과와 v4 hard-v2 결과를 합산하지 않는다.

필드 정확도, 채택 VALUE 정확도, ABSENT 거짓 추출, 잘못된 PASS의 건수와 분모, 추가 사람 확인 비율, 모델 실패 수와 시간을 함께 기록한다. OCR이 읽은 필드와 원문이 읽히지 않는 필드를 구분해 보고하며 가드 우월성·시간 절감은 실제 측정으로 입증될 때만 주장한다.
