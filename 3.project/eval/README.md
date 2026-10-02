# 문서 검수 성능 평가

이 폴더는 고객 데이터와 분리된 합성 원문·정답·독립 판독·사람 확인 출처를 보관한다. 앱이 추출한 값으로 정답을 채우지 않는다. 실행 위치는 `3.project/`이며 Python은 `backend/.venv/Scripts/python.exe`다.

## 현재 상태

| 구분 | 자료 | 정답과 측정 상태 |
| --- | --- | --- |
| dev | 계약 10건·서류 59개 | 정답 확정, 규칙 기준선·4조건 비교·가드 v3 감사 완료 |
| test | 계약 10건·서류 59개 | 초안과 독립 판독 묶음 준비, Claude 판독·사람 확인·최종 평가 대기 |

dev의 총 894칸 중 113칸(해석 26칸 + 일치 항목 10% 표본 87칸)은 사람이 원문을 보고 확인했고, 나머지 781칸은 두 AI 초안의 일치로 검증했다. 사람 전수 확인으로 표현하지 않는다. 확인 결과 JSON·Excel 사본·자료와 정답 해시는 출처 기록에 보존했다.

test 원본은 사용자 승인에 따라 정답 준비에만 읽었으며 모델 개발·튜닝·성능 측정에 쓰지 않았다. 실제 Claude 응답이나 사람 확인을 대신 만들지 않는다. test 정답 확정 뒤 고정 버전으로 최종 평가를 한 번 실행한다. 현재 test 성능 수치는 없다.

## 어디서 무엇을 찾는가

| 자료·도구 | 목적 |
| --- | --- |
| `LABELING_GUIDE.md` | 유형·필드·검수 상태 정답 기준 |
| `dataset/manifest.json` | 계약 기준·파일 경로·자료 해시 |
| `dataset/reference_labels_dev.json`, `reference_labels_test.json` | 앱 추출과 독립된 생성 설계·원문 대조 초안 |
| `dataset/ground_truth_dev.json` 및 `.freeze.json` | 확정 dev 정답·출처·버전 |
| `dataset/ground_truth_test.json` | 미확정 test 정답 자리, 실제 확인 후 확정 |
| `claude_blind_review/replies/` | 실제 dev Claude 독립 판독 응답 |
| `claude_blind_review_test.zip` | 새 Claude 대화에 제공할 test 원본·기준·빈 양식 |
| `human_review_page/` | 완료한 dev 사람 확인 페이지, 기존 결과 보존 |
| `human_review_page_test/` | 같은 빌더를 재사용한 test 판독 대기 페이지 |
| `human_reviews/` | 실제 사람 결과 JSON·Excel·확인 출처 |
| `reconciliation-v3/` | dev 대조와 10% 표본의 선정 기록 |
| `ground_truth_template.xlsx` | 초기 전수 입력 양식, 현재 표본 확인 절차와 구분 |

초안·AI 일치·사람 확인은 각각 다른 출처다. 해시는 파일 버전을 식별하며 확인의 정확도를 보증하는 서명이 아니다. 확정 자료를 덮어쓰지 않고 수정은 근거와 새 버전으로 남긴다. 무작위 표본 오류가 나오면 확인 범위를 확대한다.

## 실행 안내

- [test 독립 판독 ZIP 전달·사람 확인 절차](../docs/eval/test_review_preparation.md)
- [dev 네 조건 비교와 같은 LLM 응답 재사용](../docs/eval/dev_workflow.md)
- [고정 버전과 test 1회 최종 실행](../docs/eval/final_workflow.md)
- [가드 v3 dev 결과·지표 해석](../docs/progress/history/09_guard_v3.md)
- [이전 평가 준비 기록](../docs/progress/history/02_evaluation_setup.md)

규칙만 / LLM만 / 규칙+LLM 가드 없음 / 규칙+LLM 가드 있음의 네 조건을 비교한다. ③·④는 동일한 응답 캐시를 재사용한다. 거부·보류를 채점 분모에서 빼지 않고 필드 정확도, 검수 상태, 잘못된 PASS, 채택값 정확도와 사람 확인 비율을 나눠 보고한다.

합성 서식 dev와 test 두 계열로 측정한 결과는 실제 회사의 모든 증빙에 대한 일반화 성능을 보증하지 않는다. 생성 코드·자료·정답을 개발 중 다시 만들지 않는다. 새로운 자료가 필요하면 별도 버전과 평가 계획을 정한다.
