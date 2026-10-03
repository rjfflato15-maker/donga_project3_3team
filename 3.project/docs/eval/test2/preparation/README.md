# test2 확인 시작하기

test2는 이미 준비된 새 계약 6건·PDF 36개다. v4의 독립 최종 성능을 확인할 자료이며 이번에 원문을 다시 만들지 않았다. qwen3:latest·프롬프트 v3·가드 v4와 평가 관련 코드 해시를 원문 검토 전에 [고정](release_lock.json)했다. 2026-10-03에 정답 값을 읽지 않고 예측 1회를 보존했고, 저장된 예측만 확정 정답으로 채점했다. [최종 네 조건 결과](../final_four_modes.md)와 [현재 완료 상태](readiness.json)를 확인한다. release_lock.json의 실행 전 상태는 당시 고정 기록으로 보존한다.

## 사람 확인 결과 (2026-10-03)

Claude 실제 응답 6개를 대조했다. 540항목 중 일치 538·불일치 2였고, 불일치 2·해석 확인 27·일치 표본 52의 총 81칸을 사람이 직접 봤다. 이창헌의 실제 JSON은 원본 그대로 보관했다. 80칸은 `확인`, 1칸은 `수정 필요`다. 나머지 459칸은 두 AI 초안 일치로 채택했으며 사람 전수 검수가 아니다.

`404/40402/total_amount`의 질문은 “합계금액이라는 이름의 금액이 없다”라고 잘못 표현했다. 사용자는 항목은 있고 숫자 자리에 “확인인”이 있다고 지적했다. 원문 이미지와 같은 관찰이며 최종 상태는 읽을 수 없는 값인 `REVIEW`, 값은 null이다. 클릭을 `확인`으로 바꾸지 않고 [질문 문구 정정](../../../../eval/human_reviews/test2/question_wording_resolution.json)을 항목 출처와 함께 기록했다. [정답 확정 기록](../../../../eval/dataset-v2/ground_truth_test.freeze.json)의 문구 오류 집계도 1건이다. 생성 정답 초안·PDF·v4 판정 정책은 변경하지 않았다.

기존 [확인 페이지](../../../../eval/human_review_page_test2/index.html)에서 제출한 질문과 답을 보존했고, 이후 페이지를 만들 때 사용할 질문 빌더 문구를 고쳤다. 이미 확인한 81칸을 다시 확인할 필요는 없다.

[질문 범위 추가 점검](../../../../eval/reconciliation-test2-v1/question_wording_scope_audit.json)에서 N/A 18문항이 상태 자체 대신 원문 사실을 물었고 79문항에 답을 유도하는 문구가 있음을 기록했다. 사람의 81개 원문 확인과 81개 라벨 직접 확정을 구분한다. 직접 라벨 질문은 63개이며 나머지 18개의 N/A는 기존 명세·독립 판독 일치에 근거한다. 관찰 사실과 충돌하는 새로운 답은 발견하지 않았으므로 제출한 검수를 반복하도록 요청하지 않는다. 새 빌더는 N/A를 명시하고 확실치 않으면 보류하도록 안내하며 답을 미리 권하지 않는다. 현재 정답 값·원본 JSON·고정 예측·점수는 바꾸지 않았다.

## 독립 판독 준비 절차

로컬 파일을 읽을 수 있는 Claude의 **새 판독 대화**에 다음 문장을 넣는다. UI 개발 대화는 사용하지 않는다.

> C:\3조 색인\3.project\eval\claude_blind_review_test2\CLAUDE_PROMPT.md를 읽고 그 폴더 안의 case_01~06을 모두 독립 판독해줘. 결과는 replies/case_01.json~case_06.json에 저장해줘. 묶음 밖의 정답 초안·생성 코드·앱 코드·성능 보고서는 읽지 말고 다른 파일은 수정하지 마. 커밋·PR은 하지 마.

웹 Claude라면 `eval/claude_blind_review_test2.zip`을 첨부하고 묶음의 `CLAUDE_PROMPT.md` 지시대로 6개 JSON을 받는다. 이를 위 replies 폴더에 저장한다. 템플릿의 내부 split은 `test`, 자료 버전은 `synthetic-hard-v2`다. 예전 test의 답이나 사람 확인 결과를 재사용하지 않는다.

묶음의 50개 파일 해시와 ZIP 내용을 확인했다. 프롬프트의 작업 경로를 test2 전용으로 바로잡고 6건 전체 판독 지시를 추가했으며 원문 PDF·등록 계약·정답 초안은 변경하지 않았다. 변경 전후 해시는 [프롬프트 갱신 기록](blind_prompt_update.json)에 있다.

## 실행한 순서와 이후 재채점

