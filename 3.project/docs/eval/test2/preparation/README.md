# test2 확인 시작하기

test2는 이미 준비된 새 계약 6건·PDF 36개다. v4의 독립 최종 성능을 확인할 자료이며 이번에 원문을 다시 만들지 않았다. qwen3:latest·프롬프트 v3·가드 v4와 평가 관련 코드 해시를 원문 검토 전에 [고정](release_lock.json)했다. 모델 추론·최종 채점은 아직 실행하지 않았다.

## 지금 할 일

로컬 파일을 읽을 수 있는 Claude의 **새 판독 대화**에 다음 문장을 넣는다. UI 개발 대화는 사용하지 않는다.

> C:\3조 색인\3.project\eval\claude_blind_review_test2\CLAUDE_PROMPT.md를 읽고 그 폴더 안의 case_01~06을 모두 독립 판독해줘. 결과는 replies/case_01.json~case_06.json에 저장해줘. 묶음 밖의 정답 초안·생성 코드·앱 코드·성능 보고서는 읽지 말고 다른 파일은 수정하지 마. 커밋·PR은 하지 마.

웹 Claude라면 `eval/claude_blind_review_test2.zip`을 첨부하고 묶음의 `CLAUDE_PROMPT.md` 지시대로 6개 JSON을 받는다. 이를 위 replies 폴더에 저장한다. 템플릿의 내부 split은 `test`, 자료 버전은 `synthetic-hard-v2`다. 예전 test의 답이나 사람 확인 결과를 재사용하지 않는다.

묶음의 50개 파일 해시와 ZIP 내용을 확인했다. 프롬프트의 작업 경로를 test2 전용으로 바로잡고 6건 전체 판독 지시를 추가했으며 원문 PDF·등록 계약·정답 초안은 변경하지 않았다. 변경 전후 해시는 [프롬프트 갱신 기록](blind_prompt_update.json)에 있다.

## 이후 순서

1. Claude 실제 응답 6개를 받으면 정답 초안과 대조한다. 미응답·원문 미판독이 있으면 먼저 보완한다.
2. 불일치 전부, 해석·모호함, 나머지 일치 칸의 10%를 사례·문서 종류별로 고르게 뽑는다. 사람이 확인할 정확한 칸 수는 응답 대조 뒤 정해진다.
3. `eval/human_review_page_test2/index.html`에 기존 방식의 쉬운 질문과 큰 원문을 채운다. 현재는 **Claude 판독 대기 상태**이며 확인 문항과 결과 저장 기능은 준비되지 않았다.
4. 사용자가 원문을 보고 확인한 실제 JSON을 받으면 양식 사본 K·L열 및 검수자 B12에 반영하고 test2 정답을 확정한다. 확인표·결과 파일은 test2 전용 경로와 양식 해시로 구분한다.
5. 설치된 qwen3 모델 digest·설정과 고정 코드를 재확인하고 최종 평가를 한 번만 실행한다. 네 조건의 성능과 N/A→PASS 오류도 함께 보고한다. 실패한 test2 사례로 가드를 조정하거나 재시험하지 않는다.

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
```

이미 만든 확인표·대조 결과와 고정 정답을 덮어쓰지 않는다. 사람이 진행 중인 확인표는 다시 만들지 않는다. 수정·보류가 있으면 해당 항목을 먼저 원문으로 재확인한다. 사람 직접 확인과 AI 일치로 채택한 칸을 구분하고 사람 전수 검수라고 쓰지 않는다.

## 지금까지의 시험

| 자료 | 정답 확인 | 측정 상태 |
| --- | --- | --- |
| 기존 dev | 생성 설계 초안 + Claude 독립 판독 + 사람 113칸 | 확정 개발 비교. 가드 v3 조정에 사용 |
| 기존 test | 같은 방식 + 사람 134칸 | v3 예측 1회 보존 후 확정 채점. 가드 적용 필드 정확도 77.74% |
| 새 dev2 | 생성 설계 초안, 독립 판독·사람 확인 대기 | 같은 응답으로 가드 v3 97.55% / v4 99.51%. 예비 수치 |
| 새 test2 | 초안·원문·독립 판독 묶음 준비, 실제 응답 0개 | v4 고정 완료. 사람 확인·최종 평가는 아직 안 함 |

자료가 다르므로 77.74%→99.51%를 직접 성능 향상으로 표현하지 않는다. test2도 아직 점수가 없으며 이번 준비에서 기존 시험을 재실행하지 않았다.
