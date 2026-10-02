# test 정답 준비와 사람 확인

정답 준비에서는 test 원본을 **정답 초안 작성·독립 판독 묶음·사람 확인 화면 준비에만** 읽었다. Claude 응답 10개를 대조해 894칸 모두 일치했고, 불일치·미응답은 각각 0칸이다. 독립 묶음의 81개 수령 해시도 일치했다. **이창헌의 실제 결과 JSON을 반영해 test 정답을 확정했다.** 사람 직접 확인은 134칸(해석 46·모호 3·일치 10% 표본 85)이며 나머지 760칸은 두 AI 초안의 일치로 검증했다. 사람 전수 검수가 아니다.

검수 시각은 2026-10-03 00:34:07~00:42:43(KST), 134칸 모두 확인·수정과 보류 0건이다. 원본 결과 JSON과 K·L열 및 안내 B12를 반영한 사본은 `eval/human_reviews/test/`에 보관했다. 기존 `human_review_test.xlsx`와 확인 페이지는 그대로 유지했다. 확정 정답과 해시 기록은 `eval/dataset/ground_truth_test.json`, `ground_truth_test.freeze.json`이다.

별도 고도화 세션에서 합의한 **예측 1회 보존·채점 분리** 절차로 v3 예측 59개가 고정됐다. 저장된 예측 패키지 해시를 검증한 뒤 이 확정 정답으로 채점했다. 이 작업의 새 추론·가드 재실행은 각각 0회다. 기존 결합 평가기를 추가 실행하지 않았으며 모델·프롬프트·가드 조정이나 test 튜닝도 하지 않았다. [확정 결과](test/final/four_modes.md) · [예측 보존과 재채점](prediction_preservation.md)을 참고한다.

## 전달할 자료

- `eval/claude_blind_review_test.zip`: 원본 59개와 공통 기준·프롬프트·등록 계약·빈 응답 양식, 계약 10건.
- `eval/claude_blind_review_test/CLAUDE_PROMPT.md`: 새 Claude 대화에 입력할 요청문.
- `eval/claude_blind_review_test/replies/`: 실제 Claude 응답을 `case_01.json`~`case_10.json`으로 저장할 곳.
- `eval/human_review_page_test/index.html`: dev와 같은 빌더·화면을 재사용한 사람 확인 페이지. **134칸(꼭 볼 것 49 + 표본 85)**이 준비됐다.
- `eval/human_review_test.xlsx`: 페이지와 같은 시트·행·ID로 연결된 원래 확인 표. 수정하지 않고 보존했다. 완료 사본은 `eval/human_reviews/test/human_reviewed.xlsx`다.
- `eval/reconciliation-test-v1/comparison.json`: 실제 두 초안의 대조, 선정 사유·표본·입력 해시.

독립 판독은 frontend 개발용 Claude 대화와 별도의 새 대화에서 진행한다. Claude에는 ZIP 또는 그 폴더만 제공하고 생성 코드·정답 초안·앱 결과·평가 보고서는 제공하지 않는다. ZIP에 정답·생성 시나리오·앱 예측을 넣지 않았으며 모든 원본의 수령 해시를 제공한다. DOCX 판독에서 페이지 배치를 실제 확인하지 않았다면 그 사실을 기록한다.

Codex 초안은 `eval/dataset/reference_labels_test.json`이다. 생성 설계값을 앱 추출과 독립된 파일 판독/픽셀 대조로 확인했다. 초안의 원래 미확정 상태는 보존했고, 실제 독립 판독과 사람 확인을 반영한 확정 정답은 별도 파일이다. 두 AI 결과가 같다는 사실만으로 사람이 전부 확인했다고 기록하지 않는다.

## 다음 순서

준비 명령은 기존 정답과 묶음을 덮어쓰지 않으며 고정 기록·자료 해시를 확인한다.

```powershell
backend/.venv/Scripts/python.exe backend/scripts/prepare_test_review.py
```

Claude 응답 10개를 받은 뒤 아래 명령을 실행한다. 미판독·빈 답이 있으면 사람 확인 목록을 생성하지 않는다.