1. Claude 실제 응답 6개를 받으면 정답 초안과 대조한다. 미응답·원문 미판독이 있으면 먼저 보완한다.
2. 불일치 전부, 해석·모호함, 나머지 일치 칸의 10%를 사례·문서 종류별로 고르게 뽑는다. 사람이 확인할 정확한 칸 수는 응답 대조 뒤 정해진다.
3. `eval/human_review_page_test2/index.html`에 기존 방식의 쉬운 질문과 큰 원문을 채운다. 81칸 확인 페이지의 원본 보기·이동·확대·JSON 저장 형식을 실제 Edge/Playwright에서 확인했다. Browser 플러그인은 이 세션에 제공되지 않아 번들 Playwright와 설치된 Edge를 사용했다. 콘솔·HTTP 오류는 0건이었다.
4. 사용자가 원문을 보고 확인한 실제 JSON을 받으면 양식 사본 K·L열 및 검수자 B12에 반영하고 test2 정답을 확정한다. 확인표·결과 파일은 test2 전용 경로와 양식 해시로 구분한다.
5. 설치된 qwen3 모델 digest·설정과 고정 코드를 재확인하고 최종 예측을 한 번만 실행했다. 네 조건의 성능과 N/A→PASS 오류를 [보고서](../final_four_modes.md)에 기록했다. 이후 정답이 바뀌면 새 확정 출처를 남기고 보존 예측만 재채점한다. 실패한 test2 사례로 가드를 조정하거나 재시험하지 않는다.

사람 확인 페이지는 기존 디자인과 빌더를 재사용한다. v4 고정 뒤 원문 미리보기 2개를 검수 화면의 글자 크기·잘림 확인 목적으로 확인했으며 가드·모델·프롬프트를 변경하지 않았다.

## 처리 명령

프로젝트 폴더에서 사용한다. 이 준비 도구는 OCR·LLM·가드·성능 측정을 실행하지 않는다.

```powershell
$env:PYTHONIOENCODING = 'utf-8'
& .\backend\.venv\Scripts\python.exe .\backend\scripts\prepare_test2_review.py
# Claude 응답이 모두 온 뒤
& .\backend\.venv\Scripts\python.exe .\backend\scripts\prepare_test2_review.py --replies .\eval\claude_blind_review_test2\replies
# 사람이 페이지에서 내려받은 실제 결과를 전달한 뒤
& .\backend\.venv\Scripts\python.exe .\backend\scripts\prepare_test2_review.py --human-result 'C:\Users\Donga\Downloads\human_review_result_test2_이창헌.json'
# 이번 질문 문구 오류 1칸은 원본 답을 보존하는 근거 기록을 함께 사용했다.
# --wording-resolution .\eval\reconciliation-test2-v1\question_wording_resolution.json

# 추론 없는 환경·정답 출처 확인: test2 원문·정답 값은 열지 않음
& .\backend\.venv\Scripts\python.exe .\backend\scripts\predict_test2_locked.py --check
# 이미 실행 완료한 명령의 기록. 새 예측 실행 금지
& .\backend\.venv\Scripts\python.exe .\backend\scripts\predict_test2_locked.py
# 중단됐다면 동일 시도만 복구. 응답을 저장하지 못한 요청은 다시 보내지 않음
& .\backend\.venv\Scripts\python.exe .\backend\scripts\predict_test2_locked.py --resume
# 고정 예측만 채점: OCR·LLM·가드 재실행 없음
& .\backend\.venv\Scripts\python.exe .\backend\scripts\rescore_locked.py --package .\docs\eval\test2\v4_predictions --labels .\eval\dataset-v2\ground_truth_test.json --output .\docs\eval\test2\v4_scores
```

이미 만든 확인표·대조 결과와 고정 정답을 덮어쓰지 않는다. 사람이 진행 중인 확인표는 다시 만들지 않는다. 수정·보류가 있으면 해당 항목을 먼저 원문으로 재확인한다. 사람 직접 확인과 AI 일치로 채택한 칸을 구분하고 사람 전수 검수라고 쓰지 않는다.

## 지금까지의 시험

| 자료 | 정답 확인 | 측정 상태 |
| --- | --- | --- |
| 기존 dev | 생성 설계 초안 + Claude 독립 판독 + 사람 113칸 | 확정 개발 비교. 가드 v3 조정에 사용 |
| 기존 test | 같은 방식 + 사람 134칸 | v3 예측 1회 보존 후 확정 채점. 가드 적용 필드 정확도 77.74% |
| 새 dev2 | 생성 설계 초안, 독립 판독·사람 확인 대기 | 네 조건 94.61% / 94.12% / 99.51% / 99.51%. 예비 수치 |
| 새 test2 | 실제 독립 판독 6개 + 사람 81칸·AI 일치 459칸 | 고정 v4 예측 1회 + 확정 채점 완료. 91.67% / 90.20% / 97.55% / 95.59% |

자료가 다르므로 기존 test 77.74%와 dev2 예비 99.51% 또는 test2 95.59%를 직접 성능 향상으로 표현하지 않는다. 가드 적용 test2는 규칙+LLM 가드 없음보다 필드 정확도가 1.96%p 낮았다. 잘못된 PASS는 네 조건 모두 0/7, N/A→PASS도 0이므로 가드의 일반적 안전성 우월성은 주장하지 않는다. 기존 시험을 재실행하지 않았다.

`predict_test2_locked.py`는 기존 v3의 원자적 체크포인트·시도 예약·중단 복구를 재사용하고 v4를 명시 선택한다. 모델·프롬프트·설정·판정 코드와 원문 해시를 확인하며 실행 끝에도 고정 코드·모델 digest를 다시 확인한다. 완료 receipt가 있으면 복구는 모델 연결 확인까지 생략한다. 학습·개발·운영 DB를 변경하지 않고 예측 패키지와 후속 점수 경로를 분리한다.
