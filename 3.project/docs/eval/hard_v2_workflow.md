# 어려운 서류 v2와 독립 정답 확인

`eval/dataset-v2/`는 dev2/test2 각 6계약·36문서, 총 72개 PDF다. 내부 검증 도구의 split 값은 기존과 동일한 dev/test이고 폴더·문서 ID·자료 버전으로 v1과 구분한다. 다른 표현, 금액 표, 기울어진 스캔, 도장 가림, 여러 쪽, 두 단 서식의 여섯 조건을 미리 선언했다. dev2/test2의 서식 계열은 겹치지 않는다. 원래 test를 복사하거나 그 실패 사례로 생성하지 않았다.

`predeclared_design.json`을 원본 생성 전에 저장했고 앱 추출·LLM·RuleEngine 출력으로 정답을 만들지 않았다. PDF 글자 또는 래스터 설계로 원본을 대조했고 74페이지를 렌더링해 핵심 서식 14페이지를 시각 확인했다. dev2는 독립 판독·사람 확인 대기이며, test2는 독립 판독 6개와 사람 81칸 확인을 반영했다. 도장으로 가린 합계는 생성기가 금액을 알아도 REVIEW다. 공급가액+세액이나 등록 계약금액으로 원문 합계를 복원하지 않는다.

## Claude 독립 판독

- dev2: `eval/claude_blind_review_dev2.zip`
- test2: `eval/claude_blind_review_test2.zip`
- 각 폴더의 CLAUDE_PROMPT.md를 새 판독 대화에서 사용한다. frontend 개발 대화·정답 초안·생성 코드·앱 예측을 제공하지 않는다.
- 실제 계약별 JSON을 각 묶음의 replies/에 저장한다. 독립 판독을 대신 생성하거나 완료했다고 기록하지 않는다.
- dev2 사람 확인 페이지: `eval/human_review_page_dev2/index.html`
- test2 사람 확인 페이지: `eval/human_review_page_test2/index.html`

dev2 페이지는 판독 대기 상태다. test2에서는 실제 응답을 대조해 불일치 2·해석 확인 27·일치 표본 52의 81칸을 확인했다. 80개 확인과 질문 문구 오류 지적 1개를 원본 그대로 보존했다. 오류 문항은 항목 이름이 있고 숫자가 도장으로 가려져 있다는 사람 관찰을 원문과 대조해 기존 REVIEW 상태를 유지했으며, 클릭을 바꾸지 않고 정정 근거를 별도로 남겼다. [test2 절차와 출처](test2/preparation/README.md)를 참고한다.

## 측정과 고정

dev2에서는 규칙만·LLM 필드 추출만·혼합 가드 없음·혼합 가드 있음의 네 조건을 같은 입력과 동일 혼합 LLM 응답으로 비교한다. v4를 확정한 뒤에만 test2를 한 번 추론한다. 독립 정답·사람 확인을 기다리는 동안 다음 API 작업을 진행한다. v3 test 결과와 v4 hard-v2 결과를 합산하지 않는다.

필드 정확도, 채택 VALUE 정확도, ABSENT 거짓 추출, 잘못된 PASS의 건수와 분모, 추가 사람 확인 비율, 모델 실패 수와 시간을 함께 기록한다. OCR이 읽은 필드와 원문이 읽히지 않는 필드를 구분해 보고하며 가드 우월성·시간 절감은 실제 측정으로 입증될 때만 주장한다.

## dev2 네 조건 예측 보존 (2026-10-03)

다른 세션이 보존한 dev2 OCR·규칙 입력과 혼합 LLM 응답을 그대로 재사용했고, 같은 모델·프롬프트·설정으로 LLM 단독 조건만 추가 수집했다. test2 원문·정답을 열지 않은 실행이다. [예측 패키지](dev2/four_modes/receipt.json)와 [예비 채점](dev2/four_mode_scores/preliminary_dev2_unconfirmed_2d66ff4b6db71733_694c2dfa03c7.json)을 분리했다. 예측 receipt SHA256은 `f5626f8eb663c6735758e3b3f0f8f324ff0fa238ff3cee461a80a171ae2abb55`다.

| 조건 | 필드 정확도 | 검사 상태 정확도 | 부적합 정답의 잘못된 PASS | N/A → PASS |
| --- | --- | --- | --- | --- |
| 규칙만 | 193/204 · 94.61% | 90.91% | 0/7 | 1건 |
| LLM만 | 192/204 · 94.12% | 95.35% | 0/7 | 1건 |
| 혼합, 가드 없음 | 203/204 · 99.51% | 95.35% | 0/7 | 1건 |
| 혼합, 가드 v4 | 203/204 · 99.51% | 95.35% | 0/7 | 1건 |

정답은 생성 설계 초안이며 독립 판독·사람 확인 전이다. 가드 적용에서 채택 VALUE는 10/10, 보완 대상 12칸 중 미해결 2칸이다. 작은 표본의 예비 관찰이며 가드 안전성 우월성을 입증하지 못했다. N/A→PASS 1건도 남아 있으므로 `wrong_pass=0/7`을 전체 판정 오류 0건으로 표현하지 않는다. 시간 값은 보존된 OCR·규칙 시간과 모델 응답 시간의 합이다. dev2 가드 실행 시간은 측정하지 않았으므로 전체 처리 지연·사람 작업시간·시간 절감으로 사용하지 않는다.

```powershell
# 이미 고정한 예측을 초안으로 재채점: OCR·LLM·가드 호출 없음
& .\backend\.venv\Scripts\python.exe .\backend\scripts\compare_modes_dev2.py --preliminary
# dev2 사람 확인 정답을 확정한 뒤에도 같은 예측만 재채점
& .\backend\.venv\Scripts\python.exe .\backend\scripts\compare_modes_dev2.py --labels .\eval\dataset-v2\ground_truth_dev.json
```

처음의 수집은 `--collect --preliminary`로 수행했다. receipt가 있으면 수집 옵션을 다시 줘도 해시 확인과 재채점만 한다. 점수 파일은 정답 해시와 보고서 해시로 구분하고 기존 보고서를 덮어쓰지 않는다.