```powershell
backend/.venv/Scripts/python.exe backend/scripts/prepare_test_review.py --replies eval/claude_blind_review_test/replies
```

대조와 페이지 준비는 완료했다. 해석 확인 46칸·모호 항목 3칸을 전부 포함하고 나머지 일치 845칸의 10%를 올림한 85칸을 사례·문서 종류별로 뽑았다(seed 42). dev의 113칸과 같은 수로 줄이지 않았다. `human_questions_test_v2.json`에 dev 확정 기준과 새 질문을 기록했고 기존 v1·정답 초안·Claude 응답은 보존했다.

새 해석 질문은 검수확인서의 FULL, 계약서·견적서의 FULL/REVIEW, 금액 대조의 적용 문서, case_09 세액의 REVIEW와 ABSENT 구분, case_06 선금 또는 잔금의 PARTIAL이다. 금액 대조 적용 범위는 실제 정답 슬롯인 첫 사례의 견적서·세금계산서 항목에서 확인한다. 계약서·검수확인서의 FULL을 대조 검사 적용으로 혼동하지 않도록 설명한다. dev에서 확정한 NTS REVIEW·참고값 REVIEW·전액 청구 불일치 FAIL도 꼭 볼 것에 포함했다.

모든 문항에 “정답 초안: … / 📌 기준: …면 맞아요”와 볼 위치를 표시했다. 원문 여백을 잘라 큰 이미지로 보여주며 DOCX는 본문 판독·페이지 배치 미확인을 표시한다. 누락·불일치 문장을 반대로 표시하던 빌더 문구와 dev 금액이 고정되어 있던 계산 예시를 고쳤다. 검사 정책이나 정답 값은 변경하지 않았다.

**사용자 결과 JSON을 받을 때까지 Excel과 test 페이지를 다시 만들거나 수정하지 않는다.** 페이지에서 검수자 이름을 입력하고 꼭 볼 것·표본을 확인한 뒤 결과 파일을 저장한다. 브라우저 화면 검증의 임시 답은 별도 자동 검사 컨텍스트에서만 사용하며 사람 확인으로 기록하지 않았다.

사람이 원문을 확인한 결과 JSON을 받으면 원래 양식 해시와 test 구분, 시트·행·ID를 검사한다. 확인·근거를 Excel 사본 K·L열에 옮기고 안내 B12에 실제 검수자를 기록한다. 원본 JSON·확인 시각·Excel과 정답 해시를 출처로 보관한다.

```powershell
backend/.venv/Scripts/python.exe backend/scripts/prepare_test_review.py --human-result "검수 결과 JSON 경로"
```

수정·보류가 있으면 자동 확정하지 않는다. 무작위 표본의 답을 고쳤다면 dev와 동일하게 확인 범위를 확대하고 새 대조·양식 버전을 만든다. 완료한 정답을 다시 가져와 덮어쓰지 않는다. 기존 dev 정답·Claude 응답·사람 확인 기록은 변경하지 않는다.

## 고정 버전

qwen3 모델 digest, 프롬프트 v3, 가드 v3와 모든 AI·검수 구현은 dev 고정 기록과 같다. 기존 평가 정답 검증기가 표본 검수를 dev에만 허용했으므로 **같은 출처 검증을 test에도 허용하는 검수 절차만 확장**했다. test 예비 측정은 계속 차단한다.

기존 `docs/eval/dev/guard_v3/release_lock.json`은 보존했다. 파생 고정 기록 `docs/eval/test/preparation/release_lock.json`에는 원래 기록의 해시와 평가 정답 검증기만 변경됐다는 내역을 남겼다. AI·프롬프트·가드·판정 코드가 달라지면 준비를 차단한다. 최종 평가에는 이 파생 기록을 사용한다. [최종 실행 안내](final_workflow.md)를 따른다.

평가 준비 도구는 최종 실행을 자동으로 시작하지 않는다. 이번 v3의 예측 시도는 별도 실행기로 예약됐으므로 기존 `--final` 명령을 추가 실행하지 않는다. 완료 패키지의 해시를 검증한 뒤 저장 예측과 확정 정답으로 재채점한다. 실패·중단도 시도 기록으로 남으며 새 시도로 임의 재실행하지 않는다.
